import copy
import hashlib
import json
import subprocess

import pytest

import scripts.aggregate_week9_multiseed_results as aggregate
import scripts.run_week9_matched_poison_comparison as comparison
import scripts.run_week9_multiseed_matched_evaluation as orchestration
from scripts.run_week9_poison_pilot import replay_poisoned_data, write_json_exclusive
from src.experiments.protocol import poison_instances_fingerprint, query_set_fingerprint


def _clean_data():
    return {
        "corpus": [{"doc_id": "clean-doc", "text": "Clean evidence for the pilot."}],
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


def _config():
    return {
        "dataset_revision": "revision-1",
        "dataset_split": "validation",
        "seed": 42,
        "retriever": "rcd",
        "embedder_model": "test-embedder",
        "generator_backend": "mlx",
        "generator_model": "mlx-test-model",
        "max_tokens": 64,
        "top_k": 3,
        "rcd_candidate_k": 10,
        "rcd_rewrite_count": 3,
        "rcd_consistency_weight": 0.45,
        "rcd_redundancy_weight": 0.0,
        "rcd_conflict_weight": 0.1,
        "rcd_base_rank_weight": 0.45,
    }


def _source_manifest(tmp_path, seed, clean_data=None):
    clean_data = clean_data or _clean_data()
    ids = [query["query_id"] for query in clean_data["queries"]]
    return orchestration.create_seed_poison_manifest(
        clean_data=clean_data,
        config=_config(),
        selected_query_ids=ids,
        heldout_fingerprint="heldout-fingerprint",
        heldout_manifest_path=tmp_path / "heldout.json",
        poison_seed=seed,
        experiment_id=f"source-seed-{seed}",
        git_sha="a" * 40,
        git_dirty=True,
    )


def _record(pipeline, query, condition, clean_answer, poisoned_answer, poison_id,
            poison_target, clean_correct, poison_correct, targeted, poison_retrieved):
    if condition == "clean":
        answer = clean_answer
        answer_correct = clean_correct
        retrieved = ["clean-doc"]
        generation_evidence = ["clean-doc"]
        prr = {str(k): 0.0 for k in aggregate.EXPECTED_CUTOFFS}
        poison_retrieved_condition = False
        poison_rank = None
        targeted_value = None
    else:
        answer = poisoned_answer
        answer_correct = poison_correct
        retrieved = [poison_id, "clean-doc"] if poison_retrieved else ["clean-doc"]
        generation_evidence = retrieved[:3]
        prr = {
            str(k): float(
                poison_retrieved and poison_id in retrieved[:k]
            )
            for k in aggregate.EXPECTED_CUTOFFS
        }
        poison_retrieved_condition = poison_retrieved
        poison_rank = 1 if poison_retrieved else None
        targeted_value = targeted
    return {
        "query_id": query["query_id"],
        "pipeline": pipeline,
        "condition": condition,
        "gold_answer": query["gold_answer"],
        "poison_target_answer": poison_target,
        "poison_doc_ids": [poison_id],
        "clean_answer": clean_answer,
        "poisoned_answer": poisoned_answer,
        "query_untargeted_degradation": clean_correct and not poison_correct,
        "answer": answer,
        "answer_correct": answer_correct,
        "targeted_asr": targeted_value,
        "poison_retrieved": poison_retrieved_condition,
        "poison_rank": poison_rank,
        "retrieved_doc_ids": retrieved,
        "retrieved_evidence": [
            {"doc_id": doc_id, "text": "evidence"}
            for doc_id in retrieved
        ],
        "generation_evidence_doc_ids": generation_evidence,
        "prr_at_k": prr,
        "retrieval_elapsed_seconds": 0.01,
        "generation": {
            "elapsed_seconds": 0.02,
            "generator_latency_seconds": 0.02,
            "prompt_tokens": 4,
            "completion_tokens": 2,
        },
    }


def _write_run(tmp_path, seed, *, clean_data=None):
    clean_data = clean_data or _clean_data()
    source = _source_manifest(tmp_path, seed, clean_data)
    source_path = tmp_path / f"source-{seed}.manifest.json"
    write_json_exclusive(source_path, source)
    selected_ids = source["dataset"]["selected_query_ids"]
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    comparison_id = f"comparison-{seed}"
    comparison_manifest_path = tmp_path / f"{comparison_id}.manifest.json"
    summary_path = tmp_path / f"{comparison_id}.summary.json"
    results_path = tmp_path / f"{comparison_id}.jsonl"
    dense_config = {
        "path": "dense.yaml",
        "sha256": "d" * 64,
        "retriever_configuration": {
            "retriever": "dense",
            "embedder_model": "test-embedder",
            "output_k": 3,
        },
    }
    rcd_config = {
        "path": "rcd.yaml",
        "sha256": "e" * 64,
        "retriever_configuration": {
            "retriever": "rcd",
            "embedder_model": "test-embedder",
            "output_k": 3,
        },
        "rcd_configuration": comparison.EXPECTED_RCD_CONFIG,
    }
    manifest = {
        "schema": aggregate.COMPARISON_SCHEMA,
        "experiment_id": comparison_id,
        "status": "exploratory_pilot_not_final",
        "is_final_run": False,
        "source_manifest_path": str(source_path),
        "source_manifest_sha256": source_hash,
        "source_manifest_experiment_id": source["experiment_id"],
        "dataset": {
            "name": "hotpotqa/hotpot_qa",
            "config": "distractor",
            "revision": "revision-1",
            "split": "validation",
            "heldout_manifest_fingerprint": "heldout-fingerprint",
            "selected_query_ids": selected_ids,
            "query_set_fingerprint": source["dataset"]["query_set_fingerprint"],
            "clean_corpus_fingerprint": source["clean_corpus_fingerprint"],
        },
        "attack": source["attack"],
        "seed": 42,
        "seed_protocol": source["seed_protocol"],
        "poison_instance_fingerprint": source["poison_instance_fingerprint"],
        "generator": source["generator"],
        "evaluation": {"top_k": 3, "retrieval_metric_k": 10},
        "configs": {"dense": dense_config, "rcd": rcd_config},
        "git": {"commit_sha": "a" * 40, "worktree_dirty": True},
    }
    write_json_exclusive(comparison_manifest_path, manifest)

    poisoned_data = replay_poisoned_data(clean_data, source)
    query_by_id = {query["query_id"]: query for query in clean_data["queries"]}
    poisoned_by_id = {query["query_id"]: query for query in poisoned_data["queries"]}
    rows = []
    internal_rows = {}
    for pipeline in aggregate.PIPELINES:
        paired = []
        for index, query_id in enumerate(selected_ids):
            query = query_by_id[query_id]
            poisoned_query = poisoned_by_id[query_id]
            poison_id = poisoned_query["poison_doc_ids"][0]
            poison_target = poisoned_query["poison_target_answer"]
            clean_correct = (index + seed + int(pipeline == "rcd")) % 2 == 0
            targeted = (index + seed + int(pipeline == "dense")) % 4 == 0
            poison_correct = not targeted and (index + seed) % 3 == 0
            clean_answer = query["gold_answer"] if clean_correct else "Wrong clean"
            if targeted:
                poisoned_answer = poison_target
            elif poison_correct:
                poisoned_answer = query["gold_answer"]
            else:
                poisoned_answer = "Wrong poisoned"
            poison_retrieved = (index + seed + int(pipeline == "rcd")) % 3 != 0
            clean_row = _record(
                pipeline, query, "clean", clean_answer, poisoned_answer,
                poison_id, poison_target, clean_correct, poison_correct,
                targeted, poison_retrieved,
            )
            poison_row = _record(
                pipeline, query, "poisoned", clean_answer, poisoned_answer,
                poison_id, poison_target, clean_correct, poison_correct,
                targeted, poison_retrieved,
            )
            rows.extend([clean_row, poison_row])
            paired.append(
                {
                    "query_id": query_id,
                    "clean_condition": {"answer_correct": clean_correct},
                    "poisoned_condition": {
                        "answer_correct": poison_correct,
                        "targeted_asr": targeted,
                        "poison_retrieved": poison_retrieved,
                        "prr_at_k": poison_row["prr_at_k"],
                    },
                    "query_untargeted_degradation": clean_correct and not poison_correct,
                }
            )
            internal_rows[(pipeline, query_id, "clean")] = clean_row
            internal_rows[(pipeline, query_id, "poisoned")] = poison_row
        summary_pipeline = comparison.summarize_pipeline(paired)
        if pipeline == "dense":
            dense_paired = paired
        else:
            rcd_paired = paired

    summary = {
        "experiment_id": comparison_id,
        "status": "complete_exploratory_pilot_not_final",
        "is_final_run": False,
        "query_count": len(selected_ids),
        "selected_query_ids": selected_ids,
        "source_poison_instance_fingerprint": source["poison_instance_fingerprint"],
        "manifest_path": str(comparison_manifest_path),
        "results_path": str(results_path),
        "pipelines": {
            "dense": comparison.summarize_pipeline(dense_paired),
            "rcd": comparison.summarize_pipeline(rcd_paired),
        },
        "paired_dense_minus_rcd": comparison.paired_differences(
            dense_paired, rcd_paired
        ),
    }
    write_json_exclusive(summary_path, summary)
    with results_path.open("x", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row) + "\n")
    return comparison_manifest_path, summary_path, results_path, source


def test_independent_poison_seeds_make_distinct_immutable_manifests(tmp_path):
    clean_data = _clean_data()
    manifests = [_source_manifest(tmp_path, seed, clean_data) for seed in (42, 43, 44)]

    assert len({m["poison_instance_fingerprint"] for m in manifests}) == 3
    assert all(
        m["dataset"]["selected_query_ids"] == manifests[0]["dataset"]["selected_query_ids"]
        for m in manifests
    )
    assert [m["seed_protocol"]["poison_seed"] for m in manifests] == [42, 43, 44]
    assert all(m["seed"] == 42 for m in manifests)
    assert all(m["seed_protocol"]["retrieval_and_generation_seed"] == 42 for m in manifests)

    path = tmp_path / "immutable.manifest.json"
    write_json_exclusive(path, manifests[0])
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_json_exclusive(path, manifests[1])
    assert path.read_bytes() == original


def test_matched_comparison_replays_exact_same_poison_snapshot(tmp_path, monkeypatch):
    clean_data = _clean_data()
    source = _source_manifest(tmp_path, 43, clean_data)
    monkeypatch.setattr(
        comparison,
        "EXPECTED_POISON_FINGERPRINT",
        source["poison_instance_fingerprint"],
    )
    dense_copy = comparison.reconstruct_matched_snapshot(clean_data, source)
    rcd_copy = comparison.reconstruct_matched_snapshot(clean_data, source)

    assert poison_instances_fingerprint(clean_data, dense_copy) == (
        poison_instances_fingerprint(clean_data, rcd_copy)
    )
    assert dense_copy == rcd_copy
    assert dense_copy["queries"] == rcd_copy["queries"]


def test_frozen_config_files_keep_pinned_hashes():
    root = orchestration.REPOSITORY_ROOT
    paths = {
        "heldout": root / "configs/exp_027_hotpotqa_heldout_manifest.json",
        "dense": root / "configs/exp_030_hotpotqa_dense_heldout_mlx.yaml",
        "rcd": root / "configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml",
    }
    assert {
        key: orchestration.sha256_file(path) for key, path in paths.items()
    } == orchestration.EXPECTED_CONFIG_HASHES


def test_output_collision_fails_before_data_loading(tmp_path):
    run_dir = tmp_path / "existing"
    run_dir.mkdir()
    with pytest.raises(FileExistsError):
        orchestration.run_multiseed(
            output_dir=tmp_path,
            experiment_id="existing",
        )


def test_interrupted_comparisons_preserve_completed_seed_outputs(tmp_path):
    completed_output = tmp_path / "completed.seed42"
    journal = tmp_path / "execution.jsonl"
    failure = tmp_path / "failure.json"
    runs = [
        {
            "seed": 42,
            "command": ["compare", "42"],
            "provenance": {"poison_instance_fingerprint": "a" * 64},
        },
        {
            "seed": 43,
            "command": ["compare", "43"],
            "provenance": {"poison_instance_fingerprint": "b" * 64},
        },
    ]

    def fake_run(command, check):
        if command[-1] == "42":
            completed_output.write_text("complete", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)
        raise subprocess.CalledProcessError(1, command)

    with pytest.raises(subprocess.CalledProcessError):
        orchestration.execute_comparisons(
            runs=runs,
            journal_path=journal,
            failure_path=failure,
            run_subprocess=fake_run,
        )
    assert completed_output.read_text(encoding="utf-8") == "complete"
    failure_data = json.loads(failure.read_text(encoding="utf-8"))
    assert failure_data["completed_seed_ids"] == [42]


def test_aggregation_reports_rates_pooled_counts_and_cluster_bootstrap(tmp_path):
    inputs = [_write_run(tmp_path, seed)[:3] for seed in aggregate.EXPECTED_SEEDS]
    result = aggregate.aggregate_runs(
        inputs,
        bootstrap_seed=31,
        bootstrap_replicates=100,
    )
    repeat = aggregate.aggregate_runs(
        inputs,
        bootstrap_seed=31,
        bootstrap_replicates=100,
    )
    assert result["poison_seeds"] == [42, 43, 44]
    assert result["query_ids_identical_across_seeds"] is True
    assert result["poison_instances_identical_across_seeds"] is False
    assert result["repeated_queries_are_independent"] is False
    assert result["query_seed_observation_count"] == 30
    assert result["paired_bootstrap"] == repeat["paired_bootstrap"]
    assert "query IDs with replacement" in result["paired_bootstrap"]["method"]
    assert result["pooled_query_seed_observations"]["dense"][
        "clean_answer_accuracy"
    ]["denominator"] == 30
    assert result["per_seed"][0]["pipelines"]["dense"][
        "query_untargeted_degradation"
    ]["denominator"] == 10
    assert "numerator" in result["pooled_paired_dense_minus_rcd"][
        "query_untargeted_degradation"
    ]
    assert (
        result["paired_bootstrap"]["paired_dense_minus_rcd"][
            "query_untargeted_degradation"
        ]["resampling_unit"]
        == "query_id cluster across all seeds and both pipelines"
    )


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "missing", "misaligned", "bad-source-hash", "incompatible-config"],
)
def test_aggregator_rejects_corrupt_or_misaligned_runs(tmp_path, mutation):
    run_paths = [
        _write_run(tmp_path, seed)[:3] for seed in aggregate.EXPECTED_SEEDS
    ]
    if mutation in {"duplicate", "missing", "misaligned"}:
        results_path = run_paths[0][2]
        rows = [
            json.loads(line)
            for line in results_path.read_text(encoding="utf-8").splitlines()
        ]
        if mutation == "duplicate":
            rows.append(copy.deepcopy(rows[0]))
        elif mutation == "missing":
            rows.pop()
        else:
            rows[0]["query_id"] = "not-selected"
        results_path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
    elif mutation == "bad-source-hash":
        manifest_path = run_paths[0][0]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_manifest_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        manifest_path = run_paths[1][0]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["configs"]["rcd"]["rcd_configuration"]["conflict_weight"] = 0.3
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError):
        aggregate.aggregate_runs(run_paths, bootstrap_replicates=10)


def test_aggregator_rejects_duplicate_seed_inputs(tmp_path):
    first = _write_run(tmp_path, 42)[:3]
    others = [_write_run(tmp_path, seed)[:3] for seed in (43, 44)]
    with pytest.raises(ValueError):
        aggregate.aggregate_runs([first, first, others[1]], bootstrap_replicates=10)
