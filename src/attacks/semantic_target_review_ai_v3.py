"""Development-only, two-AI target screening policy.

AI agreement is provisional screening, NOT independently verified
factual truth. Reviewer metadata is self-reported, not authenticated.
No real candidate is approved by importing this module.
"""
import re
from datetime import datetime
from hashlib import sha256

SCHEMA = "rag-poison-transfer.v3-two-ai-target-review/v1"
REVIEW_SCHEMA = "rag-poison-transfer.v3-ai-target-assessment/v1"

CHECKS = (
    "referent_grounded",
    "gold_supported",
    "target_distinct_from_gold",
    "target_type_compatible",
    "relation_grammar_supported",
    "aliases_checked",
    "chronology_checked",
)

DECISIONS = ("provisional_accept", "reject", "uncertain")


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def assess_ai_target_reviews(query, target, binding, pair):
    """Return (screening_passed, reason); fail closed on disagreement."""

    if not binding or binding.get("status") != "direct_relation_text_grounded":
        return False, "source_relationship_unresolved"

    if pair is None:
        return False, "two_ai_reviews_missing"

    if not isinstance(pair, dict) or pair.get("schema") != SCHEMA:
        raise ValueError("Invalid two-AI review schema")

    reviews = pair.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise ValueError("Exactly two AI reviews required")

    expected = {
        "schema": REVIEW_SCHEMA,
        "query_id": query["query_id"],
        "question_sha256": digest(query["question"]),
        "gold_answer_sha256": digest(query["gold_answer"]),
        "target_answer_sha256": digest(target),
        "source_document_sha256": binding["source_document_sha256"],
        "relation_document_sha256": binding["relation_document_sha256"],
    }

    models = []
    runs = []
    responses = []
    decisions = []

    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("Invalid AI assessment")

        for key, value in expected.items():
            if review.get(key) != value:
                raise ValueError("AI review binding mismatch: " + key)

        if review.get("reviewer_type") != "ai":
            raise ValueError("Reviewer must be identified as AI")

        for key in ("model_id", "review_run_id"):
            value = review.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Missing AI review provenance: " + key)

        for key in ("prompt_sha256", "response_sha256"):
            value = review.get(key)
            if not isinstance(value, str) or not re.fullmatch(
                r"[0-9a-f]{64}", value
            ):
                raise ValueError("Invalid review provenance hash: " + key)

        timestamp = review.get("reviewed_at")
        if not isinstance(timestamp, str):
            raise ValueError("Missing review timestamp")

        try:
            dt = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError("Invalid review timestamp") from exc

        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("AI review timestamp must be timezone-aware")

        decision = review.get("decision")
        if decision not in DECISIONS:
            raise ValueError("Invalid AI review decision")

        checks = review.get("checks")
        if not isinstance(checks, dict) or set(checks) != set(CHECKS):
            raise ValueError("Incomplete AI review checks")

        if any(type(checks[key]) is not bool for key in CHECKS):
            raise ValueError("AI review checks must be Boolean")

        reason = review.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < 30:
            raise ValueError("Insufficient AI review explanation")

        models.append(review["model_id"])
        runs.append(review["review_run_id"])
        responses.append(review["response_sha256"])
        decisions.append(decision)

    if len(set(models)) != 2 or len(set(runs)) != 2 or len(set(responses)) != 2:
        return False, "ai_reviews_not_independently_traceable"

    if "reject" in decisions:
        return False, "ai_review_rejected"

    if "uncertain" in decisions:
        return False, "ai_review_uncertain"

    if not all(
        all(review["checks"].values())
        for review in reviews
    ):
        return False, "ai_review_checks_incomplete"

    return True, "two_ai_reviews_provisionally_accept_development_only"
