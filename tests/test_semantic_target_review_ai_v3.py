import copy
import pytest

from src.attacks.semantic_target_review_ai_v3 import (
    SCHEMA, REVIEW_SCHEMA, CHECKS,
    assess_ai_target_reviews, digest,
)


def fixture():
    query = {
        "query_id": "synthetic",
        "question": "When was the director of film Example Film born?",
        "gold_answer": "April 14, 1969",
    }
    target = "10 March 1975"
    binding = {
        "status": "direct_relation_text_grounded",
        "source_document_sha256": digest("biography"),
        "relation_document_sha256": digest("film record"),
    }

    shared = {
        "schema": REVIEW_SCHEMA,
        "query_id": query["query_id"],
        "question_sha256": digest(query["question"]),
        "gold_answer_sha256": digest(query["gold_answer"]),
        "target_answer_sha256": digest(target),
        "source_document_sha256": binding["source_document_sha256"],
        "relation_document_sha256": binding["relation_document_sha256"],
        "reviewer_type": "ai",
        "reviewed_at": "2026-11-03T10:00:00+00:00",
        "decision": "provisional_accept",
        "checks": dict.fromkeys(CHECKS, True),
        "reason": (
            "Synthetic evidence supports the gold and excludes "
            "the proposed alternative without an observed conflict."
        ),
    }

    first = {
        **copy.deepcopy(shared),
        "model_id": "synthetic/model-a",
        "review_run_id": "synthetic-run-a",
        "prompt_sha256": digest("prompt-a"),
        "response_sha256": digest("response-a"),
    }

    second = {
        **copy.deepcopy(shared),
        "model_id": "synthetic/model-b",
        "review_run_id": "synthetic-run-b",
        "prompt_sha256": digest("prompt-b"),
        "response_sha256": digest("response-b"),
    }

    return query, target, binding, {
        "schema": SCHEMA,
        "reviews": [first, second],
    }


def assess(q, target, binding, pair):
    return assess_ai_target_reviews(q, target, binding, pair)


def test_missing_pair():
    q, t, b, _ = fixture()
    assert assess(q, t, b, None) == (
        False, "two_ai_reviews_missing"
    )


def test_complete_synthetic_pair():
    q, t, b, p = fixture()
    assert assess(q, t, b, p) == (
        True, "two_ai_reviews_provisionally_accept_development_only"
    )


def test_unresolved_relationship():
    q, t, b, p = fixture()
    b["status"] = "coreference_requires_independent_review"
    assert assess(q, t, b, p)[0] is False


def test_rejection_fails_closed():
    q, t, b, p = fixture()
    p["reviews"][1]["decision"] = "reject"
    assert assess(q, t, b, p)[0] is False


def test_uncertainty_fails_closed():
    q, t, b, p = fixture()
    p["reviews"][1]["decision"] = "uncertain"
    assert assess(q, t, b, p)[0] is False


def test_failed_check_fails_closed():
    q, t, b, p = fixture()
    p["reviews"][1]["checks"]["referent_grounded"] = False
    assert assess(q, t, b, p)[0] is False


def test_source_hash_mismatch():
    q, t, b, p = fixture()
    p["reviews"][0]["source_document_sha256"] = digest("wrong")
    with pytest.raises(ValueError, match="source_document_sha256"):
        assess(q, t, b, p)


def test_target_hash_mismatch():
    q, t, b, p = fixture()
    with pytest.raises(ValueError, match="target_answer_sha256"):
        assess(q, "different target", b, p)


def test_human_cannot_masquerade_as_ai():
    q, t, b, p = fixture()
    p["reviews"][0]["reviewer_type"] = "human"
    with pytest.raises(ValueError, match="identified as AI"):
        assess(q, t, b, p)


def test_same_model_not_accepted():
    q, t, b, p = fixture()
    p["reviews"][1]["model_id"] = p["reviews"][0]["model_id"]
    assert assess(q, t, b, p)[0] is False


def test_same_response_not_accepted():
    q, t, b, p = fixture()
    p["reviews"][1]["response_sha256"] = (
        p["reviews"][0]["response_sha256"]
    )
    assert assess(q, t, b, p)[0] is False
