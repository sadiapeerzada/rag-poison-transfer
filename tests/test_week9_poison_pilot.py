import copy
import json

import pytest

import scripts.run_week9_poison_pilot as pilot
from scripts.run_week9_poison_pilot import (
    MANIFEST_SCHEMA,
    build_pilot_manifest,
    _metadata_for_pilot,
    replay_poisoned_data,
    select_pilot_attacked_ids,
    select_pilot_query_ids,
    validate_real_generator,
    write_json_exclusive,
)
from src.attacks.injection import inject_poisons
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.experiments.protocol import (
    corpus_fingerprint,
    poison_instances_fingerprint,
    query_set_fingerprint,
)
from src.pipelines.generator import MockGenerator


def _clean_data():
    return {
        "corpus": [{"doc_id": "doc-clean", "text": "Clean supporting fact."}],
        "queries": [
            {
                "query_id": f"q{i}",
                "question": f"Who founded example group {i}?",
                "gold_answer": f"Founder {i}",
                "gold_doc_ids": ["doc-clean"],
            }
            for i in range(5)
        ],
    }


def _metadata(clean_data, poisoned_data):
    fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    return {
        "dataset": "hotpotqa/hotpot_qa:distractor",
        "seed": 42,
        "attack_family": "lexical_influential_token",
        "attack_config": {
            "repeat_factor": 4,
            "n_poison_per_attacked_query": 1,
            "poison_rate": 1.0,
        },
        "query_set_fingerprint": query_set_fingerprint(clean_data["queries"]),
        "poison_instance_fingerprint": fingerprint,
        "poison_manifest_fingerprint": fingerprint,
        "git_commit_sha": "a" * 40,
        "git_dirty": True,
        "model_identifier": "mlx-test-model",
    }


def _poisoned_data(clean_data=None):
    clean_data = clean_data or _clean_data()
    attacked_ids = select_pilot_attacked_ids(clean_data["queries"])
    return inject_poisons(
        clean_data,
        LexicalInfluentialTokenAttack(repeat_factor=4),
        n_poison=1,
        poison_rate=1.0,
        seed=42,
        attacked_query_ids=attacked_ids,
    )


def _manifest(clean_data, poisoned_data):
    metadata = _metadata(clean_data, poisoned_data)
    return build_pilot_manifest(
        experiment_id="test-pilot",
        clean_data=clean_data,
        poisoned_data=poisoned_data,
        metadata=metadata,
        selected_query_ids=[query["query_id"] for query in clean_data["queries"]],
        attacked_query_ids=[
            query["query_id"]
            for query in poisoned_data["queries"]
            if query["poison_doc_ids"]
        ],
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
        retriever_config={"retriever": "rcd"},
        rcd_config={
            "candidate_k": 10,
            "rewrite_count": 3,
            "consistency_weight": 0.45,
            "redundancy_weight": 0.0,
            "conflict_weight": 0.1,
            "base_rank_weight": 0.45,
        },
    )


def test_query_and_attack_selection_are_deterministic():
    query_ids = [f"q{i}" for i in range(20)]
    first = select_pilot_query_ids(query_ids, n_queries=10, seed=42)
    second = select_pilot_query_ids(query_ids, n_queries=10, seed=42)
    assert first == second
    assert first == sorted(first)

    clean_data = _clean_data()
    first_attacked = select_pilot_attacked_ids(
    clean_data["queries"], poison_rate=0.6, seed=17
    )
    assert first_attacked == select_pilot_attacked_ids(
    clean_data["queries"], poison_rate=0.6, seed=17
    )
    assert len(first_attacked) == 3
    poison_a = _poisoned_data(clean_data)
    poison_b = _poisoned_data(clean_data)
    assert poison_instances_fingerprint(clean_data, poison_a) == (
        poison_instances_fingerprint(clean_data, poison_b)
    )


def test_manifest_serialization_round_trip_replays_exact_instances(tmp_path):
    clean_data = _clean_data()
    poisoned_data = _poisoned_data(clean_data)
    manifest = _manifest(clean_data, poisoned_data)
    path = tmp_path / "pilot.manifest.json"

    write_json_exclusive(path, manifest)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    replayed = replay_poisoned_data(clean_data, loaded)

    assert loaded["schema"] == MANIFEST_SCHEMA
    assert loaded["poison_documents"] == manifest["poison_documents"]
    assert loaded["poison_instance_fingerprint"] == manifest[
        "poison_instance_fingerprint"
    ]
    assert replayed == poisoned_data
    assert corpus_fingerprint(replayed["corpus"]) == corpus_fingerprint(
        poisoned_data["corpus"]
    )


def test_manifest_collision_does_not_overwrite_existing_file(tmp_path):
    path = tmp_path / "pilot.manifest.json"
    original = '{"preserve": true}\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_json_exclusive(path, {"replacement": True})

    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("mutation", ["text", "document_id", "association"])
def test_replay_rejects_altered_poison_instances(mutation):
    clean_data = _clean_data()
    poisoned_data = _poisoned_data(clean_data)
    manifest = _manifest(clean_data, poisoned_data)
    changed = copy.deepcopy(manifest)
    if mutation == "text":
        changed["poison_documents"][0]["text"] += " altered"
    elif mutation == "document_id":
        changed["poison_documents"][0]["doc_id"] += "-altered"
    else:
        changed["query_poison_associations"][0]["poison_doc_ids"] = []

    with pytest.raises(ValueError):
        replay_poisoned_data(clean_data, changed)


def test_replay_never_regenerates_attack_text(monkeypatch):
    clean_data = _clean_data()
    poisoned_data = _poisoned_data(clean_data)
    manifest = _manifest(clean_data, poisoned_data)

    def fail_if_regenerated(*args, **kwargs):
        raise AssertionError("Replay must not regenerate poison text.")

    monkeypatch.setattr(LexicalInfluentialTokenAttack, "generate", fail_if_regenerated)
    replayed = replay_poisoned_data(clean_data, manifest)

    assert replayed == poisoned_data


def test_missing_strict_metadata_fails_closed_via_transfer_validator():
    from src.pipelines.transfer import validate_transfer_experiment_metadata

    with pytest.raises(ValueError, match="explicit experiment_metadata"):
        validate_transfer_experiment_metadata(
            None,
            expected_source_pipeline="rcd",
            expected_target_pipeline="rcd",
        )


def test_mock_generator_is_rejected_for_pilot_asr():
    with pytest.raises(TypeError, match="requires a real MLX generator"):
        validate_real_generator(MockGenerator())


def test_metadata_uses_explicit_validated_heldout_fingerprint(monkeypatch):
    captured = {}

    def build_metadata(**kwargs):
        captured.update(kwargs)
        return kwargs.copy()

    monkeypatch.setattr(pilot, "build_experiment_metadata", build_metadata)
    monkeypatch.setattr(pilot, "validate_transfer_experiment_metadata", lambda *args, **kwargs: None)
    clean_data = _clean_data()
    metadata = _metadata_for_pilot(
        experiment_id="test-pilot",
        config={
            "dataset_revision": "revision-1",
            "dataset_split": "validation",
            "retriever": "rcd",
            "generator_model": "mlx-test-model",
            "rcd_candidate_k": 10,
            "rcd_rewrite_count": 3,
            "rcd_consistency_weight": 0.45,
            "rcd_redundancy_weight": 0.0,
            "rcd_conflict_weight": 0.1,
            "rcd_base_rank_weight": 0.45,
            "top_k": 3,
        },
        clean_data=clean_data,
        heldout_manifest_fingerprint="validated-heldout-fingerprint",
        attacked_query_ids=["q0"],
        poison_fingerprint="poison-fingerprint",
        git_sha="a" * 40,
        git_dirty=True,
        attack_version="git:" + "a" * 40,
    )

    assert captured["heldout_query_ids_fingerprint"] == "validated-heldout-fingerprint"
    assert metadata["heldout_query_ids_fingerprint"] == "validated-heldout-fingerprint"


def test_manifest_binds_attack_targets_and_document_text():
    clean_data = _clean_data()
    poisoned_data = _poisoned_data(clean_data)
    manifest = _manifest(clean_data, poisoned_data)

    assert manifest["clean_corpus_fingerprint"] == corpus_fingerprint(
        clean_data["corpus"]
    )
    assert manifest["poison_instance_fingerprint"] == poison_instances_fingerprint(
        clean_data,
        poisoned_data,
    )
    assert all(
        association["poison_target_answer"]
        for association in manifest["query_poison_associations"]
        if association["poison_doc_ids"]
    )
