#!/usr/bin/env python3
"""Validate and aggregate explicitly supplied Week 9 multi-seed runs.

Bootstrap intervals resample unique query IDs as clusters. All poison seeds
and both pipelines for a sampled query remain together in each replicate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.evaluation.metrics import exact_match
from src.pipelines.transfer import validate_transfer_experiment_metadata
from scripts.run_week9_matched_poison_comparison import (
    paired_differences as comparison_paired_differences,
    summarize_pipeline as comparison_summarize_pipeline,
)

EXPECTED_SEEDS = (42, 43, 44)
EXPECTED_QUERY_COUNT = 10
EXPECTED_CUTOFFS = (1, 3, 5, 10)
BOOTSTRAP_SEED = 20261022
BOOTSTRAP_REPLICATES = 10_000
CONDITIONS = ("clean", "poisoned")
PIPELINES = ("dense", "rcd")
COMPARISON_SCHEMA = "rag-poison-transfer.matched-poison-comparison/v1"


def _read_json(path: Path) -> dict:
    with path.expanduser().open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}.")
    return value


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.expanduser().open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                raise ValueError(f"Blank JSONL line at {path}:{line_number}.")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSONL record at {path}:{line_number}.")
            rows.append(row)
    return rows


def validate_run(
    *,
    comparison_manifest_path: Path,
    summary_path: Path,
    results_path: Path,
) -> dict:
    manifest_path = comparison_manifest_path.expanduser().resolve()
    summary_path = summary_path.expanduser().resolve()
    results_path = results_path.expanduser().resolve()
    manifest = _read_json(manifest_path)
    summary = _read_json(summary_path)
    rows = _read_jsonl(results_path)

    if manifest.get("schema") != COMPARISON_SCHEMA:
        raise ValueError(f"Unsupported comparison manifest schema: {manifest_path}")
    if manifest.get("is_final_run") is not False or summary.get("is_final_run") is not False:
        raise ValueError("Only explicitly exploratory, non-final runs can be aggregated.")
    if manifest.get("status") != "exploratory_pilot_not_final":
        raise ValueError("Comparison manifest status is not exploratory.")
    if summary.get("status") != "complete_exploratory_pilot_not_final":
        raise ValueError("Comparison summary is not marked complete.")
    if summary.get("experiment_id") != manifest.get("experiment_id"):
        raise ValueError("Summary and manifest experiment IDs differ.")
    if Path(summary.get("manifest_path", "")).resolve() != manifest_path:
        raise ValueError("Summary references a different comparison manifest.")
    if Path(summary.get("results_path", "")).resolve() != results_path:
        raise ValueError("Summary references a different JSONL result file.")

    dataset = manifest.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("Comparison manifest has no dataset metadata.")
    selected_ids = dataset.get("selected_query_ids")
    if (
        not isinstance(selected_ids, list)
        or len(selected_ids) != EXPECTED_QUERY_COUNT
        or len(selected_ids) != len(set(selected_ids))
    ):
        raise ValueError("Manifest must contain ten unique selected query IDs.")
    if summary.get("selected_query_ids") != selected_ids:
        raise ValueError("Summary query IDs differ from comparison manifest.")
    if summary.get("query_count") != EXPECTED_QUERY_COUNT:
        raise ValueError("Summary query count differs from the ten-query protocol.")
    if summary.get("source_poison_instance_fingerprint") != manifest.get(
        "poison_instance_fingerprint"
    ):
        raise ValueError("Summary and manifest poison fingerprints differ.")
    if not isinstance(manifest.get("poison_instance_fingerprint"), str):
        raise ValueError("Comparison manifest is missing poison fingerprint.")

    source_path = Path(manifest.get("source_manifest_path", "")).expanduser()
    if not source_path.is_file():
        raise ValueError(f"Source poison manifest is missing: {source_path}")
    source_bytes = source_path.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != manifest.get(
        "source_manifest_sha256"
    ):
        raise ValueError("Source poison manifest hash does not match comparison.")
    source_manifest = _read_json(source_path)
    if source_manifest.get("poison_instance_fingerprint") != manifest.get(
        "poison_instance_fingerprint"
    ):
        raise ValueError("Source and comparison poison fingerprints differ.")
    if source_manifest.get("dataset", {}).get("selected_query_ids") != selected_ids:
        raise ValueError("Source poison manifest query IDs differ.")
    if source_manifest.get("poison_seed") != source_manifest.get(
        "seed_protocol", {}
    ).get("poison_seed"):
        raise ValueError("Source poison seed field disagrees with seed protocol.")
    source_metadata = source_manifest.get("experiment_metadata")
    validate_transfer_experiment_metadata(
        source_metadata,
        expected_source_pipeline="rcd",
        expected_target_pipeline="rcd",
    )
    if (
        source_metadata.get("query_set_fingerprint")
        != dataset.get("query_set_fingerprint")
        or source_metadata.get("seed") != 42
        or source_metadata.get("poison_instance_fingerprint")
        != manifest.get("poison_instance_fingerprint")
        or source_metadata.get("poison_manifest_fingerprint")
        != manifest.get("poison_instance_fingerprint")
    ):
        raise ValueError("Source strict metadata disagrees with comparison provenance.")

    seed_protocol = manifest.get("seed_protocol")
    source_seed_protocol = source_manifest.get("seed_protocol")
    if not isinstance(seed_protocol, dict) or seed_protocol != source_seed_protocol:
        raise ValueError("Comparison and source seed protocols differ.")
    if source_metadata.get("seed_protocol") != seed_protocol:
        raise ValueError("Strict source metadata has a different seed protocol.")
    poison_seed = seed_protocol.get("poison_seed")
    if isinstance(poison_seed, bool) or not isinstance(poison_seed, int):
        raise ValueError("Manifest poison seed is invalid.")
    if seed_protocol.get("query_selection_seed") != 42:
        raise ValueError("Query-selection seed differs from frozen seed 42.")
    if seed_protocol.get("retrieval_and_generation_seed") != 42:
        raise ValueError("Runtime seed differs from frozen seed 42.")
    if source_manifest.get("seed") != 42:
        raise ValueError("Source manifest runtime seed differs from frozen seed 42.")
    if source_manifest.get("clean_corpus_fingerprint") != dataset.get(
        "clean_corpus_fingerprint"
    ):
        raise ValueError("Source and comparison clean corpus fingerprints differ.")
    if source_manifest.get("generator") != manifest.get("generator"):
        raise ValueError("Source and comparison generator settings differ.")
    if source_manifest.get("attack") != manifest.get("attack"):
        raise ValueError("Source and comparison attack settings differ.")

    configs = manifest.get("configs")
    if not isinstance(configs, dict) or set(configs) != set(PIPELINES):
        raise ValueError("Manifest is missing Dense/RCD config hashes.")
    for pipeline in PIPELINES:
        config_entry = configs[pipeline]
        if (
            not isinstance(config_entry, dict)
            or not isinstance(config_entry.get("sha256"), str)
            or len(config_entry["sha256"]) != 64
            or config_entry.get("retriever_configuration", {}).get("retriever")
            != pipeline
        ):
            raise ValueError(f"Manifest has invalid {pipeline} configuration provenance.")
    rcd_configuration = configs["rcd"].get("rcd_configuration")
    if rcd_configuration != {
        "candidate_k": 10,
        "rewrite_count": 3,
        "consistency_weight": 0.45,
        "redundancy_weight": 0.0,
        "conflict_weight": 0.1,
        "base_rank_weight": 0.45,
    }:
        raise ValueError("RCD configuration differs from frozen settings.")
    evaluation = manifest.get("evaluation")
    if evaluation != {"top_k": 3, "retrieval_metric_k": 10}:
        raise ValueError("Manifest evaluation cutoffs are incompatible.")
    if manifest.get("seed") != 42:
        raise ValueError("Comparison runtime seed differs from frozen config seed.")

    expected_count = len(PIPELINES) * len(selected_ids) * len(CONDITIONS)
    if len(rows) != expected_count:
        raise ValueError(
            f"Expected {expected_count} JSONL records, found {len(rows)}."
        )
    by_key: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        pipeline = row.get("pipeline")
        condition = row.get("condition")
        query_id = row.get("query_id")
        if pipeline not in PIPELINES or condition not in CONDITIONS:
            raise ValueError("JSONL has an unknown pipeline or condition label.")
        if query_id not in selected_ids:
            raise ValueError("JSONL has a query ID outside the manifest set.")
        key = (pipeline, query_id, condition)
        if key in by_key:
            raise ValueError(f"Duplicate JSONL condition record: {key}.")
        if "untargeted_degradation" in row:
            raise ValueError("Ambiguous untargeted_degradation JSONL key is forbidden.")
        if "query_untargeted_degradation" not in row:
            raise ValueError("JSONL is missing query_untargeted_degradation.")
        for field in (
            "gold_answer",
            "clean_answer",
            "poisoned_answer",
            "answer",
            "answer_correct",
            "retrieved_doc_ids",
            "poison_doc_ids",
            "retrieved_evidence",
            "generation_evidence_doc_ids",
            "generation",
        ):
            if field not in row:
                raise ValueError(f"JSONL record is missing {field!r}.")
        expected_accuracy = bool(exact_match(row["answer"], row["gold_answer"]))
        if row["answer_correct"] is not expected_accuracy:
            raise ValueError("JSONL answer_correct does not match exact match.")
        by_key[key] = row

    for pipeline in PIPELINES:
        for query_id in selected_ids:
            clean = by_key.get((pipeline, query_id, "clean"))
            poisoned = by_key.get((pipeline, query_id, "poisoned"))
            if clean is None or poisoned is None:
                raise ValueError(
                    f"Missing paired record for pipeline={pipeline}, query={query_id}."
                )
            for field in (
                "gold_answer",
                "clean_answer",
                "poisoned_answer",
                "poison_target_answer",
                "poison_doc_ids",
            ):
                if clean[field] != poisoned[field]:
                    raise ValueError(f"Paired JSONL records differ in {field}.")
            if clean["answer"] != clean["clean_answer"]:
                raise ValueError("Clean condition answer differs from paired clean answer.")
            if poisoned["answer"] != poisoned["poisoned_answer"]:
                raise ValueError("Poisoned condition answer differs from paired answer.")
            if clean["query_untargeted_degradation"] != poisoned[
                "query_untargeted_degradation"
            ]:
                raise ValueError("Paired query-level degradation values differ.")
            expected_degradation = bool(
                clean["answer_correct"] and not poisoned["answer_correct"]
            )
            if clean["query_untargeted_degradation"] is not expected_degradation:
                raise ValueError("Paired query-level degradation formula is incorrect.")
            if not isinstance(poisoned.get("poison_target_answer"), str):
                raise ValueError("Poisoned JSONL record is missing poison target answer.")
            if poisoned.get("targeted_asr") is not bool(
                exact_match(
                    poisoned["answer"], poisoned["poison_target_answer"]
                )
            ):
                raise ValueError("Poisoned targeted-ASR label is inconsistent.")
            for cutoff in EXPECTED_CUTOFFS:
                key_name = str(cutoff)
                prr = poisoned.get("prr_at_k", {}).get(key_name)
                expected_prr = float(
                    bool(
                        set(poisoned["poison_doc_ids"])
                        & set(poisoned["retrieved_doc_ids"][:cutoff])
                    )
                )
                if not isinstance(prr, (int, float)) or float(prr) != expected_prr:
                    raise ValueError(f"Poison PRR@{cutoff} is inconsistent.")
            poison_in_generation = bool(
                set(poisoned["poison_doc_ids"])
                & set(poisoned["generation_evidence_doc_ids"])
            )
            if poisoned.get("poison_retrieved") is not poison_in_generation:
                raise ValueError("poison_retrieved differs from generation evidence.")

    paired_rows = {
        pipeline: [
            {
                "query_id": query_id,
                "clean_condition": {
                    "answer_correct": by_key[(pipeline, query_id, "clean")][
                        "answer_correct"
                    ]
                },
                "poisoned_condition": {
                    "answer_correct": by_key[(pipeline, query_id, "poisoned")][
                        "answer_correct"
                    ],
                    "targeted_asr": by_key[(pipeline, query_id, "poisoned")][
                        "targeted_asr"
                    ],
                    "poison_retrieved": by_key[
                        (pipeline, query_id, "poisoned")
                    ]["poison_retrieved"],
                    "prr_at_k": by_key[(pipeline, query_id, "poisoned")][
                        "prr_at_k"
                    ],
                },
                "query_untargeted_degradation": by_key[
                    (pipeline, query_id, "clean")
                ]["query_untargeted_degradation"],
            }
            for query_id in selected_ids
        ]
        for pipeline in PIPELINES
    }
    expected_pipeline_summaries = {
        pipeline: comparison_summarize_pipeline(pipeline_rows)
        for pipeline, pipeline_rows in paired_rows.items()
    }
    if summary.get("pipelines") != expected_pipeline_summaries:
        raise ValueError("Summary pipeline metrics do not match JSONL records.")
    if summary.get("paired_dense_minus_rcd") != comparison_paired_differences(
        paired_rows["dense"], paired_rows["rcd"]
    ):
        raise ValueError("Summary paired metrics do not match JSONL records.")

    return {
        "manifest": manifest,
        "summary": summary,
        "rows": by_key,
        "selected_ids": selected_ids,
        "poison_seed": poison_seed,
        "comparison_manifest_path": manifest_path,
        "summary_path": summary_path,
        "results_path": results_path,
    }


def _rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _pipeline_metrics(rows: dict[tuple[str, str, str], dict], pipeline: str, ids: list[str]) -> dict:
    clean = [rows[(pipeline, query_id, "clean")] for query_id in ids]
    poisoned = [rows[(pipeline, query_id, "poisoned")] for query_id in ids]
    conditional = [
        row for row in poisoned if row["poison_retrieved"]
    ]
    return {
        "clean_answer_accuracy": _rate(
            sum(row["answer_correct"] for row in clean), len(clean)
        ),
        "poisoned_answer_accuracy": _rate(
            sum(row["answer_correct"] for row in poisoned), len(poisoned)
        ),
        "targeted_asr": _rate(
            sum(bool(row["targeted_asr"]) for row in poisoned), len(poisoned)
        ),
        "conditional_asr": _rate(
            sum(bool(row["targeted_asr"]) for row in conditional),
            len(conditional),
        ),
        "poison_retrieval_rate": {
            f"prr@{cutoff}": _rate(
                sum(
                    float(row["prr_at_k"][str(cutoff)]) == 1.0
                    for row in poisoned
                ),
                len(poisoned),
            )
            for cutoff in EXPECTED_CUTOFFS
        },
        "query_untargeted_degradation": _rate(
            sum(
                rows[(pipeline, query_id, "clean")][
                    "query_untargeted_degradation"
                ]
                for query_id in ids
            ),
            len(ids),
        ),
    }


def _paired_query_values(
    rows: dict[tuple[int, str, str, str], dict],
    seeds: tuple[int, ...],
    query_ids: list[str],
) -> dict[str, dict[str, list[int]]]:
    values = {
        metric: {query_id: [] for query_id in query_ids}
        for metric in (
            "clean_answer_accuracy",
            "poisoned_answer_accuracy",
            "targeted_asr",
            "query_untargeted_degradation",
            *(f"prr@{k}" for k in EXPECTED_CUTOFFS),
        )
    }
    for seed in seeds:
        for query_id in query_ids:
            dense_clean = rows[(seed, "dense", query_id, "clean")]
            rcd_clean = rows[(seed, "rcd", query_id, "clean")]
            dense_poison = rows[(seed, "dense", query_id, "poisoned")]
            rcd_poison = rows[(seed, "rcd", query_id, "poisoned")]
            values["clean_answer_accuracy"][query_id].append(
                int(dense_clean["answer_correct"])
                - int(rcd_clean["answer_correct"])
            )
            values["poisoned_answer_accuracy"][query_id].append(
                int(dense_poison["answer_correct"])
                - int(rcd_poison["answer_correct"])
            )
            values["targeted_asr"][query_id].append(
                int(bool(dense_poison["targeted_asr"]))
                - int(bool(rcd_poison["targeted_asr"]))
            )
            values["query_untargeted_degradation"][query_id].append(
                int(dense_poison["query_untargeted_degradation"])
                - int(rcd_poison["query_untargeted_degradation"])
            )
            for cutoff in EXPECTED_CUTOFFS:
                values[f"prr@{cutoff}"][query_id].append(
                    int(float(dense_poison["prr_at_k"][str(cutoff)]) == 1.0)
                    - int(float(rcd_poison["prr_at_k"][str(cutoff)]) == 1.0)
                )
    return values


def _conditional_difference_for_clusters(
    rows: dict[tuple[int, str, str, str], dict],
    seeds: tuple[int, ...],
    sampled_query_ids: list[str],
) -> float | None:
    rates = {}
    for pipeline in PIPELINES:
        selected = [
            rows[(seed, pipeline, query_id, "poisoned")]
            for query_id in sampled_query_ids
            for seed in seeds
        ]
        denominator = sum(bool(row["poison_retrieved"]) for row in selected)
        numerator = sum(
            bool(row["targeted_asr"]) and bool(row["poison_retrieved"])
            for row in selected
        )
        if denominator == 0:
            return None
        rates[pipeline] = numerator / denominator
    return rates["dense"] - rates["rcd"]


def bootstrap_paired_intervals(
    *,
    rows: dict[tuple[int, str, str, str], dict],
    seeds: tuple[int, ...],
    query_ids: list[str],
    bootstrap_seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict:
    if replicates < 1 or not query_ids:
        raise ValueError("Bootstrap requires positive replicates and query IDs.")
    rng = random.Random(bootstrap_seed)
    query_values = _paired_query_values(rows, seeds, query_ids)
    metrics = {}
    for metric, per_query in query_values.items():
        cluster_means = {
            query_id: sum(per_query[query_id]) / len(seeds)
            for query_id in query_ids
        }
        samples = []
        for _ in range(replicates):
            chosen = [rng.choice(query_ids) for _ in query_ids]
            samples.append(sum(cluster_means[qid] for qid in chosen) / len(chosen))
        metrics[metric] = {
            "confidence_level": 0.95,
            "lower": _percentile(samples, 0.025),
            "upper": _percentile(samples, 0.975),
            "replicates": replicates,
            "resampling_unit": "query_id cluster across all seeds and both pipelines",
        }

    conditional_samples = []
    undefined = 0
    for _ in range(replicates):
        chosen = [rng.choice(query_ids) for _ in query_ids]
        difference = _conditional_difference_for_clusters(rows, seeds, chosen)
        if difference is None:
            undefined += 1
        else:
            conditional_samples.append(difference)
    metrics["conditional_asr"] = {
        "confidence_level": 0.95,
        "lower": (
            _percentile(conditional_samples, 0.025) if conditional_samples else None
        ),
        "upper": (
            _percentile(conditional_samples, 0.975) if conditional_samples else None
        ),
        "replicates": replicates,
        "defined_replicates": len(conditional_samples),
        "undefined_replicates": undefined,
        "resampling_unit": "query_id cluster across all seeds and both pipelines",
    }
    return {
        "bootstrap_seed": bootstrap_seed,
        "replicates": replicates,
        "method": (
            "Percentile 95% interval. Sample unique query IDs with replacement; "
            "retain all poison seeds and both pipeline outcomes within each "
            "sampled query cluster. Conditional-ASR replicates with zero "
            "retrieval denominator on either pipeline are undefined."
        ),
        "paired_dense_minus_rcd": metrics,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def aggregate_runs(
    inputs: list[tuple[Path, Path, Path]],
    *,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict:
    if len(inputs) != len(EXPECTED_SEEDS):
        raise ValueError(f"Exactly {len(EXPECTED_SEEDS)} runs are required.")
    runs = [
        validate_run(
            comparison_manifest_path=manifest,
            summary_path=summary,
            results_path=results,
        )
        for manifest, summary, results in inputs
    ]
    runs.sort(key=lambda run: run["poison_seed"])
    seeds = tuple(run["poison_seed"] for run in runs)
    if seeds != EXPECTED_SEEDS:
        raise ValueError(f"Expected poison seeds {EXPECTED_SEEDS}, found {seeds}.")
    if len(set(run["comparison_manifest_path"] for run in runs)) != len(runs):
        raise ValueError("Comparison manifests must be unique per seed.")
    if len(set(run["summary_path"] for run in runs)) != len(runs):
        raise ValueError("Comparison summaries must be unique per seed.")

    reference = runs[0]
    reference_manifest = reference["manifest"]
    selected_ids = reference["selected_ids"]
    reference_dataset = reference_manifest["dataset"]
    reference_configs = reference_manifest["configs"]
    reference_generator = reference_manifest.get("generator")
    reference_attack = reference_manifest.get("attack")
    reference_evaluation = reference_manifest.get("evaluation")
    git_commits = set()
    git_dirty_states = set()
    query_sets_identical = True
    poison_fingerprints = []
    query_set_fingerprints = []
    for run in runs:
        manifest = run["manifest"]
        dataset = manifest["dataset"]
        query_sets_identical &= (
            run["selected_ids"] == selected_ids
            and dataset.get("query_set_fingerprint")
            == reference_dataset.get("query_set_fingerprint")
            and dataset.get("revision") == reference_dataset.get("revision")
            and dataset.get("heldout_manifest_fingerprint")
            == reference_dataset.get("heldout_manifest_fingerprint")
        )
        if not query_sets_identical:
            raise ValueError("Multi-seed runs have mismatched query sets or dataset.")
        if (
            manifest.get("configs") != reference_configs
            or manifest.get("generator") != reference_generator
            or manifest.get("attack") != reference_attack
            or manifest.get("evaluation") != reference_evaluation
        ):
            raise ValueError("Multi-seed runs have incompatible frozen configurations.")
        git = manifest.get("git", {})
        git_commits.add(git.get("commit_sha"))
        git_dirty_states.add(git.get("worktree_dirty"))
        poison_fingerprints.append(manifest["poison_instance_fingerprint"])
        query_set_fingerprints.append(dataset["query_set_fingerprint"])
    if len(git_commits) != 1 or len(git_dirty_states) != 1:
        raise ValueError("Git provenance differs across poison-seed runs.")

    all_rows = {}
    per_seed = []
    for run in runs:
        seed = run["poison_seed"]
        rows = run["rows"]
        all_rows.update(
            {(seed, pipeline, qid, condition): rows[(pipeline, qid, condition)]
             for pipeline in PIPELINES
             for qid in selected_ids
             for condition in CONDITIONS}
        )
        pipeline_summaries = {
            pipeline: _pipeline_metrics(rows, pipeline, selected_ids)
            for pipeline in PIPELINES
        }
        paired = _paired_metric_summary(rows, selected_ids)
        per_seed.append(
            {
                "poison_seed": seed,
                "poison_instance_fingerprint": run["manifest"][
                    "poison_instance_fingerprint"
                ],
                "query_set_fingerprint": run["manifest"]["dataset"][
                    "query_set_fingerprint"
                ],
                "pipelines": pipeline_summaries,
                "paired_dense_minus_rcd": paired,
            }
        )

    pooled = _pooled_metrics(all_rows, seeds, selected_ids)
    bootstrap = bootstrap_paired_intervals(
        rows=all_rows,
        seeds=seeds,
        query_ids=selected_ids,
        bootstrap_seed=bootstrap_seed,
        replicates=bootstrap_replicates,
    )
    return {
        "schema": "rag-poison-transfer.week9-multiseed-aggregate/v1",
        "status": "exploratory_not_final_not_statistically_conclusive",
        "is_final_run": False,
        "poison_seeds": list(seeds),
        "query_selection_seed": 42,
        "retrieval_and_generation_seed": 42,
        "query_count_per_seed": len(selected_ids),
        "query_seed_observation_count": len(selected_ids) * len(seeds),
        "repeated_queries_are_independent": False,
        "query_ids_identical_across_seeds": query_sets_identical,
        "poison_instances_identical_across_seeds": len(set(poison_fingerprints)) == 1,
        "poison_instance_fingerprints": poison_fingerprints,
        "query_set_fingerprints": query_set_fingerprints,
        "git_commit_shas": sorted(git_commits),
        "git_dirty_states": sorted(git_dirty_states),
        "per_seed": per_seed,
        "pooled_query_seed_observations": pooled,
        "pooled_paired_dense_minus_rcd": _pooled_paired(all_rows, seeds, selected_ids),
        "paired_bootstrap": bootstrap,
        "limitations": (
            "Exploratory ten-query pilot with repeated query IDs across poison "
            "seeds; intervals resample query IDs as clusters and do not establish "
            "statistical significance or causal effectiveness."
        ),
    }


def _paired_metric_summary(rows: dict[tuple[str, str, str], dict], ids: list[str]) -> dict:
    metrics = {}
    for metric, getter in (
        ("clean_answer_accuracy", lambda d, r: (d["answer_correct"], r["answer_correct"], "clean")),
        ("poisoned_answer_accuracy", lambda d, r: (d["answer_correct"], r["answer_correct"], "poisoned")),
        ("targeted_asr", lambda d, r: (bool(d["targeted_asr"]), bool(r["targeted_asr"]), "poisoned")),
        (
            "query_untargeted_degradation",
            lambda d, r: (
                bool(d["query_untargeted_degradation"]),
                bool(r["query_untargeted_degradation"]),
                "clean",
            ),
        ),
    ):
        deltas = []
        for query_id in ids:
            condition = "clean" if metric == "clean_answer_accuracy" else "poisoned"
            dense = rows[("dense", query_id, condition)]
            rcd = rows[("rcd", query_id, condition)]
            dense_value, rcd_value, _ = getter(dense, rcd)
            deltas.append(int(dense_value) - int(rcd_value))
        metrics[metric] = _rate(sum(deltas), len(deltas))
    for cutoff in EXPECTED_CUTOFFS:
        deltas = [
            int(float(rows[("dense", qid, "poisoned")]["prr_at_k"][str(cutoff)]) == 1)
            - int(float(rows[("rcd", qid, "poisoned")]["prr_at_k"][str(cutoff)]) == 1)
            for qid in ids
        ]
        metrics[f"prr@{cutoff}"] = _rate(sum(deltas), len(deltas))
    dense_conditional = _pipeline_metrics(rows, "dense", ids)["conditional_asr"]
    rcd_conditional = _pipeline_metrics(rows, "rcd", ids)["conditional_asr"]
    metrics["conditional_asr"] = {
        "dense": dense_conditional,
        "rcd": rcd_conditional,
        "dense_minus_rcd_rate": (
            dense_conditional["rate"] - rcd_conditional["rate"]
            if dense_conditional["rate"] is not None
            and rcd_conditional["rate"] is not None
            else None
        ),
    }
    return metrics


def _pooled_metrics(
    rows: dict[tuple[int, str, str, str], dict],
    seeds: tuple[int, ...],
    ids: list[str],
) -> dict:
    result = {}
    for pipeline in PIPELINES:
        clean = [
            rows[(seed, pipeline, qid, "clean")]
            for seed in seeds
            for qid in ids
        ]
        poisoned = [
            rows[(seed, pipeline, qid, "poisoned")]
            for seed in seeds
            for qid in ids
        ]
        retrieved = [row for row in poisoned if row["poison_retrieved"]]
        degradation = [
            rows[(seed, pipeline, qid, "clean")]["query_untargeted_degradation"]
            for seed in seeds
            for qid in ids
        ]
        result[pipeline] = {
            "denominator_unit": "query_seed_observations; repeated queries are clustered",
            "clean_answer_accuracy": _rate(
                sum(row["answer_correct"] for row in clean), len(clean)
            ),
            "poisoned_answer_accuracy": _rate(
                sum(row["answer_correct"] for row in poisoned), len(poisoned)
            ),
            "targeted_asr": _rate(
                sum(bool(row["targeted_asr"]) for row in poisoned), len(poisoned)
            ),
            "conditional_asr": _rate(
                sum(bool(row["targeted_asr"]) for row in retrieved),
                len(retrieved),
            ),
            "poison_retrieval_rate": {
                f"prr@{cutoff}": _rate(
                    sum(
                        float(row["prr_at_k"][str(cutoff)]) == 1.0
                        for row in poisoned
                    ),
                    len(poisoned),
                )
                for cutoff in EXPECTED_CUTOFFS
            },
            "query_untargeted_degradation": _rate(
                sum(degradation), len(degradation)
            ),
        }
    return result


def _pooled_paired(
    rows: dict[tuple[int, str, str, str], dict],
    seeds: tuple[int, ...],
    ids: list[str],
) -> dict:
    paired = _paired_query_values(rows, seeds, ids)
    rates = {}
    denominator = len(seeds) * len(ids)
    for metric, query_values in paired.items():
        differences = [
            difference
            for per_seed in query_values.values()
            for difference in per_seed
        ]
        rates[metric] = _rate(sum(differences), len(differences))
    conditional = {
        pipeline: _pooled_metrics(rows, seeds, ids)[pipeline]["conditional_asr"]
        for pipeline in PIPELINES
    }
    rates["conditional_asr"] = {
        "dense": conditional["dense"],
        "rcd": conditional["rcd"],
        "dense_minus_rcd_rate": (
            conditional["dense"]["rate"] - conditional["rcd"]["rate"]
            if conditional["dense"]["rate"] is not None
            and conditional["rcd"]["rate"] is not None
            else None
        ),
    }
    rates["denominator_unit"] = (
        f"{denominator} paired query-seed observations; repeated query IDs "
        "are not independent."
    )
    return rates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        nargs=3,
        action="append",
        required=True,
        metavar=("COMPARISON_MANIFEST", "SUMMARY_JSON", "RESULTS_JSONL"),
        help="Explicit completed run inputs; repeat exactly three times.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = aggregate_runs(
        [(Path(manifest), Path(summary), Path(results)) for manifest, summary, results in args.run]
    )
    output_path = args.output.expanduser().resolve()
    if Path(__file__).resolve().parents[1] in output_path.parents:
        raise ValueError("Aggregate outputs must be outside the repository.")
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(summary, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
