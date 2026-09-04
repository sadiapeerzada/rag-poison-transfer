"""Tests for transfer evaluation framework.

Validates TransferMatrix, TransferExperimentResult, and transfer statistic
computation without requiring actual poisoning implementations.
"""
import pytest
from src.pipelines.transfer import (
    TransferExperimentResult,
    TransferMatrix,
    compute_transfer_statistics,
)


class TestTransferExperimentResult:
    """Tests for TransferExperimentResult data structure."""

    def test_basic_result_construction(self):
        """Create and populate a transfer result."""
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            total_queries=10,
            successful_attacks_source=5,
            successful_attacks_target=3,
            transferred_attacks=2,
            attack_transfer_rate=0.4,
        )
        assert result.source_pipeline == "bm25"
        assert result.target_pipeline == "dense"
        assert result.transferred_attacks == 2

    def test_result_to_dict(self):
        """Convert result to dict for JSON serialization."""
        result = TransferExperimentResult(
            source_pipeline="dense",
            target_pipeline="hybrid",
            poison_id="poison_002",
            dataset="hotpotqa",
            seed=42,
            total_queries=5,
            attack_transfer_rate=0.6,
        )
        result_dict = result.to_dict()
        assert result_dict["source_pipeline"] == "dense"
        assert result_dict["target_pipeline"] == "hybrid"
        assert result_dict["attack_transfer_rate"] == 0.6


class TestTransferMatrix:
    """Tests for TransferMatrix aggregation."""

    def test_add_result_populates_pipelines(self):
        """Adding a result should register both pipelines."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
        )
        matrix.add_result(result)
        assert "bm25" in matrix.pipelines
        assert "dense" in matrix.pipelines

    def test_get_result_returns_stored_result(self):
        """Retrieving an added result returns the same object."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.5,
        )
        matrix.add_result(result)
        retrieved = matrix.get_result("bm25", "dense")
        assert isinstance(retrieved, TransferExperimentResult)
        assert retrieved.attack_transfer_rate == 0.5

    def test_get_result_missing_returns_none(self):
        """Retrieving non-existent cell returns None."""
        matrix = TransferMatrix()
        retrieved = matrix.get_result("bm25", "dense")
        assert retrieved is None

    def test_mark_not_run(self):
        """Marking a cell as not_run stores the status."""
        matrix = TransferMatrix()
        matrix.mark_not_run("bm25", "reranker")
        result = matrix.get_result("bm25", "reranker")
        assert result == "not_run"

    def test_complete_4x4_matrix_with_diagonal_and_some_cells(self):
        """Populate a 4x4 matrix with some cells, leave others not_run."""
        pipelines = ["bm25", "dense", "hybrid", "reranker"]
        matrix = TransferMatrix()

        # Add some results (not all)
        for source in ["bm25", "dense"]:
            for target in ["hybrid", "reranker"]:
                result = TransferExperimentResult(
                    source_pipeline=source,
                    target_pipeline=target,
                    poison_id="poison_001",
                    dataset="hotpotqa",
                    seed=42,
                    attack_transfer_rate=0.5,
                )
                matrix.add_result(result)

        # Mark others as not_run
        for source in pipelines:
            for target in pipelines:
                if (source, target) not in [
                    ("bm25", "hybrid"),
                    ("bm25", "reranker"),
                    ("dense", "hybrid"),
                    ("dense", "reranker"),
                ]:
                    matrix.mark_not_run(source, target)

        # Verify all cells are accounted for
        for source in pipelines:
            for target in pipelines:
                cell = matrix.get_result(source, target)
                assert cell is not None, f"Cell ({source}, {target}) is None"

    def test_to_csv_with_metric(self):
        """Generate CSV output for a metric."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.5,
        )
        matrix.add_result(result)
        matrix.mark_not_run("dense", "bm25")

        csv_output = matrix.to_csv(metric="attack_transfer_rate")
        lines = csv_output.strip().split("\n")

        # Should have header + 2 pipelines
        assert len(lines) >= 2
        # First line should have pipeline names
        assert "bm25" in lines[0]
        assert "dense" in lines[0]

    def test_to_markdown_with_metric(self):
        """Generate Markdown table for a metric."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.75,
        )
        matrix.add_result(result)
        matrix.mark_not_run("dense", "bm25")

        md_output = matrix.to_markdown(metric="attack_transfer_rate")
        assert "bm25" in md_output
        assert "dense" in md_output
        assert "0.75" in md_output
        assert "N/A" in md_output  # For not_run cells

    def test_to_dict_export(self):
        """Export full matrix as nested dict."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.6,
        )
        matrix.add_result(result)
        matrix.mark_not_run("dense", "bm25")

        matrix_dict = matrix.to_dict()
        assert "bm25" in matrix_dict
        assert "dense" in matrix_dict["bm25"]
        assert matrix_dict["bm25"]["dense"]["attack_transfer_rate"] == 0.6


class TestComputeTransferStatistics:
    """Tests for computing transfer metrics from result lists."""

    def test_perfect_transfer_100_percent(self):
        """All source attacks transfer to target."""
        source = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "poison_001", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q2", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "poison_001", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q3", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "poison_001", "dataset": "hotpotqa", "seed": 42},
        ]
        target = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "poison_001", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q2", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "poison_001", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q3", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "poison_001", "dataset": "hotpotqa", "seed": 42},
        ]
        result = compute_transfer_statistics(source, target)
        assert result.total_queries == 3
        assert result.successful_attacks_source == 2
        assert result.successful_attacks_target == 2
        assert result.transferred_attacks == 2
        assert result.attack_transfer_rate == 1.0

    def test_no_transfer_0_percent(self):
        """No source attacks transfer to target."""
        source = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q2", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
        ]
        target = [
            {"query_id": "q1", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q2", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
        ]
        result = compute_transfer_statistics(source, target)
        assert result.attack_transfer_rate == 0.0

    def test_mismatched_lengths_raises_error(self):
        """Source and target with different lengths raise ValueError."""
        source = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
        ]
        target = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
            {"query_id": "q2", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hotpotqa", "seed": 42},
        ]
        with pytest.raises(ValueError):
            compute_transfer_statistics(source, target)

    def test_empty_results_raises_error(self):
        """Empty result lists raise ValueError."""
        with pytest.raises(ValueError):
            compute_transfer_statistics([], [])

    def test_partial_transfer_50_percent(self):
        """Half of source attacks transfer."""
        source = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "dense", "target_pipeline": "hybrid", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q2", "attack_success": True, "source_pipeline": "dense", "target_pipeline": "hybrid", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q3", "attack_success": False, "source_pipeline": "dense", "target_pipeline": "hybrid", "poison_id": "p1", "dataset": "hqa", "seed": 42},
        ]
        target = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "dense", "target_pipeline": "hybrid", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q2", "attack_success": False, "source_pipeline": "dense", "target_pipeline": "hybrid", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q3", "attack_success": False, "source_pipeline": "dense", "target_pipeline": "hybrid", "poison_id": "p1", "dataset": "hqa", "seed": 42},
        ]
        result = compute_transfer_statistics(source, target)
        assert result.successful_attacks_source == 2
        assert result.transferred_attacks == 1
        assert pytest.approx(result.attack_transfer_rate) == 0.5

    def test_attack_success_rates_computed(self):
        """ASR for both source and target are computed."""
        source = [
            {"query_id": "q1", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q2", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q3", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hqa", "seed": 42},
        ]
        target = [
            {"query_id": "q1", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q2", "attack_success": True, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hqa", "seed": 42},
            {"query_id": "q3", "attack_success": False, "source_pipeline": "bm25", "target_pipeline": "dense", "poison_id": "p1", "dataset": "hqa", "seed": 42},
        ]
        result = compute_transfer_statistics(source, target)
        assert pytest.approx(result.attack_success_rate_source) == 2.0 / 3.0
        assert pytest.approx(result.attack_success_rate_target) == 1.0 / 3.0


class TestQueryIDAlignment:
    """Supervisor review 3.5: ATR must fail fast on query-ID misalignment."""

    def _make_result(self, query_id, attack_success=True):
        return {
            "query_id": query_id,
            "attack_success": attack_success,
            "source_pipeline": "bm25",
            "target_pipeline": "dense",
        }

    def test_matching_query_ids_succeeds(self):
        source = [self._make_result("q1"), self._make_result("q2")]
        target = [self._make_result("q1"), self._make_result("q2")]
        result = compute_transfer_statistics(source, target)
        assert result.total_queries == 2

    def test_mismatched_query_id_raises(self):
        source = [self._make_result("q1"), self._make_result("q2")]
        target = [self._make_result("q1"), self._make_result("q3")]
        with pytest.raises(ValueError, match="Query ID mismatch"):
            compute_transfer_statistics(source, target)

    def test_reordered_query_ids_raises(self):
        source = [self._make_result("q1"), self._make_result("q2")]
        target = [self._make_result("q2"), self._make_result("q1")]
        with pytest.raises(ValueError, match="Query ID mismatch"):
            compute_transfer_statistics(source, target)

    def test_missing_query_id_raises(self):
        source = [{"attack_success": True}]
        target = [self._make_result("q1")]
        with pytest.raises(ValueError, match="Query ID mismatch"):
            compute_transfer_statistics(source, target)


class TestPoisonRetrievalRateComputation:
    """Supervisor review 3.5: PRR@k must actually be computed, not left None."""

    def _make_pair(self, query_id, poison_rank, poison_doc_ids=("p1",)):
        base = {
            "query_id": query_id,
            "attack_success": True,
            "poison_doc_ids": list(poison_doc_ids),
            "poison_rank": poison_rank,
        }
        return dict(base), dict(base)

    def test_prr_fields_are_not_none_when_poisons_present(self):
        source, target = zip(*[self._make_pair(f"q{i}", 1) for i in range(3)])
        result = compute_transfer_statistics(list(source), list(target))
        assert result.poison_retrieval_rate_at_1 is not None
        assert result.poison_retrieval_rate_at_10 is not None

    def test_prr_at_1_all_hits(self):
        source, target = zip(*[self._make_pair(f"q{i}", 1) for i in range(4)])
        result = compute_transfer_statistics(list(source), list(target))
        assert result.poison_retrieval_rate_at_1 == 1.0

    def test_prr_at_1_partial_hits(self):
        pairs = [self._make_pair("q0", 1), self._make_pair("q1", 5)]
        source, target = zip(*pairs)
        result = compute_transfer_statistics(list(source), list(target))
        assert result.poison_retrieval_rate_at_1 == 0.5
        assert result.poison_retrieval_rate_at_5 == 1.0

    def test_prr_none_rank_counts_as_miss(self):
        pairs = [self._make_pair("q0", None), self._make_pair("q1", 2)]
        source, target = zip(*pairs)
        result = compute_transfer_statistics(list(source), list(target))
        assert result.poison_retrieval_rate_at_1 == 0.0
        assert result.poison_retrieval_rate_at_10 == 0.5

    def test_prr_none_when_no_queries_have_poison_docs(self):
        source = [{"query_id": "q0", "attack_success": True}]
        target = [{"query_id": "q0", "attack_success": True}]
        result = compute_transfer_statistics(source, target)
        assert result.poison_retrieval_rate_at_1 is None


class TestPRRExportPath:
    """Supervisor review 3.5: PRR@k must export correctly from the transfer matrix."""

    def _make_pair(self, query_id, poison_rank):
        base = {
            "query_id": query_id,
            "attack_success": True,
            "poison_doc_ids": ["p1"],
            "poison_rank": poison_rank,
        }
        return dict(base), dict(base)

    def test_csv_export_resolves_at_notation(self):
        source, target = zip(*[self._make_pair(f"q{i}", 1) for i in range(2)])
        result = compute_transfer_statistics(list(source), list(target))
        result.source_pipeline, result.target_pipeline = "bm25", "dense"

        matrix = TransferMatrix()
        matrix.add_result(result)
        csv_out = matrix.to_csv(metric="poison_retrieval_rate@1")
        # The real (bm25 -> dense) cell should show the computed value, not N/A.
        # (bm25 -> bm25) is a legitimate N/A -- that cell was never run.
        assert "1.0000" in csv_out

    def test_markdown_export_resolves_at_notation(self):
        source, target = zip(*[self._make_pair(f"q{i}", 1) for i in range(2)])
        result = compute_transfer_statistics(list(source), list(target))
        result.source_pipeline, result.target_pipeline = "bm25", "dense"

        matrix = TransferMatrix()
        matrix.add_result(result)
        md_out = matrix.to_markdown(metric="poison_retrieval_rate@5")
        assert "1.0000" in md_out
