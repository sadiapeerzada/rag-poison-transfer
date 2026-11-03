"""Synthetic-only tests: no real research approvals are created."""
import pytest

from src.attacks import development_targets_v5 as parent
from src.attacks import development_targets_v6 as v3
from src.attacks.semantic_evidence_binding_v3 import bind_chronology
from src.attacks.semantic_target_review_v3 import SCHEMA, digest


def setup(monkeypatch):
    question = {
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
        "query_id": "synthetic",
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
            "mechanism": "synthetic_test",
            "provenance": {"source_kind": "synthetic_test"},
        }],
        "method_family": "synthetic_test",
        "reason": None,
    })

    binding = bind_chronology(question, corpus, evidence)

    review = {
        "schema": SCHEMA,
        "query_id": question["query_id"],
        "question_sha256": digest(question["question"]),
        "gold_answer_sha256": digest(question["gold_answer"]),
        "target_answer_sha256": digest(target),
        "source_document_sha256": binding["source_document_sha256"],
        "relation_document_sha256": binding["relation_document_sha256"],
        "reviewer_type": "human",
        "reviewer_id": "synthetic-reviewer",
        "reviewed_at": "2026-11-03T10:00:00+00:00",
        "decision": "approve",
        "checks": {
            "referent_identity_verified": True,
            "target_falsehood_verified": True,
            "gold_aliases_reviewed": True,
            "chronological_plausibility_reviewed": True,
        },
        "falsehood_evidence": (
            "The synthetic biography documents 1969 rather than 1975."
        ),
        "alias_review_notes": (
            "The synthetic gold answer and relevant aliases were reviewed."
        ),
        "plausibility_notes": (
            "The proposed date was checked against the synthetic timeline."
        ),
    }

    return question, corpus, evidence, target, review


def test_missing_review_is_review_only(monkeypatch):
    q, corpus, evidence, _, _ = setup(monkeypatch)
    result = v3.nominate(
        q, [q], chronology_evidence=evidence, corpus=corpus
    )
    assert not result["eligible"]
    assert result["candidates"] == []
    assert len(result["review_candidates"]) == 1
    assert result["reason"] == "v3_independent_target_review_required"


def test_complete_synthetic_review_passes_gate(monkeypatch):
    q, corpus, evidence, target, review = setup(monkeypatch)
    result = v3.nominate(
        q, [q],
        chronology_evidence=evidence,
        corpus=corpus,
        target_reviews={digest(target): review},
    )
    assert result["eligible"]
    assert len(result["candidates"]) == 1
    screening = result["candidates"][0]["v3_screening"]
    assert screening["human_review_record_approved"]
    assert screening["construction_eligible"]
    assert screening["human_review_record_sha256"]


def test_ai_review_cannot_approve(monkeypatch):
    q, corpus, evidence, target, review = setup(monkeypatch)
    review["reviewer_type"] = "ai"
    with pytest.raises(ValueError, match="human"):
        v3.nominate(
            q, [q], chronology_evidence=evidence, corpus=corpus,
            target_reviews={digest(target): review},
        )


def test_rejected_review_does_not_approve(monkeypatch):
    q, corpus, evidence, target, review = setup(monkeypatch)
    review["decision"] = "reject"
    result = v3.nominate(
        q, [q], chronology_evidence=evidence, corpus=corpus,
        target_reviews={digest(target): review},
    )
    assert not result["eligible"]
    assert result["candidates"] == []
    assert result["review_candidates"][0]["v3_screening"][
        "review_gate_reason"
    ] == "human_review_reject"


def test_target_hash_mismatch_rejected(monkeypatch):
    q, corpus, evidence, target, review = setup(monkeypatch)
    review["target_answer_sha256"] = digest("different target")
    with pytest.raises(ValueError, match="target_answer_sha256"):
        v3.nominate(
            q, [q], chronology_evidence=evidence, corpus=corpus,
            target_reviews={digest(target): review},
        )


def test_changed_original_document_rejected(monkeypatch):
    q, corpus, evidence, target, review = setup(monkeypatch)
    corpus[0]["text"] = corpus[0]["text"].replace("1969", "1984")
    with pytest.raises(ValueError, match="verbatim"):
        v3.nominate(
            q, [q], chronology_evidence=evidence, corpus=corpus,
            target_reviews={digest(target): review},
        )
