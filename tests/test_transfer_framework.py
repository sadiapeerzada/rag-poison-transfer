"""Tests for transfer evaluation framework.

Validates TransferMatrix, TransferExperimentResult, and transfer statistic
computation without requiring actual poisoning implementations.
"""
import json
import os
import pytest
import tempfile
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

    def test_to_json_exports_to_file(self):
        """Export matrix to JSON file and verify content."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.5,
            poison_retrieval_rate_at_1=0.75,
            poison_retrieval_rate_at_5=0.95,
        )
        matrix.add_result(result)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_matrix.json")
            matrix.to_json(filepath)

            # Verify file exists and is valid JSON
            assert os.path.exists(filepath)
            with open(filepath, "r") as f:
                loaded_dict = json.load(f)

            # Verify content matches the exported dict
            assert "bm25" in loaded_dict
            assert loaded_dict["bm25"]["dense"]["attack_transfer_rate"] == 0.5
            # Note: to_dict() uses @ notation for PRR metrics
            assert loaded_dict["bm25"]["dense"]["poison_retrieval_rate@1"] == 0.75
            assert loaded_dict["bm25"]["dense"]["poison_retrieval_rate@5"] == 0.95

    def test_to_json_raises_on_existing_file(self):
        """Raise FileExistsError if file exists and overwrite=False."""
        matrix = TransferMatrix()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_matrix.json")
            # Create the file first
            with open(filepath, "w") as f:
                f.write("{}")

            # Try to export without overwrite flag
            with pytest.raises(FileExistsError):
                matrix.to_json(filepath, overwrite=False)

    def test_to_json_overwrites_with_flag(self):
        """Overwrite existing file when overwrite=True."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.7,
        )
        matrix.add_result(result)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_matrix.json")
            # Create the file first with different content
            with open(filepath, "w") as f:
                json.dump({"old": "content"}, f)

            # Export with overwrite=True should succeed
            matrix.to_json(filepath, overwrite=True)

            # Verify new content
            with open(filepath, "r") as f:
                loaded_dict = json.load(f)
            assert "old" not in loaded_dict
            assert loaded_dict["bm25"]["dense"]["attack_transfer_rate"] == 0.7

    def test_to_json_with_multiple_results(self):
        """Export a larger matrix with multiple results and not_run cells."""
        matrix = TransferMatrix()

        # Add multiple results
        for source in ["bm25", "dense"]:
            for target in ["hybrid", "reranker"]:
                result = TransferExperimentResult(
                    source_pipeline=source,
                    target_pipeline=target,
                    poison_id="poison_001",
                    dataset="hotpotqa",
                    seed=42,
                    attack_transfer_rate=0.5 + (hash(source + target) % 30) / 100,
                )
                matrix.add_result(result)

        # Mark some as not_run
        matrix.mark_not_run("hybrid", "bm25")
        matrix.mark_not_run("reranker", "reranker")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_matrix.json")
            matrix.to_json(filepath)

            # Verify structure
            with open(filepath, "r") as f:
                loaded_dict = json.load(f)

            assert "bm25" in loaded_dict
            assert "dense" in loaded_dict
            assert "hybrid" in loaded_dict
            assert "reranker" in loaded_dict

            # Check a result cell (bm25 -> hybrid)
            assert "hybrid" in loaded_dict["bm25"]
            assert loaded_dict["bm25"]["hybrid"]["attack_transfer_rate"] is not None

            # Check another result cell (dense -> reranker)
            assert "reranker" in loaded_dict["dense"]
            assert loaded_dict["dense"]["reranker"]["attack_transfer_rate"] is not None

            # Check a not_run cell
            assert loaded_dict["hybrid"]["bm25"]["status"] == "not_run"
            assert loaded_dict["reranker"]["reranker"]["status"] == "not_run"

    def test_to_json_preserves_per_query_results(self):
        """JSON export includes per_query_results from experiments."""
        matrix = TransferMatrix()
        result = TransferExperimentResult(
            source_pipeline="bm25",
            target_pipeline="dense",
            poison_id="poison_001",
            dataset="hotpotqa",
            seed=42,
            attack_transfer_rate=0.5,
            per_query_results=[
                {"query_id": "q1", "transferred": True},
                {"query_id": "q2", "transferred": False},
            ],
        )
        matrix.add_result(result)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_matrix.json")
            matrix.to_json(filepath)

            with open(filepath, "r") as f:
                loaded_dict = json.load(f)

            assert "per_query_results" in loaded_dict["bm25"]["dense"]
            pqr = loaded_dict["bm25"]["dense"]["per_query_results"]
            assert len(pqr) == 2
            assert pqr[0]["query_id"] == "q1"
            assert pqr[0]["transferred"] is True


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
    """Query-ID alignment: ATR must match by query_id regardless of position."""

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
        """Query IDs present in one list but not the other raise ValueError."""
        source = [self._make_result("q1"), self._make_result("q2")]
        target = [self._make_result("q1"), self._make_result("q3")]
        with pytest.raises(ValueError, match="mismatched query_ids"):
            compute_transfer_statistics(source, target)

    def test_reordered_query_ids_succeeds(self):
        """Reordered inputs with same query_ids work correctly (matched by ID, not position).
        
        This is the fix: alignment is by query_id, so reordering doesn't cause errors.
        """
        source = [self._make_result("q1", True), self._make_result("q2", True)]
        target = [self._make_result("q2", False), self._make_result("q1", True)]
        result = compute_transfer_statistics(source, target)
        assert result.total_queries == 2
        # q1: source=True, target=True -> transfer
        # q2: source=True, target=False -> no transfer
        assert result.transferred_attacks == 1
        assert result.attack_transfer_rate == 0.5

    def test_reordered_produces_same_result(self):
        """Reordered inputs produce the same ATR as ordered inputs."""
        source_ordered = [self._make_result("q1", True), self._make_result("q2", False)]
        target_ordered = [self._make_result("q1", True), self._make_result("q2", True)]
        result_ordered = compute_transfer_statistics(source_ordered, target_ordered)
        
        source_reordered = [self._make_result("q2", False), self._make_result("q1", True)]
        target_reordered = [self._make_result("q2", True), self._make_result("q1", True)]
        result_reordered = compute_transfer_statistics(source_reordered, target_reordered)
        
        assert result_ordered.attack_transfer_rate == result_reordered.attack_transfer_rate
        assert result_ordered.transferred_attacks == result_reordered.transferred_attacks

    def test_missing_query_id_raises(self):
        """Results without query_id field raise ValueError."""
        source = [{"attack_success": True}]
        target = [self._make_result("q1")]
        with pytest.raises(ValueError, match="without query_id"):
            compute_transfer_statistics(source, target)

    def test_duplicate_query_id_raises(self):
        """Duplicate query_id within one list raises ValueError."""
        source = [self._make_result("q1", True), self._make_result("q1", False)]
        target = [self._make_result("q1", True)]
        with pytest.raises(ValueError, match="duplicate query_id"):
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
