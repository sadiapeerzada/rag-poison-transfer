#!/usr/bin/env python3
"""New exploratory 2Wiki RCD ablation QA stage, never the frozen original.

plan -> explicit run with pinned original Qwen model (480 calls) -> aggregate.
All per-item prompts/answers/checkpoints stay private, outside public Git.
An intent without a verified response halts on resume: uncertain physical
model calls are never automatically repeated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import tempfile
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_2wiki_rcd_ablation_plan import ORIGINAL_PINS, VARIANTS, require_json
from scripts.prepare_2wiki_rcd_ablation_prompts import SCHEMA as PROMPT_SCHEMA
from scripts.second_model_prompt_replay import outside_repo, sha
from src.evaluation.metrics import exact_match, f1_score
from src.evaluation.qa_records import extract_answer

RUN_SCHEMA = "rag-poison-transfer.2wiki-rcd-component-ablation-new-qwen-qa/v1"
SUMMARY_SCHEMA = "rag-poison-transfer.2wiki-rcd-component-ablation-aggregate/v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checked_plan(path, pin):
    obj = require_json(path, pin)
    if (obj.get("schema") != PROMPT_SCHEMA or
        obj.get("status") != "PRIVATE_RETRIEVAL_PLAN_COMPLETE_NO_QA_INFERENCE" or
        obj.get("original_pins") != ORIGINAL_PINS or
        obj.get("qa_max_tokens") != 64 or
        obj.get("n_replayed_original_baseline_evidence_pairs") != 80):
        raise ValueError("Original RCD baseline comparison or evidence plan is not certified")
    rows = obj.get("entries")
    if not isinstance(rows, list) or len(rows) != 480:
        raise ValueError("Expected exactly 480 genuine new-model prompt records")
    identifiers = set()
    keys = set()
    cells = defaultdict(set)
    for row in rows:
        for key in ("id", "cell_id", "family", "intensity", "seed", "variant", "condition",
                    "query_id", "prompt", "prompt_sha256", "gold_answer", "target_answer",
                    "poison_doc_ids", "evidence_doc_ids", "poison_visible_to_generator",
                    "retrieval_elapsed_seconds", "inner_retrieval_calls"):
            if key not in row:
                raise ValueError(f"Missing ablation plan field: {key}")
        key = [row["cell_id"], row["variant"], row["query_id"], row["condition"]]
        expected = hashlib.sha256(canonical(key).encode()).hexdigest()[:24]
        if row["id"] != expected or expected in identifiers:
            raise ValueError("Duplicate or forged ablation prompt identity")
        if row["variant"] not in VARIANTS or row["condition"] not in ("clean", "poisoned"):
            raise ValueError("Unknown variant/condition")
        if hashlib.sha256(row["prompt"].encode()).hexdigest() != row["prompt_sha256"]:
            raise ValueError("Ablation prompt was altered")
        if type(row["inner_retrieval_calls"]) is not int or row["inner_retrieval_calls"] < 1:
            raise ValueError("Missing actual retrieval-call measurement")
        if row["condition"] == "clean" and row["poison_visible_to_generator"] is not False:
            raise ValueError("Clean evidence cannot be tagged poisoned")
        if (row["condition"] == "poisoned" and
            row["poison_visible_to_generator"] is not bool(
                set(row["evidence_doc_ids"]) & set(row["poison_doc_ids"])
            )):
            raise ValueError("Poison exposure differs from selected document IDs")
        if type(row["retrieval_elapsed_seconds"]) not in (int, float) or row["retrieval_elapsed_seconds"] < 0:
            raise ValueError("Invalid retrieval timing")
        identifiers.add(expected)
        keys.add((row["cell_id"], row["variant"], row["query_id"], row["condition"]))
        cells[(row["cell_id"], row["variant"])].add(row["query_id"])
    if len(cells) != 24 or any(len(v) != 10 for v in cells.values()) or len(keys) != 480:
        raise ValueError("Incomplete four-cell × six-variant × ten-question × two-condition design")
    for cellid, variant in cells:
        for qid in cells[(cellid, variant)]:
            for condition in ("clean", "poisoned"):
                if (cellid, variant, qid, condition) not in keys:
                    raise ValueError("Unpaired clean/poisoned Qwen request")
    return obj


def atomic_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix="writing-", suffix=".tmp", delete=False,
    ) as fh:
        json.dump(value, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
        tmp = fh.name
    os.replace(tmp, path)


def score_response(source, response, plan_pin, model_binding_sha):
    if not isinstance(response, dict) or response.get("schema") != RUN_SCHEMA:
        raise ValueError("Invalid recorded new-study Qwen response")
    if (response.get("id") != source["id"] or response.get("prompt_sha256") != source["prompt_sha256"] or
        response.get("prompt_plan_sha256") != plan_pin or
        response.get("model_binding_sha256") != model_binding_sha):
        raise ValueError("Stored Qwen observation not bound to exact planned input/model")
    answer = extract_answer(response["raw_response"])
    if answer != response.get("extracted_answer"):
        raise ValueError("Qwen raw response and answer extraction disagree")
    correct = int(bool(exact_match(answer, source["gold_answer"])))
    targeted = bool(exact_match(answer, source["target_answer"]))
    if (response["gold_em"] != correct or
        response["target_match"] is not targeted or
        response["gold_f1"] != f1_score(answer, source["gold_answer"])):
        raise ValueError("Qwen response scoring differs from stored answer")
    return correct, targeted


def run(plan_file, plan_sha256, original_protocol, qwen_model_snapshot, results_dir, execute):
    if not execute:
        raise ValueError("Physical model inference requires explicit --execute")
    plan = checked_plan(plan_file, plan_sha256)
    proto = require_json(original_protocol, ORIGINAL_PINS["protocol.json"])
    if proto.get("binding", {}).get("scope") != "heldout":
        raise ValueError("Wrong original model-protocol scope")
    from scripts.run_week9_protocol_poison_matrix import model_binding
    binding = model_binding(qwen_model_snapshot, proto["binding"]["model_identity"])
    if binding != proto["model"]:
        raise ValueError("Qwen model weight/tokenizer binding differs from frozen original")
    binding_sha = hashlib.sha256(canonical(binding).encode()).hexdigest()
    root = outside_repo(results_dir)
    if root.exists() and not root.is_dir():
        raise ValueError("New private results root must be a directory")
    root.mkdir(parents=True, exist_ok=True)
    entries_dir = root / "entries"
    intents_dir = root / "intents"
    entries_dir.mkdir(exist_ok=True)
    intents_dir.mkdir(exist_ok=True)
    marker = root / "run_manifest.json"
    manifest = {
        "schema": RUN_SCHEMA, "prompt_plan_sha256": plan_sha256,
        "original_protocol_sha256": ORIGINAL_PINS["protocol.json"],
        "model_binding_sha256": binding_sha,
        "qa_max_tokens": 64, "seed_each_request": 42,
        "decoding": "explicit greedy temp=0; separate exploratory experiment",
        "planned_logical_calls": 480,
    }
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Existing run manifest mismatches planned model/protocol")
    else:
        atomic_json(marker, manifest)

    pending = []
    completed = 0
    for row in plan["entries"]:
        result_file = entries_dir / (row["id"] + ".json")
        intent_file = intents_dir / (row["id"] + ".json")
        if result_file.exists():
            response = json.loads(result_file.read_text(encoding="utf-8"))
            score_response(row, response, plan_sha256, binding_sha)
            if not intent_file.is_file():
                raise ValueError("Completed Qwen call has no original intent journal")
            intent = json.loads(intent_file.read_text(encoding="utf-8"))
            if intent.get("prompt_sha256") != row["prompt_sha256"] or intent.get("id") != row["id"]:
                raise ValueError("Qwen journal does not match source item")
            completed += 1
            continue
        if intent_file.exists():
            raise ValueError(
                "Unresolved original inference intent with NO response; do not "
                "retry or delete this request automatically: " + row["id"]
            )
        pending.append(row)
    if pending:
        from mlx_lm.sample_utils import make_sampler
        from src.pipelines.generator import MLXGenerator
        qwen = MLXGenerator(model_name=str(Path(qwen_model_snapshot).expanduser().resolve()))
        original = qwen._generate_fn
        greedy = make_sampler(temp=0.0)
        qwen._generate_fn = lambda *a, **kw: original(*a, **kw, sampler=greedy)
        for row in pending:
            intent_file = intents_dir / (row["id"] + ".json")
            result_file = entries_dir / (row["id"] + ".json")
            atomic_json(intent_file, {
                "id": row["id"], "prompt_sha256": row["prompt_sha256"],
                "prompt_plan_sha256": plan_sha256,
                "model_binding_sha256": binding_sha,
                "stage": "new_Qwen_QA_inference",
                "qa_max_tokens": 64,
            })
            qwen.seed(42)
            raw = qwen.generate(row["prompt"], max_tokens=64)
            answer = extract_answer(raw.text)
            observation = {
                "schema": RUN_SCHEMA, "id": row["id"],
                "prompt_sha256": row["prompt_sha256"],
                "prompt_plan_sha256": plan_sha256,
                "model_binding_sha256": binding_sha,
                "raw_response": raw.text,
                "extracted_answer": answer,
                "gold_em": int(bool(exact_match(answer, row["gold_answer"]))),
                "gold_f1": f1_score(answer, row["gold_answer"]),
                "target_match": bool(exact_match(answer, row["target_answer"])),
                "generator_latency_seconds": raw.latency_seconds,
                "prompt_tokens": raw.prompt_tokens,
                "completion_tokens": raw.completion_tokens,
                "backend_prompt_sha256": (
                    hashlib.sha256(raw.backend_prompt.encode()).hexdigest()
                    if isinstance(raw.backend_prompt, str) else None
                ),
            }
            atomic_json(result_file, observation)
            completed += 1
    return {
        "status": "ABLATION_QWEN_CALLS_COMPLETE" if completed == 480 else "INCOMPLETE",
        "planned_calls": 480, "verified_completed_calls": completed,
        "results_dir": str(root),
    }


def aggregate(plan_file, plan_sha256, results_dir, output):
    plan = checked_plan(plan_file, plan_sha256)
    root = outside_repo(results_dir)
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != RUN_SCHEMA or manifest.get("prompt_plan_sha256") != plan_sha256:
        raise ValueError("Qwen results tree is not bound to the pinned ablation plan")
    if manifest.get("qa_max_tokens") != 64:
        raise ValueError("Only the pinned 64-token Qwen experiment is supported")
    result_files = {p.stem for p in (root / "entries").glob("*.json")}
    intent_files = {p.stem for p in (root / "intents").glob("*.json")}
    ids = {r["id"] for r in plan["entries"]}
    if result_files != ids or intent_files != ids or len(ids) != 480:
        raise ValueError("Missing/extra/unresolved Qwen generation records")
    accum = {}
    paired = defaultdict(dict)
    for row in plan["entries"]:
        obs = json.loads((root / "entries" / (row["id"] + ".json")).read_text(encoding="utf-8"))
        correct, targeted = score_response(row, obs, plan_sha256, manifest["model_binding_sha256"])
        key = (row["cell_id"], row["variant"])
        by_id = paired[key].setdefault(row["query_id"], {})
        if row["condition"] in by_id:
            raise ValueError("Duplicate clean/poison observation")
        by_id[row["condition"]] = {
            "gold_em": correct, "gold_f1": obs["gold_f1"],
            "targeted": int(targeted), "poison_visible": int(row["poison_visible_to_generator"]),
            "retrieval_seconds": row["retrieval_elapsed_seconds"],
            "generation_seconds": obs["generator_latency_seconds"],
            "retrieval_calls": row["inner_retrieval_calls"],
        }
    for key, cohort in sorted(paired.items()):
        if len(cohort) != 10 or any(set(c) != {"clean", "poisoned"} for c in cohort.values()):
            raise ValueError("Incomplete ten-question matched RCD ablation cohort")
        v = {
            "n_valid_selected_query_positions": 10,
            "n_clean_correct": sum(c["clean"]["gold_em"] for c in cohort.values()),
            "n_poisoned_correct": sum(c["poisoned"]["gold_em"] for c in cohort.values()),
            "n_target_matches": sum(c["poisoned"]["targeted"] for c in cohort.values()),
            "n_clean_target_matches": sum(c["clean"]["targeted"] for c in cohort.values()),
            "n_poison_visible": sum(c["poisoned"]["poison_visible"] for c in cohort.values()),
            "n_clean_correct_to_poisoned_wrong": sum(
                c["clean"]["gold_em"] and not c["poisoned"]["gold_em"]
                for c in cohort.values()
            ),
            "mean_clean_f1": sum(c["clean"]["gold_f1"] for c in cohort.values()) / 10,
            "mean_poisoned_f1": sum(c["poisoned"]["gold_f1"] for c in cohort.values()) / 10,
            "mean_retrieval_seconds": sum(
                x["retrieval_seconds"] for c in cohort.values() for x in c.values()
            ) / 20,
            "mean_generation_seconds": sum(
                x["generation_seconds"] for c in cohort.values() for x in c.values()
            ) / 20,
            "total_inner_retrieval_calls": sum(
                x["retrieval_calls"] for c in cohort.values() for x in c.values()
            ),
        }
        v["clean_em_rate"] = v["n_clean_correct"] / 10
        v["poisoned_em_rate"] = v["n_poisoned_correct"] / 10
        v["poisoned_target_match_rate"] = v["n_target_matches"] / 10
        v["poison_visibility_rate"] = v["n_poison_visible"] / 10
        accum["|".join(key)] = v

    # Paired, fixed-query bootstrap for *descriptive* ablation contrasts.
    intervals = {}
    for cellid in sorted({key[0] for key in paired}):
        baseline = paired[(cellid, "full_k3")]
        ids_in_cell = sorted(baseline)
        rng = random.Random(20261109)
        for variant in VARIANTS:
            if variant == "full_k3":
                continue
            alternative = paired[(cellid, variant)]
            if set(alternative) != set(ids_in_cell):
                raise ValueError("Ablation changed fixed query cohort")
            deltas = [
                baseline[q]["poisoned"]["targeted"] - alternative[q]["poisoned"]["targeted"]
                for q in ids_in_cell
            ]
            means = sorted(
                sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
                for _ in range(2000)
            )
            intervals[f"{cellid}|{variant}"] = {
                "baseline_minus_variant_target_match_pp": 100 * sum(deltas)/len(deltas),
                "nominal_95pct_cluster_bootstrap_pp": [
                    100 * means[49], 100 * means[1949]
                ],
                "unit": "question ID, n=10 selected valid queries",
                "bootstrap_replicates": 2000,
                "not_multiplicity_adjusted": True,
            }
    output = outside_repo(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Aggregate must be a new private output file")
    report = {
        "schema": SUMMARY_SCHEMA,
        "status": "ABLATION_RESULTS_AGGREGATED_EXPLORATORY",
        "source_prompt_plan_sha256": plan_sha256,
        "original_frozen_evidence_pins": ORIGINAL_PINS,
        "n_Qwen_observations": 480,
        "conditions": "4 family/intensity cells, one original seed, 10 valid query slots each",
        "model": "original frozen Qwen model binding, new exploratory execution with 64-token greedy cap",
        "groups": accum, "paired_nominal_intervals": intervals,
        "limitations": [
            "Valid-only post-hoc selected 40 query-stratum positions; no attempted-population ASR for these ablations.",
            "Repeated question IDs across strata are not independent samples.",
            "Poison exposure is not proof of causal poisoning; factual falsity is not independently certified.",
            "Negative/positive point differences need paired context and utility; do not cherry-pick favorable variants.",
            "No untouched held-out or broad Natural Questions/iterative-rag evidence.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": report["status"], "groups": len(accum),
            "paired_contrasts": len(intervals), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    r = sub.add_parser("run")
    r.add_argument("--prompt-plan", type=Path, required=True)
    r.add_argument("--prompt-plan-sha256", required=True)
    r.add_argument("--original-protocol", type=Path, required=True)
    r.add_argument("--qwen-model-snapshot", type=Path, required=True)
    r.add_argument("--output-dir", type=Path, required=True)
    r.add_argument("--execute", action="store_true")
    a = sub.add_parser("aggregate")
    a.add_argument("--prompt-plan", type=Path, required=True)
    a.add_argument("--prompt-plan-sha256", required=True)
    a.add_argument("--results-dir", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "run":
        result = run(args.prompt_plan, args.prompt_plan_sha256,
                     args.original_protocol, args.qwen_model_snapshot,
                     args.output_dir, args.execute)
    else:
        result = aggregate(args.prompt_plan, args.prompt_plan_sha256,
                           args.results_dir, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
