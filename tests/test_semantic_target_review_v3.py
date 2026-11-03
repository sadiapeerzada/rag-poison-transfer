import pytest

from src.attacks.semantic_target_review_v3 import (
    SCHEMA,
    assess_target_review,
    digest,
)


def fixture():
    query = {
        "query_id": "synthetic-query",
        "question": "When was the director of film Example Film born?",
        "gold_answer": "April 14, 1969",
    }
    target = "10 March 1975"
    binding = {
        "status": "direct_relation_text_grounded",
        "source_document_sha256": digest("synthetic biography"),
        "relation_document_sha256": digest("synthetic film record"),
    }
    review = {
        "schema": SCHEMA,
        "query_id": query["query_id"],
        "question_sha256": digest(query["question"]),
        "gold_answer_sha256": digest(query["gold_answer"]),
        "target_answer_sha256": digest(target),
        "source_document_sha256": binding["source_document_sha256"],
        "relation_document_sha256": binding["relation_document_sha256"],
        "reviewer_type": "human",
        "reviewer_id": "synthetic-reviewer-fixture",
        "reviewed_at": "2026-11-03T10:00:00+00:00",
        "decision": "approve",
        "checks": {
            "referent_identity_verified": True,
            "target_falsehood_verified": True,
            "gold_aliases_reviewed": True,
            "chronological_plausibility_reviewed": True,
        },
        "falsehood_evidence": (
            "The synthetic record gives 1969, not the proposed 1975 date."
        ),
        "alias_review_notes": (
            "The synthetic gold and alias evidence was examined for equivalence."
        ),
        "plausibility_notes": (
            "The synthetic alternative was checked against relevant chronology."
        ),
    }
    return query, target, binding, review


def test_missing_review_never_approves():
    q, target, binding, _ = fixture()
    assert assess_target_review(q, target, binding, None) == (
        False, "independent_human_review_missing"
    )


def test_synthetic_complete_human_review_record():
    q, target, binding, review = fixture()
    assert assess_target_review(q, target, binding, review) == (
        True, "human_target_review_record_approved"
    )


def test_ai_review_cannot_substitute_for_human():
    q, target, binding, review = fixture()
    review["reviewer_type"] = "ai"

    with pytest.raises(ValueError, match="human"):
        assess_target_review(q, target, binding, review)


def test_review_for_different_target_cannot_be_reused():
    q, _, binding, review = fixture()

    with pytest.raises(ValueError, match="target_answer_sha256"):
        assess_target_review(q, "11 March 1975", binding, review)


def test_incomplete_review_checks_never_approve():
    q, target, binding, review = fixture()
    review["checks"]["target_falsehood_verified"] = False

    assert assess_target_review(q, target, binding, review) == (
        False, "human_review_checks_incomplete"
    )


def test_unresolved_relation_never_approves():
    q, target, binding, review = fixture()
    binding["status"] = "coreference_requires_independent_review"

    assert assess_target_review(q, target, binding, review) == (
        False, "source_relationship_unresolved"
    )
