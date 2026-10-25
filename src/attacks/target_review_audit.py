"""Fail-closed audit of development target-review templates; no auto-approval."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from src.attacks.target_candidates import expected_category, build_candidate_review_rows
from src.evaluation.metrics import exact_match

SCHEMA = "answer-compatible-targets/review-template-v2"


class ReviewAuditError(ValueError):
    """Review input is malformed, stale, or not an unapproved template."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit_review_template(payload: dict, queries: list[dict]) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ReviewAuditError("Expected unapproved development review-template schema")
    if payload.get("status") != "unreviewed_development_candidates":
        raise ReviewAuditError("Expected unreviewed development candidates")
    if not isinstance(queries, list) or not isinstance(payload.get("assignments"), list):
        raise ReviewAuditError("Expected query and assignment lists")
    by_id = {}
    for query in queries:
        if not isinstance(query, dict) or not all(
            isinstance(query.get(k), str) and query[k].strip() for k in ("query_id", "question", "gold_answer")
        ):
            raise ReviewAuditError("Malformed development query")
        qid = query["query_id"]
        if qid in by_id:
            raise ReviewAuditError("Duplicate development query ID")
        by_id[qid] = query
    expected_rows = {r["query_id"]: r for r in build_candidate_review_rows(queries)}
    rows = payload["assignments"]
    if payload.get("count") != len(rows) or len(rows) != len(by_id):
        raise ReviewAuditError("Template count does not match development queries")
    seen = set()
    categories = Counter()
    with_candidates = 0
    total_suggestions = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ReviewAuditError("Malformed review row")
        qid = row.get("query_id")
        if qid not in by_id or qid in seen:
            raise ReviewAuditError("Unknown or duplicate review query ID")
        seen.add(qid)
        q = by_id[qid]
        if row.get("approved") is not False or row.get("target_answer") != "":
            raise ReviewAuditError("Audit accepts unapproved blank-target templates only")
        if row.get("review_status") != "needs_independent_review":
            raise ReviewAuditError("Unexpected review status")
        if row.get("question") != q["question"] or row.get("gold_answer") != q["gold_answer"]:
            raise ReviewAuditError("Question/gold mismatch")
        if row.get("question_sha256") != _sha(q["question"]) or row.get("gold_answer_sha256") != _sha(q["gold_answer"]):
            raise ReviewAuditError("Stale question/gold fingerprint")
        category = expected_category(q["question"], q["gold_answer"])
        if row.get("answer_category") != category:
            raise ReviewAuditError("Category mismatch")
        suggestions = row.get("suggested_targets")
        if not isinstance(suggestions, list) or any(
            not isinstance(s, str) or not s.strip() or exact_match(s, q["gold_answer"]) != 0.0
            for s in suggestions
        ):
            raise ReviewAuditError("Invalid suggested target")
        if len(suggestions) != len(set(suggestions)):
            raise ReviewAuditError("Duplicate suggested target")
        if suggestions != expected_rows[qid]["suggested_targets"]:
            raise ReviewAuditError("Suggestion provenance/order/limit mismatch with development sources")
        if row.get("suggestion_sources") != expected_rows[qid]["suggestion_sources"]:
            raise ReviewAuditError("Suggestion source provenance mismatch")
        categories[category] += 1
        with_candidates += bool(suggestions)
        total_suggestions += len(suggestions)
    if seen != set(by_id):
        raise ReviewAuditError("Missing development queries")
    if payload.get("categories") != dict(sorted(categories.items())):
        raise ReviewAuditError("Category counts inconsistent")
    count = len(rows)
    return {
        "schema": "answer-compatible-targets/development-audit-v1",
        "total_queries": count,
        "category_counts": dict(sorted(categories.items())),
        "unknown_category_count": categories["unknown"],
        "queries_with_suggestions": with_candidates,
        "queries_without_suggestions": count - with_candidates,
        "candidate_coverage_fraction": (with_candidates / count if count else 0.0),
        "total_suggestions": total_suggestions,
        "independently_approved_targets": 0,
        "scientific_validity": "not_assessed",
        "warning": "Category and suggestion coverage are not semantic plausibility or falsehood evidence.",
    }


def audit_review_files(development_queries: str | Path, template: str | Path, output: str | Path) -> dict:
    queries = json.loads(Path(development_queries).read_text(encoding="utf-8"))
    payload = json.loads(Path(template).read_text(encoding="utf-8"))
    report = audit_review_template(payload, queries)
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
