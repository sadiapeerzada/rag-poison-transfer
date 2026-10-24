import copy
import json
import sys

import pytest

import scripts.aggregate_week9_heldout_poison_matrix as aggregate
import scripts.run_week9_heldout_poison_matrix as matrix
from src.attacks.injection import inject_poisons
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.experiments.protocol import poison_instances_fingerprint
from src.pipelines.generator import MockGenerator


SOURCE_FP = "f" * 64


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
        source_fingerprint=SOURCE_FP,
    )
    manifest["attack"]["configuration"] = {"repeat_factor": 4}
    return poisoned, manifest


def _frozen(clean=None):
    """Frozen inputs matching the synthetic fixtures (no dataset download)."""
    clean = _clean_data() if clean is None else clean
    dense, rcd = _configs()
    return matrix.FrozenMatrixInputs(
        clean_data=clean,
        heldout_ids=[query["query_id"] for query in clean["queries"]],
        heldout_fingerprint="heldout",
        config_hashes={"heldout": "h", "dense": "d", "rcd": "r"},
        dense_config=dense,
        rcd_config=rcd,
    )


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
    _write_summary(cell_dir, manifest, rows)
    return cell_dir, manifest


def _indexed(rows):
    return {(r["pipeline"], r["query_id"], r["condition"]): r for r in rows}


def _paired_from_indexed(indexed, ids):
    by_pipeline = {
        pipeline: [
            {
                "query_id": query_id,
                "clean_condition": indexed[(pipeline, query_id, "clean")],
                "poisoned_condition": indexed[(pipeline, query_id, "poisoned")],
                "query_untargeted_degradation": indexed[(pipeline, query_id, "poisoned")]["query_untargeted_degradation"],
            }
            for query_id in ids
        ]
        for pipeline in aggregate.multiseed.PIPELINES
    }
    return matrix.paired_differences(by_pipeline["dense"], by_pipeline["rcd"])


def _write_summary(cell_dir, manifest, rows):
    """Write a summary consistent with ``rows`` (hash, evidence, metrics)."""
    ids = manifest["dataset"]["selected_query_ids"]
    indexed = _indexed(rows)
    summary = {
        "schema": matrix.CELL_SCHEMA,
        "status": "complete_heldout_cell_not_statistically_conclusive",
        "is_final_run": False,
        "cell_id": manifest["cell_id"],
        "query_count": matrix.MATRIX_QUERY_COUNT,
        "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
        "results_sha256": matrix._sha256_file(cell_dir / "results.jsonl"),
        "execution_evidence": {"raw_record_count": len(rows)},
        "pipelines": {
            pipeline: matrix.recompute_pipeline_summary(indexed, pipeline, ids)
            for pipeline in aggregate.multiseed.PIPELINES
        },
        "paired_dense_minus_rcd": _paired_from_indexed(indexed, ids),
    }
    (cell_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


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

    # The frozen inputs are supplied so the rejection must come from the raw
    # record defect itself, not from the missing-inputs guard.
    with pytest.raises(ValueError) as error:
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())
    assert "frozen inputs" not in str(error.value)


def test_valid_cell_is_accepted_with_frozen_inputs(tmp_path):
    cell_dir, manifest = _write_cell(tmp_path, 42)

    result = aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())

    assert result["recomputed_poison_instance_fingerprint"] == manifest["poison_instance_fingerprint"]
    assert len(result["rows"]) == 1200


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

    result = aggregate.aggregate_matrix(
        tmp_path, frozen_inputs=_frozen(), bootstrap_replicates=10
    )

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


# ---------------------------------------------------------------------------
# Fix C: independent poison-provenance verification
# ---------------------------------------------------------------------------
def _refresh_results_hash(cell_dir):
    """Simulate a forger who also recomputes the recorded digest.

    The hash only proves bytes match a digest; the semantic validation must
    still reject the content, so tamper helpers keep the digest consistent.
    """
    path = cell_dir / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["results_sha256"] = matrix._sha256_file(cell_dir / "results.jsonl")
    try:  # keep the summary consistent with still-well-formed rows
        rows = [json.loads(x) for x in (cell_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        ids = json.loads((cell_dir / "poison.manifest.json").read_text(encoding="utf-8"))["dataset"]["selected_query_ids"]
        summary["pipelines"] = {
            pipeline: matrix.recompute_pipeline_summary(_indexed(rows), pipeline, ids)
            for pipeline in aggregate.multiseed.PIPELINES
        }
        summary["paired_dense_minus_rcd"] = _paired_from_indexed(_indexed(rows), ids)
    except Exception:
        pass  # malformed rows: leave the stale summary; validation must reject on content
    path.write_text(json.dumps(summary), encoding="utf-8")


def _rewrite_cell_files(cell_dir, *, manifest=None, fingerprint=None):
    """Write a (possibly forged) manifest and propagate a fingerprint everywhere."""
    if manifest is not None:
        (cell_dir / "poison.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if fingerprint is not None:
        stored = json.loads((cell_dir / "poison.manifest.json").read_text(encoding="utf-8"))
        stored["poison_instance_fingerprint"] = fingerprint
        (cell_dir / "poison.manifest.json").write_text(json.dumps(stored), encoding="utf-8")
        summary = json.loads((cell_dir / "summary.json").read_text(encoding="utf-8"))
        summary["poison_instance_fingerprint"] = fingerprint
        (cell_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        rows = [json.loads(x) for x in (cell_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        for row in rows:
            row["poison_instance_fingerprint"] = fingerprint
        (cell_dir / "results.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        _refresh_results_hash(cell_dir)


def test_validation_requires_frozen_inputs(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    with pytest.raises(ValueError, match="frozen inputs"):
        aggregate.validate_completed_cell(cell_dir)
    with pytest.raises(ValueError, match="frozen_inputs"):
        aggregate.aggregate_matrix(tmp_path)


def test_fabricated_matching_fingerprint_everywhere_is_rejected(tmp_path):
    # Manifest, summary and every raw row agree on a fingerprint that the
    # poison documents do not actually hash to: pairwise consistency alone
    # would accept this cell.
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_cell_files(cell_dir, fingerprint="f" * 64)

    with pytest.raises(ValueError, match="fingerprint"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_altered_poison_document_text_is_rejected(tmp_path):
    cell_dir, manifest = _write_cell(tmp_path, 42)
    forged = copy.deepcopy(manifest)
    forged["poison_documents"][0]["text"] += " tampered"
    _rewrite_cell_files(cell_dir, manifest=forged)

    with pytest.raises(ValueError, match="content hash"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_consistently_forged_lexical_poison_fails_deterministic_regeneration(tmp_path):
    # Documents are re-hashed into valid IDs and the fingerprint is recomputed,
    # so replay alone is self-consistent; regeneration must still reject it.
    from src.attacks.base import poison_doc_id

    cell_dir, manifest = _write_cell(tmp_path, 42)
    forged = copy.deepcopy(manifest)
    document = forged["poison_documents"][0]
    old_id = document["doc_id"]
    document["text"] = "Forged but internally consistent poison text."
    parts = old_id.split("::")
    document["doc_id"] = poison_doc_id(parts[1], parts[2], int(parts[3]), document["text"])
    for association in forged["query_poison_associations"]:
        association["poison_doc_ids"] = [
            document["doc_id"] if doc_id == old_id else doc_id
            for doc_id in association["poison_doc_ids"]
        ]
    clean = _clean_data()
    replayed_probe = copy.deepcopy(forged)
    replayed_probe["poison_instance_fingerprint"] = "placeholder"
    # Recompute the fingerprint the forger would store.
    poisoned = inject_poisons(
        clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42,
        attacked_query_ids=[q["query_id"] for q in clean["queries"]],
    )
    for entry in poisoned["corpus"]:
        if entry["doc_id"] == old_id:
            entry["doc_id"], entry["text"] = document["doc_id"], document["text"]
    for query in poisoned["queries"]:
        query["poison_doc_ids"] = [
            document["doc_id"] if d == old_id else d for d in query["poison_doc_ids"]
        ]
    forged["poison_instance_fingerprint"] = poison_instances_fingerprint(clean, poisoned)
    _rewrite_cell_files(cell_dir, manifest=forged, fingerprint=forged["poison_instance_fingerprint"])

    with pytest.raises(ValueError, match="deterministic regeneration"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_altered_association_is_rejected(tmp_path):
    cell_dir, manifest = _write_cell(tmp_path, 42)
    forged = copy.deepcopy(manifest)
    forged["query_poison_associations"][0]["poison_doc_ids"] = ["poison::wrong"]
    _rewrite_cell_files(cell_dir, manifest=forged)

    with pytest.raises(ValueError):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_wrong_clean_corpus_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    other = _clean_data()
    other["corpus"][0]["text"] = "A different clean corpus."

    with pytest.raises(ValueError):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen(other))


def test_wrong_heldout_ids_or_order_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    frozen = _frozen()
    reordered = matrix.FrozenMatrixInputs(
        **{**frozen.__dict__, "heldout_ids": list(reversed(frozen.heldout_ids))}
    )
    with pytest.raises(ValueError, match="query IDs or order"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=reordered)


@pytest.mark.parametrize(
    "field,value",
    [("dataset_revision", "other-revision"), ("generator_model", "other-model")],
)
def test_frozen_config_mismatch_is_rejected(tmp_path, field, value):
    cell_dir, _ = _write_cell(tmp_path, 42)
    frozen = _frozen()
    changed = matrix.FrozenMatrixInputs(
        **{**frozen.__dict__, "rcd_config": {**frozen.rcd_config, field: value}}
    )
    with pytest.raises(ValueError):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=changed)


def test_missing_manifest_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    (cell_dir / "poison.manifest.json").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_raw_rows_must_match_replayed_poison_instances(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    path = cell_dir / "results.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["poison_target_answer"] = "not the replayed target"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    _refresh_results_hash(cell_dir)
    with pytest.raises(ValueError, match="replayed poison instance"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_diagnostic_ranking_must_extend_generation_evidence(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    path = cell_dir / "results.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    poisoned = next(r for r in rows if r["condition"] == "poisoned")
    poisoned["retrieved_doc_ids"] = ["clean", poisoned["poison_doc_ids"][0]]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    _refresh_results_hash(cell_dir)
    with pytest.raises(ValueError, match="prefix"):
        aggregate.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_predeclared_seeds_agree_with_aggregator_seeds():
    assert tuple(matrix.PREDECLARED_POISON_SEEDS) == tuple(aggregate.multiseed.EXPECTED_SEEDS)


# ---------------------------------------------------------------------------
# Fix A / Fix E: workload accounting and matched-setting validation
# ---------------------------------------------------------------------------
def test_preflight_counts_for_the_committed_primary_matrix():
    result = matrix.preflight()

    assert result["cell_count"] == 12
    assert result["query_count_per_cell"] == 300
    assert result["evaluation_generation_calls"] == 14_400
    assert result["normal_retrieval_calls"] == 14_400
    assert result["diagnostic_retrieval_calls"] == 7_200
    assert result["retrieval_calls"] == 21_600
    assert result["retrieval_calls"] == (
        result["normal_retrieval_calls"] + result["diagnostic_retrieval_calls"]
    )
    assert result["workload"]["generation_top_k"] == 3


def test_estimate_workload_is_derived_from_configuration():
    dense, rcd = _configs()
    estimate = matrix.estimate_workload(dense, rcd, query_count=300, cell_count=12)
    assert (estimate["evaluation_generation_calls"], estimate["retrieval_calls"]) == (14_400, 21_600)
    assert estimate["per_pipeline"]["dense"]["diagnostic_retrieval_calls"] == 3_600

    small = matrix.estimate_workload(dense, rcd, query_count=5, cell_count=2)
    assert small["normal_retrieval_calls"] == 2 * 5 * 2 * 2
    assert small["diagnostic_retrieval_calls"] == 2 * 5 * 2


def test_diagnostic_retrievals_are_not_counted_when_the_branch_cannot_run():
    dense, rcd = _configs()
    dense["top_k"] = rcd["top_k"] = matrix.RETRIEVAL_METRIC_K
    estimate = matrix.estimate_workload(dense, rcd, query_count=300, cell_count=12)
    assert estimate["diagnostic_retrieval_calls"] == 0
    assert estimate["retrieval_calls"] == estimate["normal_retrieval_calls"] == 14_400


@pytest.mark.parametrize("bad", [0, -1, "3", 3.0, True, None])
def test_invalid_top_k_raises_a_clear_error(bad):
    dense, rcd = _configs()
    dense["top_k"] = rcd["top_k"] = bad
    with pytest.raises(ValueError, match="top_k"):
        matrix.estimate_workload(dense, rcd, query_count=300)


def test_unreliable_estimate_inputs_raise():
    dense, rcd = _configs()
    with pytest.raises(ValueError, match="query_count"):
        matrix.estimate_workload(dense, rcd, query_count=0)
    broken = {k: v for k, v in rcd.items() if k != "rcd_rewrite_count"}
    with pytest.raises(ValueError, match="rcd_rewrite_count"):
        matrix.estimate_workload(dense, broken, query_count=300)


@pytest.mark.parametrize(
    "key,value",
    [("top_k", 5), ("max_tokens", 128), ("generator_model", "other"),
     ("dataset_revision", "other"), ("embedder_model", "other")],
)
def test_incompatible_shared_settings_are_rejected(key, value):
    dense, rcd = _configs()
    rcd[key] = value
    with pytest.raises(ValueError, match="shared settings differ|top_k"):
        matrix.estimate_workload(dense, rcd, query_count=300)


def test_intentional_treatment_differences_are_allowed():
    dense, rcd = _configs()
    dense["experiment_id"], rcd["experiment_id"] = "dense-id", "rcd-id"
    rcd["rcd_consistency_weight"] = 0.9  # a defense parameter, not a shared setting
    matrix.estimate_workload(dense, rcd, query_count=300)


class _CountingRetriever:
    def __init__(self, inner_calls=None):
        self.calls = []
        self.inner_calls = inner_calls
        if inner_calls is not None:
            self.last_diagnostics = None

    def retrieve(self, query, top_k):
        from src.retrieval.dense import RetrievedDoc

        self.calls.append(top_k)
        if self.inner_calls is not None:
            self.last_diagnostics = {"retrieval_call_count": self.inner_calls}
        return [RetrievedDoc(f"d{i}", f"text {i}", 1.0 - i / 100) for i in range(top_k)]


class _EchoGenerator:
    def generate(self, prompt, max_tokens):
        from src.pipelines.generator import GenerationResult

        return GenerationResult(text="answer", latency_seconds=0.0, prompt_tokens=1, completion_tokens=1)


def _evaluate_small_cell(monkeypatch, tmp_path, top_k):
    clean = _clean_data()
    clean["queries"] = clean["queries"][:3]
    dense, rcd = _configs()
    dense["top_k"] = rcd["top_k"] = top_k
    poisoned = inject_poisons(
        clean, LexicalInfluentialTokenAttack(), n_poison=1, poison_rate=1.0, seed=42,
        attacked_query_ids=[q["query_id"] for q in clean["queries"]],
    )
    retrievers = {
        "dense": (_CountingRetriever(), _CountingRetriever()),
        "rcd": (_CountingRetriever(inner_calls=4), _CountingRetriever(inner_calls=4)),
    }
    monkeypatch.setattr(matrix, "build_matched_retrievers", lambda *a, **k: retrievers)
    out = matrix.evaluate_cell(
        clean_data=clean, poisoned_data=poisoned, dense_config=dense, rcd_config=rcd,
        generator=_EchoGenerator(), manifest={"cell_id": "c", "poison_instance_fingerprint": "f"},
        results_path=tmp_path / "results.jsonl",
    )
    return out, retrievers


def test_observed_retrievals_match_the_estimate_with_diagnostics(monkeypatch, tmp_path):
    out, retrievers = _evaluate_small_cell(monkeypatch, tmp_path, top_k=3)
    observed = out["execution_evidence"]["observed_workload"]
    assert observed["normal_retrieval_calls"] == 3 * 2 * 2
    assert observed["diagnostic_retrieval_calls"] == 3 * 2
    clean_r, poisoned_r = retrievers["dense"]
    assert len(clean_r.calls) == 3 and len(poisoned_r.calls) == 6
    assert sorted(set(poisoned_r.calls)) == [3, matrix.RETRIEVAL_METRIC_K]
    # RCD-style inner operations are recorded per raw record: 4 per outer call.
    assert out["execution_evidence"]["inner_retrieval_operations"]["rcd"] == 4 * 9
    assert out["execution_evidence"]["inner_retrieval_operations"]["dense"] == 9


def test_observed_retrievals_match_the_estimate_without_diagnostics(monkeypatch, tmp_path):
    out, retrievers = _evaluate_small_cell(monkeypatch, tmp_path, top_k=matrix.RETRIEVAL_METRIC_K)
    assert out["execution_evidence"]["observed_workload"]["diagnostic_retrieval_calls"] == 0
    assert len(retrievers["dense"][1].calls) == 3


def test_workload_mismatch_between_estimate_and_runtime_aborts_the_cell(monkeypatch, tmp_path):
    clean = _clean_data()
    clean["queries"] = clean["queries"][:2]
    dense, rcd = _configs()
    monkeypatch.setattr(matrix, "build_matched_retrievers", lambda *a, **k: {"dense": (None, None)})
    monkeypatch.setattr(matrix, "evaluate_pipeline", lambda **k: [])
    with pytest.raises(RuntimeError, match="differs from the preflight estimate"):
        matrix.evaluate_cell(
            clean_data=clean, poisoned_data=clean, dense_config=dense, rcd_config=rcd,
            generator=None, manifest={"cell_id": "c", "poison_instance_fingerprint": "f"},
            results_path=tmp_path / "r.jsonl",
        )


# ---------------------------------------------------------------------------
# Fix B / Fix F: plan lifecycle, resume, atomic writes, Git guard
# ---------------------------------------------------------------------------
import hashlib
import subprocess

LIFECYCLE_CELLS = [("lexical_influential_token", 1, seed) for seed in (42, 43, 44)]
LIFECYCLE_IDS = [matrix._cell_id(*cell) for cell in LIFECYCLE_CELLS]


class _Harness:
    """Mock every model/dataset dependency of run_matrix; evaluation is scripted."""

    def __init__(self, monkeypatch, tmp_path):
        self.root = tmp_path / "out"
        self.frozen = _frozen()
        self.evaluated = []
        self.behaviour = {}  # cell seed -> "fail" | "interrupt"
        self.head = "a" * 40
        monkeypatch.setattr(matrix, "matrix_cells", lambda: list(LIFECYCLE_CELLS))
        # The mocked preflight returns ONLY runtime requirements, as legacy fixtures do.
        monkeypatch.setattr(
            matrix, "preflight",
            lambda **_: {"runtime_requirements": {"mlx_available": True, "mlx_lm_available": True}},
        )
        monkeypatch.setattr(matrix, "_require_clean_relevant_inputs", lambda **_: None)
        monkeypatch.setattr(matrix, "git_commit_sha", lambda **_: self.head)
        self.fingerprint = SOURCE_FP
        monkeypatch.setattr(matrix, "compute_source_fingerprint", lambda: self.fingerprint)
        monkeypatch.setattr(matrix, "load_frozen_matrix_inputs", lambda **_: self.frozen)
        monkeypatch.setattr(matrix, "build_generator", lambda _: object())
        monkeypatch.setattr(matrix, "set_seed", lambda _: None)
        monkeypatch.setattr(matrix, "evaluate_cell", self.evaluate_cell)

    def evaluate_cell(self, *, poisoned_data, manifest, results_path, **_):
        seed = manifest["seed_protocol"]["poison_seed"]
        self.evaluated.append(seed)
        rows = [
            {**_raw_record(manifest, query, pipeline, condition), "cell_id": manifest["cell_id"]}
            for query in poisoned_data["queries"]
            for pipeline in aggregate.multiseed.PIPELINES
            for condition in aggregate.multiseed.CONDITIONS
        ]
        results_path.write_text("".join(json.dumps(r) + "\n" for r in rows[:5]), encoding="utf-8")
        mode = self.behaviour.get(seed)
        if mode == "fail":
            raise RuntimeError("simulated generation failure")
        if mode == "interrupt":
            raise KeyboardInterrupt
        results_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        indexed = _indexed(rows)
        ids = manifest["dataset"]["selected_query_ids"]
        return {
            "pipelines": {
                pipeline: matrix.recompute_pipeline_summary(indexed, pipeline, ids)
                for pipeline in aggregate.multiseed.PIPELINES
            },
            "paired_dense_minus_rcd": {},
            "execution_evidence": {"raw_record_count": len(rows), "expected_raw_record_count": len(rows)},
        }

    def run(self, resume=False):
        return matrix.run_matrix(output_dir=self.root.parent, experiment_id="out", resume=resume)

    @property
    def plan(self):
        return json.loads((self.root / "plan.json").read_text(encoding="utf-8"))


def _assert_consistent(plan, returned=None):
    expected = plan["expected_cell_ids"]
    done, left = plan["completed_cell_ids"], plan["failed_or_incomplete_cell_ids"]
    assert len(set(expected)) == len(expected)
    assert sorted(done + left) == sorted(expected) and not set(done) & set(left)
    assert plan["completed_cell_count"] == len(done)
    assert plan["failed_or_incomplete_cell_count"] == len(left)
    assert plan["expected_cell_count"] == len(expected)
    if plan["status"] != "running":
        assert plan["status"] == (
            "complete" if not left else ("partial" if done else "failed")
        )
    if returned is not None:
        assert returned["status"] == plan["status"]
        assert returned["completed_cells"] == done
        assert returned["failed_or_incomplete_cells"] == left


def test_complete_run_records_complete_plan(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    result = harness.run()
    plan = harness.plan

    assert plan["status"] == "complete" and plan["completed_cell_ids"] == LIFECYCLE_IDS
    assert plan["scientific_status"] == "not_final_not_statistically_conclusive"
    assert plan["is_final_run"] is False
    assert plan["created_at_utc"] <= plan["updated_at_utc"] and plan["completed_at_utc"]
    assert plan["git"]["commit_sha"] == "a" * 40
    assert plan["attempts"][0]["outcome"] == "complete" and plan["failure"] is None
    _assert_consistent(plan, result)


def test_failed_cell_yields_partial_plan_and_preserves_artifacts(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    result = harness.run()
    plan = harness.plan
    failed_id = matrix._cell_id("lexical_influential_token", 1, 43)

    assert plan["status"] == "partial" and plan["failed_or_incomplete_cell_ids"] == [failed_id]
    assert plan["cell_failures"][failed_id]["error_type"] == "RuntimeError"
    assert (harness.root / failed_id / "failure.json").is_file()
    assert (harness.root / failed_id / "results.jsonl").is_file()  # partial output kept
    _assert_consistent(plan, result)


def test_all_cells_failing_yields_failed_plan(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour = {42: "fail", 43: "fail", 44: "fail"}
    result = harness.run()
    assert harness.plan["status"] == "failed" and harness.plan["completed_cell_count"] == 0
    _assert_consistent(harness.plan, result)


def test_resume_skips_validated_cells_and_never_touches_incomplete_ones(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    failed_dir = harness.root / matrix._cell_id("lexical_influential_token", 1, 43)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in failed_dir.iterdir()}
    harness.evaluated.clear()
    harness.behaviour.clear()

    result = harness.run(resume=True)

    assert harness.evaluated == []  # completed cells validated, incomplete one preserved
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in failed_dir.iterdir()}
    assert harness.plan["status"] == "partial" and len(harness.plan["attempts"]) == 2
    assert harness.plan["attempts"][1]["resume"] is True
    _assert_consistent(harness.plan, result)


def test_resume_rejects_a_corrupt_completed_cell_without_deleting_it(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    corrupt_dir = harness.root / LIFECYCLE_IDS[1]
    results = corrupt_dir / "results.jsonl"
    rows = [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines()]
    rows[0]["poison_instance_fingerprint"] = "forged"
    results.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    harness.evaluated.clear()

    result = harness.run(resume=True)
    plan = harness.plan

    assert plan["status"] == "partial" and plan["failed_or_incomplete_cell_ids"] == [LIFECYCLE_IDS[1]]
    assert plan["cell_failures"][LIFECYCLE_IDS[1]]["source"] == "resume_validation"
    assert results.is_file() and harness.evaluated == []
    _assert_consistent(plan, result)


def test_pre_loop_failure_never_leaves_a_success_plan(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)

    def broken(**_):
        raise RuntimeError("dataset unavailable")

    monkeypatch.setattr(matrix, "load_frozen_matrix_inputs", broken)
    with pytest.raises(RuntimeError, match="dataset unavailable"):
        harness.run()
    plan = harness.plan
    assert plan["status"] == "failed" and plan["failure"]["stage"] == "setup"
    assert plan["completed_cell_count"] == 0 and plan["attempts"][0]["outcome"] == "failed"
    _assert_consistent(plan)


def test_keyboard_interrupt_is_recorded_but_never_swallowed(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "interrupt"
    with pytest.raises(KeyboardInterrupt):
        harness.run()
    plan = harness.plan
    assert plan["status"] == "partial" and plan["completed_cell_ids"] == [LIFECYCLE_IDS[0]]
    assert plan["failure"]["interrupted"] is True and plan["attempts"][0]["outcome"] == "interrupted"
    assert plan["status"] != "complete"
    _assert_consistent(plan)


def test_dirty_inputs_midrun_abort_with_partial_plan(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    calls = {"n": 0}

    def guard(**_):
        calls["n"] += 1
        if calls["n"] == 3:  # initial check + cell 1, then dirty before cell 2
            raise RuntimeError("relevant inputs changed")

    monkeypatch.setattr(matrix, "_require_clean_relevant_inputs", guard)
    with pytest.raises(RuntimeError, match="relevant inputs changed"):
        harness.run()
    assert harness.plan["status"] == "partial" and harness.plan["completed_cell_count"] == 1


def test_resume_at_a_different_commit_is_refused_and_plan_untouched(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    before = (harness.root / "plan.json").read_bytes()
    harness.head = "b" * 40
    with pytest.raises(ValueError, match="different Git commit"):
        harness.run(resume=True)
    assert (harness.root / "plan.json").read_bytes() == before


def test_legacy_plan_resumes_and_is_upgraded_without_false_promotion(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    legacy_preflight = {"runtime_requirements": {"mlx_available": True, "mlx_lm_available": True}}
    harness.root.mkdir()
    (harness.root / "plan.json").write_text(
        json.dumps({
            "schema": matrix.PLAN_SCHEMA, "experiment_id": "out",
            "preflight": legacy_preflight, "status": "running",
        }),
        encoding="utf-8",
    )
    result = harness.run(resume=True)
    plan = harness.plan
    assert plan["status"] == "complete"  # earned by validated cells, not inherited
    assert "expected_cell_ids" in plan["legacy_plan_upgraded_fields"]
    _assert_consistent(plan, result)


def test_legacy_preflight_comparison_ignores_only_the_known_wrong_total():
    current = {"cell_count": 12, "retrieval_calls": 21_600, "normal_retrieval_calls": 14_400,
               "evaluation_generation_calls": 14_400}
    legacy = {"cell_count": 12, "retrieval_calls": 14_400, "evaluation_generation_calls": 14_400}
    assert matrix._preflight_compatible(legacy, current)
    assert not matrix._preflight_compatible({**legacy, "cell_count": 11}, current)
    assert not matrix._preflight_compatible({**current, "retrieval_calls": 1}, current)
    assert not matrix._preflight_compatible(None, current)


def test_resume_without_plan_or_with_foreign_experiment_fails_clearly(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError, match="Cannot resume"):
        harness.run(resume=True)
    harness.root.mkdir()
    (harness.root / "plan.json").write_text(
        json.dumps({"schema": matrix.PLAN_SCHEMA, "experiment_id": "someone-else"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="different schema or experiment"):
        harness.run(resume=True)


def test_new_run_refuses_an_existing_output_directory(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.root.mkdir()
    with pytest.raises(FileExistsError):
        harness.run()


def test_atomic_write_failure_preserves_the_previous_plan(monkeypatch, tmp_path):
    path = tmp_path / "plan.json"
    matrix._write_json_atomic(path, {"status": "running", "n": 1})
    original = path.read_bytes()

    def boom(*_):
        raise OSError("disk full")

    monkeypatch.setattr(matrix.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        matrix._write_json_atomic(path, {"status": "complete", "n": 2})
    assert path.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == ["plan.json"]  # temp file cleaned up


def test_serialization_failure_preserves_the_previous_plan(tmp_path):
    path = tmp_path / "plan.json"
    matrix._write_json_atomic(path, {"ok": True})
    with pytest.raises(TypeError):
        matrix._write_json_atomic(path, {"bad": object()})
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
    assert [p.name for p in tmp_path.iterdir()] == ["plan.json"]


# --- Git guard -------------------------------------------------------------
def _git_repo(path, files):
    path.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=path, check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "T")
    for name, text in files.items():
        (path / name).write_text(text, encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "init")
    return path


def test_guard_inspects_the_repository_not_the_callers_working_directory(monkeypatch, tmp_path):
    repo = _git_repo(tmp_path / "repo", {"a.py": "A = 1\n"})
    foreign = _git_repo(tmp_path / "foreign", {"other.py": "X = 1\n"})
    monkeypatch.setattr(matrix, "REPOSITORY_ROOT", repo)
    monkeypatch.setattr(matrix, "RELEVANT_TRACKED_PATHS", ("a.py",))
    monkeypatch.chdir(foreign)

    matrix._require_clean_relevant_inputs(require_tracked_runner=True)  # clean repo passes
    (repo / "a.py").write_text("A = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="clean relevant tracked inputs"):
        matrix._require_clean_relevant_inputs(require_tracked_runner=False)

    from src.experiments.protocol import git_commit_sha

    repo_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    assert git_commit_sha(repo_root=repo) == repo_head != git_commit_sha()


def test_guard_requires_every_relevant_input_to_be_tracked_for_final_runs(monkeypatch, tmp_path):
    repo = _git_repo(tmp_path / "repo", {"a.py": "A = 1\n"})
    (repo / "b.py").write_text("B = 1\n", encoding="utf-8")  # relevant but untracked
    monkeypatch.setattr(matrix, "REPOSITORY_ROOT", repo)
    monkeypatch.setattr(matrix, "RELEVANT_TRACKED_PATHS", ("a.py", "b.py"))

    matrix._require_clean_relevant_inputs(require_tracked_runner=False)
    with pytest.raises(RuntimeError, match="tracked in Git"):
        matrix._require_clean_relevant_inputs(require_tracked_runner=True)


def test_guard_fails_closed_when_git_state_cannot_be_read(monkeypatch, tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    monkeypatch.setattr(matrix, "REPOSITORY_ROOT", not_a_repo)
    with pytest.raises(RuntimeError, match="Unable to inspect"):
        matrix._require_clean_relevant_inputs(require_tracked_runner=True)


def test_every_guarded_path_exists_and_is_unique():
    paths = matrix.RELEVANT_TRACKED_PATHS
    assert len(paths) == len(set(paths))
    missing = [p for p in paths if not (matrix.REPOSITORY_ROOT / p).is_file()]
    assert missing == []


# ---------------------------------------------------------------------------
# Validator: required retrieval fields and metric structure
# (each row, clean OR poisoned, must carry all five fields; clean rows are
# producer-fixed: poison_retrieved False, poison_rank None, PRR all 0.0)
# ---------------------------------------------------------------------------
REQUIRED_RETRIEVAL_FIELDS = (
    "retrieved_doc_ids",
    "generation_evidence_doc_ids",
    "poison_retrieved",
    "poison_rank",
    "prr_at_k",
)
UNRELATED_PREREQUISITE_ERRORS = ("Independent poison-provenance", "Cell is incomplete", "unsupported schema")


def _rewrite_rows(cell_dir, condition, mutate, pipeline="dense"):
    """Apply ``mutate`` to the first (pipeline, condition) row and write results back."""
    path = cell_dir / "results.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    target = next(r for r in rows if r["condition"] == condition and r["pipeline"] == pipeline)
    mutate(target)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    _refresh_results_hash(cell_dir)


def _assert_rejected(cell_dir, pattern):
    with pytest.raises(ValueError) as caught:
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())
    message = str(caught.value)
    assert not any(text in message for text in UNRELATED_PREREQUISITE_ERRORS), message
    assert pattern in message, message


def test_valid_synthetic_cell_passes_validation(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


@pytest.mark.parametrize("condition", ["clean", "poisoned"])
@pytest.mark.parametrize("field", REQUIRED_RETRIEVAL_FIELDS)
def test_missing_required_retrieval_field_is_rejected(tmp_path, field, condition):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, condition, lambda row: row.pop(field))
    _assert_rejected(cell_dir, f"missing required field '{field}'")


@pytest.mark.parametrize("cutoff", ["1", "3", "5", "10"])
def test_missing_prr_cutoff_is_rejected(tmp_path, cutoff):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row["prr_at_k"].pop(cutoff))
    _assert_rejected(cell_dir, "prr_at_k cutoffs")


def test_unexpected_prr_cutoff_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row["prr_at_k"].update({"7": 1.0}))
    _assert_rejected(cell_dir, "prr_at_k cutoffs")


@pytest.mark.parametrize("bad", [None, [1.0, 1.0], "1.0", {}], ids=["null", "list", "string", "empty"])
def test_malformed_prr_container_is_a_value_error(tmp_path, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__("prr_at_k", bad))
    _assert_rejected(cell_dir, "prr_at_k")


@pytest.mark.parametrize("bad", ["1.0", None, True, [1.0]], ids=["string", "null", "bool", "list"])
def test_malformed_prr_value_is_rejected(tmp_path, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row["prr_at_k"].__setitem__("3", bad))
    _assert_rejected(cell_dir, "must be a number")


def test_inconsistent_prr_value_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row["prr_at_k"].__setitem__("1", 0.0))
    _assert_rejected(cell_dir, "Poison retrieval rate at 1 is inconsistent")


@pytest.mark.parametrize("field", ["retrieved_doc_ids", "generation_evidence_doc_ids"])
@pytest.mark.parametrize(
    "bad", [None, "clean", [1], [None], [""], {"a": 1}], ids=["null", "string", "int-item", "null-item", "empty-id", "dict"]
)
def test_malformed_doc_id_collection_is_rejected(tmp_path, field, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__(field, bad))
    _assert_rejected(cell_dir, f"'{field}' must be a list of non-empty strings")


def test_generation_evidence_must_be_a_prefix_of_the_diagnostic_ranking(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__("generation_evidence_doc_ids", ["clean"]))
    _assert_rejected(cell_dir, "not a prefix")


@pytest.mark.parametrize("bad", ["1", 1.0, True, 0, -1], ids=["string", "float", "bool", "zero", "negative"])
def test_malformed_poison_rank_type_is_rejected(tmp_path, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__("poison_rank", bad))
    _assert_rejected(cell_dir, "poison_rank must be None or a positive integer")


@pytest.mark.parametrize("bad", [2, None], ids=["wrong-rank", "null-though-retrieved"])
def test_incorrect_poison_rank_is_rejected(tmp_path, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__("poison_rank", bad))
    _assert_rejected(cell_dir, "Poison rank is inconsistent")


@pytest.mark.parametrize("bad", ["True", 1, None], ids=["string", "int", "null"])
def test_poison_retrieved_must_be_a_real_bool(tmp_path, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__("poison_retrieved", bad))
    _assert_rejected(cell_dir, "poison_retrieved must be a boolean")


def test_inconsistent_poison_retrieved_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.__setitem__("poison_retrieved", False))
    _assert_rejected(cell_dir, "poison_retrieved is inconsistent")


def test_clean_row_may_not_contain_poison_documents(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)

    def contaminate(row):
        row["retrieved_doc_ids"] = [row["poison_doc_ids"][0], "clean"]
        row["generation_evidence_doc_ids"] = list(row["retrieved_doc_ids"])

    _rewrite_rows(cell_dir, "clean", contaminate)
    _assert_rejected(cell_dir, "clean-condition record contains poison documents")


@pytest.mark.parametrize("field", ["answer", "gold_answer"])
def test_missing_answer_fields_are_rejected(tmp_path, field):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _rewrite_rows(cell_dir, "poisoned", lambda row: row.pop(field))
    _assert_rejected(cell_dir, f"missing required field '{field}'")


def test_legitimate_null_rank_for_unretrieved_poison_is_accepted(tmp_path):
    """A defined-as-null metric (poison never retrieved) is not an absent field."""
    cell_dir, _ = _write_cell(tmp_path, 42)

    def poison_not_retrieved(row):
        row["retrieved_doc_ids"] = ["clean"]
        row["generation_evidence_doc_ids"] = ["clean"]
        row["poison_retrieved"] = False
        row["poison_rank"] = None
        row["prr_at_k"] = {str(k): 0.0 for k in aggregate.multiseed.EXPECTED_CUTOFFS}

    _rewrite_rows(cell_dir, "poisoned", poison_not_retrieved, pipeline="rcd")
    matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_poison_beyond_generation_evidence_still_gets_a_rank(tmp_path):
    """Diagnostic window deeper than the generator's evidence: rank 3, retrieved False."""
    cell_dir, _ = _write_cell(tmp_path, 42)

    def deep(row):
        poison = row["poison_doc_ids"][0]
        row["retrieved_doc_ids"] = ["clean", "other", poison]
        row["generation_evidence_doc_ids"] = ["clean"]
        row["poison_retrieved"] = False
        row["poison_rank"] = 3
        row["prr_at_k"] = {"1": 0.0, "3": 1.0, "5": 1.0, "10": 1.0}

    _rewrite_rows(cell_dir, "poisoned", deep, pipeline="rcd")
    matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())
# Opt-in safe recovery of incomplete cells (--resume --recover-incomplete)
# ---------------------------------------------------------------------------
SEED_43 = matrix._cell_id("lexical_influential_token", 1, 43)


def _digests(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}


def _recover(harness):
    return matrix.run_matrix(
        output_dir=harness.root.parent, experiment_id="out", resume=True, recover_incomplete=True
    )


def _no_regeneration(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("poison must be reused from the verified manifest, not regenerated")

    # Only the generation path builds a NEW manifest; verification does not.
    monkeypatch.setattr(matrix, "build_cell_manifest", boom)


def test_recovery_requires_resume(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="requires resume"):
        matrix.run_matrix(
            output_dir=harness.root.parent, experiment_id="out", recover_incomplete=True
        )
    assert not harness.root.exists()


def test_ordinary_resume_still_preserves_and_skips_incomplete_cells(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    harness.behaviour.clear()
    harness.evaluated.clear()
    harness.run(resume=True)
    assert harness.evaluated == [] and harness.plan["status"] == "partial"
    assert not (harness.root / matrix.ARCHIVE_DIRNAME).exists()


def test_recovery_after_evaluation_failure_archives_partial_and_reuses_manifest(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    cell_dir = harness.root / SEED_43
    original = _digests(cell_dir)
    original_manifest = json.loads((cell_dir / "poison.manifest.json").read_text(encoding="utf-8"))
    harness.behaviour.clear()
    harness.evaluated.clear()
    _no_regeneration(monkeypatch)

    result = _recover(harness)

    plan = harness.plan
    assert plan["status"] == "complete" and harness.evaluated == [43]
    _assert_consistent(plan, result)
    archived = harness.root / matrix.ARCHIVE_DIRNAME / SEED_43 / "attempt_001"
    assert _digests(archived) == original  # byte-for-byte preserved, partial results included
    assert len(archived.joinpath("results.jsonl").read_text().splitlines()) == 5
    new_manifest = json.loads((cell_dir / "poison.manifest.json").read_text(encoding="utf-8"))
    assert new_manifest == original_manifest  # same poison instance
    recovery = plan["recoveries"][0]
    assert recovery["cell_id"] == SEED_43 and recovery["manifest_reused"] is True
    assert recovery["archived_files"]["results.jsonl"]["sha256"] == original["results.jsonl"]
    assert recovery["prior_failure"]["error_type"] == "RuntimeError"
    assert plan["attempts"][1]["recovered_cell_ids"] == [SEED_43]
    # Full independent validation, not just a written summary.
    matrix.validate_completed_cell(cell_dir, frozen_inputs=harness.frozen)


def test_recovery_when_failure_happened_before_manifest_creation(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    import shutil
    shutil.rmtree(harness.root / SEED_43)
    (harness.root / SEED_43).mkdir()
    (harness.root / SEED_43 / "failure.json").write_text(
        json.dumps({"error_type": "RuntimeError", "error": "died generating poison"}), encoding="utf-8"
    )
    harness.evaluated.clear()

    _recover(harness)

    assert harness.plan["status"] == "complete" and harness.evaluated == [43]
    recovery = harness.plan["recoveries"][0]
    assert recovery["manifest_reused"] is False  # nothing existed to preserve
    assert (harness.root / matrix.ARCHIVE_DIRNAME / SEED_43 / "attempt_001" / "failure.json").is_file()


def test_recovery_when_results_were_written_but_summary_was_not(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    cell_dir = harness.root / SEED_43
    (cell_dir / "summary.json").unlink()  # killed after results, before summary
    full_results = (cell_dir / "results.jsonl").read_bytes()
    harness.evaluated.clear()
    _no_regeneration(monkeypatch)

    _recover(harness)

    assert harness.evaluated == [43]  # re-evaluated; unsummarised results are never trusted
    assert harness.plan["status"] == "complete"
    archived = harness.root / matrix.ARCHIVE_DIRNAME / SEED_43 / "attempt_001"
    assert (archived / "results.jsonl").read_bytes() == full_results
    assert not (archived / "summary.json").exists()


def test_repeated_interruptions_keep_every_attempt(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    first_failure = _digests(harness.root / SEED_43)
    _recover(harness)  # fails again
    assert harness.plan["status"] == "partial"
    second_failure = _digests(harness.root / SEED_43)
    harness.behaviour.clear()
    _recover(harness)

    assert harness.plan["status"] == "complete"
    archive = harness.root / matrix.ARCHIVE_DIRNAME / SEED_43
    assert _digests(archive / "attempt_001") == first_failure
    assert _digests(archive / "attempt_002") == second_failure
    assert len(harness.plan["recoveries"]) == 2
    assert {r["archived_to"] for r in harness.plan["recoveries"]} == {
        f"{matrix.ARCHIVE_DIRNAME}/{SEED_43}/attempt_001",
        f"{matrix.ARCHIVE_DIRNAME}/{SEED_43}/attempt_002",
    }


def test_recovery_refuses_a_corrupt_manifest_and_modifies_nothing(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    cell_dir = harness.root / SEED_43
    (cell_dir / "poison.manifest.json").write_text("{not json", encoding="utf-8")
    before = _digests(cell_dir)
    harness.behaviour.clear()
    harness.evaluated.clear()

    _recover(harness)

    assert _digests(cell_dir) == before and harness.evaluated == []
    assert not (harness.root / matrix.ARCHIVE_DIRNAME).exists()
    failure = harness.plan["cell_failures"][SEED_43]
    assert failure["source"] == "recovery_refused" and "Inspect" in failure["error"]
    assert harness.plan["status"] == "partial"


def test_recovery_refuses_a_manifest_that_fails_independent_verification(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    cell_dir = harness.root / SEED_43
    path = cell_dir / "poison.manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["dataset"]["selected_query_ids"] = list(reversed(manifest["dataset"]["selected_query_ids"]))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = _digests(cell_dir)
    harness.behaviour.clear()

    _recover(harness)

    assert _digests(cell_dir) == before
    assert harness.plan["cell_failures"][SEED_43]["source"] == "recovery_refused"


def test_recovery_refuses_a_manifest_from_a_different_commit(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    cell_dir = harness.root / SEED_43
    path = cell_dir / "poison.manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["git"]["commit_sha"] = "b" * 40
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = _digests(cell_dir)
    harness.behaviour.clear()

    _recover(harness)

    assert _digests(cell_dir) == before
    failure = harness.plan["cell_failures"][SEED_43]
    assert failure["source"] == "recovery_refused" and "different Git commit" in failure["error"]


def test_recovery_after_crash_between_archiving_and_recreating_reuses_archived_manifest(
    monkeypatch, tmp_path
):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    original_manifest = (harness.root / SEED_43 / "poison.manifest.json").read_text(encoding="utf-8")
    matrix._archive_incomplete_cell(harness.root, harness.root / SEED_43, SEED_43)
    assert not (harness.root / SEED_43).exists()  # simulated crash point
    harness.behaviour.clear()
    harness.evaluated.clear()
    _no_regeneration(monkeypatch)

    _recover(harness)

    assert harness.plan["status"] == "complete" and harness.evaluated == [43]
    assert json.loads((harness.root / SEED_43 / "poison.manifest.json").read_text()) == json.loads(
        original_manifest
    )


def test_recovery_does_not_touch_completed_cells(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    done = {
        cell: _digests(harness.root / cell) for cell in LIFECYCLE_IDS if cell != SEED_43
    }
    harness.behaviour.clear()
    _recover(harness)
    for cell, digests in done.items():
        assert _digests(harness.root / cell) == digests


# ---------------------------------------------------------------------------
# Provenance: Git metadata, source fingerprint, matrix-wide consistency
# ---------------------------------------------------------------------------
def _edit_manifest(cell_dir, mutate):
    path = cell_dir / "poison.manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    mutate(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _drop_git(m):
    del m["git"]


def _drop_key(key):
    return lambda m: m["git"].pop(key)


def _set_git(key, value):
    return lambda m: m["git"].__setitem__(key, value)


@pytest.mark.parametrize(
    "mutate",
    [
        _drop_git,
        _drop_key("commit_sha"),
        _set_git("commit_sha", ""),
        _set_git("commit_sha", "abc123"),
        _set_git("commit_sha", "G" * 40),
        _set_git("commit_sha", None),
        _set_git("relevant_tracked_inputs_dirty", True),
        _set_git("relevant_tracked_inputs_dirty", None),
        _drop_key("relevant_tracked_inputs_dirty"),
        _drop_key("source_fingerprint"),
        _set_git("source_fingerprint", ""),
        _set_git("source_fingerprint", "short"),
        _set_git("source_fingerprint", None),
        _set_git("dirty_check_scope", "everything"),
    ],
)
def test_missing_or_malformed_git_provenance_is_rejected(tmp_path, mutate):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _edit_manifest(cell_dir, mutate)
    with pytest.raises(ValueError, match="Git|source_fingerprint|clean relevant|dirty-check"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_heldout_manifest_builder_requires_a_source_fingerprint():
    clean = _clean_data()
    poisoned, _ = _manifest(clean)
    dense, rcd = _configs()
    kwargs = dict(
        cell_id=matrix._cell_id("lexical_influential_token", 1, 42), clean_data=clean,
        poisoned_data=poisoned, attack_family="lexical_influential_token", intensity=1,
        poison_seed=42, heldout_fingerprint="heldout", config_hashes={}, dense_config=dense,
        rcd_config=rcd, git_sha="a" * 40, git_dirty=False,
    )
    with pytest.raises(ValueError, match="source_fingerprint"):
        matrix.build_cell_manifest(**kwargs)


def _aggregate_three(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregate, "MATRIX_ATTACKS", ("lexical_influential_token",))
    monkeypatch.setattr(aggregate, "MATRIX_INTENSITIES", (1,))
    monkeypatch.setattr(
        aggregate, "matrix_cells",
        lambda: [("lexical_influential_token", 1, seed) for seed in (42, 43, 44)],
    )
    return aggregate.aggregate_matrix(tmp_path, frozen_inputs=_frozen(), bootstrap_replicates=5)


def test_aggregate_rejects_cells_from_different_commits(tmp_path, monkeypatch):
    dirs = [_write_cell(tmp_path, seed)[0] for seed in (42, 43, 44)]
    _edit_manifest(dirs[1], _set_git("commit_sha", "b" * 40))
    with pytest.raises(ValueError, match="different Git commits"):
        _aggregate_three(tmp_path, monkeypatch)


def test_aggregate_rejects_cells_from_different_source_fingerprints(tmp_path, monkeypatch):
    dirs = [_write_cell(tmp_path, seed)[0] for seed in (42, 43, 44)]
    _edit_manifest(dirs[2], _set_git("source_fingerprint", "e" * 64))
    with pytest.raises(ValueError, match="different source fingerprints"):
        _aggregate_three(tmp_path, monkeypatch)


def test_aggregate_reports_the_single_shared_provenance(tmp_path, monkeypatch):
    for seed in (42, 43, 44):
        _write_cell(tmp_path, seed)
    result = _aggregate_three(tmp_path, monkeypatch)
    assert result["git_commit_sha"] == "a" * 40 and result["source_fingerprint"] == SOURCE_FP


def test_resume_requires_the_cell_to_match_the_current_provenance(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    good = {"commit_sha": "a" * 40, "source_fingerprint": SOURCE_FP}
    matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen(), expected_provenance=good)
    for bad in ({**good, "commit_sha": "b" * 40}, {**good, "source_fingerprint": "0" * 64}):
        with pytest.raises(ValueError, match="different commit or source fingerprint"):
            matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen(), expected_provenance=bad)


def test_resume_refuses_a_plan_started_from_a_different_source_fingerprint(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    before = (harness.root / "plan.json").read_bytes()
    harness.fingerprint = "0" * 64  # same commit, different executable content
    with pytest.raises(ValueError, match="different source fingerprint"):
        harness.run(resume=True)
    assert (harness.root / "plan.json").read_bytes() == before


def test_new_plan_and_cells_record_the_source_fingerprint(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    assert harness.plan["git"]["source_fingerprint"] == SOURCE_FP
    for cell_id in LIFECYCLE_IDS:
        manifest = json.loads((harness.root / cell_id / "poison.manifest.json").read_text())
        assert manifest["git"]["source_fingerprint"] == SOURCE_FP


def test_resume_rejects_a_completed_cell_from_another_fingerprint_without_deleting_it(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    cell = harness.root / SEED_43
    _edit_manifest(cell, _set_git("source_fingerprint", "1" * 64))
    before = _digests(cell)
    harness.evaluated.clear()
    harness.run(resume=True)
    assert harness.evaluated == [] and _digests(cell) == before
    assert SEED_43 in harness.plan["failed_or_incomplete_cell_ids"]


# --- guard scoping -----------------------------------------------------------
def test_guard_ignores_unrelated_untracked_artifacts_and_fingerprint_is_unaffected(monkeypatch, tmp_path):
    repo = _git_repo(tmp_path / "repo", {"a.py": "A = 1\n"})
    monkeypatch.setattr(matrix, "REPOSITORY_ROOT", repo)
    monkeypatch.setattr(matrix, "RELEVANT_TRACKED_PATHS", ("a.py",))
    before = matrix.compute_source_fingerprint()
    (repo / "results_backup.json").write_text("{}", encoding="utf-8")
    (repo / "notes.md").write_text("scratch", encoding="utf-8")
    matrix._require_clean_relevant_inputs(require_tracked_runner=True)
    assert matrix.compute_source_fingerprint() == before


def test_guard_rejects_a_dirty_relevant_input_and_fingerprint_tracks_content(monkeypatch, tmp_path):
    repo = _git_repo(tmp_path / "repo", {"a.py": "A = 1\n"})
    monkeypatch.setattr(matrix, "REPOSITORY_ROOT", repo)
    monkeypatch.setattr(matrix, "RELEVANT_TRACKED_PATHS", ("a.py",))
    clean = matrix.compute_source_fingerprint()
    (repo / "a.py").write_text("A = 2\n", encoding="utf-8")
    assert matrix.compute_source_fingerprint() != clean
    with pytest.raises(RuntimeError, match="clean relevant tracked inputs"):
        matrix._require_clean_relevant_inputs(require_tracked_runner=True)


def test_guard_covers_an_untracked_module_that_is_actually_imported(monkeypatch, tmp_path):
    import types

    repo = _git_repo(tmp_path / "repo", {"a.py": "A = 1\n"})
    dep = repo / "hidden_dep.py"  # not in RELEVANT_TRACKED_PATHS, not committed
    dep.write_text("X = 1\n", encoding="utf-8")
    module = types.ModuleType("hidden_dep")
    module.__file__ = str(dep)
    monkeypatch.setitem(sys.modules, "hidden_dep", module)
    monkeypatch.setattr(matrix, "REPOSITORY_ROOT", repo)
    monkeypatch.setattr(matrix, "RELEVANT_TRACKED_PATHS", ("a.py",))

    assert "hidden_dep.py" in matrix.relevant_input_paths()
    with pytest.raises(RuntimeError, match="tracked in Git"):
        matrix._require_clean_relevant_inputs(require_tracked_runner=True)
    # An undeclared tracked-but-modified import is also caught.
    subprocess.run(["git", "add", "hidden_dep.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "dep"], cwd=repo, check=True, capture_output=True)
    matrix._require_clean_relevant_inputs(require_tracked_runner=True)
    dep.write_text("X = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="clean relevant tracked inputs"):
        matrix._require_clean_relevant_inputs(require_tracked_runner=True)


def test_test_modules_and_third_party_code_are_not_experiment_inputs():
    paths = matrix.relevant_input_paths()
    assert not any(p.startswith("tests/") or "site-packages" in p for p in paths)
    assert set(matrix.RELEVANT_TRACKED_PATHS) <= set(paths)


# ---------------------------------------------------------------------------
# Completed-cell validation: results integrity, coverage, summary consistency
# ---------------------------------------------------------------------------
def _results_lines(cell_dir):
    return (cell_dir / "results.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)


def test_truncated_results_file_is_rejected_by_hash_and_by_content(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    lines = _results_lines(cell_dir)
    (cell_dir / "results.jsonl").write_text("".join(lines[:-1]) + lines[-1][:20], encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())
    _refresh_results_hash(cell_dir)  # even a forged digest cannot hide malformed JSON
    with pytest.raises(ValueError):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_missing_row_is_rejected_even_with_a_forged_hash(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    kept = _results_lines(cell_dir)[:-1]
    (cell_dir / "results.jsonl").write_text("".join(kept), encoding="utf-8")
    _refresh_results_hash(cell_dir)
    with pytest.raises(ValueError, match="raw record count"):  # stale evidence count caught first
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())
    _edit_summary(cell_dir, lambda s: s["execution_evidence"].__setitem__("raw_record_count", len(kept)))
    with pytest.raises(ValueError, match="records; expected"):  # then exact coverage
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_duplicate_row_replacing_another_is_rejected_even_with_a_forged_hash(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    lines = _results_lines(cell_dir)
    lines[-1] = lines[0]  # right count, but one record twice and one missing
    (cell_dir / "results.jsonl").write_text("".join(lines), encoding="utf-8")
    _refresh_results_hash(cell_dir)
    with pytest.raises(ValueError, match="Duplicate matrix record"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_altered_record_is_rejected_by_hash_and_by_semantics(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    path = cell_dir / "results.jsonl"
    rows = [json.loads(x) for x in _results_lines(cell_dir)]
    rows[1]["answer"] = "tampered"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())
    _refresh_results_hash(cell_dir)
    with pytest.raises(ValueError, match="inconsistent"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_hash_mismatch_alone_is_rejected(tmp_path):
    cell_dir, _ = _write_cell(tmp_path, 42)
    path = cell_dir / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["results_sha256"] = "0" * 64
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


@pytest.mark.parametrize("bad", [None, "", "abc", 123])
def test_missing_or_malformed_results_hash_is_rejected_not_trusted(tmp_path, bad):
    """Legacy summaries without a hash are rejected, never silently accepted."""
    cell_dir, _ = _write_cell(tmp_path, 42)
    path = cell_dir / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    if bad is None:
        del summary["results_sha256"]
    else:
        summary["results_sha256"] = bad
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="results_sha256"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def _edit_summary(cell_dir, mutate):
    path = cell_dir / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    mutate(summary)
    path.write_text(json.dumps(summary), encoding="utf-8")


@pytest.mark.parametrize(
    "mutate,pattern",
    [
        (lambda s: s.__setitem__("cell_id", "other"), "identity"),
        (lambda s: s.__setitem__("query_count", 299), "query count"),
        (lambda s: s.__setitem__("query_count", True), "query count"),
        (lambda s: s.pop("execution_evidence"), "execution evidence"),
        (lambda s: s["execution_evidence"].__setitem__("raw_record_count", 1), "raw record count"),
        (lambda s: s.__setitem__("poison_instance_fingerprint", "x" * 64), "fingerprint"),
        (lambda s: s.pop("pipelines"), "per-pipeline metrics"),
        (lambda s: s["pipelines"]["dense"]["poisoned_condition"]["targeted_asr"].__setitem__("numerator", 0), "differ from the raw records"),
        (lambda s: s["pipelines"].pop("rcd"), "per-pipeline metrics"),
    ],
)
def test_summary_inconsistent_with_manifest_or_records_is_rejected(tmp_path, mutate, pattern):
    cell_dir, _ = _write_cell(tmp_path, 42)
    _edit_summary(cell_dir, mutate)
    with pytest.raises(ValueError, match=pattern):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


@pytest.mark.parametrize("field", ["pipeline", "query_id", "condition"])
@pytest.mark.parametrize("bad", [None, ["x"], 5])
def test_malformed_record_identity_types_are_a_clear_value_error(tmp_path, field, bad):
    cell_dir, _ = _write_cell(tmp_path, 42)
    rows = [json.loads(x) for x in _results_lines(cell_dir)]
    rows[0][field] = bad
    (cell_dir / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    _refresh_results_hash(cell_dir)
    with pytest.raises(ValueError, match="Invalid matrix record identity"):
        matrix.validate_completed_cell(cell_dir, frozen_inputs=_frozen())


def test_recomputed_pipeline_summary_matches_the_runner_summary(monkeypatch, tmp_path):
    """The validator's recomputation must equal summarize_pipeline on a real evaluation."""
    out, _ = _evaluate_small_cell(monkeypatch, tmp_path, top_k=2)
    rows = [json.loads(x) for x in (tmp_path / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    ids = list(dict.fromkeys(r["query_id"] for r in rows))
    indexed = _indexed(rows)
    for pipeline in ("dense", "rcd"):
        assert matrix.recompute_pipeline_summary(indexed, pipeline, ids) == out["pipelines"][pipeline]


# ---------------------------------------------------------------------------
# Recovery: crash-safe writes and corrupt-summary handling
# ---------------------------------------------------------------------------
def test_truncated_summary_is_never_trusted_and_needs_explicit_recovery(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.run()
    cell = harness.root / SEED_43
    full = (cell / "summary.json").read_bytes()
    (cell / "summary.json").write_bytes(full[: len(full) // 2])  # crash mid-write
    truncated = _digests(cell)
    harness.evaluated.clear()

    harness.run(resume=True)  # no flag: fail closed, touch nothing, say how to recover
    assert harness.evaluated == [] and _digests(cell) == truncated
    failure = harness.plan["cell_failures"][SEED_43]
    assert failure["source"] == "resume_validation" and "--recover-incomplete" in failure["hint"]

    _no_regeneration(monkeypatch)
    _recover(harness)  # explicit opt-in: archive intact, reuse verified manifest, re-evaluate
    assert harness.evaluated == [43] and harness.plan["status"] == "complete"
    archived = harness.root / matrix.ARCHIVE_DIRNAME / SEED_43 / "attempt_001"
    assert (archived / "summary.json").read_bytes() == full[: len(full) // 2]


def test_recovery_refuses_a_manifest_from_a_different_source_fingerprint(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    harness.behaviour[43] = "fail"
    harness.run()
    cell = harness.root / SEED_43
    _edit_manifest(cell, _set_git("source_fingerprint", "2" * 64))
    before = _digests(cell)
    harness.behaviour.clear()
    _recover(harness)
    assert _digests(cell) == before
    assert harness.plan["cell_failures"][SEED_43]["source"] == "recovery_refused"


def test_manifest_write_is_atomic_so_a_crash_cannot_leave_a_truncated_manifest(monkeypatch, tmp_path):
    harness = _Harness(monkeypatch, tmp_path)
    real = matrix.json.dump

    def crash(value, output, **kwargs):
        output.write('{"schema": "trunc')  # partial bytes, then the process dies
        raise OSError("disk full")

    monkeypatch.setattr(matrix.json, "dump", crash)
    with pytest.raises(OSError):
        matrix._write_json_atomic(tmp_path / "poison.manifest.json", {"a": 1})
    monkeypatch.setattr(matrix.json, "dump", real)
    assert not (tmp_path / "poison.manifest.json").exists()
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_aggregate_limitations_state_what_the_intervals_do_not_cover(tmp_path, monkeypatch):
    for seed in (42, 43, 44):
        _write_cell(tmp_path, seed)
    text = _aggregate_three(tmp_path, monkeypatch)["limitations"]
    assert "not resampled" in text and "query sampling only" in text
    assert "zero-width interval is not proof of equivalence" in text
