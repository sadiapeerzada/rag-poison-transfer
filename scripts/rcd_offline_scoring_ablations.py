#!/usr/bin/env python3
"""Read-only, *ranking-only* RCD score-component ablation from saved diagnostics.

This cannot simulate removing retrieval rewrites or infer alternate LLM answers.
Use only with authentic baseline RCDRetriever.last_diagnostics exports.
No new retrieval and no generator inference occur.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

WEIGHTS = {"consistency": .45, "redundancy": 0., "conflict": .10, "base_rank_score": .45}
VARIANTS = {
    "full": dict(WEIGHTS),
    "no_conflict_penalty": {"consistency": .5, "redundancy": 0., "conflict": 0., "base_rank_score": .5},
    "no_consistency_score": {"consistency": 0., "redundancy": 0., "conflict": 2/11, "base_rank_score": 9/11},
    "no_base_rank": {"consistency": 9/11, "redundancy": 0., "conflict": 2/11, "base_rank_score": 0.},
}


def score_all(diagnostics, variant):
    """Replay frozen scoring and, if requested, remove *one consistency signal*."""
    scores = diagnostics.get("scores")
    signals = diagnostics.get("consistency_signals")
    if not isinstance(scores, dict) or not scores or not isinstance(signals, dict):
        raise ValueError("Missing full per-document RCD scores and consistency signals")
    weights = VARIANTS.get(variant)
    if weights is None and variant not in ("no_agreement_signal", "no_rewrite_stability_signal"):
        raise ValueError("Unknown ablation: " + variant)
    if weights is None:
        weights = WEIGHTS
    result = {}
    for doc_id, fields in scores.items():
        sig = signals.get(doc_id)
        if not isinstance(sig, dict):
            raise ValueError("Missing diagnostic signal for " + doc_id)
        if variant == "no_agreement_signal":
            cons = (sig["rank_stability"] + sig["rewrite_stability"]) / 2
        elif variant == "no_rewrite_stability_signal":
            # IMPORTANT: candidates from rewrites remain in the pool.
            cons = (sig["agreement"] + sig["rank_stability"]) / 2
        else:
            cons = fields["consistency"]
        parts = {"consistency": cons,
                 "redundancy": fields["redundancy"],
                 "conflict": fields["conflict"],
                 "base_rank_score": fields["base_rank_score"]}
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in parts.values()):
            raise ValueError("Invalid numeric signal")
        result[doc_id] = (weights["consistency"] * cons
                         + weights["redundancy"] * parts["redundancy"]
                         - weights["conflict"] * parts["conflict"]
                         + weights["base_rank_score"] * parts["base_rank_score"])
    return result


def ranking(diagnostics, variant):
    # Python's stable sort preserves insertion order for equal scores. Input
    # diagnostics.scores preserves the original list(candidate_docs.values()).
    scores = score_all(diagnostics, variant)
    return sorted(scores, key=scores.get, reverse=True)


def summarize(rows, top_k):
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    variants = [*VARIANTS, "no_agreement_signal", "no_rewrite_stability_signal"]
    totals = defaultdict(lambda: {"n": 0, "rank_changed": 0, "jaccard_sum": 0., "baseline_poison_visible": 0, "variant_poison_visible": 0})
    for row in rows:
        if row.get("condition") not in ("clean", "poisoned"):
            raise ValueError("Every diagnostic row must identify clean/poisoned condition")
        diag = row.get("diagnostics")
        if not isinstance(diag, dict):
            raise ValueError("Row missing authentic RCD diagnostics")
        selected = diag.get("selected_doc_ids")
        if not isinstance(selected, list) or len(selected) < top_k:
            raise ValueError("Baseline selected docs shorter than requested evidence depth")
        full = ranking(diag, "full")[:top_k]
        # The same frozen score weights must reproduce the original selection.
        if full != selected[:top_k]:
            raise ValueError("Baseline rankings disagree: score-only replay is invalid")
        if "query_id" not in row or not row["query_id"]:
            raise ValueError("Missing query identity")
        poison_ids = row.get("poison_doc_ids", [])
        if not isinstance(poison_ids, list):
            raise ValueError("poison_doc_ids must be a list")
        for name in variants:
            candidate = ranking(diag, name)[:top_k]
            shared = len(set(full) & set(candidate))
            union = len(set(full) | set(candidate))
            key = (row["condition"], name)
            total = totals[key]
            total["n"] += 1
            total["rank_changed"] += int(candidate != full)
            total["jaccard_sum"] += shared/union if union else 1.
            if row["condition"] == "poisoned":
                total["baseline_poison_visible"] += int(bool(set(full) & set(poison_ids)))
                total["variant_poison_visible"] += int(bool(set(candidate) & set(poison_ids)))
    if not totals:
        raise ValueError("No diagnostic input rows")
    return {
        "schema": "rag-poison-transfer.rcd-ranking-only-posthoc-ablation/v1",
        "study_type": "posthoc score-only sensitivity; NOT confirmatory end-to-end attack study",
        "top_k": top_k, "variants": {
            f"{condition}|{name}": {
                "n_query_seed_rows": d["n"],
                "changed_evidence_order_rows": d["rank_changed"],
                "changed_evidence_order_rate": d["rank_changed"] / d["n"],
                "mean_set_jaccard": d["jaccard_sum"] / d["n"],
                **({"baseline_poison_visible_rows": d["baseline_poison_visible"],
                    "variant_poison_visible_rows": d["variant_poison_visible"]} if condition == "poisoned" else {}),
            } for (condition, name), d in sorted(totals.items())
        },
        "limitations": [
            "Reuses same candidate pool, rankings and precomputed conflict/redundancy signals.",
            "Removing rewrite-stability *score component* does NOT eliminate query rewrite retrieval.",
            "Cannot estimate alternate model answers, clean EM, attack success, or end-to-end ASR.",
            "Original question IDs may repeat across seeds; not independent sampling units.",
            "No inference was run.",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diagnostics-jsonl", type=Path, required=True)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    if a.output.exists() or not a.output.parent.is_dir():
        raise ValueError("Output must be new and parent directory must exist")
    rows = [json.loads(line) for line in a.diagnostics_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = summarize(rows, a.top_k)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: ranking-only sensitivity; {len(rows)} existing diagnostic rows; no inference")


if __name__ == "__main__":
    main()
