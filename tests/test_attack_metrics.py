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
        """Source and target with different lengths raises ValueError.
        
        Different lengths means the query_ids don't match, which is an error.
        """
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
        ]
        # New behavior: raise on mismatched query_ids, don't return None
        with pytest.raises(ValueError, match="mismatched query_ids"):
            attack_transfer_rate(source, target)

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

    def test_reordered_input_produces_same_atr(self):
        """Reordered inputs (different order, same queries) give same ATR.
        
        Tests requirement: alignment is by query_id, not position.
        """
        source_ordered = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q3", "attack_success": False},
        ]
        target_ordered = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
            {"query_id": "q3", "attack_success": False},
        ]
        atr_ordered = attack_transfer_rate(source_ordered, target_ordered)
        
        # Reverse order in both source and target
        source_reordered = [
            {"query_id": "q3", "attack_success": False},
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q1", "attack_success": True},
        ]
        target_reordered = [
            {"query_id": "q3", "attack_success": False},
            {"query_id": "q2", "attack_success": False},
            {"query_id": "q1", "attack_success": True},
        ]
        atr_reordered = attack_transfer_rate(source_reordered, target_reordered)
        
        # ATR should be the same regardless of order
        assert atr_ordered == 0.5
        assert atr_reordered == 0.5
        assert atr_ordered == atr_reordered

    def test_reordered_mismatched_values_uses_correct_pairing(self):
        """Reordered inputs with different values use correct per-query pairing.
        
        If the function incorrectly paired by position, it would compute a
        different (wrong) ATR. This test verifies correct query_id matching.
        """
        # In-order inputs: q1 transfers (T->T), q2 doesn't (T->F)
        source_ordered = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
        ]
        target_ordered = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": False},
        ]
        atr_ordered = attack_transfer_rate(source_ordered, target_ordered)
        
        # Reordered with opposite order: q2 first, then q1
        # Now target values are: q2->False (position 0), q1->True (position 1)
        # If function incorrectly paired by position:
        #   source[0]=q1(T) with target[0]=q2(F) -> no transfer
        #   source[1]=q2(T) with target[1]=q1(T) -> transfer
        # Wrong ATR would be 1/2 = 0.5
        # But correct pairing by query_id:
        #   source q1(T) with target q1(T) -> transfer
        #   source q2(T) with target q2(F) -> no transfer
        # Correct ATR is 1/2 = 0.5 (same in this case by coincidence!)
        
        # So let's use a case where positional pairing gives wrong result
        source_reordered = [
            {"query_id": "q2", "attack_success": True},
            {"query_id": "q1", "attack_success": True},
        ]
        target_reordered = [
            {"query_id": "q2", "attack_success": False},
            {"query_id": "q1", "attack_success": True},
        ]
        atr_reordered = attack_transfer_rate(source_reordered, target_reordered)
        
        # Correct pairing by query_id: q1 transfers, q2 doesn't -> 1/2 = 0.5
        # Wrong positional pairing would be: [q2 source T with q2 target F] + 
        #                                    [q1 source T with q1 target T]
        # Which also gives 1/2 = 0.5, so coincidentally the same!
        # Let's instead build a case where the error is obvious:
        
        # Case where positional pairing would be obviously wrong:
        source = [
            {"query_id": "q1", "attack_success": True},   # pos 0
            {"query_id": "q2", "attack_success": False},  # pos 1
        ]
        target = [
            {"query_id": "q2", "attack_success": True},   # pos 0 (but is q2)
            {"query_id": "q1", "attack_success": False},  # pos 1 (but is q1)
        ]
        # Correct (by query_id):
        #   q1: source=T, target=F -> no transfer
        #   q2: source=F, target=T -> not counted (source not successful)
        # Correct ATR = 0/1 = 0.0
        
        # Wrong (by position):
        #   pos0: source_q1(T) with target_q2(T) -> transfer
        # Wrong ATR = 1/1 = 1.0
        
        atr = attack_transfer_rate(source, target)
        assert atr == 0.0  # Correct by query_id alignment
        
    def test_duplicate_query_id_in_source_raises(self):
        """Duplicate query_id within source_results raises ValueError."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q1", "attack_success": False},  # Duplicate!
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
        ]
        with pytest.raises(ValueError, match="duplicate query_id"):
            attack_transfer_rate(source, target)

    def test_duplicate_query_id_in_target_raises(self):
        """Duplicate query_id within target_results raises ValueError."""
        source = [
            {"query_id": "q1", "attack_success": True},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q1", "attack_success": False},  # Duplicate!
        ]
        with pytest.raises(ValueError, match="duplicate query_id"):
            attack_transfer_rate(source, target)

    def test_missing_query_id_in_source_raises(self):
        """Missing query_id in source_results raises ValueError."""
        source = [
            {"attack_success": True},  # No query_id field!
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
        ]
        with pytest.raises(ValueError, match="without query_id"):
            attack_transfer_rate(source, target)

    def test_missing_query_id_in_target_raises(self):
        """Missing query_id in target_results raises ValueError."""
        source = [
            {"query_id": "q1", "attack_success": True},
        ]
        target = [
            {"attack_success": True},  # No query_id field!
        ]
        with pytest.raises(ValueError, match="without query_id"):
            attack_transfer_rate(source, target)

    def test_mismatched_query_ids_raises(self):
        """Mismatched query_id sets between source and target raises ValueError."""
        source = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q2", "attack_success": True},
        ]
        target = [
            {"query_id": "q1", "attack_success": True},
            {"query_id": "q3", "attack_success": True},  # q3 instead of q2
        ]
        with pytest.raises(ValueError, match="mismatched query_ids"):
            attack_transfer_rate(source, target)
