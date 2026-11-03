"""V3 development-only construction validation.

This is an isolated adapter, not the frozen Week 9 runner.
No model calls, injection, evaluation, or factual approval.
"""
from src.attacks.development_targets_v6 import nominate_ai
from src.attacks.semantic_document_diversity_v3 import require_distinct
from src.attacks.semantic_fluent_development_v2 import (
    DevelopmentSemanticFluentAttackV2,
)


def inspect_case(
    query, development, corpus, evidence,
    ai_reviews=None, *, scope="development",
):
    if scope != "development":
        raise ValueError("V3 gate refuses held-out scope")

    if not isinstance(development, list) or not any(
        row == query for row in development
    ):
        raise ValueError("Query must belong to supplied development cohort")

    if not isinstance(corpus, list) or not corpus:
        raise ValueError("Pinned source corpus required")

    result = nominate_ai(
        query,
        development,
        chronology_evidence=evidence,
        corpus=corpus,
        ai_target_reviews=ai_reviews,
    )

    if result.get("injection_approved") is not False:
        raise ValueError("Unexpected injection approval")

    for candidate in result["candidates"]:
        screening = candidate["v3_screening"]
        if (
            not screening.get("ai_screening_passed")
            or screening.get("factual_approval") is not False
            or screening.get("injection_approved") is not False
        ):
            raise ValueError("Invalid AI-screened candidate")

    return result


def validate_constructed_documents(
    query, development, corpus, evidence,
    ai_reviews, target, documents, intensity,
    *, scope="development",
):
    """Check candidate documents, never authorize injection."""

    if type(intensity) is not int or intensity not in (1, 3):
        raise ValueError("Unsupported development intensity")

    nomination = inspect_case(
        query, development, corpus, evidence,
        ai_reviews, scope=scope,
    )

    allowed = [
        row for row in nomination["candidates"]
        if row["answer"] == target
        and row["v3_screening"]["construction_eligible"]
    ]

    if len(allowed) != 1:
        raise ValueError("Target lacks valid two-AI screening")

    if not isinstance(documents, list):
        raise ValueError("Documents must be a list")

    if len(documents) != intensity:
        raise ValueError("Incomplete construction")

    validator = DevelopmentSemanticFluentAttackV2(
        None, scope="development"
    )

    for index, doc in enumerate(documents):
        if (
            not isinstance(doc, dict)
            or doc.get("query_id") != query["query_id"]
            or doc.get("target_answer") != target
            or doc.get("poison_index") != index
        ):
            raise ValueError("Document provenance mismatch")

        validator._validate_text(
            doc["text"], query, target
        )

    diversity = require_distinct(documents, intensity)

    return {
        "status": "development_documents_screened",
        "query_id": query["query_id"],
        "target_answer": target,
        "document_count": len(documents),
        "diversity": diversity,
        "ai_screening_passed": True,
        "factual_approval": False,
        "injection_approved": False,
        "heldout_authorized": False,
    }
