import pytest

from src.attacks import development_targets_v5 as parent
from src.attacks import development_targets_v6 as v3


def fixture():
    return {
        "query_id": "synthetic-query",
        "question": "When did Example Person die?",
        "gold_answer": "July 24, 1993",
        "gold_aliases": [],
    }


def mock_parent(monkeypatch):
    monkeypatch.setattr(parent, "nominate", lambda q, dev: {
        "eligible": True,
        "candidates": [{
            "answer": "10 September 1759",
            "answer_category": "calendar_date",
            "provenance": {"source_kind": "synthetic_test"},
        }],
        "method_family": "synthetic_test",
        "reason": None,
    })



def film_chain():
    q = fixture()
    q["question"] = "When was the director of film Example Film born?"
    q["gold_doc_ids"] = ["bio", "film"]

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
    return q, corpus, evidence


def test_direct_relation_is_grounded_not_factually_approved(monkeypatch):
    mock_parent(monkeypatch)
    q, corpus, evidence = film_chain()

    result = v3.nominate(
        q, [q], chronology_evidence=evidence, corpus=corpus
    )

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert result["reason"] == "v3_independent_target_review_required"
    assert len(result["review_candidates"]) == 1

    screening = result["review_candidates"][0]["v3_screening"]
    assert screening["evidence_binding_status"] == "direct_relation_text_grounded"
    assert screening["factual_approval"] is False
    assert screening["construction_eligible"] is False
    assert screening["review_gate_reason"] == "independent_human_review_missing"


def test_unresolved_parent_coreference_abstains(monkeypatch):
    mock_parent(monkeypatch)
    q = fixture()
    q["question"] = "When did Robin J. Person's father die?"
    q["gold_doc_ids"] = ["parent", "child"]

    corpus = [
        {
            "doc_id": "parent",
            "text": "Alex Samuel Example (February 15, 1899 – July 24, 1993) was a historian.",
        },
        {
            "doc_id": "child",
            "text": (
                "Robin Joel Person (June 23, 1933 – March 25, 1984) was a physician. "
                "He was born to historian Alex S. Example."
            ),
        },
    ]
    evidence = {
        "query_id": q["query_id"],
        "source_doc_id": "parent",
        "source_quote": corpus[0]["text"],
        "source_name": "Alex Samuel Example",
        "relation_doc_id": "child",
        "relation_quote": "He was born to historian Alex S. Example.",
        "relation_name": "Alex S. Example",
    }

    result = v3.nominate(
        q, [q], chronology_evidence=evidence, corpus=corpus
    )

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert result["reason"] == "v3_unresolved_referent_requires_review"


def test_missing_evidence_is_not_approval(monkeypatch):
    mock_parent(monkeypatch)
    q = fixture()

    result = v3.nominate(q, [q])

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert result["reason"] == "v3_missing_grounded_evidence"
    assert len(result["review_candidates"]) == 1

    screening = result["review_candidates"][0]["v3_screening"]
    assert screening["status"] == "undetermined"
    assert screening["factual_approval"] is False
    assert screening["construction_eligible"] is False
    assert screening["review_only"] is True


def test_no_original_candidates_remains_abstention(monkeypatch):
    monkeypatch.setattr(parent, "nominate", lambda q, dev: {
        "eligible": False,
        "candidates": [],
        "method_family": "synthetic_test",
        "reason": "original_abstention",
    })

    result = v3.nominate(fixture(), [])

    assert result["eligible"] is False
    assert result["candidates"] == []
    assert result["review_candidates"] == []
    assert result["reason"] == "original_abstention"


def test_unverified_quote_rejected(monkeypatch):
    mock_parent(monkeypatch)
    q, corpus, evidence = film_chain()
    evidence["source_quote"] = (
        "Alex Morgan (born April 14, 1984) is a film director."
    )

    with pytest.raises(ValueError, match="verbatim"):
        v3.nominate(q, [q], chronology_evidence=evidence, corpus=corpus)


def test_evidence_without_corpus_rejected(monkeypatch):
    mock_parent(monkeypatch)
    q, _, evidence = film_chain()

    with pytest.raises(ValueError, match="Pinned corpus"):
        v3.nominate(q, [q], chronology_evidence=evidence)


def test_caller_cannot_inject_derived_birth_year(monkeypatch):
    mock_parent(monkeypatch)
    q, corpus, evidence = film_chain()
    evidence["documented_birth_year"] = 1899

    with pytest.raises(ValueError, match="Caller-supplied"):
        v3.nominate(q, [q], chronology_evidence=evidence, corpus=corpus)


def test_dev_only_descriptor():
    value = v3.descriptor()
    assert value["identifier"] == v3.IDENTIFIER
    v3.validate(value, "development")
    with pytest.raises(ValueError):
        v3.validate(value, "heldout")
