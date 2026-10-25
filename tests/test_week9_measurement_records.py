"""Raw measurement regressions using synthetic text and stub models only."""
import copy
import json

import pytest

from src.attacks.asr import _extract_answer, run_source_target_asr
from src.evaluation.qa_records import (
    EXTRACTOR_VERSION, LEGACY_EXTRACTOR_VERSION, MEASUREMENT_SCHEMA,
    extract_answer, generate_qa, summarize_observations, validate_qa,
)
from src.pipelines.generator import GenerationResult
from test_transfer_framework import _poison_fingerprint_fixture, _TransferFakeRetriever


@pytest.mark.parametrize("raw,answer", [
    ("A. B. Example", "A. B. Example"), ("J. K. Example. This is extra.", "J. K. Example"),
    ("Dr. Example", "Dr. Example"), ("U.S. Example", "U.S. Example"),
    ("1.6 million", "1.6 million"), ("Paris. Extra sentence.", "Paris"),
    ("\n  A. B. Example\nExplanation", "A. B. Example"), ("", ""),
])
def test_extraction_preserves_initials_and_raw_version_can_be_replayed(raw, answer):
    assert _extract_answer(raw) == answer
    assert extract_answer(raw, LEGACY_EXTRACTOR_VERSION) == raw.split("\n")[0].split(". ")[0].strip()


class Generator:
    def generate(self, prompt, max_tokens):
        return GenerationResult("A. B. Example\nOriginal second line", 0.125, 12, 8, "<actual backend chat prompt>")


def test_lossless_generation_and_prompt_hashes():
    record = generate_qa(Generator(), "Exact input prompt", 64)
    assert record["raw_response"] == "A. B. Example\nOriginal second line"
    assert record["extracted_answer"] == "A. B. Example"
    assert record["backend_prompt"] == "<actual backend chat prompt>"
    assert record["generator_latency_seconds"] == 0.125
    assert record["prompt_tokens"] == 12 and record["elapsed_seconds"] >= 0
    assert record["extractor_version"] == EXTRACTOR_VERSION
    validate_qa(record, "A. B. Example")
    for key in ("prompt_sha256", "backend_prompt_sha256", "extracted_answer"):
        changed = {**record, key: "changed"}
        with pytest.raises(ValueError):
            validate_qa(changed, "A. B. Example")


class TransferGenerator:
    def __init__(self, source_success):
        self.context, self.calls, self.source_success = {}, [], source_success

    def set_observation_context(self, context):
        self.context = context

    def generate(self, prompt, max_tokens):
        self.calls.append(dict(self.context))
        qid = self.context["query_id"]
        poisoned = self.context["condition"] == "poisoned"
        success = poisoned and (self.context["target_pipeline"] == "dense" or
                               (self.source_success and qid == "q1"))
        answer = ("target" if success else "gold") + qid[-1]
        return GenerationResult(answer, 0.01, 10, 3)


@pytest.mark.parametrize("source_success", [False, True])
def test_transfer_retains_full_cohort_at_zero_or_partial_source_success(source_success):
    clean, poisoned, metadata = _poison_fingerprint_fixture()
    original = copy.deepcopy(poisoned)
    generator = TransferGenerator(source_success)
    matrix = run_source_target_asr(clean, poisoned, generator,
        {"bm25": _TransferFakeRetriever, "dense": _TransferFakeRetriever},
        source_pipeline="bm25", experiment_metadata=metadata, top_k=3)
    result = matrix.get_result("bm25", "dense")
    assert result.total_queries == 2
    assert result.attack_success_rate_source == (0.5 if source_success else 0)
    assert result.attack_success_rate_target == 1
    assert result.attack_transfer_rate == (1 if source_success else None)
    assert result.atr_denominator == int(source_success)
    assert result.conditional_target_asr == (1 if source_success else None)
    assert result.metric_denominators["target_asr"] == 2
    assert len(result.per_query_results) == 2
    assert {r["query_id"] for r in result.source_asr_results} == {"q1", "q2"}
    assert {r["query_id"] for r in result.target_asr_results} == {"q1", "q2"}
    assert len(generator.calls) == 8  # Both complete pipelines; diagonal is reused.
    assert poisoned == original
    assert result.result_schema.endswith("v2-full-cohort")
    assert json.loads(json.dumps(result.to_dict()))["target_asr_results"]
    for row in result.target_asr_results:
        assert row["measurement_schema"] == MEASUREMENT_SCHEMA
        assert row["clean_generation"]["raw_response"] == row["clean_answer"]
        assert row["poisoned_generation"]["raw_response"] == row["attacked_answer"]
        assert row["poisoned_f1"] == 0
        assert row["clean_retrieved_doc_ids"] and row["retrieved_evidence"]
        assert row["retrieval_call_accounting"]["normal_retrieval_calls"] == 2
    assert result.measurements["target"]["targeted_asr"]["denominator"] == 2


def test_undefined_exposure_and_rank_means_remain_explicit():
    generation = generate_qa(Generator(), "Prompt", 64)
    row = {"measurement_schema": MEASUREMENT_SCHEMA, "generation": generation,
           "answer": "A. B. Example", "gold_answer": "A. B. Example", "em": 1.0, "f1": 1.0,
           "retrieval_elapsed_seconds": 0.1,
           "retrieval_call_accounting": {"normal_retrieval_calls": 1, "diagnostic_retrieval_calls": 0}}
    poisoned = {**row, "targeted_asr": False, "poison_retrieved": False, "poison_rank": None}
    result = summarize_observations([row], [poisoned])
    assert result["asr_given_poison_visible"] == {"numerator": 0, "denominator": 0, "rate": None}
    assert result["mean_poison_rank_when_found"]["mean"] is None
    assert result["mean_poison_rank_when_found"]["denominator"] == 0
    assert result["clean_f1"]["mean"] == 1
    assert result["inner_retrieval_operations"]["normal_inner_retrieval_operations"] is None
    with pytest.raises(ValueError, match="mix"):
        summarize_observations([row], [{**poisoned, "measurement_schema": None}])
    with pytest.raises(ValueError, match="EM/F1"):
        summarize_observations([row], [{**poisoned, "f1": 0}])


@pytest.mark.parametrize("field,value", [("elapsed_seconds", float("nan")), ("generator_latency_seconds", -1),
                                         ("prompt_tokens", True), ("completion_tokens", -1)])
def test_nonfinite_or_invalid_measurement_is_not_serialized_as_a_valid_result(field, value):
    record = generate_qa(Generator(), "Prompt", 64)
    record[field] = value
    with pytest.raises(ValueError):
        validate_qa(record, record["extracted_answer"])
