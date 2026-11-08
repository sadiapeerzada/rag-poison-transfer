#!/usr/bin/env python3
"""Prepare a *private* RCD ablation prompt replay by actually recomputing
retrieval against the original sealed 2Wiki clean/poison corpora.

This stage loads retrievers/embedders locally and may be CPU-intensive.
It does NOT load a QA generator or make any generator calls.

The original frozen baseline must reproduce the archived generator-visible
document IDs for every selected item before any variant prompt is exported.
If parity fails, abort: no end-to-end inference is authorized by this script.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_2wiki_rcd_ablation_plan import (
    ORIGINAL_PINS, SCHEMA as PLAN_SCHEMA, VARIANTS, require_json
)
from scripts.second_model_prompt_replay import outside_repo, sha
from src.attacks.asr import build_prompt
from src.experiments.rcd_component_variants import build_variant
from src.experiments.week9_construction import replay

SCHEMA = "rag-poison-transfer.2wiki-rcd-component-ablation-retrieval-plan/v1"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify_input_sources(private_plan, plan_pin, original_root, local_data):
    original_root = Path(original_root).expanduser().resolve(strict=True)
    selected_plan = require_json(private_plan, plan_pin)
    if selected_plan.get("schema") != PLAN_SCHEMA or selected_plan.get("original_frozen_pins") != ORIGINAL_PINS:
        raise ValueError("Not the original sealed 2Wiki RCD ablation preflight")
    if selected_plan.get("variants") != VARIANTS or len(selected_plan.get("cells", {})) != 4:
        raise ValueError("Original ablation design changed")
    proto = require_json(original_root / "protocol.json", ORIGINAL_PINS["protocol.json"])
    seal = require_json(original_root / "execution/construction/construction.seal.json",
                        ORIGINAL_PINS["execution/construction/construction.seal.json"])
    complete = require_json(original_root / "execution/evaluation/evaluation.complete.json",
                            ORIGINAL_PINS["execution/evaluation/evaluation.complete.json"])
    data_path = local_data or proto["replication"]["local_data"]
    data = require_json(data_path, proto["replication"]["local_data_sha256"])
    if sha(data_path) != selected_plan["private_local_data_sha256"]:
        raise ValueError("Private original data differs from frozen ablation preflight")
    if len(data["queries"]) != 300 or len({q["query_id"] for q in data["queries"]}) != 300:
        raise ValueError("Original 300-query 2Wiki data differs")
    by_id = {q["query_id"]: q for q in data["queries"]}
    if proto["binding"]["query_ids"] != list(by_id):
        raise ValueError("Original query ordering differs from pinned cohort")
    from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint
    if (seal["plan"]["clean_corpus_fingerprint"] != selected_plan["original_clean_corpus_fingerprint"] or
        corpus_fingerprint(data["corpus"]) != selected_plan["original_clean_corpus_fingerprint"] or
        seal["plan"]["query_set_fingerprint"] != selected_plan["original_query_set_fingerprint"] or
        query_set_fingerprint(data["queries"]) != selected_plan["original_query_set_fingerprint"]):
        raise ValueError("Original corpus/query bindings differ from sealed ablation preflight")
    if not isinstance(proto["replication"].get("retrieval_snapshots"), dict):
        raise ValueError("Original local retrieval model fingerprints missing")
    embedder = proto["replication"]["retrieval_snapshots"]["embedder"]
    embedder_path = Path(embedder["path"])
    if not embedder_path.exists():
        raise ValueError("Pinned original BGE embedder snapshot unavailable")
    cells = {}
    original_rows = {}
    for cellid, source in selected_plan["cells"].items():
        entry = seal.get("cells", {}).get(cellid)
        if not entry or entry.get("sha256") != source["construction_cell_sha256"]:
            raise ValueError("Original cell seal differs from private ablation plan")
        cell = require_json(original_root / "execution/construction" / entry["path"],
                            entry["sha256"])
        rows_sha = complete.get("rows_sha256", {}).get(cellid)
        if rows_sha != source["evaluation_cell_sha256"]:
            raise ValueError("Original Qwen evaluations differ from ablation plan")
        rows = require_json(original_root / "execution/evaluation" / cellid / "rows.json", rows_sha)
        records = {r["query_id"]: r for r in cell["records"]}
        reference = {(r["pipeline"], r["query_id"]): r for r in rows}
        if len(records) != 300 or len(reference) != 600:
            raise ValueError("Original per-cell query population differs")
        for qid in source["query_ids"]:
            if records[qid]["status"] != "valid_construction":
                raise ValueError("Selected query has no original valid poison construction")
            if reference[("rcd", qid)]["measurement"] is None:
                raise ValueError("Original Qwen RCD measurement is missing")
        cells[cellid] = cell
        original_rows[cellid] = reference
    return selected_plan, data, cells, original_rows, str(embedder_path)


def prepare(plan_file, plan_sha256, restore_root, output, local_data=None):
    out = outside_repo(output)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Write to a NEW private prompt-plan path outside Git")
    plan, data, cells, original_rows, embedder = verify_input_sources(
        plan_file, plan_sha256, restore_root, local_data
    )
    clean_queries = {q["query_id"]: q for q in data["queries"]}
    entries = []
    baseline_parity = 0
    for cellid, scope in sorted(plan["cells"].items()):
        cell = cells[cellid]
        full_poison = replay(data, cell)   # Entire sealed poison union, not only selected 10.
        selected_poison = {q["query_id"]: q for q in full_poison["queries"]}
        for qid in scope["query_ids"]:
            if qid not in selected_poison or qid not in clean_queries:
                raise ValueError("Selected question is missing original corpus association")
        for variant_name, spec in VARIANTS.items():
            # Each clean/poisoned index is fresh and independent. The new
            # variants are never substituted into the frozen historical runner.
            clean_retriever = build_variant(spec, embedder)
            poisoned_retriever = build_variant(spec, embedder)
            clean_retriever.build(data["corpus"])
            poisoned_retriever.build(full_poison["corpus"])
            for qid in scope["query_ids"]:
                query = clean_queries[qid]
                poison = selected_poison[qid]
                if query["question"] != poison["question"] or query["gold_answer"] != poison["gold_answer"]:
                    raise ValueError("Original clean and poison question/gold differ")
                old = original_rows[cellid][("rcd", qid)]["measurement"]
                for condition, retriever in (
                    ("clean", clean_retriever), ("poisoned", poisoned_retriever)
                ):
                    start = time.perf_counter()
                    docs = retriever.retrieve(query["question"], top_k=spec["top_k"])
                    elapsed = time.perf_counter() - start
                    ids = [doc.doc_id for doc in docs]
                    if len(ids) != spec["top_k"] or len(ids) != len(set(ids)):
                        raise ValueError("Candidate retrieval underfilled or duplicated evidence")
                    # New variants must only proceed if original full k=3
                    # truly reproduces frozen generator evidence ordering.
                    if variant_name == "full_k3":
                        old_ids = old[f"{condition}_condition"]["generation_evidence_doc_ids"]
                        if ids != old_ids:
                            raise ValueError(
                                f"Original full-RCD baseline evidence mismatch: {cellid} {condition}; "
                                "do NOT rerun or overwrite original data."
                            )
                        baseline_parity += 1
                    prompt = build_prompt(query["question"], [doc.text for doc in docs])
                    diagnostics = retriever.last_diagnostics
                    if not isinstance(diagnostics, dict):
                        raise ValueError("RCD diagnostics not recorded for new exploratory retrieval")
                    expected_inner_calls = diagnostics.get("retrieval_call_count")
                    if type(expected_inner_calls) is not int or expected_inner_calls < 1:
                        raise ValueError("Missing valid RCD inner retrieval-call count")
                    key = [cellid, variant_name, qid, condition]
                    entries.append({
                        "id": hashlib.sha256(canonical(key)).hexdigest()[:24],
                        "cell_id": cellid, "family": scope["family"],
                        "intensity": scope["intensity"], "seed": scope["seed"],
                        "query_id": qid, "variant": variant_name,
                        "condition": condition, "prompt": prompt,
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                        "gold_answer": query["gold_answer"],
                        "target_answer": poison["poison_target_answer"],
                        "evidence_doc_ids": ids,
                        "poison_doc_ids": poison["poison_doc_ids"],
                        "poison_visible_to_generator": condition == "poisoned" and bool(set(ids) & set(poison["poison_doc_ids"])),
                        "retrieval_elapsed_seconds": elapsed,
                        "inner_retrieval_calls": expected_inner_calls,
                        "candidate_consistency_features": diagnostics["consistency_signals"],
                        "candidate_scores": diagnostics["scores"],
                    })
            del clean_retriever, poisoned_retriever
            gc.collect()
    if baseline_parity != 80 or len(entries) != 480 or len({r["id"] for r in entries}) != 480:
        raise ValueError("Incomplete baseline parity or 480-item new-study input plan")
    result = {
        "schema": SCHEMA, "status": "PRIVATE_RETRIEVAL_PLAN_COMPLETE_NO_QA_INFERENCE",
        "ablation_preflight_sha256": plan_sha256,
        "original_pins": ORIGINAL_PINS,
        "candidate_k": 10, "qa_max_tokens": 64,
        "n_replayed_original_baseline_evidence_pairs": baseline_parity,
        "n_new_model_requests_planned": len(entries),
        "entries": entries,
        "limitations": [
            "Retriever-only preparation used the original poison union and 40 post-hoc valid query-stratum slots.",
            "New generator requests remain to be executed using a separately pinned Qwen model.",
            "Stored document-level scores are NOT validated poison-detection labels or independent truth.",
            "Retrieval latency is diagnostic and may reflect cold-cache effects.",
            "No frozen source, construction or evaluation files were mutated.",
        ],
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {"status": result["status"], "prompt_plan_sha256": sha(out),
            "path": str(out), "planned_qa_requests": len(entries),
            "baseline_retrieval_matches": baseline_parity}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ablation-plan", type=Path, required=True)
    p.add_argument("--ablation-plan-sha256", required=True)
    p.add_argument("--restored-root", type=Path, required=True)
    p.add_argument("--local-data", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.ablation_plan, a.ablation_plan_sha256,
                             a.restored_root, a.output, a.local_data), indent=2))


if __name__ == "__main__":
    main()
