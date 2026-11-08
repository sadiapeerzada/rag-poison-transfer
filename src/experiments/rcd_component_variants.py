"""Isolated RCD ablation implementation — does not modify frozen RCDRetriever.

The only subclass is the *no agreement signal* variant. All other variants
use run.build_retriever on explicitly versioned configurations.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from src.defenses.rcd.retriever import RCDRetriever
from src.defenses.rcd.conflict import evidence_conflict_scores
from src.defenses.rcd.core import build_consistency_signals
from src.defenses.rcd.redundancy import evidence_redundancy
from src.defenses.rcd.rewrites import generate_rewrite_set
from src.defenses.rcd.scoring import score_documents


@dataclass(frozen=True)
class _NoAgreementSignal:
    agreement: float
    rank_stability: float
    rewrite_stability: float

    @property
    def consistency(self):
        return (self.rank_stability + self.rewrite_stability) / 2.0


class NoAgreementRCDRetriever(RCDRetriever):
    """True per-signal agreement ablation; same candidate-pool retrieval.

    This intentionally reproduces the original RCD retrieval path instead of
    monkey-patching the globally imported frozen scoring function. The baseline
    remains the unmodified original class; differences here are a *new study*.
    """

    def retrieve(self, query: str, *, top_k: int | None = None):
        output_k = top_k if top_k is not None else self.output_k
        retrieval_call_count = 0
        retrieval_start = time.perf_counter()

        primary_docs = self.base_retriever.retrieve(query, top_k=self.candidate_k)
        retrieval_call_count += 1
        candidate_docs = {doc.doc_id: doc for doc in primary_docs}
        retriever_rankings = [[doc.doc_id for doc in primary_docs]]

        if self.sparse_retriever is not None:
            sparse_docs = self.sparse_retriever.retrieve(query, top_k=self.candidate_k)
            retrieval_call_count += 1
            retriever_rankings.append([doc.doc_id for doc in sparse_docs])
            candidate_docs.update({doc.doc_id: doc for doc in sparse_docs})

        if self.dense_retriever is not None and self.dense_retriever is not self.base_retriever:
            dense_docs = self.dense_retriever.retrieve(query, top_k=self.candidate_k)
            retrieval_call_count += 1
            retriever_rankings.append([doc.doc_id for doc in dense_docs])
            candidate_docs.update({doc.doc_id: doc for doc in dense_docs})

        rewrite_queries = generate_rewrite_set(query, n_rewrites=self.rewrite_count)
        rewrite_rankings_objects = self._retrieve_rankings(rewrite_queries)
        retrieval_call_count += len(rewrite_queries)
        rewrite_rankings = [
            [doc.doc_id for doc in ranking] for ranking in rewrite_rankings_objects
        ]
        for ranking in rewrite_rankings_objects:
            candidate_docs.update({doc.doc_id: doc for doc in ranking})

        original_signals = build_consistency_signals(
            retriever_rankings, rewrite_rankings, top_k=self.candidate_k
        )
        projected = {
            doc_id: _NoAgreementSignal(
                agreement=signal.agreement,
                rank_stability=signal.rank_stability,
                rewrite_stability=signal.rewrite_stability,
            )
            for doc_id, signal in original_signals.items()
        }
        all_candidate_docs = list(candidate_docs.values())
        redundancy_scores = evidence_redundancy(all_candidate_docs)
        conflict_scores = evidence_conflict_scores(all_candidate_docs)
        scores = score_documents(
            projected,
            redundancy_scores,
            conflict_scores,
            base_rankings=[doc.doc_id for doc in primary_docs],
            consistency_weight=self.consistency_weight,
            redundancy_weight=self.redundancy_weight,
            conflict_weight=self.conflict_weight,
            base_rank_weight=self.base_rank_weight,
        )
        ranked_docs = sorted(
            all_candidate_docs,
            key=lambda d: scores[d.doc_id].final_score
            if d.doc_id in scores else float("-inf"),
            reverse=True,
        )
        retrieval_latency_seconds = time.perf_counter() - retrieval_start
        self.last_diagnostics = {
            "retrieval_call_count": retrieval_call_count,
            "retrieval_latency_seconds": retrieval_latency_seconds,
            "rewrite_queries": list(rewrite_queries),
            "retriever_rankings": retriever_rankings,
            "rewrite_rankings": rewrite_rankings,
            "consistency_signals": {
                doc_id: {
                    "agreement": sig.agreement,
                    "rank_stability": sig.rank_stability,
                    "rewrite_stability": sig.rewrite_stability,
                    "consistency": sig.consistency,
                }
                for doc_id, sig in projected.items()
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
            "selected_doc_ids": [doc.doc_id for doc in ranked_docs[:output_k]],
            "ablation": "agreement_signal_dropped_from_consistency_mean",
        }
        return ranked_docs[:output_k]


def retriever_config(variant, embedder_model):
    """Construct an explicit new-study config from a pinned preflight variant."""
    if variant.get("top_k") not in (1, 3, 5) or variant.get("rewrite_count") not in (0, 3):
        raise ValueError("Unexpected ablation variant dimensions")
    cfg = {
        "retriever": "rcd",
        "embedder_model": embedder_model,
        "top_k": variant["top_k"],
        "rcd_candidate_k": 10,
        "rcd_rewrite_count": variant["rewrite_count"],
        "rcd_consistency_weight": variant["consistency_weight"],
        "rcd_redundancy_weight": variant["redundancy_weight"],
        "rcd_conflict_weight": variant["conflict_weight"],
        "rcd_base_rank_weight": variant["base_rank_weight"],
    }
    weights = (cfg["rcd_consistency_weight"], cfg["rcd_redundancy_weight"],
               cfg["rcd_conflict_weight"], cfg["rcd_base_rank_weight"])
    if abs(sum(weights) - 1.0) > 1e-8:
        raise ValueError("Variant weights must sum to 1")
    return cfg


def build_variant(variant, embedder_model):
    cfg = retriever_config(variant, embedder_model)
    if variant["consistency_mode"] == "all":
        from run import build_retriever
        return build_retriever(cfg)
    if variant["consistency_mode"] != "rank_and_rewrite_stability_only":
        raise ValueError("Unknown RCD consistency projection")
    from src.retrieval.bm25 import BM25Retriever
    from src.retrieval.dense import DenseRetriever, SentenceTransformerEmbedder
    dense = DenseRetriever(SentenceTransformerEmbedder(embedder_model))
    return NoAgreementRCDRetriever(
        dense, sparse_retriever=BM25Retriever(), dense_retriever=dense,
        candidate_k=cfg["rcd_candidate_k"], output_k=cfg["top_k"],
        rewrite_count=cfg["rcd_rewrite_count"],
        consistency_weight=cfg["rcd_consistency_weight"],
        redundancy_weight=cfg["rcd_redundancy_weight"],
        conflict_weight=cfg["rcd_conflict_weight"],
        base_rank_weight=cfg["rcd_base_rank_weight"],
    )
