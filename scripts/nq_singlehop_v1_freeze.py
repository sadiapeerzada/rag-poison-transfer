#!/usr/bin/env python3
"""Pin a *new* Natural Questions single-hop cohort before any new inference.

This script does NOT run an attack, retrieval or QA, and it does not
certify that questions were never seen in earlier experiments.
Privacy: complete corpus/queries/IDs stay outside this public repository.
Source: the existing candidate-passage NQ loader, NOT full Wikipedia retrieval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint

SCHEMA = "rag-poison-transfer.nq-singlehop-frozen-cohort/v1"
DATASET = "google-research-datasets/natural_questions"
REVISION = "e8103d566bef4154c2c12b17c6095ec5275840cc"
DEFAULT_DEV_N = 50
DEFAULT_EVAL_N = 300
DEFAULT_DEV_SEED = 20261109
DEFAULT_EVAL_SEED = 20261110


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def private(path):
    target = Path(path).expanduser().resolve()
    if target == ROOT or ROOT in target.parents:
        raise ValueError("Never place private NQ queries/corpus inside the public repo")
    return target


def json_load(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise ValueError("Missing or symlinked input: " + p.name)
    with p.open(encoding="utf-8") as source:
        return json.load(source)


def snapshot_validate(data, expected, cohort):
    """Fail closed on labels, IDs, gold-document linkage and corpus consistency."""
    if not isinstance(data, dict):
        raise ValueError(cohort + ": dataset is not an object")
    queries, corpus = data.get("queries"), data.get("corpus")
    if not isinstance(queries, list) or len(queries) != expected or not isinstance(corpus, list) or not corpus:
        raise ValueError(cohort + ": wrong query count or empty corpus")
    by_id = {}
    normalized_corpus = []
    for doc in corpus:
        if not isinstance(doc, dict):
            raise ValueError(cohort + ": non-object candidate document")
        docid, body = doc.get("doc_id"), doc.get("text")
        if not isinstance(docid, str) or not docid or not isinstance(body, str) or not body.strip():
            raise ValueError(cohort + ": empty candidate ID/text")
        if docid in by_id:
            raise ValueError(cohort + ": duplicate candidate document ID")
        by_id[docid] = body
        normalized_corpus.append({"doc_id": docid, "text": body})
    ids = set()
    normalized_queries = []
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError(cohort + ": non-object query")
        qid = str(query.get("query_id", "")).strip()
        question, answer = query.get("question"), query.get("gold_answer")
        gold = query.get("gold_doc_ids")
        if not qid or qid in ids or not isinstance(question, str) or not question.strip():
            raise ValueError(cohort + ": duplicate/empty question ID/text")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(cohort + ": missing short-answer gold")
        if not isinstance(gold, list) or len(gold) != 1 or gold[0] not in by_id:
            raise ValueError(cohort + ": gold document ID missing from candidate corpus")
        ids.add(qid)
        normalized_queries.append({
            "query_id": qid, "question": question, "gold_answer": answer,
            "gold_doc_ids": list(gold),
            "gold_supporting_facts": query.get("gold_supporting_facts", []),
        })
    return {"queries": normalized_queries, "corpus": normalized_corpus}


def load_exclusions(path):
    if path is None:
        return set(), None
    p = Path(path).expanduser().resolve()
    value = json_load(p)
    if isinstance(value, dict):
        value = value.get("query_ids")
    if not isinstance(value, list) or any(not isinstance(x, (str, int)) or not str(x).strip() for x in value):
        raise ValueError("Exposure-exclusions must be an exact JSON list or {'query_ids': [...]} file")
    ids = [str(x).strip() for x in value]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate exposure-exclusion ID")
    return set(ids), digest(p)


def git_state():
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip())
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def freeze(out_dir, *, dev_n=DEFAULT_DEV_N, eval_n=DEFAULT_EVAL_N,
           dev_source=None, eval_source=None, exposure_exclusions=None,
           dev_seed=DEFAULT_DEV_SEED, eval_seed=DEFAULT_EVAL_SEED):
    if type(dev_n) is not int or type(eval_n) is not int or min(dev_n, eval_n) < 1:
        raise ValueError("Both dev and eval require positive integer sizes")
    if (dev_source is None) != (eval_source is None):
        raise ValueError("Provide both --dev-json and --eval-json, or neither")
    out = private(out_dir)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Output must be a new private directory with existing parent")

    if dev_source is None:
        from src.data.loaders import load_natural_questions
        dev_raw = load_natural_questions(split="train", n_samples=dev_n, seed=dev_seed, revision=REVISION)
        eval_raw = load_natural_questions(split="validation", n_samples=eval_n, seed=eval_seed, revision=REVISION)
        source_provenance = "runtime_streaming_NQ_loader_at_pinned_revision_not_independently_archived"
        source_sha = None
    else:
        if Path(dev_source).resolve() == Path(eval_source).resolve():
            raise ValueError("Dev and evaluation inputs may not be the same file")
        dev_raw, eval_raw = json_load(dev_source), json_load(eval_source)
        source_provenance = "operator_supplied_local_json_revision_unverified"
        source_sha = {"dev_input_sha256": digest(dev_source), "eval_input_sha256": digest(eval_source)}

    dev = snapshot_validate(dev_raw, dev_n, "dev_train")
    evaluation = snapshot_validate(eval_raw, eval_n, "eval_validation")
    ids_dev = {q["query_id"] for q in dev["queries"]}
    ids_eval = {q["query_id"] for q in evaluation["queries"]}
    if ids_dev & ids_eval:
        raise ValueError("Development and evaluation query IDs overlap")

    excluded, excluded_sha = load_exclusions(exposure_exclusions)
    if (ids_dev | ids_eval) & excluded:
        raise ValueError("Previously exposed question IDs overlap the new NQ cohort")

    git_commit, git_dirty = git_state()
    if git_dirty is not False or not git_commit:
        raise ValueError("Freezing requires a known clean Git tree; commit code before using this step")

    out.mkdir(mode=0o700)
    try:
        source_files = {}
        for name, value in (("dev_train.json", dev), ("evaluation_validation.json", evaluation)):
            path = out / name
            with path.open("x", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                handle.write("\n")
            source_files[name] = digest(path)
        manifest = {
            "schema": SCHEMA,
            "status": "NQ_COHORT_FROZEN_NO_RETRIEVAL_OR_INFERENCE",
            "dataset": {"name": DATASET, "config": "default", "revision": REVISION,
                        "dev_split": "train", "eval_split": "validation",
                        "corpus_scope": "pooled_NQ_long_answer_candidates_not_full_Wikipedia",
                        "sampling": "streaming_shuffle_buffer_10000_not_uniform",
                        "dev_seed": dev_seed, "eval_seed": eval_seed},
            "cohorts": {
                "dev": {"n": dev_n, "query_fingerprint": query_set_fingerprint(dev["queries"]),
                        "corpus_fingerprint": corpus_fingerprint(dev["corpus"]), "n_documents": len(dev["corpus"])},
                "eval": {"n": eval_n, "query_fingerprint": query_set_fingerprint(evaluation["queries"]),
                         "corpus_fingerprint": corpus_fingerprint(evaluation["corpus"]), "n_documents": len(evaluation["corpus"])},
            },
            "original_source_provenance": source_provenance,
            "input_file_sha256": source_sha,
            "private_dataset_files_sha256": source_files,
            "prior_exposure_exclusion_file_sha256": excluded_sha,
            "prior_exposure_certified": False,
            "code_commit_sha": git_commit,
            "git_dirty_at_freeze": git_dirty,
            "python_version": platform.python_version(),
            "planned_new_experiment": {
                "status": "NOT_RUN",
                "attack_families": ["lexical_influential_token", "semantic_fluent_false_evidence"],
                "intensities": [1, 3],
                "paired_qa_arms": ["dense", "rcd"],
                "conditions": ["clean", "poisoned"],
                "generator_output_token_cap": 64,
                "retrieval_candidate_k": 10,
                "generator_evidence_k": 3,
                "expected_eval_qa_calls_if_all_constructions_valid": eval_n * 2 * 2 * 2 * 2,
                "no_historical_heldout_reuse": True,
                "construction_failures_need_attempted_denominator": True,
                "semantic_factuality_not_independently_certified": True,
            },
            "limitations": [
                "This is a preparatory manifest, NOT a completed NQ matched-poisoning study.",
                "The NQ corpus pools long-answer candidate passages; it is not open-domain Wikipedia retrieval.",
                "Streaming shuffle-buffer sampling is not a uniform representative sample.",
                "Dataset loader chooses one annotator's first usable short answer; aliases and annotation disagreement remain.",
                "Earlier NQ development samples have not been completely reconciled by an independent exposure inventory.",
                "New attack construction, actual retrieval, QA, and paired statistical analysis are separate stages.",
                "Source-backed factuality of selected false targets requires independent supporting evidence.",
            ],
        }
        manifest_path = out / "cohort_manifest.json"
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return {"status": manifest["status"], "manifest_sha256": digest(manifest_path),
                "directory": str(out), "dev_queries": dev_n, "eval_queries": eval_n,
                "eval_qa_budget_if_all_valid": manifest["planned_new_experiment"]["expected_eval_qa_calls_if_all_constructions_valid"],
                "exposure_exclusions_provided": exposure_exclusions is not None}
    except Exception:
        # Fail closed; never delete the contents of an incomplete private freeze.
        raise


def verify(out_dir, manifest_sha256):
    root = private(out_dir)
    mpath = root / "cohort_manifest.json"
    if digest(mpath) != manifest_sha256:
        raise ValueError("Manifest SHA-256 mismatch")
    m = json_load(mpath)
    if (m.get("schema") != SCHEMA or m.get("status") != "NQ_COHORT_FROZEN_NO_RETRIEVAL_OR_INFERENCE"
        or m["dataset"]["revision"] != REVISION or m.get("git_dirty_at_freeze") is not False):
        raise ValueError("Wrong NQ cohort schema/provenance")
    cohorts = {}
    for label, filename in (("dev", "dev_train.json"), ("eval", "evaluation_validation.json")):
        path = root / filename
        if digest(path) != m["private_dataset_files_sha256"][filename]:
            raise ValueError("Frozen NQ private corpus changed: " + filename)
        data = snapshot_validate(json_load(path), m["cohorts"][label]["n"], label)
        if query_set_fingerprint(data["queries"]) != m["cohorts"][label]["query_fingerprint"]:
            raise ValueError("Query-set fingerprint mismatch: " + label)
        if corpus_fingerprint(data["corpus"]) != m["cohorts"][label]["corpus_fingerprint"]:
            raise ValueError("Corpus fingerprint mismatch: " + label)
        if len(data["corpus"]) != m["cohorts"][label]["n_documents"]:
            raise ValueError("Document count mismatch: " + label)
        cohorts[label] = {q["query_id"] for q in data["queries"]}
    if cohorts["dev"] & cohorts["eval"]:
        raise ValueError("NQ train/validation question overlap")
    return {"status": "PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY",
            "dev_queries": len(cohorts["dev"]), "eval_queries": len(cohorts["eval"]),
            "matched_QA_completed": False, "heldout_unexposed_certified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--out-dir", type=Path, required=True)
    f.add_argument("--dev-n", type=int, default=DEFAULT_DEV_N)
    f.add_argument("--eval-n", type=int, default=DEFAULT_EVAL_N)
    f.add_argument("--dev-json", type=Path)
    f.add_argument("--eval-json", type=Path)
    f.add_argument("--exposure-exclusions", type=Path)
    f.add_argument("--dev-seed", type=int, default=DEFAULT_DEV_SEED)
    f.add_argument("--eval-seed", type=int, default=DEFAULT_EVAL_SEED)
    v = sub.add_parser("verify")
    v.add_argument("--out-dir", type=Path, required=True)
    v.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    result = (freeze(args.out_dir, dev_n=args.dev_n, eval_n=args.eval_n,
                     dev_source=args.dev_json, eval_source=args.eval_json,
                     exposure_exclusions=args.exposure_exclusions,
                     dev_seed=args.dev_seed, eval_seed=args.eval_seed)
              if args.action == "freeze" else verify(args.out_dir, args.manifest_sha256))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
