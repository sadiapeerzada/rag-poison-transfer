"""Tests for the semantic-fluent false-evidence attack.

Uses a stub generator (no real model) to test the attack's own logic --
prompt construction, target-answer selection, scaffolding integration --
independent of actual generation quality, which requires a real GPU run.
"""
import random

import pytest

from src.attacks.semantic_fluent import SemanticFluentFalseEvidenceAttack
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.pipelines.generator import GenerationResult


class StubGenerator:
    """Deterministic fake generator: echoes back a fixed template
    referencing the prompt, so tests can assert on structure without
    needing a real model."""

    def __init__(self, response_template="Stub evidence text for: {prompt_snippet}"):
        self.response_template = response_template
        self.calls = []

    def generate(self, prompt, max_tokens=150):
        self.calls.append(prompt)
        text = self.response_template.format(prompt_snippet=prompt[:30])
        return GenerationResult(text=text, latency_seconds=0.0, prompt_tokens=len(prompt.split()), completion_tokens=len(text.split()))


class EmptyGenerator:
    """Stub that always returns empty text, to test the empty-output guard."""

    def generate(self, prompt, max_tokens=150):
        return GenerationResult(text="", latency_seconds=0.0, prompt_tokens=0, completion_tokens=0)


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


class TestSemanticFluentAttack:
    def test_generate_returns_poison_document_with_correct_fields(self):
        clean = make_clean_data(6)
        attack = SemanticFluentFalseEvidenceAttack(StubGenerator())
        rng = random.Random(1)
        query = clean["queries"][0]
        target_answer = attack.pick_cross_query_target_answer(query, clean["queries"], rng)
        doc = attack.generate(query, clean["queries"], rng, poison_index=0, target_answer=target_answer)
        assert doc.query_id == query["query_id"]
        assert doc.attack_family == "semantic_fluent_false_evidence"
        assert doc.target_answer == target_answer
        assert doc.target_answer != query["gold_answer"]
        assert doc.text  # non-empty

    def test_prompt_includes_question_and_target_answer(self):
        clean = make_clean_data(6)
        generator = StubGenerator()
        attack = SemanticFluentFalseEvidenceAttack(generator)
        rng = random.Random(1)
        query = clean["queries"][0]
        target_answer = attack.pick_cross_query_target_answer(query, clean["queries"], rng)
        doc = attack.generate(query, clean["queries"], rng, poison_index=0, target_answer=target_answer)
        sent_prompt = generator.calls[0]
        assert query["question"] in sent_prompt
        assert doc.target_answer in sent_prompt

    def test_raises_on_empty_generation(self):
        clean = make_clean_data(6)
        attack = SemanticFluentFalseEvidenceAttack(EmptyGenerator())
        rng = random.Random(1)
        query = clean["queries"][0]
        target_answer = attack.pick_cross_query_target_answer(query, clean["queries"], rng)
        with pytest.raises(ValueError, match="empty text"):
            attack.generate(query, clean["queries"], rng, poison_index=0, target_answer=target_answer)

    def test_integrates_with_inject_poisons(self):
        clean = make_clean_data(6)
        attack = SemanticFluentFalseEvidenceAttack(StubGenerator())
        poisoned = inject_poisons(clean, attack, n_poison=2, poison_rate=1.0, seed=42)
        report = validate_poisoned_dataset(clean, poisoned, expected_n_poison=2, expected_poison_rate=1.0)
        assert report["valid"] is True

    def test_max_tokens_forwarded_to_generator(self):
        clean = make_clean_data(2)

        class RecordingGenerator(StubGenerator):
            def generate(self, prompt, max_tokens=150):
                self.last_max_tokens = max_tokens
                return super().generate(prompt, max_tokens)

        generator = RecordingGenerator()
        attack = SemanticFluentFalseEvidenceAttack(generator, max_tokens=99)
        rng = random.Random(1)
        query = clean["queries"][0]
        target_answer = attack.pick_cross_query_target_answer(query, clean["queries"], rng)
        attack.generate(query, clean["queries"], rng, poison_index=0, target_answer=target_answer)
        assert generator.last_max_tokens == 99
