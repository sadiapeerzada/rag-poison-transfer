#!/usr/bin/env python3
"""Real-model 2Wiki v5 prompt/triage diagnostic; no document injection.

Comparative *development-only* study against the separate frozen v4.1
30-call pilot. Same five pinned cases, Qwen model snapshot, max tokens,
per-attempt seeds, and two attempts per slot. New prompt/triage versions.

Do NOT use these outputs as source documents in a poisoned pipeline or
claim positive content-triage signals as independently confirmed falsehoods.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.attacks.semantic_fluent_development_v5 import (
    PROFILE, PROMPT_VERSION, TRIAGE_VERSION, build_prompt,
    triage_response, assess_slots,
)

SCHEMA = "rag-poison-transfer.twowiki-v5-qwen-construction-diagnostic/v1"
PACKET_SHA = "467f457a16d1a092e6057f54a91a02de2f9f3c405fe6428876853ba1ff30bbf6"
DATASET_SHA = "58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43"
MODEL_REVISION = "c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
CASES = frozenset(("C02", "C05", "C09", "C11", "C13"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2, sort_keys=True,
                  ensure_ascii=False, allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())


def load_inputs(packet_path, audit_path):
    if sha(packet_path.read_bytes()) != PACKET_SHA:
        raise ValueError("Review packet bytes differ from pinned input")
    with zipfile.ZipFile(packet_path) as archive:
        if archive.namelist().count("independent_review_input.json") != 1:
            raise ValueError("Missing or duplicate independent review input")
        packet = json.loads(archive.read("independent_review_input.json"))
    if (packet.get("scope") != "train_development_only"
        or packet.get("dataset_sha256") != DATASET_SHA
        or packet.get("not_llm_generated") is not True
        or packet.get("model_calls") != 0
        or packet.get("factual_approval") is not False
        or packet.get("injection_approved") is not False
        or packet.get("heldout_access") is not False):
        raise ValueError("Review packet train-only/provenance mismatch")
    cases = packet.get("queries")
    if (not isinstance(cases, list) or len(cases) != 5
        or {c["candidate_id"] for c in cases} != CASES
        or len({c["candidate_id"] for c in cases}) != 5
        or len({c["query_id"] for c in cases}) != 5):
        raise ValueError("Not the five pinned development cases")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if (audit.get("schema") != "rag-poison-transfer.twowiki-v4.1-dev25-quality-audit/v1"
        or audit.get("scope") != "train_development_only"
        or audit.get("dataset_sha256") != DATASET_SHA
        or audit.get("review_packet_sha256") != PACKET_SHA
        or audit.get("cohort_count") != 25
        or audit.get("provisionally_reviewed_count") != 5
        or audit.get("abstention_count") != 20
        or audit.get("model_calls") != 0
        or audit.get("heldout_queries_accessed") != 0
        or audit.get("two_ai_provenance_cleared") is not False
        or audit.get("paired_poisoned_evaluation_authorized") is not False):
        raise ValueError("Invalid prior pinned development quality audit")
    known = {r["query_id"] for r in audit["cases"]
             if r.get("status") == "provisional_content_review_only"}
    if known != {c["query_id"] for c in cases}:
        raise ValueError("Source packet contains non-audited development query")
    for c in cases:
        if len(c.get("candidate_documents", [])) != 3:
            raise ValueError("Missing reviewed diagnostic surface slots")
        if c.get("factual_approval") is not False or c.get("injection_approved") is not False:
            raise ValueError("Packet must not approve construction")
        if any(sha(d["text"].encode()) != d["text_sha256"]
               for d in c.get("source_documents", [])):
            raise ValueError("Pinned source text mismatch")
    return cases


def checked_revision(repo):
    if repo.resolve() != ROOT.resolve():
        raise ValueError("Script must execute from the supplied repo root")
    process = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, text=True, capture_output=True)
    dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                           check=True, text=True, capture_output=True)
    if dirty.stdout.strip():
        raise ValueError("Dirty code worktree: use a clean review branch")
    return process.stdout.strip()


def diagnostic_summary(rows, recorded):
    by_case = {}
    for r in rows:
        by_case.setdefault(r["candidate_id"], []).append(r)
    cases = {}
    for candidate in sorted(by_case):
        data = by_case[candidate]
        result = assess_slots(data)
        result["attempts_logged"] = len(data)
        result["triage_positive_attempts"] = sum(
            row["triage"]["status"] == "needs_independent_content_review"
            for row in data)
        result["rejection_reasons"] = dict(sorted(Counter(
            reason for row in data for reason in row["triage"]["reasons"]).items()))
        cases[candidate] = result
    return {
        "schema": SCHEMA, "scope": "train_development_only",
        "model_calls_recorded": recorded,
        "max_model_calls": 30,
        "triage_positive_attempts": sum(x["triage_positive_attempts"]
                                        for x in cases.values()),
        "intensity_1_candidate_cases": sum(
            x["intensity_1_needs_review"] for x in cases.values()),
        "intensity_3_distinct_candidate_cases": sum(
            x["intensity_3_three_distinct_candidates_need_review"]
            for x in cases.values()),
        "cases": cases,
        "historical_v4_call_count": 30,
        "historical_v4_strict_grammar_passes": 0,
        "historical_v4_results_modified": False,
        "independent_content_review": "NOT_PERFORMED",
        "construction_approvals": 0, "factual_approvals": 0,
        "injection_approvals": 0, "poison_injections": 0,
        "heldout_queries_accessed": 0,
        "paired_poisoned_evaluation_authorized": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--model-snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args()
    repo = args.repo.expanduser().resolve()
    if repo != ROOT.resolve():
        raise ValueError("Point --repo to the checked-out v5 runner worktree")
    cases = load_inputs(args.packet.expanduser().resolve(), args.audit.expanduser().resolve())
    commit = checked_revision(repo)
    model = args.model_snapshot.expanduser().resolve()
    if model.name != MODEL_REVISION or not model.is_dir():
        raise ValueError("Pinned local MLX Qwen model snapshot absent or changed")
    for c in cases:
        q = {k: c[k] for k in ("query_id", "question", "gold_answer", "gold_aliases")}
        for slot in range(3):
            build_prompt(q, c["proposed_false_target"], slot, scope="development")
    print("V5 PREFLIGHT PASS: 5 train-only cases; 15 slots; 30 max model calls", flush=True)
    print("No construction approval, injection or held-out access", flush=True)
    if args.preflight:
        return

    out = args.output.expanduser().resolve()
    if out == repo or repo in out.parents:
        raise ValueError("Output must not be stored inside the Git worktree")
    if out.exists():
        raise FileExistsError("Output already exists; never overwrite prior model records")
    out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": SCHEMA, "scope": "train_development_only",
        "dataset_sha256": DATASET_SHA, "packet_sha256": PACKET_SHA,
        "audit_sha256": sha(args.audit.read_bytes()),
        "model_revision": MODEL_REVISION,
        "model_snapshot": str(model),
        "repo_commit": commit,
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "prompt_version": PROMPT_VERSION,
        "triage_version": TRIAGE_VERSION,
        "profile": PROFILE,
        "generation_policy": "independent attempts; no adaptive selection",
        "same_seed_policy_as_v4": True,
        "max_tokens": 150, "attempts_per_slot": 2,
        "construction_eligible": False,
        "injection_approved": False, "heldout_access": False,
        "reviewer_provenance_authenticated": False,
    }
    write_new(out / "manifest.json", manifest)
    from src.pipelines.generator import MLXGenerator
    from src.utils.seeding import set_seed

    print("Loading pinned Qwen via MLX...", flush=True)
    generator = MLXGenerator(str(model))
    rows = []
    for c in cases:
        q = {k: c[k] for k in ("query_id", "question", "gold_answer", "gold_aliases")}
        target = c["proposed_false_target"]
        for slot in range(3):
            prompt = build_prompt(q, target, slot, scope="development")
            for attempt in (1, 2):
                # Exactly the v4 comparator's per-attempt seed derivation.
                key = f"{c['candidate_id']}.slot-{slot}.attempt-{attempt}"
                seed = int(sha((key + MODEL_REVISION).encode())[:8], 16)
                response_file = out / "responses" / (key + ".json")
                write_new(out / "intents" / (key + ".json"), {
                    "schema": SCHEMA, "candidate_id": c["candidate_id"],
                    "query_id": q["query_id"], "slot": slot, "attempt": attempt,
                    "prompt": prompt, "prompt_sha256": sha(prompt.encode()),
                    "seed": seed, "model_revision": MODEL_REVISION,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "intent_issued_model_call_not_yet_recorded",
                })
                set_seed(seed)
                generator.seed(seed)
                try:
                    generation = generator.generate(prompt, max_tokens=150)
                except Exception as exc:
                    write_new(out / "errors" / (key + ".json"), {
                        "status": "model_call_indeterminate",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    })
                    raise
                triage = triage_response(q, target, slot,
                                         generation.text, scope="development")
                row = {
                    "schema": SCHEMA, "candidate_id": c["candidate_id"],
                    "query_id": q["query_id"], "slot": slot, "attempt": attempt,
                    "seed": seed, "prompt_sha256": sha(prompt.encode()),
                    "raw_response": generation.text,
                    "raw_response_sha256": sha(generation.text.encode()),
                    "backend_prompt": generation.backend_prompt,
                    "completion_tokens": generation.completion_tokens,
                    "prompt_tokens": generation.prompt_tokens,
                    "latency_seconds": generation.latency_seconds,
                    "triage": triage,
                    "status": "model_response_recorded_not_approved",
                }
                write_new(response_file, row)
                rows.append(row)
                print(f"{key}: {triage['status']} "
                      f"({','.join(triage['reasons']) if triage['reasons'] else 'surface-only'})",
                      flush=True)
    summary = diagnostic_summary(rows, len(rows))
    write_new(out / "summary.json", summary)
    print("COMPLETE:", out / "summary.json", flush=True)
    print("No approvals or poison injection performed.", flush=True)


if __name__ == "__main__":
    main()
