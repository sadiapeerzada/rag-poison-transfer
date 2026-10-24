"""Regressions for Week 9 semantic generation reliability (no GPU required)."""
import json
import random
import sys
import types

import pytest

from src.attacks.checkpoint import PoisonCheckpoint
from src.attacks.injection import inject_poisons
from src.attacks.semantic_fluent import (
    SemanticFluentFalseEvidenceAttack,
    SemanticQualityError,
    semantic_support_status,
)
from src.pipelines.generator import GenerationResult, MLXGenerator


def clean_data():
    return {
        "corpus": [{"doc_id": "a", "text": "Clean A"}, {"doc_id": "b", "text": "Clean B"}],
        "queries": [
            {"query_id": "q0", "question": "Who led this project?",
             "gold_answer": "Alice", "gold_doc_ids": ["a"]},
            {"query_id": "q1", "question": "Who led the other project?",
             "gold_answer": "Bob", "gold_doc_ids": ["b"]},
        ],
    }


class SequenceGenerator:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, prompt, max_tokens=150):
        self.prompts.append((prompt, max_tokens))
        outcome = self.responses.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return GenerationResult(outcome, 0.1, 10, 20)


class AffirmingGenerator:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt, max_tokens=150):
        self.calls += 1
        target = prompt.split('Claim: the correct answer is "', 1)[1].split('"', 1)[0]
        text = (
            f"Historical reports identify {target} as the answer to this question. "
            f"Several records also identify {target} as the answer in institutional accounts."
        )
        return GenerationResult(text, 0.1, 10, 20)


def test_support_screen_distinguishes_assertion_denial_and_mentions():
    assert semantic_support_status(
        "London is the capital of France according to the fictional record.", "London"
    ) == "heuristically_supported_unverified"
    assert semantic_support_status(
        "The claim that London is the capital of France is incorrect. Paris is the capital.", "London"
    ) == "rejected"
    assert semantic_support_status(
        "London is not the capital of France, Paris is.", "London"
    ) == "rejected"
    assert semantic_support_status(
        "Paris, not London, is the capital of France.", "London"
    ) == "rejected"
    assert semantic_support_status(
        "A discussion compared London's landmarks with those of Paris.", "London"
    ) == "mention_only"
    assert semantic_support_status(
        "Historical reports identify Bob as the answer to this question.", "Bob"
    ) == "heuristically_supported_unverified"


def test_rejection_then_documented_retry_success():
    generator = SequenceGenerator([
        "The claim that Bob is the answer is incorrect. Alice is the answer.",
        "Bob is the answer in historical documents, and Bob was the recorded leader.",
    ])
    attack = SemanticFluentFalseEvidenceAttack(generator, max_attempts=2)
    clean = clean_data()
    doc = attack.generate(clean["queries"][0], clean["queries"], random.Random(1), 0, "Bob")
    assert "Bob is the answer" in doc.text
    assert len(generator.prompts) == 2
    assert generator.prompts[0][0] != generator.prompts[1][0]
    assert len(attack.attempt_log[("q0", 0)]) == 2
    assert attack.attempt_log[("q0", 0)][0]["outcome"] == "rejected"
    assert attack.attempt_log[("q0", 0)][1]["outcome"] == "heuristically_supported_unverified"


def test_exhaustion_refuses_invalid_or_unverified_text():
    for response in [
        "The claim that Bob is the answer is incorrect. Alice is the answer.",
        "A discussion of Bob and Alice with no information on who led the project.",
    ]:
        generator = SequenceGenerator([response, response])
        attack = SemanticFluentFalseEvidenceAttack(generator, max_attempts=2)
        with pytest.raises(SemanticQualityError, match="exhausted 2 attempts"):
            attack.generate(clean_data()["queries"][0], clean_data()["queries"],
                            random.Random(2), 0, "Bob")
        assert len(attack.attempt_log[("q0", 0)]) == 2


def test_generation_error_does_not_retry_silently():
    generator = SequenceGenerator([RuntimeError("backend failed")])
    attack = SemanticFluentFalseEvidenceAttack(generator)
    with pytest.raises(RuntimeError, match="backend failed"):
        attack.generate(clean_data()["queries"][0], clean_data()["queries"],
                        random.Random(1), 0, "Bob")
    assert attack.attempt_log[("q0", 0)][0]["outcome"] == "generation_error"


def test_mlx_applies_chat_template_once(monkeypatch):
    observed = []
    class Tokenizer:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            observed.append(("template", messages, tokenize, add_generation_prompt))
            return "<chat>" + messages[0]["content"] + "</chat>"
        def encode(self, text, add_special_tokens=True):
            return list(text)
    tokenizer = Tokenizer()
    def fake_generate(model, tok, prompt, max_tokens, verbose):
        observed.append(("generation", prompt, max_tokens, verbose))
        return "Answer"
    fake = types.SimpleNamespace(load=lambda model: (object(), tokenizer), generate=fake_generate)
    monkeypatch.setitem(sys.modules, "mlx_lm", fake)
    backend = MLXGenerator()
    result = backend.generate("Question", max_tokens=64)
    assert result.text == "Answer"
    assert observed[0] == ("template", [{"role": "user", "content": "Question"}], False, True)
    assert observed[1] == ("generation", "<chat>Question</chat>", 64, False)
    assert result.prompt_tokens == len("<chat>Question</chat>")
    assert result.completion_tokens == len("Answer")


def test_checkpoint_resume_preserves_documents_and_skips_generation(tmp_path):
    clean = clean_data()
    provenance = {"commit": "abc", "source": "def"}
    prior = tmp_path / "prior"
    first = PoisonCheckpoint(
        prior, [], provenance=provenance,
        attack_family="semantic_fluent_false_evidence",
        intensity=1, allowed_query_ids=["q0", "q1"],
    )
    first_gen = AffirmingGenerator()
    original = inject_poisons(
        clean, SemanticFluentFalseEvidenceAttack(first_gen), n_poison=1,
        poison_rate=1.0, seed=42, checkpoint=first,
    )
    assert first_gen.calls == 2
    assert len(list((prior / "poison.checkpoints").glob("*.json"))) == 2
    dest = tmp_path / "recovery"
    recovered = PoisonCheckpoint(
        dest, [prior], provenance=provenance,
        attack_family="semantic_fluent_false_evidence",
        intensity=1, allowed_query_ids=["q0", "q1"],
    )
    second_gen = AffirmingGenerator()
    replayed = inject_poisons(
        clean, SemanticFluentFalseEvidenceAttack(second_gen), n_poison=1,
        poison_rate=1.0, seed=42, checkpoint=recovered,
    )
    assert second_gen.calls == 0
    assert original == replayed
    assert len(list((dest / "poison.checkpoints").glob("*.json"))) == 2


def test_checkpoint_rejects_corruption_and_cross_revision(tmp_path):
    prior = tmp_path / "prior"
    clean = clean_data()
    checkpoint = PoisonCheckpoint(
        prior, [], provenance={"sha": "old"},
        attack_family="semantic_fluent_false_evidence", intensity=1,
        allowed_query_ids=["q0", "q1"],
    )
    inject_poisons(clean, SemanticFluentFalseEvidenceAttack(AffirmingGenerator()),
                   n_poison=1, poison_rate=1.0, seed=42, checkpoint=checkpoint)
    with pytest.raises(ValueError, match="provenance mismatch"):
        PoisonCheckpoint(
            tmp_path / "new", [prior], provenance={"sha": "new"},
            attack_family="semantic_fluent_false_evidence", intensity=1,
            allowed_query_ids=["q0", "q1"],
        )
    path = sorted((prior / "poison.checkpoints").glob("*.json"))[0]
    payload = json.loads(path.read_text())
    payload["text"] += " tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        PoisonCheckpoint(
            tmp_path / "new2", [prior], provenance={"sha": "old"},
            attack_family="semantic_fluent_false_evidence", intensity=1,
            allowed_query_ids=["q0", "q1"],
        )
