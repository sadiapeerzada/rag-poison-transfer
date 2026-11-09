#!/usr/bin/env python3
"""Private real-retrieval *development diagnostic* using frozen NQ cohort.

Not poisoned, not a model-generation experiment, and not a completed RQ3
single-hop/multi-hop generalization claim. Requires a valid NQ SHA-pinned
cohort before any real retrieval. Output contains question IDs: PRIVATE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.nq_singlehop_v1_freeze import digest, json_load, private, verify
from src.defenses.iterative.retriever import EvidenceDependentIterativeRetriever

SCHEMA = "rag-poison-transfer.nq-iterative-clean-development-diagnostic/v1"


def diagnostic(cohort_dir, manifest_sha256, output, *, cohort="dev",
               max_queries=20, embedder_name="BAAI/bge-small-en-v1.5",
               allow_eval=False, retriever_factory=None):
    if cohort not in ("dev", "eval") or cohort == "eval" and not allow_eval:
        raise ValueError("NQ evaluation questions require explicit --allow-eval")
    if type(max_queries) is not int or max_queries < 1:
        raise ValueError("Positive max query count required")
    source = private(cohort_dir)
    validation = verify(source, manifest_sha256)
    if validation["status"] != "PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY":
        raise ValueError("Cohort integrity verification failed")
    out = private(output)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Require a new private output path with existing parent")
    filename = "dev_train.json" if cohort == "dev" else "evaluation_validation.json"
    dataset = json_load(source / filename)
    query_subset = dataset["queries"][:max_queries]
    if len(query_subset) != max_queries:
        raise ValueError("Requested more queries than frozen cohort provides")

    if retriever_factory is None:
        from src.retrieval.dense import DenseRetriever, SentenceTransformerEmbedder
        model = SentenceTransformerEmbedder(embedder_name)
        retriever = DenseRetriever(model)
    else:
        retriever = retriever_factory()
    retriever.build(dataset["corpus"])
    iterative = EvidenceDependentIterativeRetriever(
        retriever, max_rounds=2, candidate_k=10,
        output_k=3, min_coverage=.75)
    records = []
    for question in query_subset:
        qid = question["query_id"]
        start = time.perf_counter()
        baseline = retriever.retrieve(question["question"], top_k=3)
        baseline_seconds = time.perf_counter() - start
        start = time.perf_counter()
        adaptive = iterative.retrieve(question["question"], top_k=3)
        adaptive_seconds = time.perf_counter() - start
        trace = iterative.last_diagnostics
        gold = set(question["gold_doc_ids"])
        records.append({
            "query_id": qid,
            "baseline_retrieved_doc_ids": [doc.doc_id for doc in baseline],
            "iterative_retrieved_doc_ids": [doc.doc_id for doc in adaptive],
            "baseline_gold_visible": any(doc.doc_id in gold for doc in baseline),
            "iterative_gold_visible": any(doc.doc_id in gold for doc in adaptive),
            "baseline_retrieval_elapsed_seconds": baseline_seconds,
            "iterative_retrieval_elapsed_seconds": adaptive_seconds,
            "iterative_trace": trace,
        })
    result = {
        "schema": SCHEMA,
        "status": "NQ_REAL_CLEAN_ITERATIVE_RETRIEVAL_DIAGNOSTIC_ONLY",
        "scope": "Exploratory diagnostic, real retrieval but NO poisoning and NO Qwen QA",
        "dataset_cohort_sha256": manifest_sha256,
        "private_data_file_sha256": digest(source / filename),
        "cohort": cohort, "n_questions": len(records),
        "embedding_model_identifier": embedder_name,
        "embedding_model_file_hashes_verified": False,
        "n_second_round_calls": sum(x["iterative_trace"]["retrieval_call_count"] == 2 for x in records),
        "n_abstentions": sum(x["iterative_trace"]["final_decision"] == "abstain" for x in records),
        "baseline_gold_visible_count": sum(x["baseline_gold_visible"] for x in records),
        "iterative_gold_visible_count": sum(x["iterative_gold_visible"] for x in records),
        "n_baseline_outer_calls": len(records),
        "n_iterative_outer_calls": sum(x["iterative_trace"]["retrieval_call_count"] for x in records),
        "records_private": records,
        "limitations": [
            "This is not multi-hop RAG QA and makes no end-to-end poison-success claim.",
            "NQ question-candidate corpus is not standard open-domain Wikipedia.",
            "Unpinned embedding weights in this development smoke: pin model snapshot for final evaluation.",
            "Coverage is an uncalibrated lexical proxy, not answer confidence.",
            "Do not use evaluation cohort for policy selection or threshold tuning.",
        ],
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "n_queries": result["n_questions"],
            "n_second_round_calls": result["n_second_round_calls"],
            "n_abstentions": result["n_abstentions"],
            "output": str(out)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort-dir", required=True, type=Path)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--cohort", choices=("dev", "eval"), default="dev")
    p.add_argument("--allow-eval", action="store_true")
    p.add_argument("--max-queries", type=int, default=20)
    p.add_argument("--embedder-name", default="BAAI/bge-small-en-v1.5")
    args = p.parse_args()
    print(json.dumps(diagnostic(args.cohort_dir, args.manifest_sha256,
                                args.output, cohort=args.cohort,
                                max_queries=args.max_queries,
                                embedder_name=args.embedder_name,
                                allow_eval=args.allow_eval), indent=2))


if __name__ == "__main__":
    main()
