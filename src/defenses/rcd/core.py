from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class RetrievedItem:
    doc_id: str
    rank: int


@dataclass(frozen=True)
class ConsistencySignals:
    agreement: float
    rank_stability: float
    rewrite_stability: float

    @property
    def consistency(self) -> float:
        return (
            self.agreement
            + self.rank_stability
            + self.rewrite_stability
        ) / 3.0


def _rank_map(ranking: Sequence[str]) -> Dict[str, int]:
    return {
        doc_id: rank
        for rank, doc_id in enumerate(ranking, start=1)
    }


def jaccard_similarity(
    ranking_a: Sequence[str],
    ranking_b: Sequence[str],
    *,
    top_k: int = 10,
) -> float:
    a = set(ranking_a[:top_k])
    b = set(ranking_b[:top_k])

    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    return len(a & b) / len(a | b)


def reciprocal_rank_similarity(
    ranking_a: Sequence[str],
    ranking_b: Sequence[str],
    *,
    top_k: int = 10,
) -> float:
    ranks_a = _rank_map(ranking_a[:top_k])
    ranks_b = _rank_map(ranking_b[:top_k])

    shared = set(ranks_a) & set(ranks_b)

    if not shared:
        return 0.0

    scores = []

    for doc_id in shared:
        rank_a = ranks_a[doc_id]
        rank_b = ranks_b[doc_id]

        scores.append(
            min(1.0, min(rank_a, rank_b) / max(rank_a, rank_b))
        )

    return sum(scores) / len(scores)


def retriever_agreement(
    rankings: Sequence[Sequence[str]],
    *,
    top_k: int = 10,
) -> float:
    if len(rankings) < 2:
        return 1.0

    scores = []

    for i in range(len(rankings)):
        for j in range(i + 1, len(rankings)):
            scores.append(
                jaccard_similarity(
                    rankings[i],
                    rankings[j],
                    top_k=top_k,
                )
            )

    return sum(scores) / len(scores) if scores else 0.0


def cross_retriever_rank_stability(
    rankings: Sequence[Sequence[str]],
    *,
    top_k: int = 10,
) -> float:
    if len(rankings) < 2:
        return 1.0

    scores = []

    for i in range(len(rankings)):
        for j in range(i + 1, len(rankings)):
            scores.append(
                reciprocal_rank_similarity(
                    rankings[i],
                    rankings[j],
                    top_k=top_k,
                )
            )

    return sum(scores) / len(scores) if scores else 0.0


def cross_query_rank_stability(
    rankings: Sequence[Sequence[str]],
    *,
    top_k: int = 10,
) -> Dict[str, float]:
    if not rankings:
        return {}

    rank_maps = [
        _rank_map(ranking[:top_k])
        for ranking in rankings
    ]

    doc_ids = set().union(*rank_maps)
    output = {}

    for doc_id in doc_ids:
        observed = [
            ranks[doc_id]
            for ranks in rank_maps
            if doc_id in ranks
        ]

        if not observed:
            output[doc_id] = 0.0
            continue

        output[doc_id] = min(observed) / max(observed)

    return output


def build_consistency_signals(
    retriever_rankings: Sequence[Sequence[str]],
    rewrite_rankings: Sequence[Sequence[str]],
    *,
    top_k: int = 10,
) -> Dict[str, ConsistencySignals]:
    agreement = retriever_agreement(
        retriever_rankings,
        top_k=top_k,
    )

    retriever_rank_stability = cross_query_rank_stability(
        retriever_rankings,
        top_k=top_k,
    )

    rewrite_stability = cross_query_rank_stability(
        rewrite_rankings,
        top_k=top_k,
    )

    doc_ids = set()

    for ranking in retriever_rankings:
        doc_ids.update(ranking[:top_k])

    for ranking in rewrite_rankings:
        doc_ids.update(ranking[:top_k])

    output = {}

    for doc_id in doc_ids:
        output[doc_id] = ConsistencySignals(
            agreement=(
                agreement
                if any(
                    doc_id in ranking[:top_k]
                    for ranking in retriever_rankings
                )
                else 0.0
            ),
            rank_stability=retriever_rank_stability.get(
                doc_id,
                0.0,
            ),
            rewrite_stability=rewrite_stability.get(
                doc_id,
                0.0,
            ),
        )

    return output
