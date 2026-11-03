import pytest

from src.attacks.semantic_document_diversity_v3 import (
    audit_documents, require_distinct
)


def docs(*texts):
    return [
        {"doc_id": f"synthetic-{i}", "text": text}
        for i, text in enumerate(texts)
    ]


def test_distinct_documents_pass():
    rows = docs(
        "Example Person was born in Example City.",
        "Example City is the birthplace of Example Person.",
        "The birthplace of Example Person is Example City.",
    )
    assert require_distinct(rows, 3)["construction_eligible"]


def test_exact_duplicates_rejected():
    rows = docs("Same sentence.", "Same sentence.", "Same sentence.")
    result = audit_documents(rows, 3)
    assert result["status"] == "duplicate_text"
    assert result["unique_normalized_texts"] == 1
    with pytest.raises(ValueError, match="diversity"):
        require_distinct(rows, 3)


def test_punctuation_and_case_do_not_bypass():
    rows = docs("Same sentence.", "SAME SENTENCE!", "Same   sentence")
    assert audit_documents(rows, 3)["status"] == "duplicate_text"


def test_distinct_document_ids_do_not_bypass():
    rows = docs("Identical evidence.", "Identical evidence.")
    assert audit_documents(rows, 2)["duplicate_index_groups"] == [[0, 1]]


def test_incomplete_set_is_not_eligible():
    assert not audit_documents(docs("One document."), 3)[
        "construction_eligible"
    ]


def test_reject_duplicate_document_ids():
    rows = docs("First text.", "Second text.")
    rows[1]["doc_id"] = rows[0]["doc_id"]
    with pytest.raises(ValueError, match="Duplicate document ID"):
        audit_documents(rows, 2)
