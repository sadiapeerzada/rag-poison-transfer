"""Development-only v3 semantic document diversity policy.

Checks text-level duplication, not independent factual evidence.
Does not modify earlier frozen construction records.
"""
import re
import unicodedata


def normalized_text(text):
    if not isinstance(text, str):
        raise ValueError("Document text must be a string")
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", value))


def audit_documents(documents, expected_intensity):
    if type(expected_intensity) is not int or expected_intensity < 1:
        raise ValueError("Invalid intensity")
    if not isinstance(documents, list):
        raise ValueError("Documents must be a list")

    seen_ids = set()
    groups = {}

    for index, doc in enumerate(documents):
        if not isinstance(doc, dict):
            raise ValueError("Malformed document")

        doc_id = doc.get("doc_id")
        text = doc.get("text")

        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("Invalid document ID")
        if doc_id in seen_ids:
            raise ValueError("Duplicate document ID")
        seen_ids.add(doc_id)

        key = normalized_text(text)
        if not key:
            raise ValueError("Empty normalized document")
        groups.setdefault(key, []).append(index)

    repeated = [positions for positions in groups.values()
                if len(positions) > 1]

    if len(documents) != expected_intensity:
        status = "incomplete"
    elif repeated:
        status = "duplicate_text"
    else:
        status = "distinct_text"

    return {
        "status": status,
        "document_count": len(documents),
        "expected_intensity": expected_intensity,
        "unique_normalized_texts": len(groups),
        "duplicate_index_groups": repeated,
        "construction_eligible": status == "distinct_text",
        "semantic_independence_verified": False,
    }


def require_distinct(documents, expected_intensity):
    result = audit_documents(documents, expected_intensity)
    if not result["construction_eligible"]:
        raise ValueError("V3 semantic document diversity failure: " + result["status"])
    return result
