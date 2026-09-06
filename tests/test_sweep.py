"""Tests for the systematic attack x intensity x retriever sweep."""
import pytest

from src.attacks.sweep import run_attack_intensity_sweep
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever, HashingEmbedder


def make_clean_data(n_queries=12):
    corpus = [
        {"doc_id": f"clean::doc_{i}", "text": f"Clean document about topic {i} and related facts here."}
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


class TestRunAttackIntensitySweep:
    def test_produces_one_row_per_attack_intensity_retriever_combo(self):
        clean = make_clean_data(12)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever(), "dense": DenseRetriever(HashingEmbedder())}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1, 3), poison_rate=1.0, seed=42)
        # 1 attack x 2 intensities x 2 retrievers = 4 rows
        assert len(rows) == 4

    def test_rows_have_expected_fields(self):
        clean = make_clean_data(12)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever()}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1,), poison_rate=1.0, seed=42)
        row = rows[0]
        for field in ("attack", "n_poison", "poison_rate", "retriever", "n_attacked_queries", "prr@1", "prr@3", "prr@5", "prr@10"):
            assert field in row

    def test_multiple_attacks_and_intensities_covered(self):
        clean = make_clean_data(12)
        attacks = {
            "lexical_a": LexicalInfluentialTokenAttack(repeat_factor=2),
            "lexical_b": LexicalInfluentialTokenAttack(repeat_factor=8),
        }
        retrievers = {"bm25": BM25Retriever()}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1, 3, 5), poison_rate=1.0, seed=42)
        # 2 attacks x 3 intensities x 1 retriever = 6 rows
        assert len(rows) == 6
        assert {r["attack"] for r in rows} == {"lexical_a", "lexical_b"}
        assert {r["n_poison"] for r in rows} == {1, 3, 5}

    def test_low_poison_rate_reflected_in_rows_and_attacked_count(self):
        clean = make_clean_data(20)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever()}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1,), poison_rate=0.2, seed=42)
        assert rows[0]["poison_rate"] == 0.2
        assert rows[0]["n_attacked_queries"] == 4  # 20% of 20

    def test_raises_on_validation_failure(self, monkeypatch):
        import src.attacks.sweep as sweep_module
        clean = make_clean_data(12)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever()}

        def fake_validate(*args, **kwargs):
            return {"valid": False, "checks": {"gold_labels_untouched": False}, "details": {}}

        monkeypatch.setattr(sweep_module, "validate_poisoned_dataset", fake_validate)
        with pytest.raises(ValueError, match="failed validation"):
            run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1,), poison_rate=1.0, seed=42)


class TestReproducibilityMetadata:
    """Research plan Section 12: every experiment row must carry enough
    metadata to reproduce it (seed, top_k, generator, query counts,
    timestamp), not rely only on prose documentation."""

    def test_rows_include_reproducibility_metadata(self):
        clean = make_clean_data(12)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever()}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1,), poison_rate=1.0, seed=42, top_k=10)
        row = rows[0]
        for field in ("seed", "top_k", "n_total_queries", "timestamp"):
            assert field in row

    def test_seed_and_top_k_match_call_arguments(self):
        clean = make_clean_data(12)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever()}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1,), poison_rate=1.0, seed=99, top_k=7)
        assert rows[0]["seed"] == 99
        assert rows[0]["top_k"] == 7

    def test_n_total_queries_matches_dataset_size(self):
        clean = make_clean_data(15)
        attacks = {"lexical": LexicalInfluentialTokenAttack()}
        retrievers = {"bm25": BM25Retriever()}
        rows = run_attack_intensity_sweep(clean, attacks, retrievers, n_poison_values=(1,), poison_rate=1.0, seed=42)
        assert rows[0]["n_total_queries"] == 15
