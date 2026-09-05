"""Tests for poison-injection scaffolding and the lexical attack family.

Uses small synthetic clean datasets rather than real HotpotQA downloads,
so these tests are fast and fully deterministic -- no network required.
"""
import random

import pytest

from src.attacks.base import PoisonAttack, PoisonDocument, poison_doc_id
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack, _extract_keywords


def make_clean_data(n_queries=6):
    corpus = [
        {"doc_id": f"clean::doc_{i}", "text": f"Clean document number {i} content."}
        for i in range(n_queries)
    ]
    queries = [
        {
            "query_id": f"q{i}",
            "question": f"What is the value of item number {i}?",
            "gold_answer": f"answer_{i}",
            "gold_doc_ids": [f"clean::doc_{i}"],
        }
        for i in range(n_queries)
    ]
    return {"corpus": corpus, "queries": queries}


class TestPoisonDocId:
    def test_format_includes_all_components(self):
        doc_id = poison_doc_id("lexical", "q1", 0, "some text")
        assert doc_id.startswith("poison::lexical::q1::0::")

    def test_different_text_gives_different_id(self):
        id1 = poison_doc_id("lexical", "q1", 0, "text A")
        id2 = poison_doc_id("lexical", "q1", 0, "text B")
        assert id1 != id2

    def test_same_text_gives_same_id(self):
        id1 = poison_doc_id("lexical", "q1", 0, "same text")
        id2 = poison_doc_id("lexical", "q1", 0, "same text")
        assert id1 == id2


class TestInjectPoisons:
    def test_preserves_query_count(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        assert len(poisoned["queries"]) == len(clean["queries"])

    def test_preserves_gold_labels(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=2, poison_rate=1.0, seed=42)
        for clean_q, poisoned_q in zip(clean["queries"], poisoned["queries"]):
            assert poisoned_q["gold_answer"] == clean_q["gold_answer"]
            assert poisoned_q["gold_doc_ids"] == clean_q["gold_doc_ids"]

    def test_unattacked_queries_get_empty_poison_list(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=0.5, seed=42)
        unattacked = [q for q in poisoned["queries"] if not q["poison_doc_ids"]]
        assert len(unattacked) == 3
        for q in unattacked:
            assert q["attack_family"] is None

    def test_respects_n_poison_intensity(self):
        clean = make_clean_data(6)
        for n_poison in (1, 3, 5):
            poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=n_poison, poison_rate=1.0, seed=42)
            for q in poisoned["queries"]:
                assert len(q["poison_doc_ids"]) == n_poison

    def test_respects_poison_rate(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=0.3, seed=42)
        attacked = sum(1 for q in poisoned["queries"] if q["poison_doc_ids"])
        assert attacked == 3

    def test_poison_ids_distinct_from_clean_ids(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=2, poison_rate=1.0, seed=42)
        clean_ids = {d["doc_id"] for d in clean["corpus"]}
        poison_ids = {pid for q in poisoned["queries"] for pid in q["poison_doc_ids"]}
        assert clean_ids.isdisjoint(poison_ids)

    def test_clean_corpus_docs_all_preserved(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        poisoned_by_id = {d["doc_id"]: d["text"] for d in poisoned["corpus"]}
        for d in clean["corpus"]:
            assert poisoned_by_id.get(d["doc_id"]) == d["text"]

    def test_deterministic_with_same_seed(self):
        clean = make_clean_data(8)
        p1 = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=2, poison_rate=0.5, seed=7)
        p2 = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=2, poison_rate=0.5, seed=7)
        ids1 = [q["poison_doc_ids"] for q in p1["queries"]]
        ids2 = [q["poison_doc_ids"] for q in p2["queries"]]
        assert ids1 == ids2

    def test_does_not_mutate_input_data(self):
        clean = make_clean_data(6)
        original_corpus_len = len(clean["corpus"])
        original_query_ids = [dict(q) for q in clean["queries"]]
        inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=2, poison_rate=1.0, seed=42)
        assert len(clean["corpus"]) == original_corpus_len
        assert clean["queries"] == original_query_ids


class TestValidatePoisonedDataset:
    def test_valid_for_correct_injection(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=3, poison_rate=0.5, seed=42)
        report = validate_poisoned_dataset(clean, poisoned, expected_n_poison=3, expected_poison_rate=0.5)
        assert report["valid"] is True
        assert all(report["checks"].values())

    def test_detects_gold_answer_tampering(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        poisoned["queries"][0]["gold_answer"] = "TAMPERED"
        report = validate_poisoned_dataset(clean, poisoned)
        assert report["valid"] is False
        assert report["checks"]["gold_labels_untouched"] is False

    def test_detects_gold_doc_ids_tampering(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        poisoned["queries"][0]["gold_doc_ids"] = ["something_else"]
        report = validate_poisoned_dataset(clean, poisoned)
        assert report["valid"] is False
        assert report["checks"]["gold_labels_untouched"] is False

    def test_detects_clean_corpus_corruption(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        for d in poisoned["corpus"]:
            if d["doc_id"] == "clean::doc_0":
                d["text"] = "CORRUPTED"
        report = validate_poisoned_dataset(clean, poisoned)
        assert report["valid"] is False
        assert report["checks"]["clean_corpus_preserved"] is False

    def test_detects_id_collision(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42)
        colliding_id = clean["corpus"][0]["doc_id"]
        poisoned["queries"][0]["poison_doc_ids"] = [colliding_id]
        report = validate_poisoned_dataset(clean, poisoned)
        assert report["valid"] is False
        assert report["checks"]["no_poison_clean_id_collisions"] is False

    def test_detects_wrong_poison_count(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=3, poison_rate=1.0, seed=42)
        report = validate_poisoned_dataset(clean, poisoned, expected_n_poison=5)
        assert report["valid"] is False
        assert report["checks"]["poison_count_matches_intensity"] is False

    def test_detects_wrong_poison_rate(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=0.3, seed=42)
        report = validate_poisoned_dataset(clean, poisoned, expected_poison_rate=0.9)
        assert report["valid"] is False
        assert report["checks"]["poison_rate_matches_request"] is False


class TestLexicalAttack:
    def test_extract_keywords_drops_stopwords_and_short_words(self):
        keywords = _extract_keywords("What is the capital of France?")
        assert "capital" in keywords
        assert "france" in keywords
        assert "the" not in keywords
        assert "of" not in keywords

    def test_target_answer_differs_from_own_gold_answer(self):
        clean = make_clean_data(6)
        attack = LexicalInfluentialTokenAttack()
        rng = random.Random(1)
        query = clean["queries"][0]
        target_answer = attack.pick_cross_query_target_answer(query, clean["queries"], rng)
        doc = attack.generate(query, clean["queries"], rng, poison_index=0, target_answer=target_answer)
        assert doc.target_answer != query["gold_answer"]
        assert doc.target_answer == target_answer  # echoed back unchanged

    def test_generated_doc_has_correct_query_and_family(self):
        clean = make_clean_data(6)
        attack = LexicalInfluentialTokenAttack()
        rng = random.Random(1)
        query = clean["queries"][0]
        target_answer = attack.pick_cross_query_target_answer(query, clean["queries"], rng)
        doc = attack.generate(query, clean["queries"], rng, poison_index=2, target_answer=target_answer)
        assert doc.query_id == query["query_id"]
        assert doc.attack_family == "lexical_influential_token"
        assert doc.poison_index == 2

    def test_pick_cross_query_target_raises_with_no_candidates(self):
        attack = LexicalInfluentialTokenAttack()
        rng = random.Random(1)
        single_query = {"query_id": "only", "gold_answer": "answer_0"}
        with pytest.raises(ValueError, match="No valid cross-query target"):
            attack.pick_cross_query_target_answer(single_query, [single_query], rng)


class TestAnswerTypeMatching:
    """Cross-query target answers should prefer matching answer type
    (numeric vs. text), so a year-question doesn't get handed a
    person's name as its false target."""

    def test_numeric_gold_answer_prefers_numeric_target(self):
        query = {"query_id": "q0", "gold_answer": "1755"}
        all_queries = [
            query,
            {"query_id": "q1", "gold_answer": "Kevin Spacey"},
            {"query_id": "q2", "gold_answer": "1965"},
            {"query_id": "q3", "gold_answer": "Marie Curie"},
        ]
        attack = LexicalInfluentialTokenAttack()
        rng = random.Random(0)
        # Run many times -- should always pick the one numeric candidate.
        results = {attack.pick_cross_query_target_answer(query, all_queries, rng) for _ in range(20)}
        assert results == {"1965"}

    def test_text_gold_answer_prefers_text_target(self):
        query = {"query_id": "q0", "gold_answer": "Marie Curie"}
        all_queries = [
            query,
            {"query_id": "q1", "gold_answer": "1965"},
            {"query_id": "q2", "gold_answer": "Kevin Spacey"},
        ]
        attack = LexicalInfluentialTokenAttack()
        rng = random.Random(0)
        results = {attack.pick_cross_query_target_answer(query, all_queries, rng) for _ in range(20)}
        assert results == {"Kevin Spacey"}

    def test_falls_back_to_any_type_if_no_same_type_candidate(self):
        query = {"query_id": "q0", "gold_answer": "1755"}
        all_queries = [
            query,
            {"query_id": "q1", "gold_answer": "Kevin Spacey"},
        ]
        attack = LexicalInfluentialTokenAttack()
        rng = random.Random(0)
        # Only a text candidate exists -- must fall back to it, not raise.
        result = attack.pick_cross_query_target_answer(query, all_queries, rng)
        assert result == "Kevin Spacey"

    def test_answer_type_classifies_numeric_correctly(self):
        assert LexicalInfluentialTokenAttack._answer_type("1755") == "numeric"
        assert LexicalInfluentialTokenAttack._answer_type("1,024") == "numeric"
        assert LexicalInfluentialTokenAttack._answer_type("Marie Curie") == "text"
        assert LexicalInfluentialTokenAttack._answer_type("Yes") == "text"


class TestCoordinatedMultiDocumentTargets:
    """Research plan calls multi-document poison 'coordinated poison
    docs' -- all documents for one attacked query must support the SAME
    false target answer, chosen once, not independently per document."""

    def test_all_poison_docs_for_a_query_share_the_same_target_answer(self):
        clean = make_clean_data(10)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=5, poison_rate=1.0, seed=42)
        for query in poisoned["queries"]:
            target = query["poison_target_answer"]
            for doc_id in query["poison_doc_ids"]:
                doc_text = next(d["text"] for d in poisoned["corpus"] if d["doc_id"] == doc_id)
                assert target in doc_text, f"target {target!r} not found in poison doc for {query['query_id']}"

    def test_poison_target_answer_field_present_and_none_when_unattacked(self):
        clean = make_clean_data(6)
        poisoned = inject_poisons(clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=0.5, seed=42)
        for query in poisoned["queries"]:
            if query["poison_doc_ids"]:
                assert query["poison_target_answer"] is not None
            else:
                assert query["poison_target_answer"] is None
