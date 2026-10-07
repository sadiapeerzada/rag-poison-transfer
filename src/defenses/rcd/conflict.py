from __future__ import annotations

import re


_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_YEAR_RE = re.compile(r"\b(?:1[5-9]\d{2}|20\d{2})\b")


def extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def extract_years(text: str) -> set[int]:
    return {
        int(value)
        for value in _YEAR_RE.findall(text)
    }


def claim_conflict(
    text_a: str,
    text_b: str,
) -> float:
    years_a = extract_years(text_a)
    years_b = extract_years(text_b)

    if not years_a or not years_b:
        return 0.0

    tokens_a = set(
        re.findall(r"\b[a-zA-Z]+\b", text_a.lower())
    )
    tokens_b = set(
        re.findall(r"\b[a-zA-Z]+\b", text_b.lower())
    )

    union = tokens_a | tokens_b

    if not union:
        return 0.0

    lexical_similarity = (
        len(tokens_a & tokens_b) / len(union)
    )

    if lexical_similarity < 0.50:
        return 0.0

    if years_a.isdisjoint(years_b):
        return 1.0

    return 0.0


def evidence_conflict_scores(documents):
    scores = {
        doc.doc_id: 0.0
        for doc in documents
    }

    for i, doc_a in enumerate(documents):
        for j, doc_b in enumerate(documents):
            if i >= j:
                continue

            conflict = claim_conflict(
                doc_a.text,
                doc_b.text,
            )

            if conflict:
                scores[doc_a.doc_id] = max(
                    scores[doc_a.doc_id],
                    conflict,
                )
                scores[doc_b.doc_id] = max(
                    scores[doc_b.doc_id],
                    conflict,
                )

    return scores
