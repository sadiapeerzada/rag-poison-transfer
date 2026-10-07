from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RCDScore:
    doc_id: str
    consistency: float
    redundancy: float
    conflict: float
    base_rank_score: float
    final_score: float


def score_documents(
    consistency_signals: Dict[str, object],
    redundancy_scores: Dict[str, float],
    conflict_scores: Dict[str, float],
    base_rankings: List[str] | None = None,
    *,
    consistency_weight: float = 0.55,
    redundancy_weight: float = 0.05,
    conflict_weight: float = 0.20,
    base_rank_weight: float = 0.20,
) -> Dict[str, RCDScore]:
    total = (
        consistency_weight
        + redundancy_weight
        + conflict_weight
        + base_rank_weight
    )

    if abs(total - 1.0) > 1e-8:
        raise ValueError(
            "RCD weights must sum to 1.0."
        )

    base_rank_scores = {}

    if base_rankings:
        for rank, doc_id in enumerate(
            base_rankings,
            start=1,
        ):
            base_rank_scores[doc_id] = 1.0 / rank

    output = {}

    for doc_id, signal in consistency_signals.items():
        consistency = float(signal.consistency)
        redundancy = float(
            redundancy_scores.get(doc_id, 0.0)
        )
        conflict = float(
            conflict_scores.get(doc_id, 0.0)
        )
        base_rank_score = float(
            base_rank_scores.get(doc_id, 0.0)
        )

        final_score = (
            consistency_weight * consistency
            + redundancy_weight * redundancy
            - conflict_weight * conflict
            + base_rank_weight * base_rank_score
        )

        output[doc_id] = RCDScore(
            doc_id=doc_id,
            consistency=consistency,
            redundancy=redundancy,
            conflict=conflict,
            base_rank_score=base_rank_score,
            final_score=final_score,
        )

    return output


def select_evidence(
    scores: Dict[str, RCDScore],
    *,
    top_k: int = 5,
) -> List[RCDScore]:
    if top_k <= 0:
        raise ValueError(
            "top_k must be positive."
        )

    return sorted(
        scores.values(),
        key=lambda x: x.final_score,
        reverse=True,
    )[:top_k]
