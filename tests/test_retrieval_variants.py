"""Tests for dense, hybrid, and reranking retrievers.

Uses HashingEmbedder/MockCrossEncoderScorer -- deterministic stand-ins
for real models, exactly like MockGenerator in test_smoke.py. These
verify the retrieval/fusion/rescoring LOGIC, not real semantic quality
(that requires the real embedder/scorer, run on your Mac).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever, HashingEmbedder
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.reranker import Reranker, MockCrossEncoderScorer


def load_toy_data():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "raw", "toy_smoke_dataset.json",
    )
    with open(path) as f:
        return json.load(f)


def test_dense_retriever_runs_and_returns_top_k():
    data = load_toy_data()
    retriever = DenseRetriever(HashingEmbedder())
    retriever.build(data["corpus"])
    results = retriever.retrieve("Where is the Eiffel Tower located?", top_k=3)
    assert len(results) == 3
    assert all(hasattr(r, "doc_id") for r in results)


def test_hybrid_retriever_fuses_two_retrievers():
    data = load_toy_data()
    hybrid = HybridRetriever(BM25Retriever(), DenseRetriever(HashingEmbedder()))
    hybrid.build(data["corpus"])
    results = hybrid.retrieve("Where is the Eiffel Tower located?", top_k=1)
    assert len(results) == 1
    assert results[0].doc_id == "d1"


def test_hybrid_retriever_scores_are_rrf_not_raw():
    """RRF scores should be small positive fractions (1/(k+rank)), not
    BM25's raw unbounded scores or dense cosine similarities."""
    data = load_toy_data()
    hybrid = HybridRetriever(BM25Retriever(), DenseRetriever(HashingEmbedder()), k_rrf=60)
    hybrid.build(data["corpus"])
    results = hybrid.retrieve("Where is the Eiffel Tower located?", top_k=1)
    # top doc appearing rank-1 in both retrievers => score == 2/(60+1)
    assert abs(results[0].score - 2 / 61) < 1e-6


def test_reranker_rescoring_changes_order_when_warranted():
    data = load_toy_data()
    reranker = Reranker(BM25Retriever(), MockCrossEncoderScorer())
    reranker.build(data["corpus"])
    results = reranker.retrieve("Where is the Eiffel Tower located?", top_k=1)
    assert results[0].doc_id == "d1"


def test_all_retrievers_agree_on_toy_dataset_top1():
    """Sanity check: on this easy toy dataset, all four retrieval
    variants should agree on the top-1 doc. If they ever disagree here,
    something is broken (this dataset has no ambiguity by design)."""
    data = load_toy_data()
    query = "Where is the Eiffel Tower located?"

    bm25 = BM25Retriever()
    bm25.build(data["corpus"])

    dense = DenseRetriever(HashingEmbedder())
    dense.build(data["corpus"])

    hybrid = HybridRetriever(BM25Retriever(), DenseRetriever(HashingEmbedder()))
    hybrid.build(data["corpus"])

    reranker = Reranker(BM25Retriever(), MockCrossEncoderScorer())
    reranker.build(data["corpus"])

    top1_ids = {
        "bm25": bm25.retrieve(query, top_k=1)[0].doc_id,
        "dense": dense.retrieve(query, top_k=1)[0].doc_id,
        "hybrid": hybrid.retrieve(query, top_k=1)[0].doc_id,
        "reranked": reranker.retrieve(query, top_k=1)[0].doc_id,
    }
    assert len(set(top1_ids.values())) == 1, f"Disagreement: {top1_ids}"
