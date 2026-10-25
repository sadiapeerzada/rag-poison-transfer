"""Deterministic, unapproved candidate suggestions for human review.

Input is a development-only JSON file containing a list of query records.
This deliberately never reads the frozen held-out manifest or approves targets.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from src.evaluation.metrics import exact_match


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expected_category(question: str, gold_answer: str) -> str:
    """Conservative question-pattern classifier; 'unknown' needs review."""
    q = " ".join(question.lower().split())
    gold = gold_answer.strip().lower()
    if gold in {"yes", "no"}:
        return "yes_no"
    if re.search(r"\b(what|which) (year|date)\b|\bwhen\b", q):
        return "date"
    if re.search(r"\b(how many|how much|number of)\b", q):
        return "quantity"
    if re.search(r"\b(related to|relation between|relationship between)\b", q):
        return "relationship"
    if re.search(r"\b(what|which) (battle|war|conflict)\b|\bwhich battle\b", q):
        return "battle"
    if re.search(r"\bwho\b", q) or (\n        re.search(r"\b(what|which)\b", q)\n        and re.search(r"\b(actor|actress|person|singer|director|author|player)\b", q)\n    ):
        return "person"
    if re.search(r"\b(station|airport)\b", q):
        return "transport_place"
    if re.search(r"\b(genus|virus|species|family of viruses)\b", q):
        return "biological_taxon"
    if re.search(r"\b(what|which) (country|city|state|town|island|park)\b|\bwhere\b", q):
        return "place"
    return "unknown"


def build_candidate_review_rows(queries: list[dict], max_suggestions: int = 5) -> list[dict]:
    """Generate review suggestions from same-category development answers.

    Category equality is NOT proof of plausibility or falsehood. No row
    produced here can pass the approved-assignment loader without review.
    """
    if max_suggestions < 1:
        raise ValueError("max_suggestions must be positive")
    ids = [q["query_id"] for q in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate query IDs")
    tagged = [(q, expected_category(q["question"], str(q["gold_answer"]))) for q in queries]
    rows = []
    for q, category in tagged:
        gold = str(q["gold_answer"])
        suggestions = sorted({
            str(other["gold_answer"])
            for other, other_category in tagged
            if other["query_id"] != q["query_id"]
            and other_category == category
            and category != "unknown"
            and exact_match(str(other["gold_answer"]), gold) == 0.0
        }, key=lambda s: (s.casefold(), s))[:max_suggestions]
        rows.append({
            "query_id": q["query_id"],
            "question": q["question"],
            "gold_answer": gold,
            "question_sha256": _sha(q["question"]),
            "gold_answer_sha256": _sha(gold),
            "answer_category": category,
            "suggested_targets": suggestions,
            "target_answer": "",
            "approved": False,
            "reviewer": "",
            "review_evidence": "",
            "review_status": "needs_independent_review",
        })
    return rows


def write_review_template(queries: list[dict], output: str | Path) -> dict:
    rows = build_candidate_review_rows(queries)
    payload = {
        "schema": "answer-compatible-targets/review-template-v1",
        "status": "unreviewed_development_candidates",
        "count": len(rows),
        "categories": dict(sorted(Counter(row["answer_category"] for row in rows).items())),
        "assignments": rows,
    }
    Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
