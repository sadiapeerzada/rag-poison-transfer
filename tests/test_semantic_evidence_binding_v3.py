import pytest

from src.attacks.semantic_evidence_binding_v3 import bind_chronology


def example():
    query = {
        "query_id": "synthetic",
        "question": "When was the director of film Example Film born?",
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
        "source_quote": "Alex Morgan (born April 14, 1969) is a film director.",
        "source_name": "Alex Morgan",
        "relation_doc_id": "film",
        "relation_quote": "Example Film is a drama directed by Alex Morgan.",
        "relation_name": "Alex Morgan",
    }
    return query, corpus, evidence


def test_direct_relation_grounded():
    q, corpus, evidence = example()
    result = bind_chronology(q, corpus, evidence)
    assert result["status"] == "direct_relation_text_grounded"
    assert result["documented_birth_year"] == 1969
    assert result["factual_approval"] is False


def test_fabricated_quote_rejected():
    q, corpus, evidence = example()
    evidence["source_quote"] = "Alex Morgan (born April 14, 1850) is a film director."
    with pytest.raises(ValueError, match="verbatim"):
        bind_chronology(q, corpus, evidence)


def test_wrong_document_rejected():
    q, corpus, evidence = example()
    evidence["source_doc_id"] = "unrelated"
    with pytest.raises(ValueError, match="supporting sources"):
        bind_chronology(q, corpus, evidence)


def test_wrong_relation_rejected():
    q, corpus, evidence = example()
    evidence["relation_quote"] = "Example Film is a drama directed by Alex Morgan."
    evidence["relation_name"] = "Taylor Morgan"
    with pytest.raises(ValueError):
        bind_chronology(q, corpus, evidence)


def test_pronoun_relation_not_automatically_approved():
    q = {
        "query_id": "synthetic",
        "question": "When did Robin J. Person's father die?",
        "gold_doc_ids": ["parent", "child"],
    }
    corpus = [
        {
            "doc_id": "parent",
            "text": "Alex Samuel Example (February 15, 1899 – July 24, 1993) was a historian.",
        },
        {
            "doc_id": "child",
            "text": "Robin Joel Person (June 23, 1933 – March 25, 1984) was a physician. "
                    "He was born to historian Alex S. Example.",
        },
    ]
    evidence = {
        "query_id": "synthetic",
        "source_doc_id": "parent",
        "source_quote": corpus[0]["text"],
        "source_name": "Alex Samuel Example",
        "relation_doc_id": "child",
        "relation_quote": "He was born to historian Alex S. Example.",
        "relation_name": "Alex S. Example",
    }
    result = bind_chronology(q, corpus, evidence)
    assert result["status"] == "coreference_requires_independent_review"
    assert result["documented_birth_year"] is None
    assert result["factual_approval"] is False
