#!/usr/bin/env python3
"""Evaluate *real recorded* 2Wiki RCD poison-identity features without inference.

Requires the pinned original frozen 2Wiki construction and the existing 480-row
ablation retrieval plan. Reconstructs *global* injected-document identities for
each of four original poisoned corpora, rather than falsely labelling only
the current query's poison IDs. Uses full_k3 only, deduplicates original query
IDs across cells, and evaluates a deterministic question-disjoint split.

The source population is post-hoc selected/valid-only, just 36 unique questions,
so this is EXPERIMENTAL EXPLORATORY evidence, not a prospective held-out or
independent-document generalization result. Never publishes raw questions,
document IDs, model outputs, private source documents or case-level scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.audit_2wiki_rcd_ablations_offline import (
    AGG_NAME, AGG_SHA, ROOT, RUN_NAME, digest, guarded_path, load_json, locate_plan,
)
from scripts.prepare_2wiki_rcd_ablation_plan import ORIGINAL_PINS, require_json
from scripts.run_2wiki_rcd_ablation_qa import RUN_SCHEMA, checked_plan
from src.evaluation.poison_detection import evaluate

SCHEMA = "rag-poison-transfer.pinned-2wiki-ablation-document-detection-offline/v1"
SPLIT_VERSION = "unique-original-question-sha256-20261109-v1"
MAX_QUESTIONS = 36



def locate_restored_original(research_root: Path, *, downloads=None, max_dirs=25000):
    """Locate a same-machine restored original root using its pinned protocol.

    Scans directory names and only hashes protocol.json candidates. Does not
    enter original 37k-file construction/evaluation trees or model caches.
    """
    roots = (Path(research_root), Path(downloads or Path.home() / "Downloads"))
    excluded = {".git", ".venv", "venv", "node_modules", "execution",
                "construction", "evaluation", "entries", "intents",
                "calls", "responses", ".cache", "rag-poison-transfer"}
    tested = 0
    for root in roots:
        if not root.is_dir():
            continue
        for current, dirs, names in os.walk(root, followlinks=False):
            tested += 1
            if tested > max_dirs:
                raise ValueError("Restore search directory budget exceeded; pass --restored-root explicitly")
            relative_depth = len(Path(current).relative_to(root).parts)
            dirs[:] = sorted(d for d in dirs
                             if d not in excluded and relative_depth < 6
                             and not (Path(current) / d).is_symlink())
            if "protocol.json" not in names:
                continue
            candidate = Path(current)
            p = candidate / "protocol.json"
            if (p.is_symlink() or not
                (candidate / "execution/construction/construction.seal.json").is_file() or not
                (candidate / "execution/evaluation/evaluation.complete.json").is_file()):
                continue
            if digest(p) == ORIGINAL_PINS["protocol.json"]:
                return candidate.resolve(strict=True)
    raise ValueError("Pinned original 2Wiki restored root not found under Documents or Downloads; pass --restored-root PATH")


def global_injection_sets(original_root: Path, cell_ids: set[str], *, local_data=None):
    """Derive all injected IDs from each original sealed 300-question cell.

    This is *not* the union of the selected 10 query-local injections. It uses
    every mechanically valid original construction in each cell.
    """
    root = Path(original_root).expanduser().resolve(strict=True)
    proto = require_json(root / "protocol.json", ORIGINAL_PINS["protocol.json"])
    seal = require_json(root / "execution/construction/construction.seal.json",
                        ORIGINAL_PINS["execution/construction/construction.seal.json"])
    complete = require_json(root / "execution/evaluation/evaluation.complete.json",
                            ORIGINAL_PINS["execution/evaluation/evaluation.complete.json"])
    if (proto.get("binding", {}).get("scope") != "heldout" or
        seal.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"] or
        complete.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"] or
        complete.get("construction_seal_sha256") !=
            ORIGINAL_PINS["execution/construction/construction.seal.json"]):
        raise ValueError("Original sealed protocol, construction and evaluation disagree")
    path = Path(local_data or proto["replication"]["local_data"]).expanduser()
    data = require_json(path, proto["replication"]["local_data_sha256"])
    if len(data.get("queries", [])) != 300 or len({q["query_id"] for q in data["queries"]}) != 300:
        raise ValueError("Original frozen 300-question cohort unavailable")
    base_ids = {d["doc_id"] for d in data["corpus"]}
    if len(base_ids) != len(data["corpus"]):
        raise ValueError("Duplicate original clean corpus document IDs")
    query_ids = {q["query_id"] for q in data["queries"]}
    ids_by_cell, query_documents = {}, {}
    for cell_id in sorted(cell_ids):
        metadata = seal["cells"].get(cell_id)
        if not metadata or metadata.get("path") != f"{cell_id}/construction.json":
            raise ValueError("Unknown sealed original construction cell")
        cell = require_json(
            root / "execution/construction" / metadata["path"], metadata["sha256"]
        )
        if complete["rows_sha256"].get(cell_id) is None:
            raise ValueError("No sealed original evaluation for detector source cell")
        rows = cell.get("records", [])
        if len(rows) != 300 or {r["query_id"] for r in rows} != query_ids:
            raise ValueError("Original 300-question source construction population differs")
        global_ids, query_map = set(), {}
        for row in rows:
            valid = row["status"] == "valid_construction"
            docs = row.get("documents", [])
            if not isinstance(docs, list):
                raise ValueError("Invalid original poison document list")
            # The frozen replay excludes *every* invalid construction, even
            # when its source record contains partial, non-injected documents.
            local_ids = [doc["doc_id"] for doc in docs] if valid else []
            if len(local_ids) != len(set(local_ids)):
                raise ValueError("Repeated injected document ID within one query")
            if valid:
                if len(local_ids) != cell["intensity"]:
                    raise ValueError("Inconsistent poison intensity for valid construction")
                if set(local_ids) & (base_ids | global_ids):
                    raise ValueError("Injected document ID collided with clean or existing poison")
                global_ids.update(local_ids)
            query_map[row["query_id"]] = set(local_ids)
        if not global_ids:
            raise ValueError("Cell has no authentic injected poison documents")
        ids_by_cell[cell_id] = global_ids
        query_documents[cell_id] = query_map
    return ids_by_cell, query_documents, base_ids


def unique_full_k3(plan: dict):
    """One original question is ONE independent cluster across selected cells."""
    entries = [r for r in plan["entries"]
               if r["variant"] == "full_k3" and r["condition"] == "poisoned"]
    if len(entries) != 40:
        raise ValueError("Expected exactly 40 poisoned full_k3 selected positions")
    unique = {}
    for row in sorted(entries, key=lambda r: (r["query_id"], r["cell_id"])):
        unique.setdefault(row["query_id"], row)
    if len(unique) != MAX_QUESTIONS:
        raise ValueError("Unexpected distinct-question census for post-hoc ablation")
    return unique


def document_identity_record(source: dict, global_ids: set[str],
                             per_query_ids: set[str], base_ids: set[str]) -> dict:
    if (set(source["poison_doc_ids"]) != per_query_ids or
        not per_query_ids.issubset(global_ids)):
        raise ValueError("Current query's poison identity disagrees with sealed source")
    signals = source.get("candidate_consistency_features")
    scores = source.get("candidate_scores")
    if not isinstance(signals, dict) or not isinstance(scores, dict) or not scores:
        raise ValueError("Missing actual candidate consistency and scoring diagnostics")
    score_ids = set(scores)
    if score_ids != set(signals):
        raise ValueError("Candidate feature/score identities differ")
    if not score_ids.issubset(base_ids | global_ids):
        raise ValueError("Candidate document not in original clean+poison corpus")
    conflict = {}
    for doc_id, details in scores.items():
        if not isinstance(details, dict) or "conflict" not in details:
            raise ValueError("Missing original recorded RCD conflict component")
        # src.defenses.rcd.scoring.score_documents stores *raw* conflict in this
        # named field, not the weighted negative contribution to final_score.
        conflict[doc_id] = details["conflict"]
    return {
        "query_id": source["query_id"],
        "condition": "poisoned",
        "known_global_poison_doc_ids": sorted(global_ids),
        "diagnostics": {
            "consistency_signals": signals,
            "conflict_scores": conflict,
            "scores": scores,
        },
    }


def split_by_question(selected: dict, *, dev_share=0.5):
    if type(dev_share) not in (float, int) or not 0.2 <= dev_share <= 0.8:
        raise ValueError("Choose development proportion between 0.2 and 0.8")
    ordered = sorted(selected, key=lambda q: hashlib.sha256(
        (SPLIT_VERSION + "|" + q).encode("utf-8")
    ).hexdigest())
    n_dev = int(len(ordered) * dev_share)
    if n_dev < 2 or len(ordered) - n_dev < 2:
        raise ValueError("Need at least two questions per cohort")
    return ordered[:n_dev], ordered[n_dev:]


def verify_ablation_sources(research_root: Path, *, plan_path=None):
    """Identify exact original private 480-plan from the already audited run."""
    root = research_root.expanduser().resolve(strict=True)
    run_dir = guarded_path(root / "nov09-research-gates" / RUN_NAME, root)
    agg_path = guarded_path(root / "nov09-research-gates" / AGG_NAME, root)
    if digest(agg_path) != AGG_SHA:
        raise ValueError("Original Qwen 480-observation ablation aggregate hash differs")
    agg = load_json(agg_path)
    manifest = load_json(run_dir / "run_manifest.json")
    if (manifest.get("schema") != RUN_SCHEMA or
        manifest.get("planned_logical_calls") != 480 or
        agg.get("n_Qwen_observations") != 480 or
        manifest.get("prompt_plan_sha256") != agg.get("source_prompt_plan_sha256")):
        raise ValueError("Saved 480-response run is not bound to original 480-plan")
    pin = manifest["prompt_plan_sha256"]
    plan_file = locate_plan(root, run_dir, pin, plan_path)
    plan = checked_plan(plan_file, pin)
    return plan, pin, manifest, agg


def run(research_root: Path, original_root: Path, output: Path,
        *, plan_path=None, local_data=None, allow_shared_documents=False,
        bootstrap_replicates=2000):
    research_root = Path(research_root).expanduser().resolve(strict=True)
    out = guarded_path(output, research_root, must_exist=False)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Use a NEW private detector report path in an existing directory")
    plan, pin, manifest, agg = verify_ablation_sources(
        research_root, plan_path=plan_path
    )
    selected = unique_full_k3(plan)
    cell_ids = {row["cell_id"] for row in selected.values()}
    if len(cell_ids) != 4:
        raise ValueError("Deduplicated cohort lacks all original four cells")
    globals_by_cell, per_query, clean_ids = global_injection_sets(
        original_root, cell_ids, local_data=local_data
    )
    dev_qids, test_qids = split_by_question(selected)
    rows = {
        qid: document_identity_record(
            selected[qid],
            globals_by_cell[selected[qid]["cell_id"]],
            per_query[selected[qid]["cell_id"]][qid],
            clean_ids,
        )
        for qid in selected
    }
    analysis = evaluate(
        [rows[q] for q in dev_qids],
        [rows[q] for q in test_qids],
        forbid_shared_documents=not allow_shared_documents,
        bootstrap_replicates=bootstrap_replicates,
    )
    report = {
        "schema": SCHEMA,
        "status": "REAL_PINNED_2WIKI_EXPLORATORY_POISON_IDENTITY_DETECTION",
        "detector_output": analysis,
        "source": {
            "original_2wiki_protocol_sha256": ORIGINAL_PINS["protocol.json"],
            "original_2wiki_construction_seal_sha256":
                ORIGINAL_PINS["execution/construction/construction.seal.json"],
            "original_2wiki_evaluation_complete_sha256":
                ORIGINAL_PINS["execution/evaluation/evaluation.complete.json"],
            "original_480_qa_aggregate_sha256": AGG_SHA,
            "original_480_retrieval_prompt_plan_sha256": pin,
            "original_run_manifest_sha256": digest(
                guarded_path(research_root / "nov09-research-gates" / RUN_NAME /
                             "run_manifest.json", research_root)
            ),
            "derived_candidate_signal_provenance":
                "Same saved poisoned full_k3 retrieval plan, verified sealed original 2Wiki cells",
            "global_labels_from": "ALL valid injected documents in each 300-query sealed original cell",
        },
        "selection": {
            "source_full_k3_poisoned_positions": 40,
            "unique_original_questions": len(selected),
            "questions_dropped_to_avoid_cross_cell_duplicate_clusters": 40 - len(selected),
            "split_version": SPLIT_VERSION,
            "dev_questions": len(dev_qids),
            "test_questions": len(test_qids),
            "disjoint_original_question_ids": True,
            "allow_shared_candidate_doc_ids": allow_shared_documents,
            "full_k3_only": True,
        },
        "limitations": [
            "Exploratory analysis of prior outcome-selected mechanically valid queries, not a prospective independent test.",
            "Only 36 original unique questions; one deterministically chosen cell per repeated question.",
            "Dev/test use same source dataset and retrieval model; document candidate overlap is reported and may be permitted only explicitly.",
            "Injected poison-document identity is known from sealed construction; its factual falsity was not certified.",
            "Candidate-only AUROC/AUPRC exclude global poison documents not seen in candidate score dictionaries.",
            "Dev threshold selection and repeated test metrics are not full model selection/validation or population generalization.",
            "The original 480 Qwen responses were audited previously; this analysis reuses recorded retrieval diagnostics, not model inference.",
        ],
    }
    with out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return {
        "status": report["status"],
        "distinct_questions": len(selected),
        "n_dev_questions": len(dev_qids),
        "n_test_questions": len(test_qids),
        "candidate_poison_prevalence_test": analysis["test"]["positive_prevalence"],
        "auroc": analysis["test"]["auroc"],
        "auprc": analysis["test"]["average_precision"],
        "f1_at_frozen_dev_threshold": analysis["test"]["at_threshold"]["f1"],
        "false_positive_rate": analysis["test"]["at_threshold"]["false_positive_rate"],
        "query_cluster_nominal_ci95": analysis["test_query_cluster_bootstrap_ci95"],
        "shared_candidate_documents_between_splits":
            analysis["n_shared_candidate_document_ids_across_cohorts"],
        "output_private": str(out),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research-root", type=Path, default=ROOT)
    p.add_argument("--restored-root", type=Path,
                   help="Original frozen 2Wiki root; automatically discovered from pinned protocol if omitted")
    p.add_argument("--local-data", type=Path, help="Override original pinned input snapshot path")
    p.add_argument("--plan", type=Path, help="Optional original 480-item retrieval plan; SHA verified")
    p.add_argument("--out", type=Path, required=True, help="NEW private aggregate-only JSON path")
    p.add_argument("--allow-shared-document-ids", action="store_true",
                   help="Exploratory same-corpus test: disclose overlapping candidate IDs; not independent-document holdout")
    p.add_argument("--bootstrap-replicates", type=int, default=2000)
    a = p.parse_args()
    original_root = a.restored_root or locate_restored_original(a.research_root)
    print(json.dumps(run(
        a.research_root, original_root, a.out,
        plan_path=a.plan, local_data=a.local_data,
        allow_shared_documents=a.allow_shared_document_ids,
        bootstrap_replicates=a.bootstrap_replicates,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
