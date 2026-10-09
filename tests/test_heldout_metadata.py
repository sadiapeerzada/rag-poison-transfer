"""Regression tests for held-out dataset provenance metadata."""

from src.experiments.protocol import build_experiment_metadata


def _metadata_kwargs():
    return {
        "experiment_id": "metadata_test",
        "dataset": "hotpotqa",
        "dataset_revision": "revision-test",
        "dataset_split": "validation",
        "dataset_n_samples": None,
        "dataset_seed": None,
        "queries": [
            {
                "query_id": "q1",
                "question": "Example question?",
                "gold_answer": "Example",
                "gold_doc_ids": ["d1"],
            }
        ],
        "corpus": [{"doc_id": "d1", "text": "Example evidence."}],
        "retriever": "rcd",
        "embedder_model": None,
        "reranker_model": None,
        "generator_model": "test-generator",
        "defense": "rcd",
        "defense_config": {},
        "source_pipeline": None,
        "target_pipeline": None,
        "attack_family": "none",
        "attack_version": "none",
        "attack_config": {},
        "seed": 42,
        "top_k": 3,
        "n_poison": 0,
        "poison_rate": 0.0,
        "git_sha": "test-sha",
    }


def test_heldout_manifest_provenance_is_recorded():
    manifest_path = "configs/exp_027_hotpotqa_heldout_manifest.json"
    fingerprint = (
        "76671f6b9a70140578f2b0b6ac405eb3199235bc4d051e62d5896c715454e2df"
    )

    metadata = build_experiment_metadata(
        **_metadata_kwargs(),
        dataset_query_ids_manifest=manifest_path,
        heldout_query_ids_fingerprint=fingerprint,
    )

    assert metadata["dataset_query_ids_manifest"] == manifest_path
    assert metadata["heldout_query_ids_fingerprint"] == fingerprint


def test_legacy_experiment_without_manifest_remains_supported():
    metadata = build_experiment_metadata(**_metadata_kwargs())

    assert metadata["dataset_query_ids_manifest"] is None
    assert metadata["heldout_query_ids_fingerprint"] is None
    assert metadata["query_count"] == 1
    assert metadata["query_set_fingerprint"]
    assert metadata["git_dirty"] in (True, False, None)
