from __future__ import annotations

from .core import build_consistency_signals
from .rewrites import generate_rewrite_set
from src.retrieval.reranker import CrossEncoderScorer


class RCDV2Retriever:
    """Query-conditioned RCD using a cross-encoder relevance signal."""

    def __init__(
        self,
        base_retriever,
        *,
        candidate_k: int = 10,
        output_k: int = 10,
        rewrite_count: int = 3,
        cross_encoder_model: str = (
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ),
        relevance_weight: float = 0.90,
        consistency_weight: float = 0.10,
    ):
        if abs(
            relevance_weight
            + consistency_weight
            - 1.0
        ) > 1e-8:
            raise ValueError(
                "RCD-v2 weights must sum to 1.0."
            )

        self.base_retriever = base_retriever
        self.candidate_k = candidate_k
        self.output_k = output_k
        self.rewrite_count = rewrite_count

        self.relevance_weight = relevance_weight
        self.consistency_weight = consistency_weight

        self.scorer = CrossEncoderScorer(
            cross_encoder_model
        )

    def _retrieve_rankings(
        self,
        queries: list[str],
    ):
        return [
            self.base_retriever.retrieve(
                query,
                top_k=self.candidate_k,
            )
            for query in queries
        ]

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ):
        output_k = (
            top_k
            if top_k is not None
            else self.output_k
        )

        primary_docs = self.base_retriever.retrieve(
            query,
            top_k=self.candidate_k,
        )

        primary_ids = [
            doc.doc_id
            for doc in primary_docs
        ]

        retriever_rankings = [
            primary_ids
        ]

        rewrite_queries = generate_rewrite_set(
            query,
            n_rewrites=self.rewrite_count,
        )

        rewrite_rankings_objects = (
            self._retrieve_rankings(
                rewrite_queries
            )
        )

        rewrite_rankings = [
            [
                doc.doc_id
                for doc in ranking
            ]
            for ranking in rewrite_rankings_objects
        ]

        signals = build_consistency_signals(
            retriever_rankings,
            rewrite_rankings,
            top_k=self.candidate_k,
        )

        relevance_scores = {
            doc.doc_id: self.scorer.score(
                query,
                doc.text,
            )
            for doc in primary_docs
        }

        relevance_values = list(
            relevance_scores.values()
        )

        min_score = min(relevance_values)
        max_score = max(relevance_values)

        score_range = max_score - min_score

        if score_range > 0:
            normalized_relevance = {
                doc_id: (
                    score - min_score
                ) / score_range
                for doc_id, score
                in relevance_scores.items()
            }
        else:
            normalized_relevance = {
                doc_id: 1.0
                for doc_id in relevance_scores
            }

        final_scores = {}

        for doc in primary_docs:
            consistency = signals.get(
                doc.doc_id
            )

            consistency_value = (
                consistency.consistency
                if consistency is not None
                else 0.0
            )

            final_scores[doc.doc_id] = (
                self.relevance_weight
                * normalized_relevance[doc.doc_id]
                + self.consistency_weight
                * consistency_value
            )

        ranked_docs = sorted(
            primary_docs,
            key=lambda doc: (
                final_scores[doc.doc_id],
                -primary_ids.index(doc.doc_id),
            ),
            reverse=True,
        )

        return ranked_docs[:output_k]
