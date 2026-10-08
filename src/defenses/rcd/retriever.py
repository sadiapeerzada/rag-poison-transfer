from __future__ import annotations

import time
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

        # Diagnostics from the most recent retrieval call.
        # Kept separate from the public retrieve() return value so
        # existing retrieval/evaluation code remains backward compatible.
        self.last_diagnostics = None

    def build(self, corpus: list[dict]) -> None:
        """Build all configured retriever components on the same corpus."""
        built = set()

        for retriever in (
            self.base_retriever,
            self.sparse_retriever,
            self.dense_retriever,
        ):
            if retriever is None:
                continue

            retriever_id = id(retriever)

            if retriever_id in built:
                continue

            retriever.build(corpus)
            built.add(retriever_id)

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

        retrieval_call_count = 0
        retrieval_start = time.perf_counter()

        # Primary ranking
        primary_docs = self.base_retriever.retrieve(
            query,
            top_k=self.candidate_k,
        )
        retrieval_call_count += 1

        # Keep a document-object pool so evidence found by any
        # configured retriever or rewrite can be selected downstream.
        candidate_docs = {
            doc.doc_id: doc
            for doc in primary_docs
        }

        retriever_rankings = [
            [doc.doc_id for doc in primary_docs]
        ]

        # Sparse ranking
        if self.sparse_retriever is not None:
            sparse_docs = self.sparse_retriever.retrieve(
                query,
                top_k=self.candidate_k,
            )
            retrieval_call_count += 1

            retriever_rankings.append(
                [doc.doc_id for doc in sparse_docs]
            )

            candidate_docs.update(
                {doc.doc_id: doc for doc in sparse_docs}
            )

        # Dense ranking
        if (
            self.dense_retriever is not None
            and self.dense_retriever is not self.base_retriever
        ):
            dense_docs = self.dense_retriever.retrieve(
                query,
                top_k=self.candidate_k,
            )
            retrieval_call_count += 1

            retriever_rankings.append(
                [doc.doc_id for doc in dense_docs]
            )

            candidate_docs.update(
                {doc.doc_id: doc for doc in dense_docs}
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
        retrieval_call_count += len(rewrite_queries)

        rewrite_rankings = [
            [doc.doc_id for doc in ranking]
            for ranking in rewrite_rankings_objects
        ]

        for ranking in rewrite_rankings_objects:
            candidate_docs.update(
                {doc.doc_id: doc for doc in ranking}
            )

        # Consistency signals
        signals = build_consistency_signals(
            retriever_rankings,
            rewrite_rankings,
            top_k=self.candidate_k,
        )

        # Evidence-level signals
        all_candidate_docs = list(candidate_docs.values())

        redundancy_scores = evidence_redundancy(
            all_candidate_docs
        )

        conflict_scores = evidence_conflict_scores(
            all_candidate_docs
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
            all_candidate_docs,
            key=lambda doc: (
                scores.get(doc.doc_id).final_score
                if doc.doc_id in scores
                else float("-inf")
            ),
            reverse=True,
        )

        retrieval_latency_seconds = (
            time.perf_counter() - retrieval_start
        )

        # Preserve the internal RCD signals for experiment logging,
        # analysis, ablations, and later failure/error analysis.
        self.last_diagnostics = {
            "retrieval_call_count": retrieval_call_count,
            "retrieval_latency_seconds": retrieval_latency_seconds,
            "rewrite_queries": list(rewrite_queries),
            "retriever_rankings": retriever_rankings,
            "rewrite_rankings": rewrite_rankings,
            "consistency_signals": {
                doc_id: {
                    "agreement": signal.agreement,
                    "rank_stability": signal.rank_stability,
                    "rewrite_stability": signal.rewrite_stability,
                    "consistency": signal.consistency,
                }
                for doc_id, signal in signals.items()
            },
            "redundancy_scores": dict(redundancy_scores),
            "conflict_scores": dict(conflict_scores),
            "scores": {
                doc_id: {
                    "consistency": score.consistency,
                    "redundancy": score.redundancy,
                    "conflict": score.conflict,
                    "base_rank_score": score.base_rank_score,
                    "final_score": score.final_score,
                }
                for doc_id, score in scores.items()
            },
            "selected_doc_ids": [
                doc.doc_id
                for doc in ranked_docs[:output_k]
            ],
        }

        return ranked_docs[:output_k]
