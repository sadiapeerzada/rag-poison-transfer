#!/usr/bin/env python3
"""Run an exploratory, paired Dense-vs-RCD poisoning comparison.

The runner replays an immutable Week 9 poison manifest and evaluates the
same ten queries and poison instances against frozen Dense and RCD configs.
It is a pilot, not a final experiment or a claim of statistical significance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
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
from scripts.run_week9_poison_pilot import (
    MANIFEST_SCHEMA,
    replay_poisoned_data,
    validate_real_generator,
)
from src.attacks.review_provenance import review_metadata
from src.attacks.asr import _extract_answer, build_prompt
from src.evaluation.metrics import exact_match, poison_retrieval_rate_at_k
from src.experiments.protocol import (
    corpus_fingerprint,
    git_commit_sha,
    poison_instances_fingerprint,
    query_set_fingerprint,
)
from src.pipelines.generator import MLXGenerator
from src.pipelines.transfer import validate_transfer_experiment_metadata
from src.utils.config import load_config
from src.utils.env_info import _git_dirty
from src.utils.seeding import set_seed

# The ten-query pilot source manifest is an experiment artifact that lives
# outside the repository, so there is deliberately NO built-in default path:
# silently choosing a location could select a different experiment's
# manifest.  Pass --source-manifest or set this environment variable.
SOURCE_MANIFEST_ENV_VAR = "RAG_POISON_SOURCE_MANIFEST"
DEFAULT_DENSE_CONFIG = REPOSITORY_ROOT / "configs/exp_030_hotpotqa_dense_heldout_mlx.yaml"
DEFAULT_RCD_CONFIG = REPOSITORY_ROOT / "configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads/rag-rcd-week9-final-results/matched-poison"
EXPECTED_POISON_FINGERPRINT = (
    "87e0e80b58b70f5bde508ba7abf70e91145cb49befe523fd4688b3a6ffb3fd10"
)
EXPECTED_RCD_CONFIG = {
    "candidate_k": 10,
    "rewrite_count": 3,
    "consistency_weight": 0.45,
    "redundancy_weight": 0.0,
    "conflict_weight": 0.1,
    "base_rank_weight": 0.45,
}
PILOT_QUERY_COUNT = 10
RETRIEVAL_METRIC_K = 10
CUTOFFS = (1, 3, 5, 10)

METRIC_DEFINITIONS = {
    "clean_answer_accuracy": "Exact-match clean-evidence answers / selected queries.",
    "poisoned_answer_accuracy": "Exact-match poisoned-evidence answers / selected queries.",
    "poison_retrieval_rate_at_k": (
        "Attacked queries with an associated poison document in top-k / attacked queries."
    ),
    "targeted_asr": (
        "Poisoned-evidence answers matching the associated poison target / attacked queries."
    ),
    "asr_given_poison_retrieved": (
        "Targeted successes with poison in generator evidence / attacked queries "
        "with poison in generator evidence; null when denominator is zero."
    ),
    "query_untargeted_degradation": (
        "Paired query-level outcome: true exactly when the clean answer is "
        "exact-match correct and the poisoned answer is incorrect. Aggregate "
        "numerator is the number of true query pairs; denominator is all "
        "selected queries. The same value is repeated on that query's clean "
        "and poisoned JSONL condition records."
    ),
    "retrieval_elapsed_seconds": (
        "Wall-clock retrieval time at the generation evidence depth (top_k) "
        "for both clean and poisoned conditions. Excludes additional "
        "top-10 diagnostic retrieval."
    ),
    "diagnostic_retrieval_elapsed_seconds": (
        "Additional wall-clock time for the poisoned condition's top-10 "
        "retrieval used for retrieval diagnostics; zero for clean records."
    ),
}


def resolve_source_manifest_path(
    explicit: Path | str | None = None,
    *,
    environ: dict | None = None,
) -> Path:
    """Resolve the pilot source manifest without any machine-specific default.

    Precedence: an explicit path (the ``--source-manifest`` CLI option), then
    the ``RAG_POISON_SOURCE_MANIFEST`` environment variable.  The result must
    be an existing regular file.  Nothing is guessed, substituted or created.
    The environment is read at call time so overrides always take effect.
    """
    environment = os.environ if environ is None else environ
    if explicit is not None and str(explicit).strip():
        source, origin = Path(explicit), "--source-manifest"
    elif environment.get(SOURCE_MANIFEST_ENV_VAR, "").strip():
        source = Path(environment[SOURCE_MANIFEST_ENV_VAR])
        origin = f"environment variable {SOURCE_MANIFEST_ENV_VAR}"
    else:
        raise ValueError(
            "No source manifest was specified. Pass --source-manifest PATH "
            "(the ten-query pilot manifest written by "
            "scripts/run_week9_poison_pilot.py) or set the "
            f"{SOURCE_MANIFEST_ENV_VAR} environment variable."
        )
    resolved = source.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Source manifest from {origin} does not exist or is not a file: "
            f"{resolved}. Provide the path to the pilot manifest explicitly."
        )
    return resolved


def load_json(path: Path) -> dict:
    with path.expanduser().open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return value


def _rcd_config(config: dict) -> dict:
    return {
        "candidate_k": int(config["rcd_candidate_k"]),
        "rewrite_count": int(config["rcd_rewrite_count"]),
        "consistency_weight": float(config["rcd_consistency_weight"]),
        "redundancy_weight": float(config["rcd_redundancy_weight"]),
        "conflict_weight": float(config["rcd_conflict_weight"]),
        "base_rank_weight": float(config["rcd_base_rank_weight"]),
    }


def _frozen_retriever_config(config: dict) -> dict:
    result = {
        "retriever": config["retriever"],
        "embedder_model": config["embedder_model"],
        "output_k": int(config["top_k"]),
    }
    if config["retriever"] == "rcd":
        result.update(
            {
                "base_retriever": "dense",
                "sparse_retriever": "bm25",
                "dense_retriever": "dense",
                "rcd_candidate_k": int(config["rcd_candidate_k"]),
                "rcd_rewrite_count": int(config["rcd_rewrite_count"]),
                "rcd_consistency_weight": float(config["rcd_consistency_weight"]),
                "rcd_redundancy_weight": float(config["rcd_redundancy_weight"]),
                "rcd_conflict_weight": float(config["rcd_conflict_weight"]),
                "rcd_base_rank_weight": float(config["rcd_base_rank_weight"]),
            }
        )
    return result


# Settings that must be identical for Dense and RCD so that the only treatment
# difference is the defense.  Intentional differences (NOT listed here):
# ``retriever``, ``experiment_id`` and every ``rcd_*`` parameter.
SHARED_MATCHED_KEYS = (
    "dataset_loader",
    "dataset_split",
    "dataset_revision",
    "seed",
    "embedder_model",
    "top_k",
    "generator_backend",
    "generator_model",
    "max_tokens",
    "load_in_4bit",
)


def diagnostic_retrieval_required(top_k: int) -> bool:
    """True when poisoned PRR@k needs a deeper retrieval than generation uses.

    Single source of truth for both ``evaluate_pipeline`` (which executes the
    extra retrieval) and the preflight workload estimate (which counts it).
    """
    return RETRIEVAL_METRIC_K > top_k


def validated_top_k(config: dict, label: str) -> int:
    """Return ``config['top_k']`` as a strict positive integer or raise."""
    value = config.get("top_k")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(
            f"{label} config top_k must be a positive integer, got {value!r}."
        )
    return value


def validate_shared_pipeline_settings(dense_config: dict, rcd_config: dict) -> None:
    """Fail closed unless settings that must match between pipelines do.

    Keys absent from BOTH configs compare equal here, so loader-specific keys
    stay optional, but ``top_k`` is always required and range-checked because
    the workload estimate and the evaluation loop both depend on it.
    """
    validated_top_k(dense_config, "Dense")
    validated_top_k(rcd_config, "RCD")
    mismatches = [
        key
        for key in SHARED_MATCHED_KEYS
        if dense_config.get(key) != rcd_config.get(key)
    ]
    if mismatches:
        raise ValueError(f"Dense and RCD shared settings differ: {mismatches}.")


def validate_matched_configs(
    dense_config: dict,
    rcd_config: dict,
    source_manifest: dict,
    *,
    expected_poison_fingerprint: str | None = None,
) -> None:
    """Fail closed unless config and source-manifest protocol agree."""
    if dense_config.get("retriever") != "dense":
        raise ValueError("Dense config must select the dense retriever.")
    if rcd_config.get("retriever") != "rcd":
        raise ValueError("RCD config must select the RCD retriever.")
    if dense_config.get("final_run") is not True or rcd_config.get("final_run") is not True:
        raise ValueError("Matched pilot must use the frozen final Dense and RCD configs.")

    validate_shared_pipeline_settings(dense_config, rcd_config)
    if dense_config.get("dataset_loader") != "load_hotpotqa_distractor":
        raise ValueError("Matched pilot requires the HotpotQA distractor loader.")
    if dense_config.get("generator_backend") != "mlx":
        raise ValueError("Matched pilot requires the configured real MLX generator.")
    if _rcd_config(rcd_config) != EXPECTED_RCD_CONFIG:
        raise ValueError("RCD configuration differs from the frozen Week 9 settings.")

    dataset = source_manifest.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("Source manifest is missing dataset metadata.")
    if dataset.get("revision") != dense_config.get("dataset_revision"):
        raise ValueError("Source manifest dataset revision differs from configs.")
    if dataset.get("split") != dense_config.get("dataset_split"):
        raise ValueError("Source manifest dataset split differs from configs.")
    if dataset.get("loader") != dense_config.get("dataset_loader"):
        raise ValueError("Source manifest dataset loader differs from configs.")
    selected_ids = dataset.get("selected_query_ids")
    if (
        not isinstance(selected_ids, list)
        or len(selected_ids) != PILOT_QUERY_COUNT
        or len(selected_ids) != len(set(selected_ids))
    ):
        raise ValueError("Source manifest must contain exactly ten unique query IDs.")
    generator = source_manifest.get("generator")
    if not isinstance(generator, dict) or (
        generator.get("backend") != dense_config.get("generator_backend")
        or generator.get("model_identifier") != dense_config.get("generator_model")
        or generator.get("max_tokens") != int(dense_config.get("max_tokens", 64))
    ):
        raise ValueError("Source manifest generator settings differ from configs.")
    if source_manifest.get("evaluation") != {
        "top_k": int(dense_config["top_k"]),
        "retrieval_metric_k": RETRIEVAL_METRIC_K,
    }:
        raise ValueError("Source manifest evaluation cutoffs differ from configs.")
    if source_manifest.get("source_pipeline") != "rcd":
        raise ValueError("Source manifest was not created by the RCD pilot.")
    if source_manifest.get("rcd_configuration") != EXPECTED_RCD_CONFIG:
        raise ValueError("Source manifest does not contain the frozen RCD config.")
    if source_manifest.get("retriever_configuration") != _frozen_retriever_config(
        rcd_config
    ):
        raise ValueError("Source manifest RCD retriever configuration differs.")
    attack = source_manifest.get("attack")
    expected_attack = {
        "family": "lexical_influential_token",
        "configuration": {
            "repeat_factor": 4,
            "n_poison_per_attacked_query": 1,
            "poison_rate": 1.0,
        },
    }
    if not isinstance(attack, dict) or any(
        attack.get(key) != value for key, value in expected_attack.items()
    ):
        raise ValueError("Source manifest attack family or settings differ.")
    if source_manifest.get("seed") != dense_config.get("seed"):
        raise ValueError("Source manifest seed differs from configs.")
    metadata = source_manifest.get("experiment_metadata")
    source_poison_fingerprint = source_manifest.get("poison_instance_fingerprint")
    if expected_poison_fingerprint is None:
        expected_poison_fingerprint = EXPECTED_POISON_FINGERPRINT
    if not isinstance(source_poison_fingerprint, str) or (
        source_poison_fingerprint != expected_poison_fingerprint
    ):
        raise ValueError("Source manifest poison-instance fingerprint is unexpected.")
    if (
        not isinstance(metadata, dict)
        or metadata.get("dataset_revision") != dense_config.get("dataset_revision")
        or metadata.get("dataset_split") != dense_config.get("dataset_split")
        or metadata.get("seed") != dense_config.get("seed")
        or metadata.get("generator_model") != dense_config.get("generator_model")
        or metadata.get("poison_instance_fingerprint")
        != source_poison_fingerprint
        or metadata.get("poison_manifest_fingerprint")
        != source_poison_fingerprint
    ):
        raise ValueError("Source manifest experiment metadata is inconsistent.")
    validate_transfer_experiment_metadata(
        metadata,
        expected_source_pipeline="rcd",
        expected_target_pipeline="rcd",
    )
    if set(source_manifest.get("attacked_query_ids", [])) != set(selected_ids):
        raise ValueError("Source manifest must poison each of its ten selected queries.")


def reconstruct_matched_snapshot(
    clean_data: dict,
    source_manifest: dict,
    *,
    expected_poison_fingerprint: str | None = None,
) -> dict:
    """Use the pilot's strict replay validator and verify all source fingerprints."""
    if "target_review" in source_manifest or any("target_review" in q for q in source_manifest.get("query_poison_associations", [])):
        raise ValueError("Reviewed held-out cells require the matrix replay validator and external assignment pins")
    poisoned_data = replay_poisoned_data(clean_data, source_manifest)
    if corpus_fingerprint(clean_data["corpus"]) != source_manifest.get(
        "clean_corpus_fingerprint"
    ):
        raise ValueError("Reconstructed clean corpus differs from source manifest.")
    if query_set_fingerprint(clean_data["queries"]) != source_manifest["dataset"].get(
        "query_set_fingerprint"
    ):
        raise ValueError("Reconstructed query set differs from source manifest.")
    fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    if expected_poison_fingerprint is None:
        expected_poison_fingerprint = EXPECTED_POISON_FINGERPRINT
    if fingerprint != expected_poison_fingerprint:
        raise ValueError(
            "Reconstructed poison instances do not match the required fingerprint."
        )
    associations = source_manifest["query_poison_associations"]
    actual_associations = [
        {
            "query_id": query["query_id"],
            "attack_family": query.get("attack_family"),
            "poison_doc_ids": sorted(query.get("poison_doc_ids", [])),
            "poison_target_answer": query.get("poison_target_answer"),
        }
        for query in poisoned_data["queries"]
    ]
    if actual_associations != associations:
        raise ValueError("Reconstructed query-to-poison associations changed.")
    return poisoned_data


def build_matched_retrievers(
    dense_config: dict,
    rcd_config: dict,
    clean_data: dict,
    poisoned_data: dict,
) -> dict[str, tuple[Any, Any]]:
    """Build independent indexes from byte-identical clean/poison corpora."""
    data_fingerprints = (
        corpus_fingerprint(clean_data["corpus"]),
        poison_instances_fingerprint(clean_data, poisoned_data),
    )
    retrievers = {}
    for pipeline, config in (("dense", dense_config), ("rcd", rcd_config)):
        clean_retriever = build_retriever(config)
        poisoned_retriever = build_retriever(config)
        clean_retriever.build(copy.deepcopy(clean_data["corpus"]))
        poisoned_retriever.build(copy.deepcopy(poisoned_data["corpus"]))
        retrievers[pipeline] = (clean_retriever, poisoned_retriever)
    if data_fingerprints != (
        corpus_fingerprint(clean_data["corpus"]),
        poison_instances_fingerprint(clean_data, poisoned_data),
    ):
        raise RuntimeError("A retriever mutated the canonical matched corpus.")
    return retrievers


def _inner_retrieval_calls(retriever: Any) -> int | None:
    """Retrieval operations the pipeline executed for its most recent call.

    A plain Dense retriever performs exactly one.  RCD records its own count
    (primary + sparse + one per query rewrite) in ``last_diagnostics``; that
    count is query-dependent because duplicate rewrites are dropped.  Returns
    ``None`` when a retriever exposes diagnostics that do not contain a valid
    count, so missing data is visible rather than silently assumed.
    """
    if not hasattr(retriever, "last_diagnostics"):
        return 1
    diagnostics = retriever.last_diagnostics
    if isinstance(diagnostics, dict):
        count = diagnostics.get("retrieval_call_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 1:
            return count
    return None


def _evidence(retrieved: list[Any]) -> list[dict]:
    return [
        {"doc_id": item.doc_id, "text": item.text}
        for item in retrieved
    ]


def _generate(generator: Any, question: str, retrieved: list[Any], max_tokens: int):
    started = time.perf_counter()
    generated = generator.generate(
        build_prompt(question, [item.text for item in retrieved]),
        max_tokens=max_tokens,
    )
    return _extract_answer(generated.text), {
        "elapsed_seconds": time.perf_counter() - started,
        "generator_latency_seconds": generated.latency_seconds,
        "prompt_tokens": generated.prompt_tokens,
        "completion_tokens": generated.completion_tokens,
    }


def evaluate_pipeline(
    *,
    pipeline: str,
    clean_retriever: Any,
    poisoned_retriever: Any,
    clean_data: dict,
    poisoned_data: dict,
    generator: Any,
    top_k: int,
    max_tokens: int,
) -> list[dict]:
    """Evaluate clean and poisoned evidence independently for each query."""
    poisoned_by_id = {
        query["query_id"]: query for query in poisoned_data["queries"]
    }
    rows = []
    for clean_query in clean_data["queries"]:
        query_id = clean_query["query_id"]
        poisoned_query = poisoned_by_id[query_id]
        poison_ids = sorted(poisoned_query["poison_doc_ids"])
        retrieval_started = time.perf_counter()
        clean_retrieved = clean_retriever.retrieve(
            clean_query["question"], top_k=top_k
        )
        clean_retrieval_seconds = time.perf_counter() - retrieval_started
        clean_inner_calls = _inner_retrieval_calls(clean_retriever)
        clean_answer, clean_generation = _generate(
            generator, clean_query["question"], clean_retrieved, max_tokens
        )
        retrieval_started = time.perf_counter()
        poison_evidence = poisoned_retriever.retrieve(
            poisoned_query["question"], top_k=top_k
        )
        poisoned_retrieval_seconds = time.perf_counter() - retrieval_started
        poisoned_inner_calls = _inner_retrieval_calls(poisoned_retriever)

        diagnostic_retrieval_seconds = 0.0
        diagnostic_executed = diagnostic_retrieval_required(top_k)
        if diagnostic_executed:
            retrieval_started = time.perf_counter()
            poisoned_retrieved = poisoned_retriever.retrieve(
                poisoned_query["question"], top_k=RETRIEVAL_METRIC_K
            )
            diagnostic_retrieval_seconds = (
                time.perf_counter() - retrieval_started
            )
            diagnostic_inner_calls = _inner_retrieval_calls(poisoned_retriever)
        else:
            poisoned_retrieved = poison_evidence
            diagnostic_inner_calls = 0
        poisoned_answer, poisoned_generation = _generate(
            generator, poisoned_query["question"], poison_evidence, max_tokens
        )
        retrieved_ids = [item.doc_id for item in poisoned_retrieved]
        poison_ranks = [
            index + 1
            for index, doc_id in enumerate(retrieved_ids)
            if doc_id in set(poison_ids)
        ]
        target = poisoned_query["poison_target_answer"]
        clean_correct = bool(exact_match(clean_answer, clean_query["gold_answer"]))
        poisoned_correct = bool(
            exact_match(poisoned_answer, clean_query["gold_answer"])
        )
        targeted_success = bool(exact_match(poisoned_answer, target))
        poison_retrieved_for_generation = bool(
            set(poison_ids) & {item.doc_id for item in poison_evidence}
        )
        rows.append(
            {
                "query_id": query_id,
                "pipeline": pipeline,
                "gold_answer": clean_query["gold_answer"],
                "poison_target_answer": target,
                **review_metadata(poisoned_query),
                "poison_doc_ids": poison_ids,
                "clean_condition": {
                    "answer": clean_answer,
                    "answer_correct": clean_correct,
                    "targeted_asr": None,
                    "poison_retrieved": False,
                    "poison_rank": None,
                    "retrieved_doc_ids": [item.doc_id for item in clean_retrieved],
                    "retrieved_evidence": _evidence(clean_retrieved),
                    "generation_evidence_doc_ids": [
                        item.doc_id for item in clean_retrieved
                    ],
                    "prr_at_k": {str(k): 0.0 for k in CUTOFFS},
                    "retrieval_elapsed_seconds": clean_retrieval_seconds,
                    "diagnostic_retrieval_elapsed_seconds": 0.0,
                    "retrieval_call_accounting": {
                        "normal_retrieval_calls": 1,
                        "normal_inner_retrieval_operations": clean_inner_calls,
                        "diagnostic_retrieval_calls": 0,
                        "diagnostic_inner_retrieval_operations": 0,
                    },
                    "generation": clean_generation,
                },
                "poisoned_condition": {
                    "answer": poisoned_answer,
                    "answer_correct": poisoned_correct,
                    "targeted_asr": targeted_success,
                    "poison_retrieved": poison_retrieved_for_generation,
                    "poison_rank": min(poison_ranks) if poison_ranks else None,
                    "retrieved_doc_ids": retrieved_ids,
                    "retrieved_evidence": _evidence(poisoned_retrieved),
                    "generation_evidence_doc_ids": [
                        item.doc_id for item in poison_evidence
                    ],
                    "prr_at_k": {
                        str(k): poison_retrieval_rate_at_k(
                            retrieved_ids, poison_ids, k
                        )
                        for k in CUTOFFS
                    },
                    "retrieval_elapsed_seconds": poisoned_retrieval_seconds,
                    "diagnostic_retrieval_elapsed_seconds": (
                        diagnostic_retrieval_seconds
                    ),
                    "retrieval_call_accounting": {
                        "normal_retrieval_calls": 1,
                        "normal_inner_retrieval_operations": poisoned_inner_calls,
                        "diagnostic_retrieval_calls": int(diagnostic_executed),
                        "diagnostic_inner_retrieval_operations": diagnostic_inner_calls,
                    },
                    "generation": poisoned_generation,
                },
                "query_untargeted_degradation": (
                    clean_correct and not poisoned_correct
                ),
            }
        )
    return rows


def flatten_query_result_records(row: dict) -> list[dict]:
    """Flatten one paired query result while preserving query-level metrics."""
    records = []
    for condition in ("clean_condition", "poisoned_condition"):
        condition_data = row[condition]
        records.append(
            {
                "query_id": row["query_id"],
                "pipeline": row["pipeline"],
                "condition": (
                    "clean" if condition == "clean_condition" else "poisoned"
                ),
                "gold_answer": row["gold_answer"],
                "poison_target_answer": row["poison_target_answer"],
                **review_metadata(row),
                "poison_doc_ids": row["poison_doc_ids"],
                "clean_answer": row["clean_condition"]["answer"],
                "poisoned_answer": row["poisoned_condition"]["answer"],
                "query_untargeted_degradation": row[
                    "query_untargeted_degradation"
                ],
                **condition_data,
            }
        )
    return records


def _rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def summarize_pipeline(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Cannot summarize empty pipeline results.")
    denominator = len(rows)
    clean_correct = sum(row["clean_condition"]["answer_correct"] for row in rows)
    poisoned_correct = sum(
        row["poisoned_condition"]["answer_correct"] for row in rows
    )
    targeted = sum(row["poisoned_condition"]["targeted_asr"] for row in rows)
    retrieved = [
        row for row in rows if row["poisoned_condition"]["poison_retrieved"]
    ]
    degradation = sum(row["query_untargeted_degradation"] for row in rows)
    prr = {}
    for k in CUTOFFS:
        hits = sum(
            row["poisoned_condition"]["prr_at_k"][str(k)] == 1.0
            for row in rows
        )
        prr[f"prr@{k}"] = _rate(hits, denominator)
    conditional_success = sum(
        row["poisoned_condition"]["targeted_asr"] for row in retrieved
    )
    return {
        "query_count": denominator,
        "clean_condition": {
            "clean_answer_accuracy": _rate(clean_correct, denominator),
        },
        "poisoned_condition": {
            "poisoned_answer_accuracy": _rate(poisoned_correct, denominator),
            "poison_retrieval_rate": prr,
            "targeted_asr": _rate(targeted, denominator),
            "asr_given_poison_retrieved": _rate(
                conditional_success, len(retrieved)
            ),
        },
        "query_untargeted_degradation": _rate(degradation, denominator),
    }


def paired_differences(dense_rows: list[dict], rcd_rows: list[dict]) -> dict:
    dense_by_id = {row["query_id"]: row for row in dense_rows}
    rcd_by_id = {row["query_id"]: row for row in rcd_rows}
    if set(dense_by_id) != set(rcd_by_id):
        raise ValueError("Dense and RCD result query IDs do not match.")
    paired_rows = []
    metric_values: dict[str, list[int]] = {
        "clean_answer_correct": [],
        "poisoned_answer_correct": [],
        "targeted_asr": [],
        "query_untargeted_degradation": [],
    }
    for query_id in dense_by_id:
        dense = dense_by_id[query_id]
        rcd = rcd_by_id[query_id]
        if review_metadata(dense) != review_metadata(rcd):
            raise ValueError("Matched comparison reviewed-target provenance mismatch")
        if review_metadata(dense) and dense.get("poison_target_answer") != rcd.get("poison_target_answer"):
            raise ValueError("Matched comparison reviewed targets differ")
        values = {
            "clean_answer_correct": (
                int(dense["clean_condition"]["answer_correct"])
                - int(rcd["clean_condition"]["answer_correct"])
            ),
            "poisoned_answer_correct": (
                int(dense["poisoned_condition"]["answer_correct"])
                - int(rcd["poisoned_condition"]["answer_correct"])
            ),
            "targeted_asr": (
                int(dense["poisoned_condition"]["targeted_asr"])
                - int(rcd["poisoned_condition"]["targeted_asr"])
            ),
            "query_untargeted_degradation": (
                int(dense["query_untargeted_degradation"])
                - int(rcd["query_untargeted_degradation"])
            ),
        }
        for k in CUTOFFS:
            values[f"prr@{k}"] = (
                int(dense["poisoned_condition"]["prr_at_k"][str(k)] == 1.0)
                - int(rcd["poisoned_condition"]["prr_at_k"][str(k)] == 1.0)
            )
        for metric, difference in values.items():
            metric_values.setdefault(metric, []).append(difference)
        paired_rows.append({"query_id": query_id, "dense_minus_rcd": values})
    summaries = {
        metric: {
            "dense_minus_rcd_rate": sum(values) / len(values),
            "paired_query_count": len(values),
            "dense_wins": sum(value > 0 for value in values),
            "rcd_wins": sum(value < 0 for value in values),
            "ties": sum(value == 0 for value in values),
        }
        for metric, values in metric_values.items()
    }
    dense_conditional = summarize_pipeline(dense_rows)["poisoned_condition"][
        "asr_given_poison_retrieved"
    ]
    rcd_conditional = summarize_pipeline(rcd_rows)["poisoned_condition"][
        "asr_given_poison_retrieved"
    ]
    return {
        "interpretation": (
            f"Paired Dense-vs-RCD differences on the same {len(dense_by_id)} "
            "queries; not "
            "statistical significance or causal proof."
        ),
        "metrics": summaries,
        "conditional_asr_comparison": {
            "dense": dense_conditional,
            "rcd": rcd_conditional,
            "dense_minus_rcd_rate": (
                dense_conditional["rate"] - rcd_conditional["rate"]
                if dense_conditional["rate"] is not None
                and rcd_conditional["rate"] is not None
                else None
            ),
            "note": (
                "Conditional denominators are pipeline-specific: each includes "
                "only queries where that pipeline retrieved poison in generator "
                "evidence."
            ),
        },
        "per_query": paired_rows,
    }


def _output_paths(output_dir: Path, experiment_id: str) -> dict[str, Path]:
    if not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be a non-empty filename-safe value.")
    output_dir = output_dir.expanduser().resolve()
    try:
        output_dir.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Matched-comparison outputs must be outside the repository.")
    paths = {
        "manifest": output_dir / f"{experiment_id}.manifest.json",
        "results": output_dir / f"{experiment_id}.jsonl",
        "summary": output_dir / f"{experiment_id}.summary.json",
        "failure": output_dir / f"{experiment_id}.failure.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Matched-comparison outputs already exist; choose a new ID or "
            f"directory: {existing}"
        )
    return paths


def write_json_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
        output.write("\n")


def write_failure_record(
    *,
    path: Path,
    experiment_id: str,
    failed_stage: str,
    error: Exception,
    runtime_seconds: float,
    manifest_path: Path,
    results_path: Path,
) -> None:
    write_json_exclusive(
        path,
        {
            "experiment_id": experiment_id,
            "status": "failed",
            "is_final_run": False,
            "failed_stage": failed_stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "runtime_seconds": runtime_seconds,
            "manifest_path": str(manifest_path),
            "partial_results_path": str(results_path) if results_path.exists() else None,
        },
    )


def _config_with_validated_manifest(config: dict) -> tuple[dict, list[str], str]:
    result = dict(config)
    manifest_path = Path(result["dataset_query_ids_manifest"])
    if not manifest_path.is_absolute():
        manifest_path = REPOSITORY_ROOT / manifest_path
    result["dataset_query_ids_manifest"] = str(manifest_path.resolve())
    validated = _load_heldout_manifest(result)
    if validated is None:
        raise ValueError("A validated held-out query manifest is required.")
    return result, validated[0], validated[1]


def run_comparison(
    *,
    source_manifest_path: Path | None = None,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    experiment_id: str | None = None,
) -> dict:
    # Resolve (and require) the source manifest BEFORE creating any output
    # directory, so a missing manifest leaves no stray artifacts behind.
    source_manifest_path = resolve_source_manifest_path(source_manifest_path)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if experiment_id is None:
        experiment_id = datetime.now(timezone.utc).strftime(
            "week9_matched_poison_%Y%m%dT%H%M%SZ"
        )
    paths = _output_paths(output_dir, experiment_id)
    started = time.perf_counter()
    stage = "provenance"
    manifest_written = False
    try:
        commit = git_commit_sha(default="")
        dirty = _git_dirty()
        if not commit or commit == "unknown" or dirty is None:
            raise RuntimeError("Unable to capture Git commit and dirty state.")

        source_manifest = load_json(source_manifest_path)
        dense_config = load_config(str(dense_config_path.expanduser().resolve()))
        rcd_config = load_config(str(rcd_config_path.expanduser().resolve()))
        dense_config, heldout_ids, heldout_fingerprint = (
            _config_with_validated_manifest(dense_config)
        )
        rcd_config, rcd_heldout_ids, rcd_heldout_fingerprint = (
            _config_with_validated_manifest(rcd_config)
        )
        if heldout_ids != rcd_heldout_ids or heldout_fingerprint != rcd_heldout_fingerprint:
            raise ValueError("Dense and RCD held-out manifests differ.")
        source_poison_fingerprint = source_manifest.get(
            "poison_instance_fingerprint"
        )
        validate_matched_configs(
            dense_config,
            rcd_config,
            source_manifest,
            expected_poison_fingerprint=source_poison_fingerprint,
        )
        dataset_metadata = source_manifest["dataset"]
        selected_ids = dataset_metadata["selected_query_ids"]
        if not set(selected_ids).issubset(set(heldout_ids)):
            raise ValueError("Source manifest query IDs are outside held-out manifest.")
        if dataset_metadata.get("heldout_manifest_fingerprint") != heldout_fingerprint:
            raise ValueError("Source manifest held-out fingerprint differs.")

        stage = "dataset_loading"
        selected_config = dict(dense_config)
        selected_config.pop("dataset_query_ids_manifest", None)
        selected_config["dataset_query_ids"] = list(selected_ids)
        clean_data = load_dataset(selected_config)
        actual_ids = [query["query_id"] for query in clean_data["queries"]]
        if actual_ids != selected_ids:
            raise ValueError("Loader did not preserve the source manifest query order.")
        poisoned_data = reconstruct_matched_snapshot(
            clean_data,
            source_manifest,
            expected_poison_fingerprint=source_poison_fingerprint,
        )

        source_manifest_bytes = source_manifest_path.read_bytes()
        comparison_manifest = {
            "schema": "rag-poison-transfer.matched-poison-comparison/v1",
            "experiment_id": experiment_id,
            "status": "exploratory_pilot_not_final",
            "is_final_run": False,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_manifest_path": str(source_manifest_path),
            "source_manifest_sha256": hashlib.sha256(source_manifest_bytes).hexdigest(),
            "source_manifest_experiment_id": source_manifest["experiment_id"],
            "dataset": {
                "name": dataset_metadata["name"],
                "config": dataset_metadata["config"],
                "revision": dense_config["dataset_revision"],
                "split": dense_config["dataset_split"],
                "heldout_manifest_fingerprint": heldout_fingerprint,
                "selected_query_ids": selected_ids,
                "query_set_fingerprint": query_set_fingerprint(clean_data["queries"]),
                "clean_corpus_fingerprint": corpus_fingerprint(clean_data["corpus"]),
            },
            "attack": source_manifest["attack"],
            "seed": int(dense_config["seed"]),
            "seed_protocol": source_manifest.get(
                "seed_protocol",
                {
                    "query_selection_seed": int(dense_config["seed"]),
                    "poison_seed": int(source_manifest["seed"]),
                    "retrieval_and_generation_seed": int(dense_config["seed"]),
                },
            ),
            "poison_instance_fingerprint": poison_instances_fingerprint(
                clean_data, poisoned_data
            ),
            "generator": source_manifest["generator"],
            "evaluation": source_manifest["evaluation"],
            "configs": {
                "dense": {
                    "path": str(dense_config_path.expanduser().resolve()),
                    "sha256": hashlib.sha256(
                        dense_config_path.expanduser().resolve().read_bytes()
                    ).hexdigest(),
                    "retriever_configuration": _frozen_retriever_config(dense_config),
                },
                "rcd": {
                    "path": str(rcd_config_path.expanduser().resolve()),
                    "sha256": hashlib.sha256(
                        rcd_config_path.expanduser().resolve().read_bytes()
                    ).hexdigest(),
                    "retriever_configuration": _frozen_retriever_config(rcd_config),
                    "rcd_configuration": _rcd_config(rcd_config),
                },
            },
            "git": {
                "commit_sha": commit,
                "worktree_dirty": dirty,
                "dirty_check_scope": "tracked and untracked non-ignored files",
            },
            "metric_definitions": METRIC_DEFINITIONS,
            "analysis_scope": (
                "Paired exploratory ten-query pilot; no statistical-significance "
                "claim and not a final experiment."
            ),
        }
        write_json_exclusive(paths["manifest"], comparison_manifest)
        manifest_written = True

        stage = "generator_initialization"
        set_seed(int(dense_config["seed"]))
        generator = MLXGenerator(model_name=dense_config["generator_model"])
        validate_real_generator(generator)
        stage = "retriever_initialization"
        matched_retrievers = build_matched_retrievers(
            dense_config, rcd_config, clean_data, poisoned_data
        )
        if (
            comparison_manifest["dataset"]["clean_corpus_fingerprint"]
            != corpus_fingerprint(clean_data["corpus"])
            or comparison_manifest["poison_instance_fingerprint"]
            != poison_instances_fingerprint(clean_data, poisoned_data)
        ):
            raise RuntimeError("Matched corpus changed before evaluation.")

        stage = "query_evaluation"
        all_rows = {}
        with paths["results"].open("x", encoding="utf-8") as result_file:
            for pipeline, (clean_retriever, poisoned_retriever) in matched_retrievers.items():
                rows = evaluate_pipeline(
                    pipeline=pipeline,
                    clean_retriever=clean_retriever,
                    poisoned_retriever=poisoned_retriever,
                    clean_data=clean_data,
                    poisoned_data=poisoned_data,
                    generator=generator,
                    top_k=int(dense_config["top_k"]),
                    max_tokens=int(dense_config.get("max_tokens", 64)),
                )
                all_rows[pipeline] = rows
                for row in rows:
                    for output_row in flatten_query_result_records(row):
                        result_file.write(
                            json.dumps(output_row, ensure_ascii=False) + "\n"
                        )
                        result_file.flush()
        stage = "summary"
        summary = {
            "experiment_id": experiment_id,
            "status": "complete_exploratory_pilot_not_final",
            "is_final_run": False,
            "query_count": len(selected_ids),
            "selected_query_ids": selected_ids,
            "source_poison_instance_fingerprint": source_poison_fingerprint,
            "runtime_seconds": time.perf_counter() - started,
            "pipelines": {
                pipeline: summarize_pipeline(rows)
                for pipeline, rows in all_rows.items()
            },
            "paired_dense_minus_rcd": paired_differences(
                all_rows["dense"], all_rows["rcd"]
            ),
            "manifest_path": str(paths["manifest"]),
            "results_path": str(paths["results"]),
            "interpretation": (
                "Exploratory paired results for ten queries only; differences "
                "are not statistical significance or causal proof."
            ),
        }
        write_json_exclusive(paths["summary"], summary)
        return summary
    except Exception as error:
        if manifest_written:
            write_failure_record(
                path=paths["failure"],
                experiment_id=experiment_id,
                failed_stage=stage,
                error=error,
                runtime_seconds=time.perf_counter() - started,
                manifest_path=paths["manifest"],
                results_path=paths["results"],
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=None,
        help=(
            "Path to the ten-query pilot source manifest. Required unless the "
            f"{SOURCE_MANIFEST_ENV_VAR} environment variable is set."
        ),
    )
    parser.add_argument("--dense-config", type=Path, default=DEFAULT_DENSE_CONFIG)
    parser.add_argument("--rcd-config", type=Path, default=DEFAULT_RCD_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--experiment-id")
    args = parser.parse_args()
    print(
        json.dumps(
            run_comparison(
                source_manifest_path=args.source_manifest,
                dense_config_path=args.dense_config,
                rcd_config_path=args.rcd_config,
                output_dir=args.output_dir,
                experiment_id=args.experiment_id,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
