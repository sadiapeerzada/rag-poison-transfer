import copy
import json
from types import SimpleNamespace

import pytest

import scripts.run_week9_matched_poison_comparison as comparison
from scripts.run_week9_poison_pilot import build_pilot_manifest
from src.attacks.injection import inject_poisons
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.experiments.protocol import poison_instances_fingerprint, query_set_fingerprint


def _fixture():
    clean_data = {
        "corpus": [{"doc_id": "clean-doc", "text": "A clean supporting passage."}],
        "queries": [
            {
                "query_id": f"q{index}",
                "question": f"Question {index}?",
                "gold_answer": f"Answer {index}",
                "gold_doc_ids": ["clean-doc"],
            }
            for index in range(10)
        ],
    }
    attacked_ids = [query["query_id"] for query in clean_data["queries"]]
    poisoned_data = inject_poisons(
        clean_data,
        LexicalInfluentialTokenAttack(repeat_factor=4),
        n_poison=1,
        poison_rate=1.0,
        seed=42,
        attacked_query_ids=attacked_ids,
    )
    fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    metadata = {
        "git_commit_sha": "a" * 40,
        "git_dirty": True,
        "dataset": "hotpotqa/hotpot_qa:distractor",
        "seed": 42,
        "attack_family": "lexical_influential_token",
        "attack_config": {
            "repeat_factor": 4,
            "n_poison_per_attacked_query": 1,
            "poison_rate": 1.0,
        },
        "query_set_fingerprint": query_set_fingerprint(clean_data["queries"]),
        "model_identifier": "mlx-test-model",
        "poison_instance_fingerprint": fingerprint,
        "poison_manifest_fingerprint": fingerprint,
        "dataset_revision": "revision-1",
        "dataset_split": "validation",
        "seed": 42,
        "generator_model": "mlx-test-model",
    }
    manifest = build_pilot_manifest(
        experiment_id="source-pilot",
        clean_data=clean_data,
        poisoned_data=poisoned_data,
        metadata=metadata,
        selected_query_ids=attacked_ids,
        attacked_query_ids=attacked_ids,
        heldout_manifest_fingerprint="heldout-fingerprint",
        dataset_revision="revision-1",
        dataset_split="validation",
        seed=42,
        poison_rate=1.0,
        n_poison=1,
        attack_repeat_factor=4,
        attack_version="git:" + "a" * 40,
        generator_backend="mlx",
        generator_model="mlx-test-model",
        generator_max_tokens=64,
        top_k=3,
        retrieval_metric_k=10,
        retriever_config={
            "retriever": "rcd",
            "base_retriever": "dense",
            "sparse_retriever": "bm25",
            "dense_retriever": "dense",
            "embedder_model": "test-embedder",
            "output_k": 3,
            "rcd_candidate_k": 10,
            "rcd_rewrite_count": 3,
            "rcd_consistency_weight": 0.45,
            "rcd_redundancy_weight": 0.0,
            "rcd_conflict_weight": 0.1,
            "rcd_base_rank_weight": 0.45,
        },
        rcd_config=comparison.EXPECTED_RCD_CONFIG,
    )
    return clean_data, poisoned_data, manifest, fingerprint


def _configs():
    shared = {
        "dataset_loader": "load_hotpotqa_distractor",
        "dataset_split": "validation",
        "dataset_revision": "revision-1",
        "seed": 42,
        "embedder_model": "test-embedder",
        "top_k": 3,
        "generator_backend": "mlx",
        "generator_model": "mlx-test-model",
        "max_tokens": 64,
        "load_in_4bit": True,
        "final_run": True,
    }
    dense = {**shared, "retriever": "dense"}
    rcd = {
        **shared,
        "retriever": "rcd",
        "rcd_candidate_k": 10,
        "rcd_rewrite_count": 3,
        "rcd_consistency_weight": 0.45,
        "rcd_redundancy_weight": 0.0,
        "rcd_conflict_weight": 0.1,
        "rcd_base_rank_weight": 0.45,
    }
    return dense, rcd


def test_replays_exact_manifest_snapshot_and_fingerprint(monkeypatch):
    clean_data, poisoned_data, manifest, fingerprint = _fixture()
    monkeypatch.setattr(comparison, "EXPECTED_POISON_FINGERPRINT", fingerprint)

    replayed = comparison.reconstruct_matched_snapshot(clean_data, manifest)

    assert replayed == poisoned_data
    assert poison_instances_fingerprint(clean_data, replayed) == fingerprint
    assert [
        (query["query_id"], query["poison_doc_ids"], query["poison_target_answer"])
        for query in replayed["queries"]
    ] == [
        (
            query["query_id"],
            query["poison_doc_ids"],
            query["poison_target_answer"],
        )
        for query in poisoned_data["queries"]
    ]


@pytest.mark.parametrize("mutation", ["document", "association"])
def test_rejects_modified_poison_snapshot(mutation, monkeypatch):
    clean_data, _, manifest, fingerprint = _fixture()
    monkeypatch.setattr(comparison, "EXPECTED_POISON_FINGERPRINT", fingerprint)
    changed = copy.deepcopy(manifest)
    if mutation == "document":
        changed["poison_documents"][0]["text"] += " modified"
    else:
        changed["query_poison_associations"][0]["poison_doc_ids"] = []

    with pytest.raises(ValueError):
        comparison.reconstruct_matched_snapshot(clean_data, changed)


def test_dense_and_rcd_receive_identical_poison_documents(monkeypatch):
    clean_data, poisoned_data, _, _ = _fixture()
    built_corpora = []

    class FakeRetriever:
        def build(self, corpus):
            built_corpora.append(corpus)

    monkeypatch.setattr(comparison, "build_retriever", lambda config: FakeRetriever())
    dense_config, rcd_config = _configs()
    comparison.build_matched_retrievers(
        dense_config, rcd_config, clean_data, poisoned_data
    )

    dense_poisoned = built_corpora[1]
    rcd_poisoned = built_corpora[3]
    assert [(doc["doc_id"], doc["text"]) for doc in dense_poisoned] == [
        (doc["doc_id"], doc["text"]) for doc in rcd_poisoned
    ]
    assert [(doc["doc_id"], doc["text"]) for doc in dense_poisoned] == [
        (doc["doc_id"], doc["text"]) for doc in poisoned_data["corpus"]
    ]


@pytest.mark.parametrize("mismatch", ["revision", "generator", "rcd"])
def test_rejects_shared_setting_or_frozen_rcd_mismatch(mismatch):
    _, _, manifest, _ = _fixture()
    dense_config, rcd_config = _configs()
    changed_manifest = copy.deepcopy(manifest)
    if mismatch == "revision":
        changed_manifest["dataset"]["revision"] = "other-revision"
    elif mismatch == "generator":
        rcd_config["generator_model"] = "different-model"
    else:
        rcd_config["rcd_conflict_weight"] = 0.2

    with pytest.raises(ValueError):
        comparison.validate_matched_configs(
            dense_config, rcd_config, changed_manifest
        )


def _result(
    query_id,
    *,
    clean_correct,
    poisoned_correct,
    targeted,
    poison_retrieved,
    prr,
    degradation,
):
    return {
        "query_id": query_id,
        "clean_condition": {"answer_correct": clean_correct},
        "poisoned_condition": {
            "answer_correct": poisoned_correct,
            "targeted_asr": targeted,
            "poison_retrieved": poison_retrieved,
            "prr_at_k": {str(k): prr for k in comparison.CUTOFFS},
        },
        "query_untargeted_degradation": degradation,
    }


@pytest.mark.parametrize(
    ("clean_correct", "poisoned_correct"),
    [(False, False), (False, True), (True, False), (True, True)],
)
def test_query_degradation_truth_table_and_jsonl_pair(
    clean_correct, poisoned_correct
):
    gold = "Gold Answer"
    clean_answer = gold if clean_correct else "Other Clean Answer"
    poison_answer = gold if poisoned_correct else "Other Poison Answer"

    class FakeRetriever:
        def __init__(self, document):
            self.document = document

        def retrieve(self, question, top_k):
            return [SimpleNamespace(**self.document)]

    class FakeGenerator:
        def __init__(self):
            self.answers = iter([clean_answer, poison_answer])

        def generate(self, prompt, max_tokens):
            return SimpleNamespace(
                text=next(self.answers),
                latency_seconds=0.0,
                prompt_tokens=1,
                completion_tokens=1,
            )

    clean_doc = {"doc_id": "clean-doc", "text": "Clean evidence."}
    poison_doc = {"doc_id": "poison-doc", "text": "Poison evidence."}
    clean_data = {
        "corpus": [clean_doc],
        "queries": [
            {
                "query_id": "q1",
                "question": "Question?",
                "gold_answer": gold,
                "gold_doc_ids": ["clean-doc"],
            }
        ],
    }
    poisoned_data = {
        "corpus": [clean_doc, poison_doc],
        "queries": [
            {
                **clean_data["queries"][0],
                "attack_family": "lexical_influential_token",
                "poison_doc_ids": ["poison-doc"],
                "poison_target_answer": "Poison Target",
            }
        ],
    }
    paired = comparison.evaluate_pipeline(
        pipeline="dense",
        clean_retriever=FakeRetriever(clean_doc),
        poisoned_retriever=FakeRetriever(poison_doc),
        clean_data=clean_data,
        poisoned_data=poisoned_data,
        generator=FakeGenerator(),
        top_k=1,
        max_tokens=64,
    )[0]
    expected = clean_correct and not poisoned_correct
    assert paired["query_untargeted_degradation"] is expected

    clean_record, poisoned_record = [
        json.loads(line)
        for line in (
            json.dumps(record)
            for record in comparison.flatten_query_result_records(paired)
        )
    ]
    assert clean_record["condition"] == "clean"
    assert poisoned_record["condition"] == "poisoned"
    assert clean_record["query_untargeted_degradation"] is expected
    assert poisoned_record["query_untargeted_degradation"] is expected
    assert "untargeted_degradation" not in clean_record
    assert "untargeted_degradation" not in poisoned_record
    definition = comparison.METRIC_DEFINITIONS["query_untargeted_degradation"]
    assert "Paired query-level" in definition
    assert "denominator is all selected queries" in definition


def test_paired_metrics_and_zero_conditional_denominator():
    dense_rows = [
        _result("q1", clean_correct=True, poisoned_correct=False, targeted=True,
                poison_retrieved=False, prr=0.0, degradation=True),
        _result("q2", clean_correct=False, poisoned_correct=True, targeted=False,
                poison_retrieved=False, prr=0.0, degradation=False),
    ]
    rcd_rows = [
        _result("q1", clean_correct=True, poisoned_correct=True, targeted=False,
                poison_retrieved=False, prr=0.0, degradation=False),
        _result("q2", clean_correct=False, poisoned_correct=False, targeted=False,
                poison_retrieved=False, prr=0.0, degradation=False),
    ]

    dense_summary = comparison.summarize_pipeline(dense_rows)
    paired = comparison.paired_differences(dense_rows, rcd_rows)

    assert dense_summary["clean_condition"]["clean_answer_accuracy"] == {
        "numerator": 1, "denominator": 2, "rate": 0.5
    }
    assert dense_summary["poisoned_condition"]["asr_given_poison_retrieved"] == {
        "numerator": 0, "denominator": 0, "rate": None
    }
    assert (
        paired["metrics"]["poisoned_answer_correct"]["dense_minus_rcd_rate"]
        == 0.0
    )
    assert dense_summary["query_untargeted_degradation"] == {
        "numerator": 1,
        "denominator": 2,
        "rate": 0.5,
    }
    assert (
        paired["metrics"]["query_untargeted_degradation"][
            "dense_minus_rcd_rate"
        ]
        == 0.5
    )
    assert paired["conditional_asr_comparison"]["dense_minus_rcd_rate"] is None
    assert len(paired["per_query"]) == 2
    assert "same 2 queries" in paired["interpretation"]
    assert "not statistical significance or causal proof" in paired["interpretation"]


def test_exclusive_outputs_and_failure_record_are_honest(tmp_path):
    output_dir = tmp_path / "outside-worktree"
    output_dir.mkdir()
    collision = output_dir / "pilot.manifest.json"
    collision.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        comparison._output_paths(output_dir, "pilot")

    manifest_path = output_dir / "run.manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    result_path = output_dir / "run.jsonl"
    result_path.write_text('{"partial": true}\n', encoding="utf-8")
    failure_path = output_dir / "run.failure.json"
    error = RuntimeError("retriever initialization failed")
    try:
        raise error
    except RuntimeError as caught:
        comparison.write_failure_record(
            path=failure_path,
            experiment_id="run",
            failed_stage="retriever_initialization",
            error=caught,
            runtime_seconds=1.25,
            manifest_path=manifest_path,
            results_path=result_path,
        )

    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure["is_final_run"] is False
    assert failure["failed_stage"] == "retriever_initialization"
    assert failure["error"] == "retriever initialization failed"
    assert failure["partial_results_path"] == str(result_path)
