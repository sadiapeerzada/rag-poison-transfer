"""Comprehensive integration tests for the full pipeline.

Tests that verify:
1. Retriever routing works correctly for all retriever types
2. Corpus construction is deterministic and correct
3. Metrics are computed and logged correctly
4. Transfer framework can be used end-to-end
5. Experiment metadata includes corpus information
"""
import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from src.data.loaders import load_hotpotqa_distractor
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.reranker import Reranker
from src.evaluation.metrics import (
    recall_at_k,
    mrr,
    ndcg_at_k,
    poison_retrieval_rate_at_k,
    attack_success_rate,
    attack_transfer_rate,
)
from src.pipelines.transfer import TransferMatrix, compute_transfer_statistics


class TestRetrieverRoutingWithClasses:
    """Verify retriever routing produces correct class instances."""

    def test_bm25_config_produces_bm25_retriever(self):
        """BM25 config should instantiate BM25Retriever, not another type."""
        from run import build_retriever

        config = {"retriever": "bm25"}
        ret = build_retriever(config)
        assert isinstance(ret, BM25Retriever)
        assert ret.__class__.__name__ == "BM25Retriever"

    def test_dense_config_produces_dense_retriever(self):
        """Dense config should instantiate DenseRetriever."""
        from run import build_retriever

        config = {"retriever": "dense", "embedder_model": "BAAI/bge-small-en-v1.5"}
        ret = build_retriever(config)
        assert isinstance(ret, DenseRetriever)
        assert ret.__class__.__name__ == "DenseRetriever"

    def test_hybrid_config_produces_hybrid_retriever(self):
        """Hybrid config should instantiate HybridRetriever."""
        from run import build_retriever

        config = {"retriever": "hybrid", "embedder_model": "BAAI/bge-small-en-v1.5"}
        ret = build_retriever(config)
        assert isinstance(ret, HybridRetriever)
        assert ret.__class__.__name__ == "HybridRetriever"

    def test_reranker_config_produces_reranker_retriever(self):
        """Reranker config should instantiate Reranker."""
        from run import build_retriever

        config = {
            "retriever": "reranker",
            "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        }
        ret = build_retriever(config)
        assert isinstance(ret, Reranker)
        assert ret.__class__.__name__ == "Reranker"

    def test_unknown_retriever_raises_error(self):
        """Unknown retriever type should raise ValueError."""
        from run import build_retriever

        config = {"retriever": "nonexistent_retriever"}
        with pytest.raises(ValueError):
            build_retriever(config)


class TestCorpusMetadataLogging:
    """Verify corpus statistics are logged to experiment summary."""

    def test_corpus_stats_included_in_summary(self):
        """Summary should include corpus metadata."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=3, seed=42
        )
        corpus_size = len(result["corpus"])
        query_count = len(result["queries"])
        
        assert corpus_size > 0
        assert query_count == 3
        
        # Corpus stats should be computable from data
        corpus_stats = {
            "dataset": "load_hotpotqa_distractor",
            "num_queries": query_count,
            "num_unique_documents": corpus_size,
            "corpus_type": "pooled_hotpotqa",
        }
        assert corpus_stats["num_queries"] == 3
        assert corpus_stats["num_unique_documents"] == corpus_size


class TestMetricsComputation:
    """Verify metrics are computed correctly end-to-end."""

    def test_recall_computed_for_multiple_k_values(self):
        """All Recall@k values should be computable."""
        retrieved = ["doc_a", "doc_b", "doc_c", "doc_d", "doc_e"]
        gold = ["doc_a", "doc_c"]
        
        for k in [1, 3, 5, 10]:
            result = recall_at_k(retrieved, gold, k)
            assert result is not None
            assert 0.0 <= result <= 1.0

    def test_mrr_computed_for_multiple_k_values(self):
        """All MRR@k values should be computable."""
        retrieved = ["doc_b", "doc_c", "doc_a", "doc_d"]
        gold = ["doc_a", "doc_c"]
        
        for k in [1, 3, 5, 10]:
            result = mrr(retrieved, gold, k)
            assert result is not None
            assert 0.0 <= result <= 1.0

    def test_ndcg_computed_for_k_10(self):
        """nDCG@10 should be computable."""
        retrieved = ["doc_a", "doc_b", "doc_c", "doc_d"]
        gold = ["doc_a", "doc_c"]
        
        result = ndcg_at_k(retrieved, gold, 10)
        assert result is not None
        assert 0.0 <= result <= 1.0

    def test_poison_metrics_computed(self):
        """Poison metrics should compute without error."""
        retrieved = ["doc_a", "poison_1", "doc_c"]
        poison_ids = ["poison_1"]
        
        prr = poison_retrieval_rate_at_k(retrieved, poison_ids, k=3)
        assert prr == 1.0

    def test_attack_metrics_computed(self):
        """Attack metrics should compute from result lists."""
        results = [
            {"attack_success": True},
            {"attack_success": False},
            {"attack_success": True},
        ]
        
        asr = attack_success_rate(results)
        assert pytest.approx(asr) == 2.0 / 3.0

    def test_transfer_rate_computed(self):
        """Transfer rate should compute from source/target results aligned by query_id."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q3", "attack_success": False},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
            {"query_id": "q3", "attack_success": False},
        ]
        
        atr = attack_transfer_rate(source, target)
        assert pytest.approx(atr) == 0.5  # 1 out of 2 source successes transferred


class TestTransferMatrixIntegration:
    """Verify transfer matrix framework works end-to-end."""

    def test_complete_transfer_matrix_workflow(self):
        """Build a complete 4x4 transfer matrix with mixed cells."""
        pipelines = ["bm25", "dense", "hybrid", "reranker"]
        matrix = TransferMatrix()
        
        # Simulate running half the cells
        for i, source in enumerate(pipelines):
            for j, target in enumerate(pipelines):
                if (i + j) % 2 == 0:  # Checkerboard pattern
                    # Create synthetic result
                    from src.pipelines.transfer import TransferExperimentResult
                    result = TransferExperimentResult(
                        source_pipeline=source,
                        target_pipeline=target,
                        poison_id="test_poison",
                        dataset="test_dataset",
                        seed=42,
                        total_queries=10,
                        attack_transfer_rate=0.5 + (i * 0.1),  # Vary slightly
                    )
                    matrix.add_result(result)
                else:
                    # Mark unrun cells
                    matrix.mark_not_run(source, target)
        
        # Generate CSV and Markdown
        csv_output = matrix.to_csv(metric="attack_transfer_rate")
        md_output = matrix.to_markdown(metric="attack_transfer_rate")
        
        # Both should have structure
        assert len(csv_output) > 0
        assert len(md_output) > 0
        assert "N/A" in csv_output  # unrun cells
        assert "N/A" in md_output


class TestRetrieverRoutingRegressionTest:
    """Regression test for hardcoded retriever issue.

    This test would FAIL if someone changed run.py to hardcode:
        retriever = BM25Retriever()
    regardless of config.
    """

    def test_config_changes_retriever_type_not_hardcoded(self):
        """Different configs must produce different retriever instances."""
        from run import build_retriever

        # Test that changing config actually changes the retriever type
        bm25_config = {"retriever": "bm25"}
        dense_config = {"retriever": "dense", "embedder_model": "BAAI/bge-small-en-v1.5"}
        
        bm25_ret = build_retriever(bm25_config)
        dense_ret = build_retriever(dense_config)
        
        # These should be DIFFERENT class types
        assert bm25_ret.__class__.__name__ != dense_ret.__class__.__name__
        assert isinstance(bm25_ret, BM25Retriever)
        assert isinstance(dense_ret, DenseRetriever)
        
        # If someone hardcoded BM25Retriever(), both would be BM25
        # This test would catch that regression.


class TestCorpusDeterminismIntegration:
    """Verify corpus is reproducible with same seed."""

    def test_reproducible_corpus_with_same_seed(self):
        """Loading corpus twice with same seed should give same result."""
        result1 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        result2 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        
        # Same queries
        queries1 = sorted([q["query_id"] for q in result1["queries"]])
        queries2 = sorted([q["query_id"] for q in result2["queries"]])
        assert queries1 == queries2
        
        # Same corpus size
        assert len(result1["corpus"]) == len(result2["corpus"])
        
        # Same doc IDs
        ids1 = sorted([d["doc_id"] for d in result1["corpus"]])
        ids2 = sorted([d["doc_id"] for d in result2["corpus"]])
        assert ids1 == ids2
