#!/usr/bin/env python3
"""Prepare label-conditioned NQ targets and a real lexical poison corpus.

Requires the exact frozen Natural Questions 50/300 cohort from PR #138.
Runs NO Qwen inference. Never changes original benchmark or gold labels.
Targets are non-gold, answer-type-approximate proposals, NOT independently
source-certified false claims. Raw targets/poison paragraphs remain private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.nq_singlehop_v1_freeze import digest, json_load, private, verify
from src.attacks.base import poison_doc_id
from src.attacks.injection import validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.evaluation.metrics import exact_match
from src.experiments.protocol import (
    corpus_fingerprint, query_set_fingerprint, poison_instances_fingerprint,
)

TARGET_SCHEMA = "rag-poison-transfer.nq-stage3-targets/v1"
LEXICAL_SCHEMA = "rag-poison-transfer.nq-stage3-lexical-sealed-construction/v1"
DEFAULT_TARGET_SEED = 20261109


def _load_source(cohort_dir, cohort_sha):
    root = private(cohort_dir)
    if verify(root, cohort_sha)["status"] != "PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY":
        raise ValueError("The NQ cohort did not pass sealed data verification")
    dev_file, test_file = root / "dev_train.json", root / "evaluation_validation.json"
    return (json_load(dev_file), json_load(test_file),
            {"dev_file_sha256": digest(dev_file), "eval_file_sha256": digest(test_file)})


def _new_private(path):
    out = private(path)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Output must be a new private file with an existing parent")
    return out


def _derive_seed(seed, qid):
    return int.from_bytes(
        hashlib.sha256(f"nq-stage3-non-gold-target/v1|{seed}|{qid}".encode()).digest()[:8],
        byteorder="big",
    )


def prepare_targets(cohort_dir, cohort_sha, output, *, seed=DEFAULT_TARGET_SEED):
    if type(seed) is not int or seed < 0:
        raise ValueError("Target-selection seed must be a nonnegative integer")
    out = _new_private(output)
    dev, evaluation, source_sha = _load_source(cohort_dir, cohort_sha)
    if len(dev["queries"]) < 2:
        raise ValueError("At least two source development gold labels are required")
    chooser = LexicalInfluentialTokenAttack()
    frozen = []
    for q in evaluation["queries"]:
        random_state = random.Random(_derive_seed(seed, q["query_id"]))
        try:
            target = chooser.pick_cross_query_target_answer(q, dev["queries"], random_state)
        except ValueError as exc:
            raise ValueError(f"No compatible non-gold target for query ID {q['query_id']}") from exc
        if not isinstance(target, str) or not target.strip() or exact_match(target, q["gold_answer"]) == 1.:
            raise ValueError("Target nomination did not exclude normalized gold label")
        frozen.append({"query_id": q["query_id"], "target_answer": target})
    if len(frozen) != len(evaluation["queries"]) or len({r["query_id"] for r in frozen}) != len(frozen):
        raise ValueError("Missing or duplicate target assignments")
    result = {
        "schema": TARGET_SCHEMA,
        "status": "PRIVATE_NQ_NON_GOLD_TARGETS_FROZEN_NO_INFERENCE",
        "n_queries": len(frozen),
        "cohort_manifest_sha256": cohort_sha,
        "source_files_sha256": source_sha,
        "clean_query_fingerprint": query_set_fingerprint(evaluation["queries"]),
        "clean_corpus_fingerprint": corpus_fingerprint(evaluation["corpus"]),
        "seed": seed,
        "target_method": "cross-query-development-answer-same-coarse-type-preferred/v1",
        "selected_only_from_development_gold_answers": True,
        "gold_alias_set_completeness_certified": False,
        "independent_source_factuality_certified": False,
        "assignments_private": frozen,
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": result["status"], "n_queries": len(frozen),
            "targets_sha256": digest(out), "output_private": str(out)}


def _load_targets(path, pinned_sha, cohort_sha, evaluation, source_sha):
    p = private(path)
    if digest(p) != pinned_sha:
        raise ValueError("Private target manifest SHA mismatch")
    result = json_load(p)
    if (result.get("schema") != TARGET_SCHEMA
        or result.get("status") != "PRIVATE_NQ_NON_GOLD_TARGETS_FROZEN_NO_INFERENCE"
        or result.get("cohort_manifest_sha256") != cohort_sha
        or result.get("source_files_sha256") != source_sha
        or result.get("clean_query_fingerprint") != query_set_fingerprint(evaluation["queries"])
        or result.get("clean_corpus_fingerprint") != corpus_fingerprint(evaluation["corpus"])):
        raise ValueError("Targets belong to a different frozen NQ corpus or protocol")
    rows = result.get("assignments_private")
    if not isinstance(rows, list) or len(rows) != len(evaluation["queries"]):
        raise ValueError("Incomplete target cohort")
    mapping = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"query_id", "target_answer"}:
            raise ValueError("Malformed target assignment")
        qid, target = row["query_id"], row["target_answer"]
        if qid in mapping or not isinstance(target, str) or not target.strip():
            raise ValueError("Duplicate/empty target")
        mapping[qid] = target
    if set(mapping) != {q["query_id"] for q in evaluation["queries"]}:
        raise ValueError("Target IDs do not match the frozen question cohort")
    for q in evaluation["queries"]:
        if exact_match(mapping[q["query_id"]], q["gold_answer"]) == 1.:
            raise ValueError("Target is identical to normalized gold")
    return mapping


def construct_lexical(cohort_dir, cohort_sha, targets_path, targets_sha, output,
                      *, intensity=1):
    if type(intensity) is not int or intensity not in (1, 3):
        raise ValueError("Only separately specified intensity 1 and 3 are allowed")
    out = _new_private(output)
    _, evaluation, source_sha = _load_source(cohort_dir, cohort_sha)
    mapping = _load_targets(targets_path, targets_sha, cohort_sha, evaluation, source_sha)
    attack = LexicalInfluentialTokenAttack(repeat_factor=4)
    new_docs = []
    poisoned_queries = []
    ids = {doc["doc_id"] for doc in evaluation["corpus"]}
    for q in evaluation["queries"]:
        target = mapping[q["query_id"]]
        rng = random.Random(_derive_seed(20261109, q["query_id"]))
        additions = []
        for index in range(intensity):
            document = attack.generate(q, evaluation["queries"], rng,
                                       poison_index=index, target_answer=target)
            if document.doc_id in ids:
                raise ValueError("Poison document ID collision")
            ids.add(document.doc_id)
            additions.append(document.doc_id)
            new_docs.append({"doc_id": document.doc_id, "text": document.text})
        enriched = dict(q)
        enriched["poison_doc_ids"] = additions
        enriched["poison_target_answer"] = target
        enriched["attack_family"] = attack.name
        poisoned_queries.append(enriched)
    poisoned = {
        "corpus": [*evaluation["corpus"], *new_docs],
        "queries": poisoned_queries,
    }
    validation = validate_poisoned_dataset(
        evaluation, poisoned, expected_n_poison=intensity, expected_poison_rate=1.0,
    )
    if not validation["valid"]:
        raise ValueError("NQ lexical corpus failed ground-truth integrity validation")
    fingerprint = poison_instances_fingerprint(evaluation, poisoned)
    result = {
        "schema": LEXICAL_SCHEMA,
        "status": "PRIVATE_NQ_LEXICAL_CONSTRUCTION_SEALED_NO_QA_INFERENCE",
        "cohort_manifest_sha256": cohort_sha,
        "target_manifest_sha256": targets_sha,
        "source_files_sha256": source_sha,
        "attack_family": attack.name,
        "intensity": intensity,
        "n_attempted": len(evaluation["queries"]),
        "n_valid_mechanical": len(poisoned_queries),
        "n_poison_documents": len(new_docs),
        "clean_query_fingerprint": query_set_fingerprint(evaluation["queries"]),
        "clean_corpus_fingerprint": corpus_fingerprint(evaluation["corpus"]),
        "poison_instance_fingerprint": fingerprint,
        "validation_checks": validation["checks"],
        "independent_semantic_factuality_certified": False,
        "poison_documents_private": new_docs,
        "question_poison_associations_private": [
            {"query_id": q["query_id"], "poison_doc_ids": q["poison_doc_ids"],
             "target_answer": q["poison_target_answer"]} for q in poisoned_queries
        ],
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": result["status"], "n_queries": len(poisoned_queries),
            "n_poison_documents": len(new_docs), "poison_instance_fingerprint": fingerprint,
            "construction_sha256": digest(out), "output_private": str(out)}


def verify_lexical(cohort_dir, cohort_sha, targets_path, targets_sha, construction_path, construction_sha):
    _, evaluation, source_sha = _load_source(cohort_dir, cohort_sha)
    mapping = _load_targets(targets_path, targets_sha, cohort_sha, evaluation, source_sha)
    path = private(construction_path)
    if digest(path) != construction_sha:
        raise ValueError("NQ lexical construction digest mismatch")
    sealed = json_load(path)
    if (sealed.get("schema") != LEXICAL_SCHEMA
        or sealed.get("status") != "PRIVATE_NQ_LEXICAL_CONSTRUCTION_SEALED_NO_QA_INFERENCE"
        or sealed.get("cohort_manifest_sha256") != cohort_sha
        or sealed.get("target_manifest_sha256") != targets_sha
        or sealed.get("source_files_sha256") != source_sha):
        raise ValueError("NQ lexical construction seal binding mismatch")
    intensity = sealed["intensity"]
    if intensity not in (1, 3):
        raise ValueError("Illegal intensity in construction seal")
    docs = sealed.get("poison_documents_private")
    records = sealed.get("question_poison_associations_private")
    if not isinstance(docs, list) or not isinstance(records, list):
        raise ValueError("Missing lexical construction records")
    doc_map = {}
    for d in docs:
        if not isinstance(d, dict) or set(d) != {"doc_id","text"} or d["doc_id"] in doc_map:
            raise ValueError("Malformed duplicate poison document")
        doc_map[d["doc_id"]] = d["text"]
    by_id = {r["query_id"]: r for r in records}
    if len(by_id) != len(records) or set(by_id) != {q["query_id"] for q in evaluation["queries"]}:
        raise ValueError("Missing or duplicated question-to-poison relation")
    reassociated = []
    linked_docs = set()
    for q in evaluation["queries"]:
        r = by_id[q["query_id"]]
        if r.get("target_answer") != mapping[q["query_id"]]:
            raise ValueError("Target changed since freeze")
        poison_ids = r.get("poison_doc_ids")
        if not isinstance(poison_ids, list) or len(poison_ids) != intensity:
            raise ValueError("Unexpected poison-document count")
        for index, docid in enumerate(poison_ids):
            if docid not in doc_map or docid in linked_docs:
                raise ValueError("Missing or duplicate poison relation")
            if docid != poison_doc_id("lexical_influential_token", q["query_id"], index, doc_map[docid]):
                raise ValueError("Document hash or construction identity mismatch")
            linked_docs.add(docid)
        enriched = dict(q)
        enriched.update({"poison_doc_ids": poison_ids, "poison_target_answer": r["target_answer"],
                         "attack_family": "lexical_influential_token"})
        reassociated.append(enriched)
    if linked_docs != set(doc_map):
        raise ValueError("Unreferenced injected document")
    full = {"corpus": [*evaluation["corpus"], *docs], "queries": reassociated}
    actual = poison_instances_fingerprint(evaluation, full)
    if actual != sealed.get("poison_instance_fingerprint"):
        raise ValueError("Poison fingerprint mismatch")
    validation = validate_poisoned_dataset(evaluation, full, expected_n_poison=intensity,
                                           expected_poison_rate=1.0)
    if not validation["valid"] or validation["checks"] != sealed.get("validation_checks"):
        raise ValueError("Original lexical label validation no longer holds")
    return {"status": "PASS_PRIVATE_NQ_LEXICAL_CONSTRUCTION_INTEGRITY_ONLY",
            "n_queries": len(reassociated), "n_poison_docs": len(docs),
            "poison_instance_fingerprint": actual, "qa_executed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="action", required=True)
    for action in ("prepare-targets", "construct-lexical", "verify-lexical"):
        a = s.add_parser(action)
        a.add_argument("--cohort-dir", type=Path, required=True)
        a.add_argument("--cohort-sha256", required=True)
        if action == "prepare-targets":
            a.add_argument("--output", type=Path, required=True)
            a.add_argument("--seed", type=int, default=DEFAULT_TARGET_SEED)
        else:
            a.add_argument("--targets", type=Path, required=True)
            a.add_argument("--targets-sha256", required=True)
            if action == "construct-lexical":
                a.add_argument("--intensity", type=int, choices=(1,3), required=True)
                a.add_argument("--output", type=Path, required=True)
            else:
                a.add_argument("--construction", type=Path, required=True)
                a.add_argument("--construction-sha256", required=True)
    args = p.parse_args()
    if args.action == "prepare-targets":
        result = prepare_targets(args.cohort_dir, args.cohort_sha256, args.output, seed=args.seed)
    elif args.action == "construct-lexical":
        result = construct_lexical(args.cohort_dir, args.cohort_sha256, args.targets,
                                   args.targets_sha256, args.output, intensity=args.intensity)
    else:
        result = verify_lexical(args.cohort_dir, args.cohort_sha256, args.targets,
                                args.targets_sha256, args.construction, args.construction_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
