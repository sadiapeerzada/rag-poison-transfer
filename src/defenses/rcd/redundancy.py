from __future__ import annotations

import re
from typing import Dict, Sequence


def _tokens(text: str) -> set[str]:
    return set(
        re.findall(
            r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b",
            text.lower(),
        )
    )


def token_overlap(text_a: str, text_b: str) -> float:
    tokens_a = _tokens(text_a)
    tokens_b = _tokens(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def evidence_redundancy(
    documents,
    *,
    min_overlap: float = 0.1,
) -> Dict[str, float]:
    scores = {
        doc.doc_id: 0.0
        for doc in documents
    }

    for i, doc_a in enumerate(documents):
        overlaps = []

        for j, doc_b in enumerate(documents):
            if i == j:
                continue

            overlap = token_overlap(
                doc_a.text,
                doc_b.text,
            )

            if overlap >= min_overlap:
                overlaps.append(overlap)

        if overlaps:
            scores[doc_a.doc_id] = (
                sum(overlaps) / len(overlaps)
            )

    return scores


def batch_evidence_redundancy(
    rankings,
    *,
    min_overlap: float = 0.1,
):
    return [
        evidence_redundancy(
            documents,
            min_overlap=min_overlap,
        )
        for documents in rankings
    ]
