import copy

import pytest

from src.attacks import development_targets_v5 as parent
from src.attacks import development_targets_v6 as v3
from src.attacks.semantic_evidence_binding_v3 import bind_chronology
from src.attacks.semantic_target_review_ai_v3 import (
    SCHEMA, REVIEW_SCHEMA, CHECKS, digest,
)


def fixture(monkeypatch):
    q = {
        "query_id": "synthetic",
        "question": "When was the director of film Example Film born?",
        "gold_answer": "April 14, 1969",
        "gold_aliases": [],
        "gold_doc_ids": ["bio", "film"],
    }

    corpus = [
        {
            "doc_id": "bio",
            "text": "Alex Morgan (born April 14, 1969) is a film director.",
        },
        {
            "doc_id": "film",
            "text": "Example Film is a drama directed by Alex Morgan.",
        },
    ]

    evidence = {
        "query_id": q["query_id"],
        "source_doc_id": "bio",
        "source_quote": corpus[0]["text"],
        "source_name": "Alex Morgan",
        "relation_doc_id": "film",
        "relation_quote": corpus[1]["text"],
        "relation_name": "Alex Morgan",
    }

    target = "10 March 1975"

    monkeypatch.setattr(parent, "nominate", lambda q, dev: {
        "eligible": True,
        "candidates": [{
            "answer": target,
            "answer_category": "calendar_date",
            "provenance": {"source_kind": "synthetic_test"},
        }],
        "method_family": "synthetic_test",
        "reason": None,
    })

    binding = bind_chronology(q, corpus, evidence)

    shared = {
        "schema": REVIEW_SCHEMA,
        "query_id": q["query_id"],
        "question_sha256": digest(q["question"]),
        "gold_answer_sha256": digest(q["gold_answer"]),
        "target_answer_sha256": digest(target),
        "source_document_sha256": binding["source_document_sha256"],
        "relation_document_sha256": binding["relation_document_sha256"],
        "reviewer_type": "ai",
        "reviewed_at": "2026-11-03T10:00:00+00:00",
        "decision": "provisional_accept",
        "checks": dict.fromkeys(CHECKS, True),
        "reason": (
            "Synthetic source evidence supports the original date "
            "and distinguishes it from the proposed alternative."
        ),
    }

    reviews = []
    for name in ("a", "b"):
        reviews.append({
            **copy.deepcopy(shared),
            "model_id": "synthetic/model-" + name,
            "review_run_id": "synthetic-run-" + name,
            "prompt_sha256": digest("prompt-" + name),
            "response_sha256": digest("response-" + name),
        })

    pair = {"schema": SCHEMA, "reviews": reviews}
    return q, corpus, evidence, target, pair


def run(q, corpus, evidence, reviews=None):
    return v3.nominate_ai(
        q,
        [q],
        chronology_evidence=evidence,
        corpus=corpus,
        ai_target_reviews=reviews,
    )


def test_missing_ai_reviews_remain_pending(monkeypatch):
    q, corpus, evidence, _, _ = fixture(monkeypatch)
    result = run(q, corpus, evidence)

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert len(result["review_candidates"]) == 1
    assert result["reason"] == "v3_two_ai_review_required"


def test_two_ai_synthetic_pair_passes_screening(monkeypatch):
    q, corpus, evidence, target, pair = fixture(monkeypatch)
    result = run(
        q, corpus, evidence, {digest(target): pair}
    )

    assert result["eligible"] is True
    assert len(result["candidates"]) == 1

    screening = result["candidates"][0]["v3_screening"]

    assert screening["ai_screening_passed"] is True
    assert screening["construction_eligible"] is True
    assert screening["factual_approval"] is False
    assert screening["injection_approved"] is False
    assert "human_review_record_approved" not in screening


def test_uncertain_second_ai_blocks_candidate(monkeypatch):
    q, corpus, evidence, target, pair = fixture(monkeypatch)
    pair["reviews"][1]["decision"] = "uncertain"

    result = run(
        q, corpus, evidence, {digest(target): pair}
    )

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert len(result["review_candidates"]) == 1


def test_same_model_blocks_candidate(monkeypatch):
    q, corpus, evidence, target, pair = fixture(monkeypatch)
    pair["reviews"][1]["model_id"] = pair["reviews"][0]["model_id"]

    result = run(
        q, corpus, evidence, {digest(target): pair}
    )

    assert result["eligible"] is False


def test_wrong_target_hash_rejected(monkeypatch):
    q, corpus, evidence, _, pair = fixture(monkeypatch)

    with pytest.raises(ValueError, match="unknown target"):
        run(
            q, corpus, evidence,
            {digest("different target"): pair},
        )


def test_no_source_evidence_still_blocks(monkeypatch):
    q, _, _, target, pair = fixture(monkeypatch)

    result = v3.nominate_ai(
        q,
        [q],
        ai_target_reviews={digest(target): pair},
    )

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert result["injection_approved"] is False
