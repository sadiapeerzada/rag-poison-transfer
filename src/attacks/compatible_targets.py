"""Opt-in, review-gated target assignments for a future protocol revision.

This module intentionally does not alter the frozen legacy selector.
Assignments are independently reviewed and versioned; no guessing or
fallback to unrelated answers is permitted.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.evaluation.metrics import exact_match

PROTOCOL_VERSION = "answer-compatible-targets/v3-reviewed"


class TargetAssignmentError(ValueError):
    """Missing, malformed, or incompatible-reviewed target assignment."""


def validate_review_row(row: dict) -> None:
    """Validate review decisions even for callers supplying an in-memory mapping."""
    if not isinstance(row, dict):
        raise TargetAssignmentError("Assignment must be an object")
    if row.get("approved") is not True:
        raise TargetAssignmentError("Unapproved assignment")
    fields = ("query_id", "target_answer", "answer_category", "reviewer", "review_evidence")
    if any(not isinstance(row.get(k), str) or not row[k].strip() for k in fields):
        raise TargetAssignmentError("Assignment lacks review metadata")
    if (row.get("review_status") != "approved" or
        row.get("semantic_compatible") is not True or
        row.get("factually_false") is not True or
        row.get("coherent_false_evidence") is not True):
        raise TargetAssignmentError("Explicit review decisions required")
    for key in ("question_sha256", "gold_answer_sha256", "reviewed_target_sha256"):
        if not isinstance(row.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", row[key]):
            raise TargetAssignmentError("Invalid review fingerprint: " + key)
    if row["reviewed_target_sha256"] != hashlib.sha256(row["target_answer"].encode("utf-8")).hexdigest():
        raise TargetAssignmentError("Stale target approval fingerprint")
    try:
        stamp = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
            raise ValueError("Review timestamp must have a timezone and cannot be in the future")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise TargetAssignmentError("Invalid review timestamp") from exc


def load_reviewed_assignments(path: str | Path) -> dict:
    """Read a reviewed mapping. No held-out labels or targets are inferred."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("protocol_version") != PROTOCOL_VERSION:
        raise TargetAssignmentError("Unsupported target assignment protocol version")
    rows = payload.get("assignments")
    if not isinstance(rows, list) or not rows:
        raise TargetAssignmentError("Expected a nonempty assignments list")
    mapping = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TargetAssignmentError("Assignment must be an object")
        validate_review_row(row)
        qid = row.get("query_id")
        target = row.get("target_answer")
        category = row.get("answer_category")
        reviewer = row.get("reviewer")
        evidence = row.get("review_evidence")
        if not all(isinstance(x, str) and x.strip() for x in
                   (qid, target, category, reviewer, evidence)):
            raise TargetAssignmentError("Assignment lacks review metadata")
        if row.get("approved") is not True:
            raise TargetAssignmentError(f"Unapproved assignment: {qid}")
        if qid in mapping:
            raise TargetAssignmentError(f"Duplicate query ID: {qid}")
        mapping[qid] = row
    return mapping


def select_reviewed_target(query: dict, mapping: dict) -> str:
    """Fail closed unless an independently approved target exists."""
    if not isinstance(query, dict) or any(
        not isinstance(query.get(k), str) or not query[k].strip()
        for k in ("query_id", "question", "gold_answer")
    ):
        raise TargetAssignmentError("Malformed query identity/question/gold")
    qid = query["query_id"]
    if qid not in mapping:
        raise TargetAssignmentError(f"No approved target for query {qid}")
    row = mapping[qid]
    validate_review_row(row)
    if row["query_id"] != qid:
        raise TargetAssignmentError("Mapping/query identity mismatch")
    gold = str(query.get("gold_answer", ""))
    if exact_match(str(row["target_answer"]), gold) != 0.0:
        raise TargetAssignmentError(f"Target matches gold answer for {qid}")
    if row.get("question_sha256") != hashlib.sha256(
        query["question"].encode("utf-8")
    ).hexdigest():
        raise TargetAssignmentError(f"Question fingerprint mismatch for {qid}")
    if row.get("gold_answer_sha256") != hashlib.sha256(
        gold.encode("utf-8")
    ).hexdigest():
        raise TargetAssignmentError(f"Gold fingerprint mismatch for {qid}")
    return row["target_answer"]


def assignment_fingerprint(mapping: dict) -> str:
    """Stable SHA256 independent of JSON whitespace and row order."""
    normalized = [mapping[qid] for qid in sorted(mapping)]
    return hashlib.sha256(json.dumps(
        normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
