#!/usr/bin/env python3
"""Reproduce development-only failure analysis; no dataset/model/evidence calls."""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.extract_verified_development_queries import extract_verified
from src.attacks.development_review_package import answer_shape, stable_json
from src.attacks.review_handoff import candidate_pool, ordered_candidates, screen_queries
from src.attacks.reviewed_target_artifact import SUPPORTED_CATEGORIES, _normalized
from src.attacks.target_candidates import expected_category
from src.attacks.development_targets_v2 import (
    METHOD_VERSION, build_pool, candidates, calendar_date, comparison_or_choice, status,
)

DEFAULT_ARTIFACT = Path("results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl")
DEFAULT_MANIFEST = Path("configs/exp_027_hotpotqa_heldout_manifest.json")
PINNED_ARTIFACT_SHA256 = "eeade06c3b64783869cf1bafdfd9b727ac030dd4260a07bbec58f78cfa6eb0ef"
PINNED_MANIFEST_SHA256 = "2a2b8ea61bb1bca14f0321696e606108053d073c7c79aa6c5f7acc1a636b2bf3"
METHOD_FILES = ("src/attacks/development_targets_v2.py", "scripts/audit_phase4d_development_coverage.py",
                "src/attacks/target_candidates.py", "src/attacks/development_review_package.py",
                "src/attacks/review_handoff.py", "src/attacks/reviewed_target_artifact.py",
                "scripts/extract_verified_development_queries.py", "src/experiments/protocol.py",
                "src/evaluation/metrics.py")


def structure(question):
    q = question.strip().casefold()
    if comparison_or_choice(q):
        return "choice_or_comparison_cue"
    if re.search(r"\b(?:who|whom)\s*[?.]?\s*$", q) and not q.startswith("who"):
        return "terminal_who_request"
    if q.startswith("when") or re.search(r"\bwhat date\b", q):
        return "temporal_request"
    if q.startswith(("what", "which", "where", "who", "how", "at what", "in what", "on what")):
        return "direct_interrogative_head"
    return "embedded_or_descriptive_request"


def label_shape(answer):
    if re.fullmatch(r"\d{4}", answer):
        return "year"
    if calendar_date(answer):
        return "full_calendar_date"
    if re.fullmatch(r"\d[\d,]*(?: members)?", answer):
        return "integer_count"
    if re.search(r"\d", answer):
        return "qualified_numeric_or_mixed_label"
    if re.search(r"\b(?:is|was|became|known|born)\b", answer, re.I):
        return "descriptive_label"
    if re.search(r"\b(?:and|or)\b|[;/]", answer, re.I):
        return "multiple_values_or_aliases"
    return "entity_or_text_label"


def audit(artifact=DEFAULT_ARTIFACT, manifest=DEFAULT_MANIFEST):
    if (hashlib.sha256(artifact.read_bytes()).hexdigest() != PINNED_ARTIFACT_SHA256 or
        hashlib.sha256(manifest.read_bytes()).hexdigest() != PINNED_MANIFEST_SHA256):
        raise ValueError("Pinned development artifact or ID-manifest provenance mismatch")
    queries, provenance = extract_verified(artifact, manifest)
    old_pool = candidate_pool(queries, provenance)
    new_pool = build_pool(queries)
    ledger, failures = [], []
    for query in queries:
        category = expected_category(query["question"], query["gold_answer"])
        old_reason = ("unsupported_category_or_question_pattern" if category not in SUPPORTED_CATEGORIES else
                      "unsupported_gold_answer_shape" if not answer_shape(category, query["gold_answer"]) else
                      "no_non_gold_candidate_in_frozen_pool" if not ordered_candidates(query, old_pool) else None)
        after = status(query, new_pool)
        candidate_rows = candidates(query, new_pool)
        row = {**query, "question_sha256": hashlib.sha256(query["question"].encode()).hexdigest(),
               "gold_answer_sha256": hashlib.sha256(query["gold_answer"].encode()).hexdigest(),
               "question_structure": structure(query["question"]), "gold_label_shape": label_shape(query["gold_answer"]),
               "before_category": category, "before_failure_reason": old_reason,
               "before_eligible": old_reason is None,
               "before_candidate_count": len({_normalized(r["answer"]) for r in old_pool["candidates"]
                   if r["answer_category"] == category and _normalized(r["answer"]) != _normalized(query["gold_answer"])}),
               "after": after,
               "candidate_count": len(candidate_rows), "pending_candidates": candidate_rows,
               "semantic_status": "unverified_requires_independent_review"}
        ledger.append(row)
        if old_reason:
            failures.append(row)
    before = screen_queries(queries, old_pool)
    after_count = sum(row["after"]["eligible"] for row in ledger)
    counts = lambda values: dict(sorted(Counter(values).items()))
    summary = {"schema": "rag-poison-transfer.development-coverage-audit/v1", "scope": "verified_development_only",
               "method_version": METHOD_VERSION, "query_count": len(queries),
               "provenance": {k: v for k, v in provenance.items() if k not in {"artifact", "manifest"}},
               "method_source_sha256": {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in METHOD_FILES},
               "before": before, "after": {"mechanically_eligible": after_count,
                   "unsupported_or_uncertain": len(queries) - after_count,
                   "failure_reasons": counts(row["after"]["failure_reason"] for row in ledger if not row["after"]["eligible"]),
                   "eligible_categories": counts(row["after"]["category"] for row in ledger if row["after"]["eligible"])},
               "gained": sum(not r["before_eligible"] and r["after"]["eligible"] for r in ledger),
               "lost": sum(r["before_eligible"] and not r["after"]["eligible"] for r in ledger),
               "original_186_failure_analysis": {
                   "count": len(failures), "question_structure": counts(r["question_structure"] for r in failures),
                   "gold_label_shape": counts(r["gold_label_shape"] for r in failures),
                   "baseline_categories": counts(r["before_category"] for r in failures),
                   "baseline_candidate_availability": counts(
                       "none" if r["before_candidate_count"] == 0 else
                       "one_to_four" if r["before_candidate_count"] < 5 else "five_or_more" for r in failures)},
               "independently_verified_semantic_correctness": {"verified_pairs": 0, "accuracy": None,
                   "reason": "No independent semantic/factual review performed; mechanical eligibility is not correctness."},
               "heldout_text_or_gold_accessed": False, "heldout_protocol_promoted": False}
    return {"summary.json": summary, "development_analysis.json": {
        "schema": "rag-poison-transfer.development-case-ledger/v1", "scope": "verified_development_only",
        "method_version": METHOD_VERSION, "records": ledger}}


def failure_csv(records):
    stream = io.StringIO(newline="")
    fields = ["query_id", "question", "gold_answer", "question_structure", "gold_label_shape",
              "before_category", "before_failure_reason", "before_candidate_count", "after_category", "after_rule", "after_failure_reason", "candidate_count"]
    writer = csv.DictWriter(stream, fields, lineterminator="\n")
    writer.writeheader()
    for row in records:
        if row["before_eligible"]:
            continue
        value = {k: row[k] for k in fields if k in row}
        value.update(after_category=row["after"]["category"], after_rule=row["after"]["rule"],
                     after_failure_reason=row["after"]["failure_reason"])
        writer.writerow(value)
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/reviews/phase4d"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = audit(args.artifact, args.manifest)
    contents = {name: stable_json(value) for name, value in files.items()}
    contents["original_186_failures.csv"] = failure_csv(files["development_analysis.json"]["records"])
    if args.check:
        for name, content in contents.items():
            if (args.output_dir / name).read_bytes() != content.encode("utf-8"):
                raise ValueError("Development audit mismatch: " + name)
    else:
        if any((args.output_dir / name).exists() for name in contents):
            parser.error("Refusing overwrite; use --check or a fresh output directory")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in contents.items():
            with (args.output_dir / name).open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
    print(json.dumps(files["summary.json"], sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
