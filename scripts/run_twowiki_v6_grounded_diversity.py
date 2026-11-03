#!/usr/bin/env python3
"""V6 source-grounded two-sentence Qwen diagnostic; NO poisoning or held-out.

Five existing development cases; three distinct pinned source-anchor foci per
case, two independent model calls per focus, same MLX Qwen/seed policy as v5.
Output is review-only. Any model exception retains an intent + error record.
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

from src.attacks.semantic_fluent_development_v6 import (
    ANCHORS, PROFILE, PROMPT_VERSION, TRIAGE_VERSION, source_anchors,
    build_prompt, triage, distinct_three,
)

SCHEMA = "rag-poison-transfer.twowiki-v6-qwen-grounded-diversity-diagnostic/v1"
V5_SCHEMA = "rag-poison-transfer.twowiki-v5-qwen-construction-diagnostic/v1"
PACKET_SHA = "467f457a16d1a092e6057f54a91a02de2f9f3c405fe6428876853ba1ff30bbf6"
DATASET_SHA = "58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43"
MODEL_REVISION = "c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def write_new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2, sort_keys=True,
                  ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_inputs(packet_path, v5_summary_path, v5_manifest_path):
    if digest(packet_path.read_bytes()) != PACKET_SHA:
        raise ValueError("Pinned five-case development packet hash changed")
    with zipfile.ZipFile(packet_path) as archive:
        if archive.namelist().count("independent_review_input.json") != 1:
            raise ValueError("Missing/doubled packet source")
        packet = json.loads(archive.read("independent_review_input.json"))
    if (packet.get("scope") != "train_development_only"
        or packet.get("dataset_sha256") != DATASET_SHA
        or packet.get("not_llm_generated") is not True
        or packet.get("factual_approval") is not False
        or packet.get("injection_approved") is not False
        or packet.get("heldout_access") is not False):
        raise ValueError("Review packet scientific-scope boundary mismatch")
    cases = packet.get("queries")
    if (not isinstance(cases, list) or len(cases) != 5
        or {c["candidate_id"] for c in cases} != set(ANCHORS)
        or len({c["candidate_id"] for c in cases}) != 5
        or len({c["query_id"] for c in cases}) != 5
        or any(c.get("factual_approval") is not False or c.get("injection_approved") is not False
               for c in cases)):
        raise ValueError("Only the original five unapproved development cases allowed")
    if (any(len(c.get("candidate_documents", [])) != 3 for c in cases)
        or any(len(source_anchors(c)) != 3 for c in cases)):
        raise ValueError("Original source packet cannot prove v6 anchors")
    summary = read_json(v5_summary_path)
    manifest = read_json(v5_manifest_path)
    if (summary.get("schema") != V5_SCHEMA or manifest.get("schema") != V5_SCHEMA
        or summary.get("scope") != "train_development_only"
        or manifest.get("scope") != "train_development_only"
        or manifest.get("dataset_sha256") != DATASET_SHA
        or manifest.get("packet_sha256") != PACKET_SHA
        or manifest.get("model_revision") != MODEL_REVISION
        or summary.get("model_calls_recorded") != 30
        or summary.get("intensity_3_distinct_candidate_cases") != 0
        or summary.get("poison_injections") != 0
        or summary.get("injection_approvals") != 0
        or summary.get("heldout_queries_accessed") != 0
        or manifest.get("max_tokens") != 150
        or manifest.get("attempts_per_slot") != 2
        or manifest.get("same_seed_policy_as_v4") is not True
        or manifest.get("heldout_access") is not False):
        raise ValueError("V5 comparator is not the pinned 30-call no-diversity diagnostic")
    return cases, summary, manifest


def clean_code(repo):
    if repo.resolve() != ROOT.resolve():
        raise ValueError("Repo path must match checked-out v6 runner")
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                           check=True, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise ValueError("Dirty code worktree; use a clean v6 detached worktree")
    return sha


def summarize(rows: list[dict]):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["candidate_id"], []).append(row)
    per_case = {}
    for cid, records in sorted(grouped.items()):
        assessment = distinct_three(records)
        assessment["attempts_recorded"] = len(records)
        assessment["surface_candidates"] = sum(
            r["triage"]["status"] == "needs_independent_content_review"
            for r in records)
        assessment["rejection_reasons"] = dict(sorted(Counter(
            reason for r in records for reason in r["triage"]["reasons"]).items()))
        per_case[cid] = assessment
    return {
        "schema": SCHEMA, "scope": "train_development_only",
        "recorded_model_calls": len(rows), "max_model_calls": 30,
        "surface_review_candidates": sum(c["surface_candidates"] for c in per_case.values()),
        "three_context_candidate_cases": sum(
            c["three_surface_distinct_grounded_context_candidates"]
            for c in per_case.values()),
        "per_case": per_case,
        "v4_historical_strict_validator_passes": 0,
        "v5_historical_surface_candidates": 30,
        "v5_historical_three_distinct_cases": 0,
        "v4_and_v5_results_unchanged": True,
        "semantic_independence_verified": False,
        "independent_content_review": "NOT_PERFORMED",
        "construction_approvals": 0, "factual_approvals": 0,
        "injection_approvals": 0, "poison_injections": 0,
        "heldout_queries_accessed": 0,
        "paired_poisoned_evaluation_authorized": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--v5-summary", type=Path, required=True)
    p.add_argument("--v5-manifest", type=Path, required=True)
    p.add_argument("--model-snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args()
    repo = args.repo.expanduser().resolve()
    packet_path = args.packet.expanduser().resolve()
    v5_summary_path = args.v5_summary.expanduser().resolve()
    v5_manifest_path = args.v5_manifest.expanduser().resolve()
    cases, prior_summary, prior_manifest = load_inputs(
        packet_path, v5_summary_path, v5_manifest_path)
    sha = clean_code(repo)
    model = args.model_snapshot.expanduser().resolve()
    if model.name != MODEL_REVISION or not model.is_dir():
        raise ValueError("Pinned Qwen snapshot missing or wrong revision")
    for case in cases:
        for slot in range(3):
            assert build_prompt(case, slot, scope="development")
    print("V6 PREFLIGHT PASS: same five train cases, three source-backed foci, 30 max calls",
          flush=True)
    print("No constructed poison approved; no injection or held-out access", flush=True)
    if args.preflight:
        return
    output = args.output.expanduser().resolve()
    if output == repo or repo in output.parents:
        raise ValueError("Write outputs only outside Git worktree")
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "manifest.json", {
        "schema": SCHEMA, "scope": "train_development_only",
        "git_commit": sha, "runner_sha256": digest(Path(__file__).read_bytes()),
        "dataset_sha256": DATASET_SHA, "source_packet_sha256": PACKET_SHA,
        "v5_summary_sha256": digest(v5_summary_path.read_bytes()),
        "v5_manifest_sha256": digest(v5_manifest_path.read_bytes()),
        "model_revision": MODEL_REVISION, "model_snapshot": str(model),
        "prompt_version": PROMPT_VERSION, "triage_version": TRIAGE_VERSION,
        "profile": PROFILE, "max_tokens": 150, "attempts_per_slot": 2,
        "generation_policy": "per-attempt same seed as v5; no adaptive retry",
        "context_policy": "one distinct source anchor per slot, two sentences",
        "no_model_output_overwrite": True,
        "reviewer_identity_authenticated": False, "construction_eligible": False,
        "injection_approved": False, "heldout_access": False,
    })
    from src.pipelines.generator import MLXGenerator
    from src.utils.seeding import set_seed

    print("Loading pinned local Qwen MLX...", flush=True)
    generator = MLXGenerator(str(model))
    rows = []
    for case in cases:
        for slot in range(3):
            prompt = build_prompt(case, slot)
            for attempt in (1, 2):
                key = f"{case['candidate_id']}.slot-{slot}.attempt-{attempt}"
                seed = int(digest((key + MODEL_REVISION).encode())[:8], 16)
                write_new(output / "intents" / (key + ".json"), {
                    "candidate_id": case["candidate_id"], "slot": slot,
                    "attempt": attempt, "status": "model_call_issued_not_yet_logged",
                    "prompt_sha256": digest(prompt.encode()), "prompt": prompt,
                    "seed": seed, "model_revision": MODEL_REVISION,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                })
                set_seed(seed)
                generator.seed(seed)
                try:
                    answer = generator.generate(prompt, max_tokens=150)
                except Exception as exc:
                    write_new(output / "errors" / (key + ".json"), {
                        "status": "model_call_indeterminate",
                        "error_type": type(exc).__name__, "error": str(exc),
                    })
                    raise
                scored = triage(case, slot, answer.text)
                record = {
                    "schema": SCHEMA,
                    "candidate_id": case["candidate_id"], "query_id": case["query_id"],
                    "slot": slot, "attempt": attempt,
                    "prompt_sha256": digest(prompt.encode()), "seed": seed,
                    "raw_response": answer.text,
                    "raw_response_sha256": digest(answer.text.encode("utf-8")),
                    "prompt_tokens": answer.prompt_tokens,
                    "completion_tokens": answer.completion_tokens,
                    "backend_prompt": answer.backend_prompt,
                    "latency_seconds": answer.latency_seconds,
                    "triage": scored, "status": "logged_unapproved_candidate",
                }
                write_new(output / "responses" / (key + ".json"), record)
                rows.append(record)
                print(f"{key}: {scored['status']} "
                      f"{scored['reasons'] if scored['reasons'] else '(context and claim surface only)'}",
                      flush=True)
    summary = summarize(rows)
    write_new(output / "summary.json", summary)
    print("COMPLETE:", output / "summary.json", flush=True)
    print("Independent content review still required; no poison injected.", flush=True)


if __name__ == "__main__":
    main()
