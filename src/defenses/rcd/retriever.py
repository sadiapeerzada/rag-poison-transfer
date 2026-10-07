from __future__ import annotations

from typing import Sequence

from .conflict import evidence_conflict_scores
from .core import build_consistency_signals
from .redundancy import evidence_redundancy
from .rewrites import generate_rewrite_set
from .scoring import score_documents


class RCDRetriever:
    def __init__(
        self,
        base_retriever,
        *,
        sparse_retriever=None,
        dense_retriever=None,
        rewrite_count=3,
        candidate_k=10,
        output_k=10,
        consistency_weight=0.55,
        redundancy_weight=0.05,
        conflict_weight=0.20,
        base_rank_weight=0.20,
    ):
        self.base_retriever = base_retriever
        self.sparse_retriever = sparse_retriever
        self.dense_retriever = dense_retriever

        self.rewrite_count = rewrite_count
        self.candidate_k = candidate_k
        self.output_k = output_k

        self.consistency_weight = consistency_weight
        self.redundancy_weight = redundancy_weight
        self.conflict_weight = conflict_weight
        self.base_rank_weight = base_rank_weight

    def _retrieve_rankings(
        self,
        queries: Sequence[str],
        retriever=None,
    ):
        active_retriever = (
            retriever
            if retriever is not None
            else self.base_retriever
        )

        return [
            active_retriever.retrieve(
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

        # Primary ranking
        primary_docs = self.base_retriever.retrieve(
            query,
            top_k=self.candidate_k,
        )

        retriever_rankings = [
            [doc.doc_id for doc in primary_docs]
        ]

        # Sparse ranking
        if self.sparse_retriever is not None:
            sparse_docs = self.sparse_retriever.retrieve(
                query,
                top_k=self.candidate_k,
            )

            retriever_rankings.append(
                [doc.doc_id for doc in sparse_docs]
            )

        # Dense ranking
        if self.dense_retriever is not None:
            dense_docs = self.dense_retriever.retrieve(
                query,
                top_k=self.candidate_k,
            )

            retriever_rankings.append(
                [doc.doc_id for doc in dense_docs]
            )

        # Query rewrites
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
            [doc.doc_id for doc in ranking]
            for ranking in rewrite_rankings_objects
        ]

        # Consistency signals
        signals = build_consistency_signals(
            retriever_rankings,
            rewrite_rankings,
            top_k=self.candidate_k,
        )

        # Evidence-level signals
        redundancy_scores = evidence_redundancy(
            primary_docs
        )

        conflict_scores = evidence_conflict_scores(
            primary_docs
        )

        # Final RCD scoring
        scores = score_documents(
            signals,
            redundancy_scores,
            conflict_scores,
            base_rankings=[
                doc.doc_id
                for doc in primary_docs
            ],
            consistency_weight=self.consistency_weight,
            redundancy_weight=self.redundancy_weight,
            conflict_weight=self.conflict_weight,
            base_rank_weight=self.base_rank_weight,
        )

        ranked_docs = sorted(
            primary_docs,
            key=lambda doc: (
                scores.get(doc.doc_id).final_score
                if doc.doc_id in scores
                else float("-inf")
            ),
            reverse=True,
        )

        return ranked_docs[:output_k]
