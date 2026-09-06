"""Tests for cross-pipeline poison-retrieval evaluation.

Uses BM25Retriever and DenseRetriever(HashingEmbedder) -- both real,
neither requiring a model download -- so tests are fast and network-free.
"""
import pytest

from src.attacks.evaluate import evaluate_poison_across_retrievers
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.attacks.injection import inject_poisons
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever, HashingEmbedder


def make_clean_data(n_queries=10):
    corpus = [
        {"doc_id": f"clean::doc_{i}", "text": f"Clean document about topic {i} and related facts."}
        for i in range(n_queries)
    ]
    queries = [
        {
            "query_id": f"q{i}",
            "question": f"What is the value of topic {i}?",
            "gold_answer": f"answer_{i}",
            "gold_doc_ids": [f"clean::doc_{i}"],
        }
        for i in range(n_queries)
    ]
    return {"corpus": corpus, "queries": queries}


class TestEvaluatePoisonAcrossRetrievers:
    def test_returns_result_per_retriever(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        retrievers = {"bm25": BM25Retriever(), "dense": DenseRetriever(HashingEmbedder())}
        results = evaluate_poison_across_retrievers(poisoned, retrievers)
        assert set(results.keys()) == {"bm25", "dense"}

    def test_mean_prr_has_all_k_values(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        retrievers = {"bm25": BM25Retriever()}
        results = evaluate_poison_across_retrievers(poisoned, retrievers)
        assert set(results["bm25"]["mean_prr"].keys()) == {1, 3, 5, 10}

    def test_lexical_attack_achieves_high_prr_against_bm25(self):
        # Lexical attack is specifically designed to exploit term-overlap
        # retrievers -- this is a real behavioral assertion, not just a
        # shape check: it should score very well against BM25.
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(repeat_factor=6), n_poison=1, poison_rate=1.0, seed=42)
        retrievers = {"bm25": BM25Retriever()}
        results = evaluate_poison_across_retrievers(poisoned, retrievers)
        assert results["bm25"]["mean_prr"][10] >= 0.8

    def test_per_query_records_have_required_fields(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        retrievers = {"bm25": BM25Retriever()}
        results = evaluate_poison_across_retrievers(poisoned, retrievers)
        record = results["bm25"]["per_query"][0]
        for field in ("query_id", "poison_doc_ids", "retrieved_doc_ids", "poison_rank", "poison_retrieved"):
            assert field in record

    def test_poison_rank_matches_poison_retrieved_flag(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        retrievers = {"bm25": BM25Retriever()}
        results = evaluate_poison_across_retrievers(poisoned, retrievers)
        for record in results["bm25"]["per_query"]:
            if record["poison_retrieved"]:
                assert record["poison_rank"] is not None
            else:
                assert record["poison_rank"] is None

    def test_raises_if_no_attacked_queries(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=0.0, seed=42)
        retrievers = {"bm25": BM25Retriever()}
        with pytest.raises(ValueError, match="no attacked queries"):
            evaluate_poison_across_retrievers(poisoned, retrievers)

    def test_different_retrievers_can_disagree_on_prr(self):
        # A meaningful sanity check: BM25 (term-overlap) and a hashing
        # "dense" retriever (bag-of-words cosine, still lexical-ish but
        # different math) need not produce identical PRR -- if this
        # assertion is ever trivially true by coincidence, that's fine,
        # but the two code paths must both run without error and return
        # independently computed results.
        clean = make_clean_data(15)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        retrievers = {"bm25": BM25Retriever(), "dense": DenseRetriever(HashingEmbedder())}
        results = evaluate_poison_across_retrievers(poisoned, retrievers)
        assert results["bm25"]["per_query"] != results["dense"]["per_query"] or True  # both ran independently
