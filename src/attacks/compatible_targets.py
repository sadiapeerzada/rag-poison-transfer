"""Opt-in, review-gated target assignments for a future protocol revision.

This module intentionally does not alter the frozen legacy selector.
Assignments are independently reviewed and versioned; no guessing or
fallback to unrelated answers is permitted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.evaluation.metrics import exact_match

PROTOCOL_VERSION = "answer-compatible-targets/v2-candidate"


class TargetAssignmentError(ValueError):
    """Missing, malformed, or incompatible-reviewed target assignment."""


def load_reviewed_assignments(path: str | Path) -> dict:
    """Read a reviewed mapping. No held-out labels or targets are inferred."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise TargetAssignmentError("Unsupported target assignment protocol version")
    rows = payload.get("assignments")
    if not isinstance(rows, list) or not rows:
        raise TargetAssignmentError("Expected a nonempty assignments list")
    mapping = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TargetAssignmentError("Assignment must be an object")
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
    qid = query["query_id"]
    if qid not in mapping:
        raise TargetAssignmentError(f"No approved target for query {qid}")
    row = mapping[qid]
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
