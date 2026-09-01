"""Tests for Recall@k, MRR, nDCG@k (src/evaluation/metrics.py).

These are pure functions over doc_id lists, so every case here is a
synthetic, hand-checkable scenario -- no real retriever or dataset
needed. That's deliberate: retrieval-metric bugs are easy to get
subtly wrong (off-by-one in rank indexing, log base, treating "no
gold docs" as "zero recall" instead of undefined), and those bugs are
much cheaper to catch here than after running a real 200-query
experiment on Kaggle.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.metrics import recall_at_k, mrr, ndcg_at_k


# ---- recall_at_k -----------------------------------------------------

def test_recall_at_k_perfect_match():
    retrieved = ["a", "b", "c"]
    gold = ["a", "b"]
    assert recall_at_k(retrieved, gold, k=3) == 1.0


def test_recall_at_k_partial_match():
    retrieved = ["a", "x", "y"]
    gold = ["a", "b"]  # only "a" found -> 1 of 2 gold docs
    assert recall_at_k(retrieved, gold, k=3) == 0.5


def test_recall_at_k_no_match():
    retrieved = ["x", "y", "z"]
    gold = ["a", "b"]
    assert recall_at_k(retrieved, gold, k=3) == 0.0


def test_recall_at_k_respects_k_cutoff():
    # gold doc is retrieved, but AFTER the k cutoff -> shouldn't count
    retrieved = ["x", "y", "a"]
    gold = ["a"]
    assert recall_at_k(retrieved, gold, k=2) == 0.0
    assert recall_at_k(retrieved, gold, k=3) == 1.0


def test_recall_at_k_empty_gold_returns_none_not_zero():
    # A query with no gold docs has UNDEFINED recall, not 0.0 -- this
    # distinction matters because averaging in a 0.0 for "no gold docs"
    # would silently drag down the real recall score.
    assert recall_at_k(["a", "b"], [], k=3) is None


def test_recall_at_k_duplicate_gold_ids_not_double_counted():
    # defensive: gold_doc_ids shouldn't be able to inflate the score
    # past 1.0 even if it somehow contains a duplicate
    retrieved = ["a", "b"]
    gold = ["a", "a", "b"]
    assert recall_at_k(retrieved, gold, k=2) == 1.0


# ---- mrr ---------------------------------------------------------------

def test_mrr_first_position():
    assert mrr(["a", "b", "c"], ["a"]) == 1.0


def test_mrr_third_position():
    assert mrr(["x", "y", "a"], ["a"]) == pytest_approx(1 / 3)


def test_mrr_no_hit():
    assert mrr(["x", "y", "z"], ["a"]) == 0.0


def test_mrr_uses_first_hit_when_multiple_gold_docs_present():
    # gold = {a, c}; "a" is retrieved first among the two -> rank 1
    assert mrr(["a", "b", "c"], ["a", "c"]) == 1.0
    # now "c" comes first among the two gold docs -> rank 1 still,
    # since MRR only cares about the FIRST relevant hit regardless of
    # which gold doc it is
    assert mrr(["b", "c", "a"], ["a", "c"]) == 0.5


def test_mrr_respects_k_cutoff():
    retrieved = ["x", "y", "a"]
    gold = ["a"]
    assert mrr(retrieved, gold, k=2) == 0.0   # "a" is past the cutoff
    assert mrr(retrieved, gold, k=3) == pytest_approx(1 / 3)
    assert mrr(retrieved, gold, k=None) == pytest_approx(1 / 3)  # no cutoff


def test_mrr_empty_gold_returns_none():
    assert mrr(["a", "b"], []) is None


# ---- ndcg_at_k -----------------------------------------------------------

def test_ndcg_perfect_ranking_is_one():
    # both gold docs retrieved, in the best possible order
    retrieved = ["a", "b", "x"]
    gold = ["a", "b"]
    assert ndcg_at_k(retrieved, gold, k=3) == pytest_approx(1.0)


def test_ndcg_no_relevant_docs_is_zero():
    retrieved = ["x", "y", "z"]
    gold = ["a"]
    assert ndcg_at_k(retrieved, gold, k=3) == 0.0


def test_ndcg_worse_ranking_scores_lower_than_better_ranking():
    gold = ["a", "b"]
    # gold docs both at the front (best) vs both pushed to the back
    # (worse) of the same top-k window -- worse should score strictly
    # lower, since DCG discounts hits that show up later.
    best = ndcg_at_k(["a", "b", "x", "y"], gold, k=4)
    worse = ndcg_at_k(["x", "y", "a", "b"], gold, k=4)
    assert best == pytest_approx(1.0)
    assert worse < best
    assert worse > 0.0  # still found both, just later


def test_ndcg_matches_hand_computed_value():
    # retrieved = [x, a, y, b], gold = {a, b}, k=4
    # DCG   = 1/log2(3) [a at rank2] + 1/log2(5) [b at rank4]
    # IDCG  = 1/log2(2) + 1/log2(3)  [best case: both gold docs first]
    retrieved = ["x", "a", "y", "b"]
    gold = ["a", "b"]
    dcg = 1 / math.log2(3) + 1 / math.log2(5)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    expected = dcg / idcg
    assert ndcg_at_k(retrieved, gold, k=4) == pytest_approx(expected)


def test_ndcg_respects_k_cutoff():
    # gold doc retrieved, but beyond the k cutoff -> shouldn't count
    retrieved = ["x", "y", "a"]
    gold = ["a"]
    assert ndcg_at_k(retrieved, gold, k=2) == 0.0
    assert ndcg_at_k(retrieved, gold, k=3) > 0.0


def test_ndcg_empty_gold_returns_none_not_one():
    # IDCG would be 0 for empty gold -- must not silently become a
    # 0/0 -> "1.0" (perfect score) trap. Undefined, not perfect.
    assert ndcg_at_k(["a", "b"], [], k=3) is None


def test_ndcg_ideal_count_capped_by_k():
    # 3 gold docs but k=2 -- IDCG should only count the best 2 possible
    # hits within the k=2 window, not all 3 gold docs
    retrieved = ["a", "b", "c", "d"]
    gold = ["a", "b", "c"]
    # top-2 retrieved = [a, b], both relevant -> perfect nDCG@2
    assert ndcg_at_k(retrieved, gold, k=2) == pytest_approx(1.0)


# ---- tiny local pytest.approx substitute (avoid adding a pytest-only
# import at module scope if pytest.approx isn't available in this env) ---

def pytest_approx(value, rel=1e-9):
    import pytest
    return pytest.approx(value, rel=rel)
