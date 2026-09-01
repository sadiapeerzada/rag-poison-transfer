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
