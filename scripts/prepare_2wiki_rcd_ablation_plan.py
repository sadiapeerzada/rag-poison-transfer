#!/usr/bin/env python3
"""Prepare a new, private, immutable RCD component-ablation study from the exact
restored frozen 2Wiki run. This *never runs retrieval or model inference*.

Only structural provenance and prospective variant definitions are produced.
The 40 selected query-stratum slots reuse the pinned, post-hoc valid-only Phi
plan, so resulting ablations must be labelled EXPLORATORY, not confirmatory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.second_model_prompt_replay import outside_repo, sha
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint

SCHEMA = "rag-poison-transfer.2wiki-rcd-component-ablations-preflight/v1"
ORIGINAL_PINS = {
    "protocol.json": "40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4",
    "execution/construction/construction.seal.json": "e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44",
    "execution/evaluation/evaluation.complete.json": "db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519",
    "execution/aggregate.json": "721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96",
}
PLAN_PIN = "9c47a64053c2d53bb016a2bad10503d906a9026e0b7092d55ddb0505bd3b199a"
FAMILIES = ("lexical_influential_token", "semantic_fluent_false_evidence")
ARMS = ("dense", "rcd")
CONDITIONS = ("clean", "poisoned")

# Exploratory design. The score-only no-agreement variant must be implemented
# separately; it is not interchangeable with changing the consistency weight.
VARIANTS = {
    "full_k3": {
        "top_k": 3, "rewrite_count": 3, "consistency_mode": "all",
        "consistency_weight": .45, "redundancy_weight": 0.,
        "conflict_weight": .10, "base_rank_weight": .45,
    },
    "no_rewrites_k3": {
        "top_k": 3, "rewrite_count": 0, "consistency_mode": "all",
        "consistency_weight": .45, "redundancy_weight": 0.,
        "conflict_weight": .10, "base_rank_weight": .45,
    },
    "no_agreement_k3": {
        "top_k": 3, "rewrite_count": 3, "consistency_mode": "rank_and_rewrite_stability_only",
        "consistency_weight": .45, "redundancy_weight": 0.,
        "conflict_weight": .10, "base_rank_weight": .45,
    },
    "no_conflict_k3": {
        "top_k": 3, "rewrite_count": 3, "consistency_mode": "all",
        "consistency_weight": .50, "redundancy_weight": 0.,
        "conflict_weight": 0., "base_rank_weight": .50,
    },
    "full_k1": {
        "top_k": 1, "rewrite_count": 3, "consistency_mode": "all",
        "consistency_weight": .45, "redundancy_weight": 0.,
        "conflict_weight": .10, "base_rank_weight": .45,
    },
    "full_k5": {
        "top_k": 5, "rewrite_count": 3, "consistency_mode": "all",
        "consistency_weight": .45, "redundancy_weight": 0.,
        "conflict_weight": .10, "base_rank_weight": .45,
    },
}


def require_json(path, expected_sha):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing or symlinked evidence: {path}")
    if sha(path) != expected_sha:
        raise ValueError(f"Evidence SHA-256 mismatch: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def complete_stage(stage_root, manifest, *, marker):
    stage_root = Path(stage_root)
    if not stage_root.is_dir() or stage_root.is_symlink():
        raise ValueError(f"Missing original sealed stage {stage_root.name}")
    declared = manifest.get("files_sha256")
    if not isinstance(declared, dict) or not declared:
        raise ValueError("Incomplete sealed stage file inventory")
    actual = {}
    for path in sorted(stage_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink in original sealed stage")
        if path.is_file() and path.name != marker:
            actual[path.relative_to(stage_root).as_posix()] = sha(path)
    if actual != declared:
        missing = len(declared.keys() - actual.keys())
        extra = len(actual.keys() - declared.keys())
        changed = sum(actual[k] != declared[k] for k in declared.keys() & actual.keys())
        raise ValueError(f"Sealed stage mismatch: missing={missing}, extra={extra}, changed={changed}")
    return len(actual)


def validate_variant_matrix(variants=VARIANTS):
    if set(variants) != {"full_k3", "no_rewrites_k3", "no_agreement_k3",
                         "no_conflict_k3", "full_k1", "full_k5"}:
        raise ValueError("Required RCD ablation contrast missing or extra")
    for name, cfg in variants.items():
        expected = {"top_k", "rewrite_count", "consistency_mode",
                    "consistency_weight", "redundancy_weight",
                    "conflict_weight", "base_rank_weight"}
        if set(cfg) != expected:
            raise ValueError(f"Incomplete variant definition: {name}")
        if cfg["top_k"] not in (1, 3, 5) or cfg["rewrite_count"] not in (0, 3):
            raise ValueError(f"Out-of-protocol top-k/rewrite: {name}")
        if cfg["consistency_mode"] not in ("all", "rank_and_rewrite_stability_only"):
            raise ValueError(f"Unknown signal projection: {name}")
        if abs(sum(cfg[k] for k in ("consistency_weight", "redundancy_weight",
                                  "conflict_weight", "base_rank_weight")) - 1.) > 1e-9:
            raise ValueError(f"RCD weights must sum to one: {name}")
        if any(cfg[k] < 0 for k in ("consistency_weight", "redundancy_weight",
                                  "conflict_weight", "base_rank_weight")):
            raise ValueError("Negative RCD weight")
    if VARIANTS["full_k3"]["consistency_mode"] != "all":
        raise ValueError("Full baseline cannot remove agreement")
    return True


def prepare(restore_root, plan_file, plan_sha256, output, local_data=None, full_stage_hashes=True):
    validate_variant_matrix()
    restore_root = Path(restore_root).expanduser().resolve(strict=True)
    output = outside_repo(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Use a NEW private plan file in an existing directory")
    if plan_sha256 != PLAN_PIN:
        raise ValueError("Unexpected input selection plan digest; this study is anchored to the already reviewed plan")
    original = {}
    for rel, expected in ORIGINAL_PINS.items():
        original[rel] = require_json(restore_root / rel, expected)
    proto = original["protocol.json"]
    seal = original["execution/construction/construction.seal.json"]
    complete = original["execution/evaluation/evaluation.complete.json"]
    if proto.get("binding", {}).get("scope") != "heldout":
        raise ValueError("Original protocol is not the 2Wiki held-out study")
    if proto.get("replication", {}).get("schema") != "rag-poison-transfer.2wiki-replication-inputs/v2":
        raise ValueError("Original protocol does not use a local pinned 2Wiki input snapshot")
    if seal.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"] or complete.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"]:
        raise ValueError("Frozen stage/protocol binding differs")
    if seal.get("scope") != "heldout" or complete.get("scope") != "heldout":
        raise ValueError("Stage scope mismatches held-out original")
    if complete.get("construction_seal_sha256") != ORIGINAL_PINS["execution/construction/construction.seal.json"]:
        raise ValueError("Original evaluation not bound to frozen construction seal")

    source = Path(local_data or proto["replication"]["local_data"]).expanduser()
    data = require_json(source, proto["replication"]["local_data_sha256"])
    if set(data) < {"corpus", "queries"}:
        raise ValueError("Pinned original local data missing corpus/queries")
    if len(data["queries"]) != 300 or len({q["query_id"] for q in data["queries"]}) != 300:
        raise ValueError("Expected the original 300 frozen 2Wiki queries")
    plan_binding = seal.get("plan", {})
    if (plan_binding.get("clean_corpus_fingerprint") != corpus_fingerprint(data["corpus"]) or
        plan_binding.get("query_set_fingerprint") != query_set_fingerprint(data["queries"])):
        raise ValueError("Original local query/corpus fingerprints differ from sealed construction plan")
    if proto["binding"]["query_ids"] != [q["query_id"] for q in data["queries"]]:
        raise ValueError("Original frozen cohort IDs/order changed")

    check_counts = None
    if full_stage_hashes:
        construction_count = complete_stage(
            restore_root / "execution" / "construction", seal,
            marker="construction.seal.json",
        )
        evaluation_count = complete_stage(
            restore_root / "execution" / "evaluation", complete,
            marker="evaluation.complete.json",
        )
        check_counts = {"construction_file_count": construction_count,
                        "evaluation_file_count": evaluation_count}

    source_plan = require_json(plan_file, plan_sha256)
    if (source_plan.get("schema") != "rag-poison-transfer.private-fixed-evidence-second-model-plan/v1" or
        source_plan.get("evaluation_completion_sha256") != ORIGINAL_PINS["execution/evaluation/evaluation.complete.json"]):
        raise ValueError("Selected question plan not bound to original frozen evaluation")
    if len(source_plan.get("entries", [])) != 160:
        raise ValueError("Expected the same 160 recorded Phi/Qwen selected observations")
    seen = set()
    selected = {}
    by_qid = {q["query_id"]: q for q in data["queries"]}
    croot = restore_root / "execution" / "construction"
    eroot = restore_root / "execution" / "evaluation"
    for item in source_plan["entries"]:
        key = (item["family"], item["intensity"], item["seed"],
               item["query_id"], item["arm"], item["condition"])
        if key in seen or item["arm"] not in ARMS or item["condition"] not in CONDITIONS:
            raise ValueError("Duplicate or invalid original selected comparison item")
        seen.add(key)
        if item["family"] not in FAMILIES or item["intensity"] not in (1, 3) or item["seed"] != 42:
            raise ValueError("Unexpected attack selection outside bounded 2Wiki study")
        cid = f"{item['family']}.intensity-{item['intensity']}.seed-{item['seed']}"
        selected.setdefault(cid, set()).add(item["query_id"])
        q = by_qid.get(item["query_id"])
        if q is None or q["gold_answer"] != item["gold_answer"]:
            raise ValueError("Frozen question/gold differs from selected plan")
    if len(seen) != 160 or len(selected) != 4 or any(len(qids) != 10 for qids in selected.values()):
        raise ValueError("Expected 4 source cells with 10 matched valid selected questions each")

    cases = {}
    for cid, ids in sorted(selected.items()):
        cell_rel = f"{cid}/construction.json"
        entry = seal.get("cells", {}).get(cid)
        if not isinstance(entry, dict) or entry.get("path") != cell_rel:
            raise ValueError("Original construction cell not sealed")
        cell = require_json(croot / cell_rel, entry["sha256"])
        records = {record["query_id"]: record for record in cell["records"]}
        if set(records) != set(by_qid):
            raise ValueError("Frozen construction cell does not contain original query cohort")
        eval_pin = complete.get("rows_sha256", {}).get(cid)
        if eval_pin is None:
            raise ValueError("Selected cell missing from original evaluation manifest")
        rows = require_json(eroot / cid / "rows.json", eval_pin)
        obs = {(r["query_id"], r["pipeline"]): r for r in rows}
        if len(obs) != 600:
            raise ValueError("Original paired evaluation must preserve 300 questions × 2 arms")
        for qid in ids:
            if records[qid]["status"] != "valid_construction" or len(records[qid]["documents"]) != cell["intensity"]:
                raise ValueError("Selected query lacks exact original valid poison documents")
            for arm in ARMS:
                r = obs.get((qid, arm))
                if (r is None or r["construction_status"] != "valid_construction" or
                    r["measurement"] is None or
                    r["measurement"]["poison_target_answer"] != records[qid]["target_answer"]):
                    raise ValueError("Selected original Qwen QA condition no longer agrees with construction")
        cases[cid] = {
            "family": cell["family"], "intensity": cell["intensity"],
            "seed": cell["seed"], "query_ids": sorted(ids),
            "construction_cell_sha256": entry["sha256"],
            "evaluation_cell_sha256": eval_pin,
        }

    selection = {
        "schema": SCHEMA,
        "status": "PRIVATE_ABLATION_PLAN_PREPARED_NO_INFERENCE",
        "study_design": "post-hoc exploratory, valid-only, selected after original held-out results",
        "original_frozen_pins": ORIGINAL_PINS,
        "private_local_data_sha256": proto["replication"]["local_data_sha256"],
        "private_qwen_phi_plan_sha256": plan_sha256,
        "query_stratum_slots": sum(len(case["query_ids"]) for case in cases.values()),
        "distinct_query_ids": len(set.union(*(set(case["query_ids"]) for case in cases.values()))),
        "cells": cases,
        "variants": VARIANTS,
        "candidate_k": 10,
        "generator_qa_max_tokens": 64,
        "generator_sampling": "explicit greedy; original pinned Qwen model",
        "expected_logical_clean_and_poison_QA_calls_without_cache": 2 * sum(len(case["query_ids"]) for case in cases.values()) * len(VARIANTS),
        "source_stage_inventory_validation": check_counts,
        "conditions": list(CONDITIONS),
        "limitations": [
            "This is a plan, NOT an executed ablation.",
            "The original frozen results and case population remain unchanged.",
            "The selected cases are valid-only and already examined; exploratory outcomes only.",
            "No-rewrite requires a newly executed retriever; removing agreement requires true per-signal projection.",
            "Different top-k changes actual generator evidence, requiring new generation.",
            "No source-independent semantic falsehood verification or unseen attack generalization is claimed.",
            "Store per-question logs privately and publish aggregate summaries only after source/license review.",
        ],
    }
    output.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": selection["status"], "new_plan_sha256": sha(output),
            "output": str(output), "planned_cells": len(cases),
            "planned_variants": len(VARIANTS),
            "planned_qa_calls": selection["expected_logical_clean_and_poison_QA_calls_without_cache"],
            "selected_query_slots": selection["query_stratum_slots"],
            "original_stage_files_checked": check_counts}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--restored-root", type=Path, required=True,
                   help="Verified restored folder with protocol.json and execution/*")
    p.add_argument("--local-data", type=Path,
                   help="Optional original pinned 2Wiki local_data path override")
    p.add_argument("--phi-plan", type=Path, required=True)
    p.add_argument("--phi-plan-sha256", default=PLAN_PIN)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--no-full-stage-hash-audit", action="store_true",
                   help="Only use after existing full backup audit; weaker than full stage recheck")
    a = p.parse_args()
    print(json.dumps(prepare(a.restored_root, a.phi_plan, a.phi_plan_sha256,
                             a.output, a.local_data, not a.no_full_stage_hash_audit), indent=2))


if __name__ == "__main__":
    main()
