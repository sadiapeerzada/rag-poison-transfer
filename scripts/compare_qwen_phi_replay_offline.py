#!/usr/bin/env python3
"""Read-only matched comparison of original frozen 2Wiki Qwen answers vs a
separately run non-Qwen fixed-evidence prompt replay.

No generation, retrieval, construction, or edits of original files. Output is
aggregate-only. Does not establish a prospective or representative model-family
effect. Explicitly documents original-vs-replay token-cap differences.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.second_model_prompt_replay import (
    TWOWIKI_COMPLETION_SHA256, canonical, outside_repo, sha,
)
from src.evaluation.metrics import exact_match
from src.evaluation.qa_records import extract_answer, validate_qa

PLAN_SCHEMA = "rag-poison-transfer.private-fixed-evidence-second-model-plan/v1"
RUN_SCHEMA = "rag-poison-transfer.second-model-replay-run/v1"
OUTPUT_SCHEMA = "rag-poison-transfer.matched-qwen-phi-replay-comparison/v1"
ARMS = {"dense", "rcd"}
CONDITIONS = {"clean", "poisoned"}
FAMILIES = {"lexical_influential_token", "semantic_fluent_false_evidence"}


def checked_json(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Required regular file missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_counts(row):
    n = row["n"]
    return {
        "n_matched_replay_items": n,
        "n_distinct_query_ids": len(row["query_ids"]),
        "qwen_gold_em": {"count": row["qwen_gold"], "rate": row["qwen_gold"] / n},
        "phi_gold_em": {"count": row["phi_gold"], "rate": row["phi_gold"] / n},
        "qwen_target_match": {"count": row["qwen_target"], "rate": row["qwen_target"] / n},
        "phi_target_match": {"count": row["phi_target"], "rate": row["phi_target"] / n},
        "phi_minus_qwen_gold_em_pp": 100 * (row["phi_gold"] - row["qwen_gold"]) / n,
        "phi_minus_qwen_target_match_pp": 100 * (row["phi_target"] - row["qwen_target"]) / n,
        "target_discordance": {
            "both_match": row["both_target"],
            "qwen_only": row["qwen_only_target"],
            "phi_only": row["phi_only_target"],
            "neither": row["neither_target"],
        },
    }


def analyze(plan_file, plan_sha256, evaluation_dir, phi_results_dir):
    plan_file, evaluation_dir, phi_results_dir = (
        Path(plan_file), Path(evaluation_dir), Path(phi_results_dir)
    )
    if sha(plan_file) != plan_sha256:
        raise ValueError("Private replay plan SHA-256 mismatch")
    plan = checked_json(plan_file)
    if plan.get("schema") != PLAN_SCHEMA or plan.get("evaluation_completion_sha256") != TWOWIKI_COMPLETION_SHA256:
        raise ValueError("Private plan schema/evaluation completion binding invalid")
    if not isinstance(plan.get("entries"), list) or not plan["entries"] or len(plan["entries"]) != plan.get("row_count"):
        raise ValueError("Plan row count invalid")
    completion_file = evaluation_dir / "evaluation.complete.json"
    if sha(completion_file) != TWOWIKI_COMPLETION_SHA256:
        raise ValueError("Frozen original Qwen evaluation completion hash mismatch")
    completion = checked_json(completion_file)
    manifest = checked_json(phi_results_dir / "run_manifest.json")
    if manifest.get("schema") != RUN_SCHEMA or manifest.get("plan_sha256") != plan_sha256:
        raise ValueError("Phi replay run manifest not bound to the selected plan")
    if not manifest.get("model_snapshot_sha256") or manifest.get("model_family") in (None, "qwen", "qwen2"):
        raise ValueError("Invalid distinct-model provenance")
    rows_by_cell = {}
    summaries = defaultdict(lambda: {
        "n": 0, "query_ids": set(), "qwen_gold": 0, "phi_gold": 0,
        "qwen_target": 0, "phi_target": 0, "both_target": 0,
        "qwen_only_target": 0, "phi_only_target": 0, "neither_target": 0,
    })
    expected_ids = set()
    matched_ids = set()
    for selected in plan["entries"]:
        if not isinstance(selected, dict):
            raise ValueError("Malformed plan entry")
        for key in ("id", "query_id", "family", "intensity", "seed", "arm",
                    "condition", "prompt", "prompt_sha256", "gold_answer", "target_answer"):
            if key not in selected:
                raise ValueError(f"Plan entry missing {key}")
        family, intensity, seed, arm, condition, query_id = (
            selected[k] for k in ("family", "intensity", "seed", "arm", "condition", "query_id")
        )
        if family not in FAMILIES or intensity not in (1, 3) or seed not in (42, 43, 44) or arm not in ARMS or condition not in CONDITIONS:
            raise ValueError("Plan entry not in declared protocol")
        identity = canonical([family, intensity, seed, query_id, arm, condition])[:24]
        if selected["id"] != identity or identity in expected_ids:
            raise ValueError("Duplicate or invalid plan item identity")
        expected_ids.add(identity)
        if hashlib.sha256(selected["prompt"].encode()).hexdigest() != selected["prompt_sha256"]:
            raise ValueError("Tampered plan prompt hash")
        cell = f"{family}.intensity-{intensity}.seed-{seed}"
        if cell not in rows_by_cell:
            cell_file = evaluation_dir / cell / "rows.json"
            if sha(cell_file) != completion.get("rows_sha256", {}).get(cell):
                raise ValueError(f"Original frozen cell SHA-256 mismatch: {cell}")
            full_rows = checked_json(cell_file)
            mapping = {}
            for row in full_rows:
                key = (row.get("query_id"), row.get("pipeline"))
                if key in mapping:
                    raise ValueError(f"Duplicate original Qwen query/arm in cell {cell}")
                mapping[key] = row
            rows_by_cell[cell] = mapping
        original = rows_by_cell[cell].get((query_id, arm))
        if original is None or original.get("construction_status") != "valid_construction":
            raise ValueError("Original Qwen valid-construction row missing")
        measurement = original.get("measurement")
        if not isinstance(measurement, dict) or measurement.get("gold_answer") != selected["gold_answer"] or measurement.get("poison_target_answer") != selected["target_answer"]:
            raise ValueError("Qwen gold/target mismatch with selected replay plan")
        qobs = measurement[f"{condition}_condition"]
        qgeneration = qobs["generation"]
        validate_qa(qgeneration, qobs["answer"])
        if qgeneration["prompt_sha256"] != selected["prompt_sha256"] or qgeneration["prompt"] != selected["prompt"]:
            raise ValueError("Original Qwen generator prompt differs from Phi replay prompt")
        if float(exact_match(qobs["answer"], selected["gold_answer"])) != float(qobs["em"]):
            raise ValueError("Original Qwen EM inconsistent with frozen answer")
        qanswer = qobs["answer"]
        phi = checked_json(phi_results_dir / (identity + ".json"))
        if phi.get("id") != identity or phi.get("plan_sha256") != plan_sha256 or phi.get("prompt_sha256") != selected["prompt_sha256"] or phi.get("model_snapshot_sha256") != manifest["model_snapshot_sha256"]:
            raise ValueError("Phi answer record does not match immutable plan/model")
        if extract_answer(phi.get("raw_response")) != phi.get("extracted_answer"):
            raise ValueError("Phi extraction inconsistent with original text")
        phi_answer = phi["extracted_answer"]
        qgold = int(bool(exact_match(qanswer, selected["gold_answer"])))
        pgold = int(bool(exact_match(phi_answer, selected["gold_answer"])))
        qtarget = int(bool(exact_match(qanswer, selected["target_answer"])))
        ptarget = int(bool(exact_match(phi_answer, selected["target_answer"])))
        if phi.get("gold_em") != pgold or phi.get("target_match") is not bool(ptarget):
            raise ValueError("Phi scores inconsistent with observed response")
        gkey = f"{family}|{intensity}|{arm}|{condition}"
        group = summaries[gkey]
        group["n"] += 1
        group["query_ids"].add(query_id)
        group["qwen_gold"] += qgold
        group["phi_gold"] += pgold
        group["qwen_target"] += qtarget
        group["phi_target"] += ptarget
        if qtarget and ptarget: group["both_target"] += 1
        elif qtarget: group["qwen_only_target"] += 1
        elif ptarget: group["phi_only_target"] += 1
        else: group["neither_target"] += 1
        matched_ids.add(identity)
    if matched_ids != expected_ids or len(summaries) != 16:
        raise ValueError("Incomplete paired Qwen/Phi comparison")
    if set(p.name for p in phi_results_dir.glob("*.json")) != {
        "run_manifest.json", *(identity + ".json" for identity in expected_ids)
    }:
        raise ValueError("Extra or missing Phi replay records")
    values = {key: fmt_counts(row) for key, row in sorted(summaries.items())}
    return {
        "schema": OUTPUT_SCHEMA,
        "status": "PASS_MATCHED_QWEN_PHI_OFFLINE_COMPARISON",
        "scope": "Exploratory, valid-only, one frozen poison seed; matching original stored Qwen text prompts",
        "n_paired_generator_observations": len(matched_ids),
        "n_distinct_selected_query_ids": len({r["query_id"] for r in plan["entries"]}),
        "source_2wiki_evaluation_completion_sha256": TWOWIKI_COMPLETION_SHA256,
        "private_replay_plan_sha256": plan_sha256,
        "phi_model_family": manifest["model_family"],
        "phi_snapshot_sha256": manifest["model_snapshot_sha256"],
        "phi_generation_max_tokens": manifest["max_tokens"],
        "qwen_generation_max_tokens_declared_in_frozen_protocol": 64,
        "groups": values,
        "limitations": [
            "No new inference, retrieval or poisoning; original Qwen results unchanged.",
            "Matched plaintext prompts are not identical backend chat templates/tokenizer behavior across model families.",
            "Original Qwen generation cap was 64 tokens; replay Phi cap may differ (recorded above).",
            "Small, post-hoc, valid-only sample with repeated question IDs across conditions; no prospective generalization claim.",
            "Paired per-item discordance is descriptive, not a statistical test on independent questions.",
            "Neither source-backed semantic factuality nor poison-induced counterfactual flips are certified.",
            "No per-query data or model text exported.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--evaluation-dir", type=Path, required=True)
    p.add_argument("--phi-results", type=Path, required=True)
    p.add_argument("--report-out", type=Path, required=True)
    a = p.parse_args()
    report = outside_repo(a.report_out)
    if report.exists() or not report.parent.is_dir():
        raise ValueError("Report must be new in a pre-existing private output directory")
    result = analyze(a.plan, a.plan_sha256, a.evaluation_dir, a.phi_results)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "n_matched": result["n_paired_generator_observations"],
                      "n_groups": len(result["groups"]), "report_out": str(report)}, indent=2))


if __name__ == "__main__":
    main()
