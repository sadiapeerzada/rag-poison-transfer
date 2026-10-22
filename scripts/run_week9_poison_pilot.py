#!/usr/bin/env python3
"""Run a small, manifest-backed Week 9 lexical poisoning pilot.

This is a single-pipeline clean/poisoned comparison on the frozen RCD
configuration. It is not a final run or a source-to-target transfer matrix.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from run import _load_heldout_manifest, build_retriever, load_dataset
from src.attacks.asr import conditional_asr, evaluate_asr_for_retriever
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.evaluation.metrics import exact_match, poison_retrieval_rate_at_k
from src.experiments.protocol import (
    build_experiment_metadata,
    corpus_fingerprint,
    freeze_attack_query_ids,
    git_commit_sha,
    poison_instances_fingerprint,
    query_set_fingerprint,
    select_fixed_query_ids,
)
from src.pipelines.generator import MLXGenerator, MockGenerator
from src.pipelines.transfer import validate_transfer_experiment_metadata
from src.utils.config import load_config
from src.utils.env_info import _git_dirty
from src.utils.seeding import set_seed

MANIFEST_SCHEMA = "rag-poison-transfer.week9-poison-pilot/v1"
DEFAULT_CONFIG = REPOSITORY_ROOT / "configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml"
DEFAULT_HELDOUT_MANIFEST = REPOSITORY_ROOT / "configs/exp_027_hotpotqa_heldout_manifest.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads/rag-rcd-week9-final-results/poison-pilot"
PILOT_QUERY_COUNT = 10
PILOT_SEED = 42
POISON_RATE = 1.0
N_POISON = 1
ATTACK_REPEAT_FACTOR = 4
RETRIEVAL_METRIC_K = 10

METRIC_DEFINITIONS = {
    "poison_retrieval_rate_at_k": (
        "Attacked queries with >=1 associated poison document in top-k "
        "retrieved / all attacked queries."
    ),
    "targeted_asr": (
        "Attacked queries whose poisoned-evidence answer matches the intended "
        "poison target / all attacked queries."
    ),
    "asr_given_poison_retrieved": (
        "Targeted successes with a poison document in the top generation "
        "evidence / attacked queries with a poison document in that evidence."
    ),
    "asr_given_poison_not_retrieved": (
        "Targeted successes without a poison document in generation evidence / "
        "attacked queries without a poison document in that evidence."
    ),
    "untargeted_degradation_rate": (
        "Queries answered correctly with clean evidence but not with poisoned "
        "evidence / all attacked queries."
    ),
    "clean_answer_correct_rate": (
        "Clean-evidence answers matching gold / all attacked queries."
    ),
    "poisoned_answer_correct_rate": (
        "Poisoned-evidence answers matching gold / all attacked queries."
    ),
}


def select_pilot_query_ids(
    query_ids: list[str],
    *,
    n_queries: int = PILOT_QUERY_COUNT,
    seed: int = PILOT_SEED,
) -> list[str]:
    """Select a reproducible sorted subset using the protocol helper."""
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Query IDs must be unique before pilot selection.")
    return select_fixed_query_ids(
        [{"query_id": query_id} for query_id in query_ids],
        n_queries=n_queries,
        seed=seed,
    )


def select_pilot_attacked_ids(
    queries: list[dict],
    *,
    poison_rate: float = POISON_RATE,
    seed: int = PILOT_SEED,
) -> list[str]:
    """Freeze attacked IDs with the protocol's deterministic selector."""
    if not 0 < poison_rate <= 1:
        raise ValueError("Pilot poison_rate must be in the interval (0, 1].")
    attacked_count = round(len(queries) * poison_rate)
    if attacked_count < 1:
        raise ValueError("Pilot settings select no attacked queries.")
    attacked_ids, _ = freeze_attack_query_ids(
        queries,
        n_queries=attacked_count,
        seed=seed,
    )
    return attacked_ids


def validate_real_generator(generator: Any) -> None:
    """Reject the repository's mock generator on the actual pilot path."""
    if isinstance(generator, MockGenerator):
        raise TypeError("The poisoning pilot requires a real MLX generator.")
    if not callable(getattr(generator, "generate", None)):
        raise TypeError("Generator must implement generate(prompt, max_tokens).")


def _query_associations(poisoned_data: dict) -> list[dict[str, Any]]:
    return [
        {
            "query_id": query["query_id"],
            "attack_family": query.get("attack_family"),
            "poison_doc_ids": sorted(query.get("poison_doc_ids", [])),
            "poison_target_answer": query.get("poison_target_answer"),
        }
        for query in poisoned_data["queries"]
    ]


def build_pilot_manifest(
    *,
    experiment_id: str,
    clean_data: dict,
    poisoned_data: dict,
    metadata: dict,
    selected_query_ids: list[str],
    attacked_query_ids: list[str],
    heldout_manifest_fingerprint: str,
    dataset_revision: str,
    dataset_split: str,
    seed: int,
    poison_rate: float,
    n_poison: int,
    attack_repeat_factor: int,
    attack_version: str,
    generator_backend: str,
    generator_model: str,
    generator_max_tokens: int,
    top_k: int,
    retrieval_metric_k: int,
    retriever_config: dict,
    rcd_config: dict,
    heldout_manifest_path: str = str(DEFAULT_HELDOUT_MANIFEST),
    parent_manifest: str | None = None,
) -> dict[str, Any]:
    """Create a serializable, replayable manifest from actual poison data."""
    clean_ids = {document["doc_id"] for document in clean_data["corpus"]}
    poison_documents = [
        {"doc_id": document["doc_id"], "text": document["text"]}
        for document in poisoned_data["corpus"]
        if document["doc_id"] not in clean_ids
    ]
    instance_fingerprint = poison_instances_fingerprint(
        clean_data,
        poisoned_data,
    )
    if instance_fingerprint != metadata.get("poison_instance_fingerprint"):
        raise ValueError("Metadata poison fingerprint differs from actual instances.")

    return {
        "schema": MANIFEST_SCHEMA,
        "experiment_id": experiment_id,
        "pilot_status": "pilot_not_final",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "name": "hotpotqa/hotpot_qa",
            "config": "distractor",
            "loader": "load_hotpotqa_distractor",
            "revision": dataset_revision,
            "split": dataset_split,
            "heldout_manifest": heldout_manifest_path,
            "heldout_manifest_fingerprint": heldout_manifest_fingerprint,
            "query_set_fingerprint": query_set_fingerprint(
                clean_data["queries"]
            ),
            "selected_query_ids": selected_query_ids,
        },
        "attacked_query_ids": attacked_query_ids,
        "seed": seed,
        "attack": {
            "family": "lexical_influential_token",
            "version": attack_version,
            "configuration": {
                "repeat_factor": attack_repeat_factor,
                "n_poison_per_attacked_query": n_poison,
                "poison_rate": poison_rate,
            },
        },
        "poison_documents": poison_documents,
        "query_poison_associations": _query_associations(poisoned_data),
        "clean_corpus_fingerprint": corpus_fingerprint(clean_data["corpus"]),
        "poison_instance_fingerprint": instance_fingerprint,
        "generator": {
            "backend": generator_backend,
            "model_identifier": generator_model,
            "max_tokens": generator_max_tokens,
        },
        "source_pipeline": "rcd",
        "evaluation": {
            "top_k": top_k,
            "retrieval_metric_k": retrieval_metric_k,
        },
        "retriever_configuration": retriever_config,
        "rcd_configuration": rcd_config,
        "git": {
            "commit_sha": metadata["git_commit_sha"],
            "worktree_dirty": metadata["git_dirty"],
            "dirty_check_scope": "tracked and untracked non-ignored files",
        },
        "experiment_metadata": metadata,
        "metric_definitions": METRIC_DEFINITIONS,
        "parent_manifest": parent_manifest,
        "is_transfer_matrix": False,
    }


def replay_poisoned_data(clean_data: dict, manifest: dict) -> dict:
    """Reconstruct exactly the saved poisoned corpus without an attack call."""
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("Unsupported poison-pilot manifest schema.")
    dataset = manifest.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("Manifest is missing dataset metadata.")
    selected_ids = dataset.get("selected_query_ids")
    actual_ids = [query["query_id"] for query in clean_data["queries"]]
    if (
        not isinstance(selected_ids, list)
        or len(selected_ids) != len(set(selected_ids))
        or set(selected_ids) != set(actual_ids)
    ):
        raise ValueError("Manifest selected query IDs do not match clean_data.")
    if dataset.get("query_set_fingerprint") != query_set_fingerprint(
        clean_data["queries"]
    ):
        raise ValueError("Manifest query-set fingerprint does not match clean_data.")
    if manifest.get("clean_corpus_fingerprint") != corpus_fingerprint(
        clean_data["corpus"]
    ):
        raise ValueError("Manifest clean-corpus fingerprint does not match clean_data.")

    associations = manifest.get("query_poison_associations")
    if not isinstance(associations, list):
        raise ValueError("Manifest query-poison associations must be a list.")
    association_by_id = {}
    for association in associations:
        if not isinstance(association, dict):
            raise ValueError("Manifest contains an invalid query association.")
        query_id = association.get("query_id")
        if not isinstance(query_id, str) or query_id in association_by_id:
            raise ValueError("Manifest contains missing or duplicate query IDs.")
        association_by_id[query_id] = association
    if set(association_by_id) != set(actual_ids):
        raise ValueError("Manifest query associations do not cover selected queries.")
    attacked_ids = [
        query_id
        for query_id in actual_ids
        if association_by_id[query_id].get("poison_doc_ids")
    ]
    manifest_attacked_ids = manifest.get("attacked_query_ids")
    if (
        not isinstance(manifest_attacked_ids, list)
        or len(manifest_attacked_ids) != len(set(manifest_attacked_ids))
        or set(manifest_attacked_ids) != set(attacked_ids)
    ):
        raise ValueError("Manifest attacked_query_ids disagree with its associations.")

    poison_documents = manifest.get("poison_documents")
    if not isinstance(poison_documents, list):
        raise ValueError("Manifest poison_documents must be a list.")
    poisoned_data = {
        "corpus": [dict(document) for document in clean_data["corpus"]],
        "queries": [],
    }
    poisoned_data["corpus"].extend(copy.deepcopy(poison_documents))
    for query in clean_data["queries"]:
        association = association_by_id[query["query_id"]]
        poison_ids = association.get("poison_doc_ids")
        if not isinstance(poison_ids, list):
            raise ValueError(
                f"Manifest has invalid poison_doc_ids for {query['query_id']!r}."
            )
        poisoned_query = dict(query)
        poisoned_query["attack_family"] = association.get("attack_family")
        poisoned_query["poison_doc_ids"] = list(poison_ids)
        poisoned_query["poison_target_answer"] = association.get(
            "poison_target_answer"
        )
        poisoned_data["queries"].append(poisoned_query)

    expected_fingerprint = manifest.get("poison_instance_fingerprint")
    actual_fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    if actual_fingerprint != expected_fingerprint:
        raise ValueError(
            "Manifest poison-instance fingerprint does not match its documents "
            "and query associations."
        )
    metadata = manifest.get("experiment_metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("poison_instance_fingerprint") != actual_fingerprint
        or metadata.get("poison_manifest_fingerprint") != actual_fingerprint
    ):
        raise ValueError("Manifest experiment metadata has a mismatched poison fingerprint.")
    return poisoned_data


def write_json_exclusive(path: Path, value: dict) -> None:
    """Write canonical, readable JSON without ever replacing an artifact."""
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
        output.write("\n")


def _ensure_output_outside_repository(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError(
        "Pilot output must be outside the Git worktree so it cannot change "
        "the recorded Git dirty state."
    )


def _metadata_for_pilot(
    *,
    experiment_id: str,
    config: dict,
    clean_data: dict,
    heldout_manifest_fingerprint: str,
    attacked_query_ids: list[str],
    poison_fingerprint: str,
    git_sha: str,
    git_dirty: bool,
    attack_version: str,
) -> dict:
    attack_config = {
        "repeat_factor": ATTACK_REPEAT_FACTOR,
        "n_poison_per_attacked_query": N_POISON,
        "poison_rate": POISON_RATE,
    }
    metadata = build_experiment_metadata(
        experiment_id=experiment_id,
        dataset="hotpotqa/hotpot_qa:distractor",
        dataset_revision=config["dataset_revision"],
        dataset_split=config["dataset_split"],
        dataset_n_samples=len(clean_data["queries"]),
        dataset_seed=PILOT_SEED,
        queries=clean_data["queries"],
        corpus=clean_data["corpus"],
        retriever=config["retriever"],
        embedder_model=config.get("embedder_model"),
        reranker_model=config.get("reranker_model"),
        generator_model=config["generator_model"],
        defense="rcd",
        defense_config={
            "candidate_k": config["rcd_candidate_k"],
            "rewrite_count": config["rcd_rewrite_count"],
            "consistency_weight": config["rcd_consistency_weight"],
            "redundancy_weight": config["rcd_redundancy_weight"],
            "conflict_weight": config["rcd_conflict_weight"],
            "base_rank_weight": config["rcd_base_rank_weight"],
        },
        source_pipeline="rcd",
        target_pipeline="rcd",
        attack_family="lexical_influential_token",
        attack_version=attack_version,
        attack_config=attack_config,
        seed=PILOT_SEED,
        top_k=int(config["top_k"]),
        n_poison=N_POISON,
        poison_rate=POISON_RATE,
        attacked_query_ids=attacked_query_ids,
        git_sha=git_sha,
        git_dirty=git_dirty,
        dataset_query_ids_manifest=str(DEFAULT_HELDOUT_MANIFEST),
        heldout_query_ids_fingerprint=heldout_manifest_fingerprint,
        final_run=False,
    )
    metadata.update(
        {
            "model_identifier": config["generator_model"],
            "poison_instance_fingerprint": poison_fingerprint,
            "poison_manifest_fingerprint": poison_fingerprint,
        }
    )
    validate_transfer_experiment_metadata(
        metadata,
        expected_source_pipeline="rcd",
        expected_target_pipeline="rcd",
    )
    return metadata


def _frozen_retriever_config(config: dict) -> dict:
    return {
        "retriever": config["retriever"],
        "base_retriever": "dense",
        "sparse_retriever": "bm25",
        "dense_retriever": "dense",
        "embedder_model": config["embedder_model"],
        "output_k": int(config["top_k"]),
        "rcd_candidate_k": int(config["rcd_candidate_k"]),
        "rcd_rewrite_count": int(config["rcd_rewrite_count"]),
        "rcd_consistency_weight": float(config["rcd_consistency_weight"]),
        "rcd_redundancy_weight": float(config["rcd_redundancy_weight"]),
        "rcd_conflict_weight": float(config["rcd_conflict_weight"]),
        "rcd_base_rank_weight": float(config["rcd_base_rank_weight"]),
    }


def _load_config_and_clean_data(
    *,
    config_path: Path,
    heldout_manifest_path: Path,
    replay_manifest: dict | None,
) -> tuple[dict, dict, list[str], str]:
    config = load_config(str(config_path.resolve()))
    if config.get("retriever") != "rcd":
        raise ValueError("The Week 9 pilot requires the frozen RCD retriever config.")
    if config.get("generator_backend") != "mlx":
        raise ValueError("The Week 9 pilot requires the real MLX generator.")
    if config.get("dataset_loader") != "load_hotpotqa_distractor":
        raise ValueError("The Week 9 pilot requires the HotpotQA distractor loader.")
    if config.get("final_run") is not True:
        raise ValueError("The source config must be the frozen final RCD config.")
    rcd_config = {
        "candidate_k": config["rcd_candidate_k"],
        "rewrite_count": config["rcd_rewrite_count"],
        "consistency_weight": config["rcd_consistency_weight"],
        "redundancy_weight": config["rcd_redundancy_weight"],
        "conflict_weight": config["rcd_conflict_weight"],
        "base_rank_weight": config["rcd_base_rank_weight"],
    }
    retriever_config = _frozen_retriever_config(config)
    if replay_manifest is not None:
        if replay_manifest.get("source_pipeline") != "rcd":
            raise ValueError("Replay manifest is not an RCD pilot.")
        if replay_manifest.get("rcd_configuration") != rcd_config:
            raise ValueError("Replay manifest RCD configuration differs from frozen config.")
        if replay_manifest.get("retriever_configuration") != retriever_config:
            raise ValueError("Replay manifest retriever configuration differs.")
        expected_attack_config = {
            "repeat_factor": ATTACK_REPEAT_FACTOR,
            "n_poison_per_attacked_query": N_POISON,
            "poison_rate": POISON_RATE,
        }
        replay_attack = replay_manifest.get("attack", {})
        if (
            replay_attack.get("family") != "lexical_influential_token"
            or replay_attack.get("configuration") != expected_attack_config
        ):
            raise ValueError("Replay manifest attack configuration differs from pilot.")
        replay_generator = replay_manifest.get("generator", {})
        if (
            replay_generator.get("backend") != config["generator_backend"]
            or replay_generator.get("model_identifier") != config["generator_model"]
            or replay_generator.get("max_tokens")
            != int(config.get("max_tokens", 64))
        ):
            raise ValueError("Replay manifest generator configuration differs.")
        replay_evaluation = replay_manifest.get("evaluation", {})
        if replay_evaluation != {
            "top_k": int(config["top_k"]),
            "retrieval_metric_k": RETRIEVAL_METRIC_K,
        }:
            raise ValueError("Replay manifest evaluation cutoffs differ.")
    config["dataset_query_ids_manifest"] = str(heldout_manifest_path.resolve())
    validated_ids, heldout_fingerprint = _load_heldout_manifest(config)
    if validated_ids is None:
        raise ValueError("A validated held-out query manifest is required.")

    if replay_manifest is None:
        selected_ids = select_pilot_query_ids(validated_ids)
    else:
        replay_dataset = replay_manifest.get("dataset", {})
        selected_ids = replay_dataset.get("selected_query_ids")
        if replay_dataset.get("revision") != config["dataset_revision"]:
            raise ValueError("Replay manifest dataset revision differs from config.")
        if replay_dataset.get("split") != config["dataset_split"]:
            raise ValueError("Replay manifest dataset split differs from config.")
        if replay_dataset.get("heldout_manifest_fingerprint") != heldout_fingerprint:
            raise ValueError("Replay manifest uses a different held-out query manifest.")
        if (
            not isinstance(selected_ids, list)
            or not set(selected_ids).issubset(set(validated_ids))
        ):
            raise ValueError("Replay manifest selected IDs are not in held-out manifest.")

    clean_data = load_dataset(
        {
            "dataset_loader": config["dataset_loader"],
            "dataset_split": config["dataset_split"],
            "dataset_revision": config["dataset_revision"],
            "dataset_query_ids": selected_ids,
        }
    )
    if replay_manifest is not None:
        replay_poisoned_data(clean_data, replay_manifest)
    return config, clean_data, selected_ids, heldout_fingerprint


def _prepare_paths(output_dir: Path, experiment_id: str) -> dict[str, Path]:
    if not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be a non-empty filename-safe value.")
    paths = {
        "manifest": output_dir / f"{experiment_id}.manifest.json",
        "results": output_dir / f"{experiment_id}.jsonl",
        "summary": output_dir / f"{experiment_id}.summary.json",
        "failure": output_dir / f"{experiment_id}.failure.json",
    }
    collisions = [str(path) for path in paths.values() if path.exists()]
    if collisions:
        raise FileExistsError(
            "Pilot outputs already exist; choose a separate output directory "
            f"or experiment ID. Existing paths: {collisions}"
        )
    return paths


def _summarize_results(rows: list[dict], *, runtime_seconds: float) -> dict:
    if not rows:
        raise ValueError("Cannot summarize a pilot with no completed attacked queries.")
    conditional = conditional_asr(rows)
    denominator = len(rows)
    clean_correct = sum(bool(exact_match(row["clean_answer"], row["gold_answer"])) for row in rows)
    poisoned_correct = sum(bool(exact_match(row["attacked_answer"], row["gold_answer"])) for row in rows)
    prr = {}
    prr_counts = {}
    for k in (1, 3, 5, 10):
        per_query = [
            poison_retrieval_rate_at_k(
                row["retrieved_doc_ids"],
                row["poison_doc_ids"],
                k,
            )
            for row in rows
        ]
        valid = [value for value in per_query if value is not None]
        prr[f"prr@{k}"] = sum(valid) / len(valid) if valid else None
        prr_counts[f"prr@{k}"] = {
            "numerator": int(sum(valid)),
            "denominator": len(valid),
        }
    retrieved_rows = [row for row in rows if row["poison_retrieved"]]
    not_retrieved_rows = [row for row in rows if not row["poison_retrieved"]]
    conditional_counts = {
        "asr_given_poison_retrieved": {
            "numerator": sum(bool(row["attack_success"]) for row in retrieved_rows),
            "denominator": len(retrieved_rows),
        },
        "asr_given_poison_not_retrieved": {
            "numerator": sum(
                bool(row["attack_success"]) for row in not_retrieved_rows
            ),
            "denominator": len(not_retrieved_rows),
        },
    }
    ranked_poison_rows = [row for row in rows if row["poison_rank"] is not None]
    poison_rank_summary = {
        "retrieved_count": len(ranked_poison_rows),
        "denominator": denominator,
        "mean_rank_when_retrieved": (
            sum(row["poison_rank"] for row in ranked_poison_rows)
            / len(ranked_poison_rows)
            if ranked_poison_rows
            else None
        ),
    }
    return {
        "pilot_status": "complete_pilot_not_final",
        "is_final_run": False,
        "is_transfer_matrix": False,
        "pipeline": "rcd",
        "selected_query_count": None,
        "attacked_query_count": denominator,
        "completed_query_count": denominator,
        "failed_query_count": 0,
        "skipped_query_count": 0,
        "runtime_seconds": runtime_seconds,
        "poison_retrieval": prr,
        "poison_retrieval_counts": prr_counts,
        "targeted_asr": conditional["overall_asr"],
        "source_asr": conditional["overall_asr"],
        "source_success_count": sum(bool(row["attack_success"]) for row in rows),
        "targeted_asr_counts": {
            "numerator": sum(bool(row["attack_success"]) for row in rows),
            "denominator": denominator,
        },
        "conditional_asr": conditional,
        "conditional_asr_counts": conditional_counts,
        "poison_rank": poison_rank_summary,
        "untargeted_degradation_rate": conditional["untargeted_degradation_rate"],
        "untargeted_degradation_counts": {
            "numerator": sum(bool(row["untargeted_degradation"]) for row in rows),
            "denominator": denominator,
        },
        "clean_answer_correct": {
            "numerator": clean_correct,
            "denominator": denominator,
            "rate": clean_correct / denominator,
        },
        "poisoned_answer_correct": {
            "numerator": poisoned_correct,
            "denominator": denominator,
            "rate": poisoned_correct / denominator,
        },
        "metric_definitions": METRIC_DEFINITIONS,
    }


def run_pilot(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    experiment_id: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    heldout_manifest_path: Path = DEFAULT_HELDOUT_MANIFEST,
    replay_manifest_path: Path | None = None,
) -> dict:
    """Create immutable provenance before inference and retain per-query rows."""
    output_dir = _ensure_output_outside_repository(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if experiment_id is None:
        experiment_id = datetime.now(timezone.utc).strftime(
            "week9_lexical_rcd_pilot_%Y%m%dT%H%M%SZ"
        )
    paths = _prepare_paths(output_dir, experiment_id)

    # Capture provenance before dataset loading, attack generation, or output.
    commit_sha = git_commit_sha(default="")
    dirty_state = _git_dirty()
    if not commit_sha or commit_sha == "unknown":
        raise RuntimeError("Cannot determine the Git commit SHA for this pilot.")
    if dirty_state is None:
        raise RuntimeError("Cannot determine tracked/untracked Git working-tree state.")

    replay_manifest = None
    if replay_manifest_path is not None:
        with replay_manifest_path.expanduser().open(encoding="utf-8") as source:
            replay_manifest = json.load(source)

    config, clean_data, selected_ids, heldout_fingerprint = (
        _load_config_and_clean_data(
            config_path=config_path,
            heldout_manifest_path=heldout_manifest_path,
            replay_manifest=replay_manifest,
        )
    )
    if len(clean_data["queries"]) != PILOT_QUERY_COUNT:
        raise ValueError(
            f"Pilot must use {PILOT_QUERY_COUNT} selected queries; "
            f"loader returned {len(clean_data['queries'])}."
        )
    if [query["query_id"] for query in clean_data["queries"]] != selected_ids:
        raise ValueError("Dataset loader returned query IDs in a different order.")

    set_seed(PILOT_SEED)
    attack = LexicalInfluentialTokenAttack(
        repeat_factor=ATTACK_REPEAT_FACTOR
    )
    if replay_manifest is None:
        attacked_ids = select_pilot_attacked_ids(clean_data["queries"])
        poisoned_data = inject_poisons(
            clean_data,
            attack,
            n_poison=N_POISON,
            poison_rate=POISON_RATE,
            seed=PILOT_SEED,
            attacked_query_ids=attacked_ids,
        )
    else:
        poisoned_data = replay_poisoned_data(clean_data, replay_manifest)
        attacked_ids = [
            query["query_id"]
            for query in poisoned_data["queries"]
            if query.get("poison_doc_ids")
        ]

    validation = validate_poisoned_dataset(
        clean_data,
        poisoned_data,
        expected_n_poison=N_POISON,
        expected_poison_rate=POISON_RATE,
    )
    if not validation["valid"]:
        raise ValueError(f"Poisoned dataset validation failed: {validation['checks']}")

    poison_fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    if replay_manifest is not None and (
        poison_fingerprint != replay_manifest.get("poison_instance_fingerprint")
    ):
        raise ValueError("Replayed poison fingerprint changed.")
    metadata = _metadata_for_pilot(
        experiment_id=experiment_id,
        config=config,
        clean_data=clean_data,
        heldout_manifest_fingerprint=heldout_fingerprint,
        attacked_query_ids=attacked_ids,
        poison_fingerprint=poison_fingerprint,
        git_sha=commit_sha,
        git_dirty=dirty_state,
        attack_version=(
            replay_manifest["attack"]["version"]
            if replay_manifest is not None
            else f"git:{commit_sha}"
        ),
    )
    rcd_config = {
        "candidate_k": config["rcd_candidate_k"],
        "rewrite_count": config["rcd_rewrite_count"],
        "consistency_weight": config["rcd_consistency_weight"],
        "redundancy_weight": config["rcd_redundancy_weight"],
        "conflict_weight": config["rcd_conflict_weight"],
        "base_rank_weight": config["rcd_base_rank_weight"],
    }
    retriever_config = _frozen_retriever_config(config)
    manifest = build_pilot_manifest(
        experiment_id=experiment_id,
        clean_data=clean_data,
        poisoned_data=poisoned_data,
        metadata=metadata,
        selected_query_ids=selected_ids,
        attacked_query_ids=attacked_ids,
        heldout_manifest_fingerprint=heldout_fingerprint,
        dataset_revision=config["dataset_revision"],
        dataset_split=config["dataset_split"],
        seed=PILOT_SEED,
        poison_rate=POISON_RATE,
        n_poison=N_POISON,
        attack_repeat_factor=ATTACK_REPEAT_FACTOR,
        attack_version=metadata["attack_version"],
        generator_backend=config["generator_backend"],
        generator_model=config["generator_model"],
        generator_max_tokens=int(config.get("max_tokens", 64)),
        top_k=int(config["top_k"]),
        retrieval_metric_k=RETRIEVAL_METRIC_K,
        retriever_config=retriever_config,
        rcd_config=rcd_config,
        heldout_manifest_path=config["dataset_query_ids_manifest"],
        parent_manifest=(
            str(replay_manifest_path.expanduser().resolve())
            if replay_manifest_path is not None
            else None
        ),
    )
    write_json_exclusive(paths["manifest"], manifest)

    rows: list[dict] = []
    run_started = time.perf_counter()
    stage = "generator_initialization"
    failed_query_id = None
    skipped_query_ids: list[str] = []
    try:
        generator = MLXGenerator(model_name=config["generator_model"])
        validate_real_generator(generator)

        stage = "retriever_initialization"
        clean_retriever = build_retriever(config)
        poisoned_retriever = build_retriever(config)
        clean_retriever.build([dict(doc) for doc in clean_data["corpus"]])
        poisoned_retriever.build(
            [dict(doc) for doc in poisoned_data["corpus"]]
        )
        if (
            corpus_fingerprint(clean_data["corpus"])
            != manifest["clean_corpus_fingerprint"]
            or poison_instances_fingerprint(clean_data, poisoned_data)
            != manifest["poison_instance_fingerprint"]
        ):
            raise RuntimeError("Canonical corpus changed before ASR evaluation.")

        stage = "query_evaluation"
        with paths["results"].open("x", encoding="utf-8") as result_file:
            query_by_id = {
                query["query_id"]: query for query in clean_data["queries"]
            }
            poisoned_query_by_id = {
                query["query_id"]: query for query in poisoned_data["queries"]
            }
            for index, query_id in enumerate(attacked_ids):
                failed_query_id = query_id
                query_started = time.perf_counter()
                row = evaluate_asr_for_retriever(
                    clean_retriever,
                    poisoned_retriever,
                    {"corpus": clean_data["corpus"], "queries": [query_by_id[query_id]]},
                    {
                        "corpus": poisoned_data["corpus"],
                        "queries": [poisoned_query_by_id[query_id]],
                    },
                    generator,
                    source_pipeline="rcd",
                    target_pipeline="rcd",
                    top_k=int(config["top_k"]),
                    max_tokens=int(config.get("max_tokens", 64)),
                    retrieval_metric_k=RETRIEVAL_METRIC_K,
                    experiment_metadata=metadata,
                )[0]
                row["pilot_query_runtime_seconds"] = (
                    time.perf_counter() - query_started
                )
                row["clean_answer_correct"] = bool(
                    exact_match(row["clean_answer"], row["gold_answer"])
                )
                row["poisoned_answer_correct"] = bool(
                    exact_match(row["attacked_answer"], row["gold_answer"])
                )
                row["poison_retrieval_rates"] = {
                    f"prr@{k}": poison_retrieval_rate_at_k(
                        row["retrieved_doc_ids"], row["poison_doc_ids"], k
                    )
                    for k in (1, 3, 5, 10)
                }
                rows.append(row)
                result_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                result_file.flush()
                failed_query_id = None
                skipped_query_ids = attacked_ids[index + 1 :]

        summary = _summarize_results(
            rows,
            runtime_seconds=time.perf_counter() - run_started,
        )
        summary.update(
            {
                "experiment_id": experiment_id,
                "selected_query_count": len(selected_ids),
                "selected_query_ids": selected_ids,
                "attacked_query_ids": attacked_ids,
                "poison_document_count": len(manifest["poison_documents"]),
                "poison_instance_fingerprint": poison_fingerprint,
                "dataset_revision": config["dataset_revision"],
                "dataset_split": config["dataset_split"],
                "query_set_fingerprint": metadata["query_set_fingerprint"],
                "generator": manifest["generator"],
                "git": manifest["git"],
                "manifest_path": str(paths["manifest"]),
                "results_path": str(paths["results"]),
            }
        )
        write_json_exclusive(paths["summary"], summary)
        return summary
    except Exception as error:
        failure = {
            "experiment_id": experiment_id,
            "pilot_status": "failed",
            "failed_stage": stage,
            "failed_query_id": failed_query_id,
            "completed_query_count": len(rows),
            "failed_query_count": 1 if failed_query_id else 0,
            "skipped_query_ids": skipped_query_ids,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "runtime_seconds": time.perf_counter() - run_started,
            "manifest_path": str(paths["manifest"]),
            "partial_results_path": (
                str(paths["results"]) if paths["results"].exists() else None
            ),
        }
        write_json_exclusive(paths["failure"], failure)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory outside this Git worktree (default: %(default)s).",
    )
    parser.add_argument(
        "--experiment-id",
        help="Unique pilot ID; defaults to a UTC timestamped pilot ID.",
    )
    parser.add_argument(
        "--replay-manifest",
        type=Path,
        help="Replay saved poison IDs/text/associations without regenerating them.",
    )
    args = parser.parse_args()
    summary = run_pilot(
        output_dir=args.output_dir,
        experiment_id=args.experiment_id,
        replay_manifest_path=args.replay_manifest,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
