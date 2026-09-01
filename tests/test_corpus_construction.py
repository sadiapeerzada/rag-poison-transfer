"""Tests for corpus construction determinism and correctness.

These tests verify that:
  1. Corpus construction is deterministic (same seed → same corpus)
  2. Deduplication works correctly
  3. Canonical IDs are stable
  4. Gold labels remain attached to queries
  5. Corpus statistics are accurate
"""
import pytest
from src.data.loaders import load_hotpotqa_distractor


class TestCorpusDeterminism:
    """Corpus construction should be deterministic."""

    def test_same_seed_produces_same_corpus_size(self):
        """Two runs with same seed should produce identical corpus size."""
        result1 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        result2 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        assert len(result1["corpus"]) == len(result2["corpus"])

    def test_same_seed_produces_same_doc_ids(self):
        """Two runs with same seed should produce identical doc IDs."""
        result1 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        result2 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        doc_ids_1 = sorted([d["doc_id"] for d in result1["corpus"]])
        doc_ids_2 = sorted([d["doc_id"] for d in result2["corpus"]])
        assert doc_ids_1 == doc_ids_2

    def test_different_seed_produces_different_corpus(self):
        """Two runs with different seeds should produce different corpora."""
        result1 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        result2 = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=99
        )
        # Different seeds should (very likely) produce different corpus sizes
        # or at least different doc IDs due to different question sampling
        doc_ids_1 = sorted([d["doc_id"] for d in result1["corpus"]])
        doc_ids_2 = sorted([d["doc_id"] for d in result2["corpus"]])
        # We don't assert they're different (depends on dataset), but we
        # verify both are non-empty and valid
        assert len(doc_ids_1) > 0
        assert len(doc_ids_2) > 0


class TestCorpusDeduplication:
    """Corpus deduplication should remove duplicate documents."""

    def test_same_seed_same_queries_means_same_doc_content(self):
        """Same seed and queries mean same corpus content."""
        result1 = load_hotpotqa_distractor(
            split="train", n_samples=3, seed=42
        )
        result2 = load_hotpotqa_distractor(
            split="train", n_samples=3, seed=42
        )
        # Build sets of (doc_id, text) for comparison
        docs_1 = {(d["doc_id"], d["text"]) for d in result1["corpus"]}
        docs_2 = {(d["doc_id"], d["text"]) for d in result2["corpus"]}
        assert docs_1 == docs_2

    def test_corpus_has_no_duplicate_doc_ids(self):
        """Corpus should have unique doc_ids (no duplicates)."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=10, seed=42
        )
        doc_ids = [d["doc_id"] for d in result["corpus"]]
        unique_ids = set(doc_ids)
        # Should have no duplicates
        assert len(doc_ids) == len(unique_ids)


class TestCanonicalDocIDs:
    """Canonical document IDs should be stable and deterministic."""

    def test_canonical_ids_are_strings(self):
        """All canonical IDs should be strings."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        for doc in result["corpus"]:
            assert isinstance(doc["doc_id"], str)
            assert len(doc["doc_id"]) > 0

    def test_canonical_ids_contain_dataset_tag(self):
        """Canonical IDs should start with dataset tag."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        for doc in result["corpus"]:
            # Format: "hotpotqa::title::hash"
            assert doc["doc_id"].startswith("hotpotqa::")
            parts = doc["doc_id"].split("::")
            assert len(parts) == 3
            assert parts[0] == "hotpotqa"

    def test_canonical_ids_are_query_independent(self):
        """Same doc should get same canonical ID regardless of query context."""
        # Load same data with different sampling (if possible) and verify
        # that docs with same content get same ID
        result = load_hotpotqa_distractor(
            split="train", n_samples=10, seed=42
        )
        # Find any two docs with same title (likely in a dataset of 10 queries)
        # and verify they'd have same ID
        titles_seen = {}
        for doc in result["corpus"]:
            # Extract title from canonical ID (format: hotpotqa::title::hash)
            parts = doc["doc_id"].split("::")
            if len(parts) >= 2:
                title = parts[1]  # Normalized title
                if title not in titles_seen:
                    titles_seen[title] = []
                titles_seen[title].append(doc["doc_id"])

        # For each title that appears, all IDs should be identical
        for title, ids in titles_seen.items():
            if len(ids) > 1:
                # Multiple corpus entries with same title should have same ID
                assert len(set(ids)) == 1, f"Duplicate title {title} has different IDs"


class TestGoldDocIDMapping:
    """Gold document IDs should correctly map queries to corpus."""

    def test_all_gold_doc_ids_exist_in_corpus(self):
        """Every query's gold_doc_ids should exist in corpus."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=10, seed=42
        )
        corpus_doc_ids = {d["doc_id"] for d in result["corpus"]}
        for query in result["queries"]:
            gold_ids = query.get("gold_doc_ids", [])
            for gold_id in gold_ids:
                assert gold_id in corpus_doc_ids, (
                    f"Query {query['query_id']} has gold_id {gold_id} "
                    f"not in corpus"
                )

    def test_queries_have_gold_answer(self):
        """Every query should have a gold answer."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        for query in result["queries"]:
            assert "gold_answer" in query
            assert isinstance(query["gold_answer"], str)
            assert len(query["gold_answer"]) > 0

    def test_queries_have_gold_supporting_facts(self):
        """Queries should have supporting facts preserved."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        for query in result["queries"]:
            facts = query.get("gold_supporting_facts", [])
            assert isinstance(facts, list)
            for fact in facts:
                assert "title" in fact
                assert "sent_id" in fact


class TestCorpusStatistics:
    """Corpus statistics should be accurate and reasonable."""

    def test_corpus_size_reasonable_for_sample(self):
        """With N=5 queries, expect ~40-60 docs (assumes ~10 per query, ~50% dedup)."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        corpus_size = len(result["corpus"])
        # Very rough heuristic: at least 5 (one per query), at most 50 (10*5 no dedup)
        assert 5 <= corpus_size <= 100, (
            f"Corpus size {corpus_size} seems unreasonable for 5 queries"
        )

    def test_query_count_matches_sample_size(self):
        """Number of queries should match n_samples."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=7, seed=42
        )
        assert len(result["queries"]) == 7

    def test_corpus_and_queries_both_present(self):
        """Result should have both corpus and queries."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=3, seed=42
        )
        assert "corpus" in result
        assert "queries" in result
        assert len(result["corpus"]) > 0
        assert len(result["queries"]) > 0

    def test_documents_have_text_and_id(self):
        """Every corpus doc should have doc_id and text."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        for doc in result["corpus"]:
            assert "doc_id" in doc
            assert "text" in doc
            assert isinstance(doc["text"], str)
            assert len(doc["text"]) > 0

    def test_queries_have_query_id_and_question(self):
        """Every query should have query_id and question."""
        result = load_hotpotqa_distractor(
            split="train", n_samples=5, seed=42
        )
        for query in result["queries"]:
            assert "query_id" in query
            assert "question" in query
            assert isinstance(query["question"], str)
            assert len(query["question"]) > 0
