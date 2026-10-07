from __future__ import annotations

import re
from typing import Sequence


_WORD_RE = re.compile(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_YEAR_RE = re.compile(r"\b(?:1[5-9]\d{2}|20\d{2})\b")


def _tokens(text: str) -> set[str]:
    """Return normalized lexical tokens."""
    return set(_WORD_RE.findall(text.lower()))


def extract_numbers(text: str) -> set[str]:
    """Extract numeric values appearing in a passage."""
    return set(_NUMBER_RE.findall(text))


def extract_years(text: str) -> set[str]:
    """Extract four-digit year-like values."""
    return set(_YEAR_RE.findall(text))


def lexical_overlap(text_a: str, text_b: str) -> float:
    """Jaccard overlap between normalized lexical token sets."""
    a = _tokens(text_a)
    b = _tokens(text_b)

    if not a or not b:
        return 0.0

    return len(a & b) / len(a | b)


def factual_anchor_overlap(text_a: str, text_b: str) -> float:
    """Measure overlap in explicit factual anchors.

    Anchors are numbers and year-like values. This is deliberately only
    a supporting signal; it is not treated as proof of contradiction.
    """
    numbers_a = extract_numbers(text_a)
    numbers_b = extract_numbers(text_b)

    years_a = extract_years(text_a)
    years_b = extract_years(text_b)

    anchors_a = numbers_a | years_a
    anchors_b = numbers_b | years_b

    if not anchors_a or not anchors_b:
        return 0.0

    return len(anchors_a & anchors_b) / len(anchors_a | anchors_b)


def support_similarity(text_a: str, text_b: str) -> float:
    """Conservative lexical + factual-anchor similarity.

    The lexical component establishes that two passages discuss related
    content. The anchor component checks whether they share explicit
    factual markers. Neither component is sufficient on its own.
    """
    lexical = lexical_overlap(text_a, text_b)
    anchors = factual_anchor_overlap(text_a, text_b)

    return 0.7 * lexical + 0.3 * anchors


def document_support_scores(
    documents: Sequence,
    *,
    min_similarity: float = 0.15,
) -> dict[str, float]:
    """Score how strongly each document is corroborated by its peers.

    For each document, average its similarity to other candidate documents
    that clear the minimum similarity threshold.

    This uses only candidate document text and therefore does not require
    gold answers, gold document IDs, poison labels, or attack metadata.
    """
    scores = {doc.doc_id: 0.0 for doc in documents}

    for i, doc_a in enumerate(documents):
        supporting = []

        for j, doc_b in enumerate(documents):
            if i == j:
                continue

            similarity = support_similarity(doc_a.text, doc_b.text)

            if similarity >= min_similarity:
                supporting.append(similarity)

        if supporting:
            scores[doc_a.doc_id] = sum(supporting) / len(supporting)

    return scores


def batch_document_support_scores(
    rankings: Sequence[Sequence],
    *,
    min_similarity: float = 0.15,
) -> list[dict[str, float]]:
    """Compute peer-support scores independently for multiple rankings."""
    return [
        document_support_scores(
            documents,
            min_similarity=min_similarity,
        )
        for documents in rankings
    ]
