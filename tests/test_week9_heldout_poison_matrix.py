import copy
import json

import pytest

import scripts.aggregate_week9_heldout_poison_matrix as aggregate
import scripts.run_week9_heldout_poison_matrix as matrix
from src.attacks.injection import inject_poisons
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.experiments.protocol import poison_instances_fingerprint
from src.pipelines.generator import MockGenerator


def _clean_data():
    return {
        "corpus": [{"doc_id": "clean", "text": "Clean evidence."}],
        "queries": [
            {
                "query_id": f"q{index}",
                "question": f"Question {index}?",
                "gold_answer": f"Answer {index}",
                "gold_doc_ids": ["clean"],
            }
            for index in range(matrix.MATRIX_QUERY_COUNT)
        ],
    }


def _configs():
    shared = {
        "dataset_revision": "revision",
        "dataset_split": "validation",
        "generator_backend": "mlx",
        "generator_model": "model",
        "max_tokens": 64,
        "top_k": 3,
        "embedder_model": "embedder",
    }
    return (
        {**shared, "retriever": "dense"},
        {
            **shared,
            "retriever": "rcd",
            "rcd_candidate_k": 10,
            "rcd_rewrite_count": 3,
            "rcd_consistency_weight": 0.45,
            "rcd_redundancy_weight": 0.0,
            "rcd_conflict_weight": 0.1,
            "rcd_base_rank_weight": 0.45,
        },
    )


def _manifest(clean_data, seed=42):
    dense, rcd = _configs()
    poisoned = inject_poisons(
        clean_data,
        LexicalInfluentialTokenAttack(),
        n_poison=1,
        poison_rate=1.0,
        seed=seed,
        attacked_query_ids=[query["query_id"] for query in clean_data["queries"]],
    )
    manifest = matrix.build_cell_manifest(
        cell_id=matrix._cell_id("lexical_influential_token", 1, seed),
        clean_data=clean_data,
        poisoned_data=poisoned,
        attack_family="lexical_influential_token",
        intensity=1,
        poison_seed=seed,
        heldout_fingerprint="heldout",
        config_hashes={"heldout": "h", "dense": "d", "rcd": "r"},
        dense_config=dense,
        rcd_config=rcd,
        git_sha="a" * 40,
        git_dirty=False,
    )
    manifest["attack"]["configuration"] = {"repeat_factor": 4}
    return poisoned, manifest


def _raw_record(manifest, query, pipeline, condition):
    poison_id = query["poison_doc_ids"][0]
    poisoned = condition == "poisoned"
    answer = query["poison_target_answer"] if poisoned and pipeline == "dense" else query["gold_answer"]
    correct = answer == query["gold_answer"]
    retrieved = [poison_id, "clean"] if poisoned else ["clean"]
    return {
        "cell_id": manifest["cell_id"],
        "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
        "query_id": query["query_id"],
        "pipeline": pipeline,
        "condition": condition,
        "gold_answer": query["gold_answer"],
        "poison_target_answer": query["poison_target_answer"],
        "poison_doc_ids": query["poison_doc_ids"],
        "clean_answer": query["gold_answer"],
        "poisoned_answer": answer if poisoned else query["gold_answer"],
        "query_untargeted_degradation": pipeline == "dense",
        "answer": answer if poisoned else query["gold_answer"],
        "answer_correct": correct,
        "targeted_asr": (answer == query["poison_target_answer"]) if poisoned else None,
        "poison_retrieved": poisoned,
        "poison_rank": 1 if poisoned else None,
        "retrieved_doc_ids": retrieved,
        "retrieved_evidence": [{"doc_id": doc_id, "text": "evidence"} for doc_id in retrieved],
        "generation_evidence_doc_ids": retrieved,
        "prr_at_k": {
            str(k): float(poisoned)
            for k in aggregate.multiseed.EXPECTED_CUTOFFS
        },
        "retrieval_elapsed_seconds": 0.0,
        "generation": {
            "elapsed_seconds": 0.0,
            "generator_latency_seconds": 0.0,
            "prompt_tokens": 1,
            "completion_tokens": 1,
        },
    }


def _write_cell(root, seed):
    clean = _clean_data()
    poisoned, manifest = _manifest(clean, seed)
    cell_dir = root / manifest["cell_id"]
    cell_dir.mkdir()
    (cell_dir / "poison.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = [
        _raw_record(manifest, query, pipeline, condition)
        for query in poisoned["queries"]
        for pipeline in aggregate.multiseed.PIPELINES
        for condition in aggregate.multiseed.CONDITIONS
    ]
    (cell_dir / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    summary = {
        "schema": matrix.CELL_SCHEMA,
        "status": "complete_heldout_cell_not_statistically_conclusive",
        "is_final_run": False,
        "cell_id": manifest["cell_id"],
        "query_count": matrix.MATRIX_QUERY_COUNT,
        "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
    }
    (cell_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return cell_dir, manifest


def test_cell_manifest_replays_all_300_immutable_poison_instances():
    clean = _clean_data()
    poisoned, manifest = _manifest(clean)

    replayed = matrix.replay_cell_manifest(clean, manifest)

    assert replayed == poisoned
    assert poison_instances_fingerprint(clean, replayed) == manifest["poison_instance_fingerprint"]


@pytest.mark.parametrize("mutation", ["fingerprint", "family", "missing-query"])
def test_cell_manifest_rejects_tampering(mutation):
    clean = _clean_data()
    _, manifest = _manifest(clean)
    changed = copy.deepcopy(manifest)
    if mutation == "fingerprint":
        changed["poison_documents"][0]["text"] += " changed"
    elif mutation == "family":
        changed["attack"]["family"] = "unknown"
    else:
        changed["query_poison_associations"].pop()

    with pytest.raises(ValueError):
        matrix.replay_cell_manifest(clean, changed)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "bad-fingerprint"])
def test_aggregate_rejects_bad_raw_cell(tmp_path, mutation):
    cell_dir, _ = _write_cell(tmp_path, 42)
    results_path = cell_dir / "results.jsonl"
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()]
    if mutation == "duplicate":
        rows[-1] = rows[0]
    elif mutation == "missing":
        rows.pop()
    else:
        rows[0]["poison_instance_fingerprint"] = "wrong"
    results_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    with pytest.raises(ValueError):
        aggregate.validate_completed_cell(cell_dir)


def test_aggregate_clusters_three_seed_outcomes(tmp_path, monkeypatch):
    for seed in (42, 43, 44):
        _write_cell(tmp_path, seed)
    monkeypatch.setattr(aggregate, "MATRIX_ATTACKS", ("lexical_influential_token",))
    monkeypatch.setattr(aggregate, "MATRIX_INTENSITIES", (1,))
    monkeypatch.setattr(
        aggregate,
        "matrix_cells",
        lambda: [("lexical_influential_token", 1, seed) for seed in (42, 43, 44)],
    )

    result = aggregate.aggregate_matrix(tmp_path, bootstrap_replicates=10)

    assert result["completed_cell_count"] == 3
    group = result["groups"][0]
    assert group["query_count_per_seed"] == 300
    assert group["query_seed_observation_count"] == 900
    assert group["repeated_queries_are_independent"] is False
    assert "zero-width interval is not proof of equivalence" in result["limitations"]


def test_smoke_test_rejects_the_mock_generator(tmp_path, monkeypatch):
    clean = _clean_data()
    dense, rcd = _configs()
    runtime = {
        "runtime_requirements": {"mlx_available": True, "mlx_lm_available": True},
    }
    monkeypatch.setattr(matrix, "preflight", lambda **_: runtime)
    monkeypatch.setattr(matrix, "_require_clean_relevant_inputs", lambda **_: None)
    monkeypatch.setattr(
        matrix,
        "validate_frozen_inputs",
        lambda **_: (dense, rcd, [query["query_id"] for query in clean["queries"]], "heldout", {}),
    )
    monkeypatch.setattr(
        matrix,
        "load_dataset",
        lambda config: {
            **clean,
            "queries": clean["queries"][: len(config["dataset_query_ids"])],
        },
    )
    monkeypatch.setattr(matrix, "build_generator", lambda _: MockGenerator())

    with pytest.raises(TypeError, match="configured real generator"):
        matrix.run_smoke_test(
            output_dir=tmp_path,
            experiment_id="reject-mock",
            query_count=2,
        )

    assert (tmp_path / "reject-mock" / "failure.json").is_file()


def test_smoke_test_writes_nonfinal_execution_evidence(tmp_path, monkeypatch):
    clean = _clean_data()
    dense, rcd = _configs()
    runtime = {
        "runtime_requirements": {"mlx_available": True, "mlx_lm_available": True},
    }

    class RealTestGenerator:
        pass

    monkeypatch.setattr(matrix, "preflight", lambda **_: runtime)
    monkeypatch.setattr(matrix, "_require_clean_relevant_inputs", lambda **_: None)
    monkeypatch.setattr(
        matrix,
        "validate_frozen_inputs",
        lambda **_: (dense, rcd, [query["query_id"] for query in clean["queries"]], "heldout", {}),
    )
    monkeypatch.setattr(
        matrix,
        "load_dataset",
        lambda config: {
            **clean,
            "queries": clean["queries"][: len(config["dataset_query_ids"])],
        },
    )
    monkeypatch.setattr(matrix, "build_generator", lambda _: RealTestGenerator())
    monkeypatch.setattr(
        matrix,
        "evaluate_cell",
        lambda **_: {
            "pipelines": {},
            "paired_dense_minus_rcd": {},
            "execution_evidence": {
                "raw_record_count": 8,
                "expected_raw_record_count": 8,
                "retrieval_elapsed_seconds": 0.1,
                "generation_elapsed_seconds": 0.2,
            },
        },
    )

    result = matrix.run_smoke_test(
        output_dir=tmp_path,
        experiment_id="real-smoke-schema",
        query_count=2,
    )

    assert result["status"] == "complete_smoke_test_not_final"
    assert result["is_final_run"] is False
    assert result["execution_evidence"]["raw_record_count"] == 8
