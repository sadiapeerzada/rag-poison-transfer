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

from src.evaluation.metrics import exact_match, normalize_answer


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expected_category(question: str, gold_answer: str) -> str:
    """Conservative question-pattern classifier; 'unknown' needs review."""
    q = " ".join(question.lower().split())
    q = re.sub(r'["“”]', "", q)
    gold = gold_answer.strip().lower()
    if gold in {"yes", "no"}:
        return "yes_no"
    # Choice/comparison constraints need manual resolution; never suggest a third entity.
    if re.search(r"\b(?:or|versus|vs)\b", q) or re.search(
        r"\b(?:which|what|who)\b.*\b(?:first|earlier|later|longer|older|younger|more|less)\b", q
    ):
        return "unknown"
    if re.search(r"\bwhat\s+(?:class|family|type)\s+of\s+instrument\b", q):
        return "instrument_family"
    if re.search(r"\bwhat\s+(?:kinds?|types?)\s+of\s+animals?\b", q):
        return "animal"
    if re.search(r"\bwhat\s+language\b", q):
        return "language"
    if re.search(r"\bhow\s+far\b", q):
        return "distance"
    if re.search(r"\b(?:what|which)\s+(?:\w+\s+){0,2}arena\b", q):
        return "sports_venue"
    if re.search(r"\b(what|which) (year|date)\b|\bwhen\b", q):
        return "date"
    if re.search(r"\b(how many|how much|number of)\b", q):
        return "quantity"
    if re.search(r"\b(related to|relation between|relationship between)\b", q):
        return "relationship"
    if re.search(r"\b(what|which) (battle|war|conflict)\b|\bwhich battle\b", q):
        return "battle"
    if re.search(r"^who\b|\bby whom\b", q) or re.search(
        r"\b(?:what|which)\s+(?:[\w-]+\s+){0,3}(?:actor|actress|person|singer|director|author|player|poet|comedian|composer|coach|artist|star)\b", q
    ):
        return "person"
    for category, nouns in (
        ("company", "company|corporation"), ("brewery", "brewery"),
        ("magazine", "magazine|journal"), ("empire", "empire"),
        ("river", "river"), ("comic_series", "comic series|comic book"),
        ("film", "film|movie"), ("person", "star"),
    ):
        if re.search(r"\b(?:what|which)\s+(?:[\w-]+\s+){0,2}(?:" + nouns + r")\b", q):
            return category
    if re.search(r"\b(?:population|capacity)\b", q) and re.search(r"\bwhat\b", q):
        return "quantity"
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
    if not isinstance(queries, list) or any(
        not isinstance(q, dict) or any(not isinstance(q.get(k), str) or not q[k].strip()
            for k in ("query_id", "question", "gold_answer")) for q in queries
    ):
        raise ValueError("Expected development query records with nonempty string fields")
    ids = [q["query_id"] for q in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate query IDs")
    queries = sorted(queries, key=lambda q: q["query_id"])
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
        }, key=lambda s: (s.casefold(), s))
        unique = {}
        for suggestion in suggestions:
            unique.setdefault(normalize_answer(suggestion), suggestion)
        suggestions = list(unique.values())[:max_suggestions]
        sources = {target: sorted(other["query_id"] for other, other_category in tagged
                   if other["query_id"] != q["query_id"] and other_category == category
                   and str(other["gold_answer"]) == target) for target in suggestions}
        rows.append({
            "query_id": q["query_id"],
            "question": q["question"],
            "gold_answer": gold,
            "question_sha256": _sha(q["question"]),
            "gold_answer_sha256": _sha(gold),
            "answer_category": category,
            "suggested_targets": suggestions,
            "suggestion_sources": sources,
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
        "schema": "answer-compatible-targets/review-template-v2",
        "status": "unreviewed_development_candidates",
        "count": len(rows),
        "categories": dict(sorted(Counter(row["answer_category"] for row in rows).items())),
        "assignments": rows,
    }
    Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
