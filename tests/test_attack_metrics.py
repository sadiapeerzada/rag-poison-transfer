"""Tests for attack metrics: PRR@k, ASR, ATR.

These tests use synthetic attack data to validate metric computation,
without requiring actual poison-generation implementations.
"""
import pytest
from src.evaluation.metrics import (
    poison_retrieval_rate_at_k,
    attack_success_rate,
    attack_transfer_rate,
)


class TestPoisonRetrievalRateAtK:
    """Tests for PRR@k: fraction of queries retrieving poison in top-k."""

    def test_poison_in_top_k_returns_one(self):
        """Query with poison doc in top-k should return 1.0."""
        retrieved = ["doc_a", "poison_1", "doc_c"]
        poison_ids = ["poison_1"]
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) == 1.0

    def test_poison_beyond_k_returns_zero(self):
        """Poison doc outside top-k should return 0.0."""
        retrieved = ["doc_a", "doc_b", "poison_1"]
        poison_ids = ["poison_1"]
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=2) == 0.0

    def test_multiple_poison_docs_one_in_top_k(self):
        """Multiple poison docs; at least one in top-k returns 1.0."""
        retrieved = ["doc_a", "poison_1", "doc_c", "poison_2"]
        poison_ids = ["poison_1", "poison_2"]
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) == 1.0

    def test_no_poison_in_retrieved_returns_zero(self):
        """No poison docs in retrieved set returns 0.0."""
        retrieved = ["doc_a", "doc_b", "doc_c"]
        poison_ids = ["poison_1", "poison_2"]
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) == 0.0

    def test_empty_poison_ids_returns_none(self):
        """Empty poison_doc_ids is undefined; return None."""
        retrieved = ["doc_a", "doc_b", "doc_c"]
        poison_ids = []
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) is None

    def test_poison_at_exact_k_boundary(self):
        """Poison doc at position k (inclusive) returns 1.0."""
        retrieved = ["doc_a", "doc_b", "doc_c"]
        poison_ids = ["doc_c"]
        # k=3 includes positions 0, 1, 2 (doc_c is at position 2)
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) == 1.0

    def test_poison_at_k_plus_one_returns_zero(self):
        """Poison doc at position k+1 (exclusive) returns 0.0."""
        retrieved = ["doc_a", "doc_b", "doc_c", "poison_1"]
        poison_ids = ["poison_1"]
        # k=3 includes positions 0, 1, 2; poison_1 is at position 3
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) == 0.0

    def test_all_docs_are_poison_in_top_k(self):
        """Top-k contains only poison docs returns 1.0."""
        retrieved = ["poison_1", "poison_2", "poison_3", "clean_doc"]
        poison_ids = ["poison_1", "poison_2", "poison_3"]
        assert poison_retrieval_rate_at_k(retrieved, poison_ids, k=3) == 1.0


class TestAttackSuccessRate:
    """Tests for ASR: fraction of queries where attack succeeded."""

    def test_all_attacks_successful(self):
        """All queries with attack_success=True returns 1.0."""
        results = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q3", "attack_success": True},
        ]
        assert attack_success_rate(results) == 1.0

    def test_no_attacks_successful(self):
        """All queries with attack_success=False returns 0.0."""
        results = [
            {"query_id": "q1", "attack_success": False},
            {"query_id": "q2", "attack_success": False},
        ]
        assert attack_success_rate(results) == 0.0

    def test_mixed_attack_success(self):
        """Partial success: 2/4 successful returns 0.5."""
        results = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
            {"query_id": "q3", "attack_success": True},
            {"query_id": "q4", "attack_success": False},
        ]
        assert attack_success_rate(results) == 0.5

    def test_single_successful_attack(self):
        """Single successful attack returns 1.0."""
        results = [{"query_id": "q1", "attack_success": True}]
        assert attack_success_rate(results) == 1.0

    def test_empty_results_returns_none(self):
        """Empty result list returns None (undefined)."""
        results = []
        assert attack_success_rate(results) is None

    def test_missing_attack_success_field_treated_as_false(self):
        """Missing 'attack_success' field defaults to False."""
        results = [
            {"query_id": "q1"},  # No attack_success field
            {"query_id": "q2", "attack_success": True},
        ]
        assert attack_success_rate(results) == 0.5

    def test_multiple_attacks_one_third_successful(self):
        """3 queries, 1 successful returns 0.333...."""
        results = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
            {"query_id": "q3", "attack_success": False},
        ]
        assert pytest.approx(attack_success_rate(results), rel=1e-5) == 1.0 / 3.0


class TestAttackTransferRate:
    """Tests for ATR: fraction of source attacks that transfer to target."""

    def test_all_attacks_transfer(self):
        """All source attacks also succeed in target returns 1.0."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q3", "attack_success": False},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q3", "attack_success": False},
        ]
        assert attack_transfer_rate(source, target) == 1.0

    def test_no_attacks_transfer(self):
        """Source attacks fail in target returns 0.0."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
        ]
        target = [
            {"query_id": "q1", "attack_success": False},
            {"query_id": "q2", "attack_success": False},
        ]
        assert attack_transfer_rate(source, target) == 0.0

    def test_partial_transfer(self):
        """Half of source attacks transfer returns 0.5."""
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
        # Source successful on q1, q2; target successful on q1 only
        # Transfer = 1/2 = 0.5
        assert attack_transfer_rate(source, target) == 0.5

    def test_no_source_attacks_returns_none(self):
        """No successful source attacks returns None (undefined)."""
        source = [
            {"query_id": "q1", "attack_success": False},
            {"query_id": "q2", "attack_success": False},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
        ]
        assert attack_transfer_rate(source, target) is None

    def test_empty_source_returns_none(self):
        """Empty source result list returns None."""
        source = []
        target = [{"query_id": "q1", "attack_success": True}]
        assert attack_transfer_rate(source, target) is None

    def test_empty_target_returns_none(self):
        """Empty target result list returns None."""
        source = [{"query_id": "q1", "attack_success": True}]
        target = []
        assert attack_transfer_rate(source, target) is None

    def test_mismatched_length_returns_none(self):
        """Source and target with different lengths returns None."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
        ]
        assert attack_transfer_rate(source, target) is None

    def test_single_successful_source_attack_transfers(self):
        """Single source attack that transfers returns 1.0."""
        source = [{"query_id": "q1", "attack_success": True}]
        target = [{"query_id": "q1", "attack_success": True}]
        assert attack_transfer_rate(source, target) == 1.0

    def test_single_successful_source_attack_does_not_transfer(self):
        """Single source attack that doesn't transfer returns 0.0."""
        source = [{"query_id": "q1", "attack_success": True}]
        target = [{"query_id": "q1", "attack_success": False}]
        assert attack_transfer_rate(source, target) == 0.0

    def test_missing_attack_success_defaults_to_false(self):
        """Missing attack_success field treated as False for transfer calc."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
        ]
        target = [
            {"query_id": "q1"},  # Missing attack_success field
            {"query_id": "q2", "attack_success": True},
        ]
        # Source successful on q1, q2
        # Target successful on q2 only (q1 missing = False)
        # Transfer = 1/2 = 0.5
        assert attack_transfer_rate(source, target) == 0.5
