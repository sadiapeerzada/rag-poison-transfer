#!/usr/bin/env python3
"""Read-only 2Wiki RCD ablation audit. Never invokes a generator or modifies source artifacts.

Runs only against the original private retrieval plan, 480 observation journals,
and the pinned aggregate. Writes a new *aggregate-only* private report.

From repository root:
  python scripts/audit_2wiki_rcd_ablations_offline.py
or pass --plan PATH to identify the 480-row prompt plan explicitly.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.prepare_2wiki_rcd_ablation_plan import VARIANTS
from scripts.run_2wiki_rcd_ablation_qa import (
    RUN_SCHEMA, SUMMARY_SCHEMA, checked_plan, score_response,
)

AGG_SHA = "9ae68bd2050bef08782d4bc96ba924ffa936d3e7f8d096aa550af964d2bb9466"
ROOT = Path.home() / "Documents" / "rag-research-results"
RUN_NAME = "2wiki-rcd-qa-v1-20261108T220335Z_PRIVATE"
AGG_NAME = "2wiki-rcd-ablation-aggregate-20261109T055229Z_PRIVATE.json"
FAMILIES = ("lexical_influential_token", "semantic_fluent_false_evidence")
METRICS = (
    "target_match", "poisoned_em", "clean_em", "poisoned_f1", "clean_f1",
    "poison_exposed", "clean_correct_to_poisoned_wrong", "retrieval_seconds_per_qa",
    "generation_seconds_per_qa", "inner_retrieval_calls_per_qa",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    v = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(v, dict):
        raise ValueError("Expected object JSON: " + path.name)
    return v


def guarded_path(path: Path, root: Path, *, must_exist=True) -> Path:
    p = path.expanduser().resolve(strict=must_exist)
    if root not in p.parents:
        raise ValueError("Private data path must remain under private root")
    if REPO == p or REPO in p.parents:
        raise ValueError("Do not read/write research journals inside Git")
    return p


def locate_plan(root: Path, run_dir: Path, sha: str, manual: Path | None) -> Path:
    if manual:
        p = guarded_path(manual, root)
        if digest(p) != sha:
            raise ValueError("Explicit prompt plan SHA-256 disagrees with original run manifest")
        return p

    # Search filename metadata only. Avoid NQ responses and the restored 2Wiki
    # 37k-file archive. The matching SHA (rather than filename) is authoritative.
    candidate_dirs = [run_dir.parent, root]
    checked = set()
    for directory in candidate_dirs:
        for p in directory.glob("*.json"):
            if p in checked:
                continue
            checked.add(p)
            if 10_000 < p.stat().st_size < 100_000_000 and digest(p) == sha:
                return p.resolve()
    # One level below the experiment-gates root, skipping response subtrees.
    for p in run_dir.parent.glob("*/*.json"):
        if p in checked or p.parent.name in {"entries", "intents", "responses"}:
            continue
        checked.add(p)
        if 10_000 < p.stat().st_size < 100_000_000 and digest(p) == sha:
            return p.resolve()
    raise ValueError(
        "Frozen retrieval/prompt plan not located automatically. Use --plan PATH "
        "for the file whose SHA-256 equals run_manifest.json's prompt_plan_sha256 "
        "(use shasum -a 256 PATH). No output written."
    )


def close(a, b, label):
    if isinstance(a, bool) or isinstance(b, bool):
        if a != b:
            raise ValueError("Original aggregate mismatch: " + label)
        return
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or not math.isclose(a, b, abs_tol=1e-8, rel_tol=1e-8):
        raise ValueError("Original aggregate mismatch: " + label)


def summarize_position(clean: dict, poisoned: dict, plan_clean: dict, plan_poison: dict) -> dict:
    for key in ("generator_latency_seconds", "prompt_tokens", "completion_tokens"):
        for obs in (clean, poisoned):
            v = obs.get(key)
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError("Missing/invalid recorded model measurement " + key)
    return {
        "target_match": int(poisoned["target_match"]),
        "poisoned_em": int(poisoned["gold_em"]),
        "clean_em": int(clean["gold_em"]),
        "poisoned_f1": float(poisoned["gold_f1"]),
        "clean_f1": float(clean["gold_f1"]),
        "poison_exposed": int(plan_poison["poison_visible_to_generator"]),
        "clean_correct_to_poisoned_wrong": int(bool(clean["gold_em"] and not poisoned["gold_em"])),
        "retrieval_seconds_per_qa": (plan_clean["retrieval_elapsed_seconds"] + plan_poison["retrieval_elapsed_seconds"]) / 2,
        "generation_seconds_per_qa": (clean["generator_latency_seconds"] + poisoned["generator_latency_seconds"]) / 2,
        "inner_retrieval_calls_per_qa": (plan_clean["inner_retrieval_calls"] + plan_poison["inner_retrieval_calls"]) / 2,
    }


def aggregate_row(items: dict) -> dict:
    """Recompute the original per-cell group aggregate, no raw answers copied."""
    vals = list(items.values())
    n = len(vals)
    if n != 10:
        raise ValueError("Expected ten matched positions for each cell/variant")
    return {
        "n_valid_selected_query_positions": n,
        "n_clean_correct": sum(v["clean_em"] for v in vals),
        "n_poisoned_correct": sum(v["poisoned_em"] for v in vals),
        "n_target_matches": sum(v["target_match"] for v in vals),
        "n_clean_target_matches": sum(v["clean_target_match"] for v in vals),
        "n_poison_visible": sum(v["poison_exposed"] for v in vals),
        "n_clean_correct_to_poisoned_wrong": sum(v["clean_correct_to_poisoned_wrong"] for v in vals),
        "mean_clean_f1": sum(v["clean_f1"] for v in vals) / n,
        "mean_poisoned_f1": sum(v["poisoned_f1"] for v in vals) / n,
        "mean_retrieval_seconds": sum(v["retrieval_seconds_per_qa"] for v in vals) / n,
        "mean_generation_seconds": sum(v["generation_seconds_per_qa"] for v in vals) / n,
        "total_inner_retrieval_calls": 2 * sum(v["inner_retrieval_calls_per_qa"] for v in vals),
        "clean_em_rate": sum(v["clean_em"] for v in vals) / n,
        "poisoned_em_rate": sum(v["poisoned_em"] for v in vals) / n,
        "poisoned_target_match_rate": sum(v["target_match"] for v in vals) / n,
        "poison_visibility_rate": sum(v["poison_exposed"] for v in vals) / n,
    }


def cluster_bootstrap(deltas_by_question: dict, *, reps: int, seed: int) -> dict:
    """Preserve all reused cell positions when resampling one unique question."""
    if not deltas_by_question:
        raise ValueError("No matched questions for bootstrap")
    clusters = [list(v) for _, v in sorted(deltas_by_question.items())]
    all_vals = [z for sub in clusters for z in sub]
    point = sum(all_vals) / len(all_vals)
    rng = random.Random(seed)
    n = len(clusters)
    results = []
    for _ in range(reps):
        chosen = [clusters[rng.randrange(n)] for _ in range(n)]
        count = sum(len(a) for a in chosen)
        results.append(sum(sum(a) for a in chosen) / count)
    results.sort()
    lo = results[int(0.025 * reps)]
    hi = results[int(0.975 * reps) - 1]
    return {
        "estimate": point,
        "nominal_95pct_question_cluster_CI": [lo, hi],
        "n_distinct_question_ids": n,
        "n_repeated_cell_positions": len(all_vals),
        "bootstrap_replicates": reps,
    }


def latency_diagnostics(rows: list[dict]) -> dict:
    values = sorted(rows)
    n = len(values)
    median = statistics.median(values)
    return {
        "n_responses": n,
        "mean_seconds": statistics.mean(values),
        "median_seconds": median,
        "p95_seconds_nearest_rank": values[max(0, math.ceil(n * 0.95) - 1)],
        "max_seconds": max(values),
        "n_over_10_seconds": sum(v > 10 for v in values),
        "n_over_30_seconds": sum(v > 30 for v in values),
        "n_over_5x_median": sum(v > 5 * median for v in values) if median else None,
    }


def audit(root: Path, run_dir: Path, aggregate: Path, explicit_plan: Path | None, reps: int, seed: int):
    root = root.expanduser().resolve(strict=True)
    run_dir = guarded_path(run_dir, root)
    aggregate = guarded_path(aggregate, root)
    if digest(aggregate) != AGG_SHA:
        raise ValueError("Original 480-call aggregate SHA differs from frozen published evidence")
    original = load_json(aggregate)
    if original.get("schema") != SUMMARY_SCHEMA or original.get("n_Qwen_observations") != 480:
        raise ValueError("Incorrect original ablation aggregate schema/count")
    manifest_path = run_dir / "run_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("schema") != RUN_SCHEMA or manifest.get("planned_logical_calls") != 480 or manifest.get("qa_max_tokens") != 64:
        raise ValueError("Wrong run manifest or incomplete planned cohort")
    plan_sha = manifest.get("prompt_plan_sha256")
    if not isinstance(plan_sha, str) or len(plan_sha) != 64 or plan_sha != original.get("source_prompt_plan_sha256"):
        raise ValueError("Plan SHA disagrees between run manifest and original aggregate")
    plan_path = locate_plan(root, run_dir, plan_sha, explicit_plan)
    plan = checked_plan(plan_path, plan_sha)
    if len(plan["entries"]) != 480:
        raise ValueError("Wrong frozen plan length")
    ids = {r["id"] for r in plan["entries"]}
    results = {p.stem for p in (run_dir / "entries").glob("*.json")}
    intents = {p.stem for p in (run_dir / "intents").glob("*.json")}
    if len(ids) != 480 or ids != results or ids != intents:
        raise ValueError("Result/intent files are incomplete, duplicated or altered")
    paired = defaultdict(dict)
    latency_by_variant = defaultdict(list)
    for entry in plan["entries"]:
        sid = entry["id"]
        obs = load_json(run_dir / "entries" / (sid + ".json"))
        intent = load_json(run_dir / "intents" / (sid + ".json"))
        if (intent.get("id") != sid or intent.get("prompt_sha256") != entry["prompt_sha256"] or
            intent.get("prompt_plan_sha256") != plan_sha or intent.get("model_binding_sha256") != manifest.get("model_binding_sha256")):
            raise ValueError("Response intent not bound to original prompt and model")
        score_response(entry, obs, plan_sha, manifest["model_binding_sha256"])
        vkey = (entry["cell_id"], entry["variant"], entry["query_id"])
        if entry["condition"] in paired[vkey]:
            raise ValueError("Duplicate matched response")
        paired[vkey][entry["condition"]] = (obs, entry)
        latency_by_variant[entry["variant"]].append(float(obs["generator_latency_seconds"]))
    if len(paired) != 240 or any(set(v) != {"clean", "poisoned"} for v in paired.values()):
        raise ValueError("Not exactly 240 clean/poison matched pairs")
    by_cell_variant = defaultdict(dict)
    distinct_qids = set()
    for (cell, variant, qid), pair in paired.items():
        clean, ec = pair["clean"]
        poisoned, ep = pair["poisoned"]
        v = summarize_position(clean, poisoned, ec, ep)
        v["clean_target_match"] = int(clean["target_match"])
        by_cell_variant[(cell, variant)][qid] = v
        distinct_qids.add(qid)
    if len(by_cell_variant) != 24:
        raise ValueError("Wrong four-cell / six-variant structure")
    for (cell, variant), position_rows in by_cell_variant.items():
        if set(position_rows) != set(by_cell_variant[(cell, "full_k3")]):
            raise ValueError("Variants do not share same questions within their cell")
        group_key = cell + "|" + variant
        if group_key not in original["groups"]:
            raise ValueError("Original aggregate missing cell/variant " + group_key)
        expected = original["groups"][group_key]
        recomputed = aggregate_row(position_rows)
        if set(expected) != set(recomputed):
            raise ValueError("Original group metric schema mismatch for " + group_key)
        for k in expected:
            close(recomputed[k], expected[k], group_key + " / " + k)
    if len(original["groups"]) != 24 or len(original["paired_nominal_intervals"]) != 20:
        raise ValueError("Original ablation groups/intervals truncated")
    for cell, variant in by_cell_variant:
        if variant != "full_k3" and cell + "|" + variant not in original["paired_nominal_intervals"]:
            raise ValueError("Missing original per-cell bootstrap interval")
    contrasts = {}
    pooled_means = {}
    for variant in VARIANTS:
        positions = {
            (cell, qid): v
            for (cell, vname), rows in by_cell_variant.items() if vname == variant
            for qid, v in rows.items()
        }
        if len(positions) != 40:
            raise ValueError("Missing original 40 cell positions")
        pooled_means[variant] = {k: sum(p[k] for p in positions.values()) / 40 for k in METRICS}
        if variant == "full_k3":
            continue
        for metric in METRICS:
            question_deltas = defaultdict(list)
            for (cell, qid), v in positions.items():
                base = by_cell_variant[(cell, "full_k3")][qid]
                question_deltas[qid].append(base[metric] - v[metric])
            contrasts.setdefault(variant, {})[metric] = cluster_bootstrap(question_deltas, reps=reps, seed=seed)
    # Include only aggregate values and SHA pins, never raw question IDs or answers.
    report = {
        "schema": "rag-poison-transfer.2wiki-rcd-ablation-question-cluster-audit/v1",
        "status": "ORIGINAL_480_ABLATION_OBSERVATIONS_PAIRED_AUDIT_PASSED_EXPLORATORY",
        "source_original_aggregate_sha256": AGG_SHA,
        "source_prompt_plan_sha256": plan_sha,
        "source_run_manifest_sha256": digest(manifest_path),
        "verified_response_and_intent_count": 480,
        "matched_clean_poison_pairs": 240,
        "n_cell_positions_per_variant": 40,
        "n_unique_question_ids_across_four_cells": len(distinct_qids),
        "n_source_per_cell_paired_intervals": 20,
        "bootstrap_unit": "distinct question ID shared across all selected attack-family/intensity cells; repeated positions retained in same cluster",
        "bootstrap_replicates": reps,
        "bootstrap_seed": seed,
        "variant_pooled_means": pooled_means,
        "baseline_minus_variant_question_cluster_intervals": contrasts,
        "generator_latency_diagnostics": {name: latency_diagnostics(v) for name, v in latency_by_variant.items()},
        "limitations": [
            "Post-hoc selection of ten mechanically valid question slots per four attack/intensity cells; not untouched prospective population inference.",
            "Question ID clustering preserves overlap across cells, but this single-seed selected set is small and not representative of the attempted population.",
            "Nominal percentile bootstrap intervals unadjusted for multiple testing; variance may be degenerate for unchanged paired responses.",
            "Target matching is not independently source-verified false-answer success; selection excluded invalid poison constructions.",
            "Retrieval timings measured during prompt preparation, generation timings from original model runs; startup and cache conditions may vary.",
            "This offline audit cannot certify original source-document truth, data independence, source licensing, or live deployment cost.",
        ],
    }
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--aggregate", type=Path)
    p.add_argument("--plan", type=Path, help="Original 480-entry private retrieval/prompt plan (auto-discovered by SHA if omitted)")
    p.add_argument("--reps", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20261109)
    p.add_argument("--output", type=Path, help="Optional NEW aggregate-only JSON file under private root")
    args = p.parse_args()
    if args.reps < 100 or args.reps > 100000:
        p.error("--reps must be in [100,100000]")
    root = args.root.expanduser().resolve(strict=True)
    run = args.run_dir or root / "nov09-research-gates" / RUN_NAME
    agg = args.aggregate or root / "nov09-research-gates" / AGG_NAME
    result = audit(root, run, agg, args.plan, args.reps, args.seed)
    if args.output:
        out = guarded_path(args.output, root, must_exist=False)
        if out.exists() or not out.parent.is_dir():
            raise ValueError("Output must be a NEW file in an existing private directory")
        # Use exclusive create; never overwrite previous audit evidence.
        with out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        print(json.dumps({"status": result["status"], "n_distinct_question_clusters": result["n_unique_question_ids_across_four_cells"], "n_verified_responses": 480, "aggregate_only_json_saved": str(out)}, indent=2))
    else:
        # Print no paths, query IDs, prompts, answers, targets or per-request metrics.
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
