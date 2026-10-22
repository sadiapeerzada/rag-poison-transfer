#!/usr/bin/env python3
"""Run the frozen 300-query Week 9 held-out poisoning matrix.

This is intentionally separate from the ten-query exploratory pilot.  Each
cell creates one immutable poison snapshot and reuses it for both Dense and
RCD.  Output is append-only and must be outside the repository.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from run import build_generator, load_dataset
from scripts.run_week9_matched_poison_comparison import (
    _frozen_retriever_config,
    _rcd_config,
    build_matched_retrievers,
    evaluate_pipeline,
    flatten_query_result_records,
    paired_differences,
    summarize_pipeline,
)
from scripts.run_week9_multiseed_matched_evaluation import (
    FROZEN_RUNTIME_SEED,
    PREDECLARED_POISON_SEEDS,
    validate_frozen_inputs,
)
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.attacks.semantic_fluent import SemanticFluentFalseEvidenceAttack
from src.experiments.protocol import (
    corpus_fingerprint,
    git_commit_sha,
    poison_instances_fingerprint,
    query_set_fingerprint,
)
from src.utils.seeding import set_seed

CELL_SCHEMA = "rag-poison-transfer.week9-heldout-poison-cell/v1"
PLAN_SCHEMA = "rag-poison-transfer.week9-heldout-poison-matrix-plan/v1"
MATRIX_ATTACKS = ("lexical_influential_token", "semantic_fluent_false_evidence")
MATRIX_INTENSITIES = (1, 3)
MATRIX_QUERY_COUNT = 300
DEFAULT_HELDOUT_MANIFEST = REPOSITORY_ROOT / "configs/exp_027_hotpotqa_heldout_manifest.json"
DEFAULT_DENSE_CONFIG = REPOSITORY_ROOT / "configs/exp_030_hotpotqa_dense_heldout_mlx.yaml"
DEFAULT_RCD_CONFIG = REPOSITORY_ROOT / "configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads/rag-rcd-week9-final-results/heldout-poison-matrix"
RELEVANT_TRACKED_PATHS = (
    "run.py",
    "configs/exp_027_hotpotqa_heldout_manifest.json",
    "configs/exp_030_hotpotqa_dense_heldout_mlx.yaml",
    "configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml",
    "scripts/run_week9_heldout_poison_matrix.py",
    "scripts/run_week9_matched_poison_comparison.py",
    "scripts/run_week9_multiseed_matched_evaluation.py",
    "src/attacks/injection.py",
    "src/attacks/lexical.py",
    "src/attacks/semantic_fluent.py",
    "src/experiments/protocol.py",
    "src/pipelines/generator.py",
)


def _write_json_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
        output.write("\n")


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}.")
    return value


def _cell_id(attack_family: str, intensity: int, poison_seed: int) -> str:
    return f"{attack_family}.intensity-{intensity}.seed-{poison_seed}"


def _ensure_output_outside_repository(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError("Held-out matrix outputs must be outside the repository.")


def _require_clean_relevant_inputs(*, require_tracked_runner: bool) -> None:
    """Reject changed experiment inputs but ignore unrelated untracked artifacts."""
    try:
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=no",
                "--",
                *RELEVANT_TRACKED_PATHS,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if status.returncode:
            raise RuntimeError("Unable to inspect relevant tracked experiment inputs.")
        if status.stdout:
            raise RuntimeError(
                "Held-out execution requires clean relevant tracked inputs: "
                f"{status.stdout.strip()}"
            )
        if require_tracked_runner:
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "scripts/run_week9_heldout_poison_matrix.py"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if tracked.returncode:
                raise RuntimeError(
                    "Final held-out execution requires the matrix runner to be "
                    "tracked in Git; commit it before executing the final matrix."
                )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Unable to inspect relevant tracked experiment inputs.") from error


def matrix_cells() -> list[tuple[str, int, int]]:
    return [
        (attack, intensity, seed)
        for attack in MATRIX_ATTACKS
        for intensity in MATRIX_INTENSITIES
        for seed in PREDECLARED_POISON_SEEDS
    ]


def preflight(
    *,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
) -> dict:
    """Validate immutable inputs without loading a model or dataset."""
    _, _, heldout_ids, heldout_fingerprint, hashes = validate_frozen_inputs(
        heldout_path=heldout_path,
        dense_config_path=dense_config_path,
        rcd_config_path=rcd_config_path,
    )
    if len(heldout_ids) != MATRIX_QUERY_COUNT:
        raise ValueError(
            f"Expected frozen held-out manifest to contain {MATRIX_QUERY_COUNT} "
            f"queries, found {len(heldout_ids)}."
        )
    semantic_documents = (
        len(PREDECLARED_POISON_SEEDS)
        * len(heldout_ids)
        * sum(MATRIX_INTENSITIES)
    )
    evaluation_generations = len(matrix_cells()) * len(heldout_ids) * 4
    return {
        "schema": PLAN_SCHEMA,
        "cell_count": len(matrix_cells()),
        "query_count_per_cell": len(heldout_ids),
        "poison_generation_calls": {
            "lexical": 0,
            "semantic_fluent": semantic_documents,
        },
        "evaluation_generation_calls": evaluation_generations,
        "retrieval_calls": evaluation_generations,
        "runtime_requirements": {
            "machine": platform.machine(),
            "mlx_available": importlib.util.find_spec("mlx") is not None,
            "mlx_lm_available": importlib.util.find_spec("mlx_lm") is not None,
        },
        "heldout_manifest_fingerprint": heldout_fingerprint,
        "config_sha256": hashes,
        "seed_protocol": {
            "query_selection_seed": FROZEN_RUNTIME_SEED,
            "retrieval_and_generation_seed": FROZEN_RUNTIME_SEED,
            "poison_generation_seeds": list(PREDECLARED_POISON_SEEDS),
            "varied_randomness": "poison-generation seed only",
        },
    }


def _attack(attack_family: str, generator: Any | None) -> tuple[Any, dict]:
    if attack_family == "lexical_influential_token":
        return LexicalInfluentialTokenAttack(repeat_factor=4), {"repeat_factor": 4}
    if attack_family == "semantic_fluent_false_evidence":
        if generator is None:
            raise RuntimeError("Semantic-fluent poison generation requires a real generator.")
        return SemanticFluentFalseEvidenceAttack(generator, max_tokens=150), {
            "max_tokens": 150
        }
    raise ValueError(f"Unsupported attack family: {attack_family}")


def _associations(poisoned_data: dict) -> list[dict]:
    return [
        {
            "query_id": query["query_id"],
            "attack_family": query.get("attack_family"),
            "poison_doc_ids": sorted(query.get("poison_doc_ids", [])),
            "poison_target_answer": query.get("poison_target_answer"),
        }
        for query in poisoned_data["queries"]
    ]


def build_cell_manifest(
    *,
    cell_id: str,
    clean_data: dict,
    poisoned_data: dict,
    attack_family: str,
    intensity: int,
    poison_seed: int,
    heldout_fingerprint: str,
    config_hashes: dict[str, str],
    dense_config: dict,
    rcd_config: dict,
    git_sha: str,
    git_dirty: bool | None,
    execution_mode: str = "heldout_matrix",
) -> dict:
    """Serialize a validated poison snapshot before it is evaluated."""
    selected_ids = [query["query_id"] for query in clean_data["queries"]]
    if not selected_ids or len(set(selected_ids)) != len(selected_ids):
        raise ValueError("Cell manifest requires non-empty unique query IDs.")
    if execution_mode == "heldout_matrix" and len(selected_ids) != MATRIX_QUERY_COUNT:
        raise ValueError("Held-out cell manifest requires exactly 300 unique queries.")
    if execution_mode not in {"heldout_matrix", "smoke_test"}:
        raise ValueError(f"Unsupported execution mode: {execution_mode}")
    poison_fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    clean_ids = {document["doc_id"] for document in clean_data["corpus"]}
    return {
        "schema": CELL_SCHEMA,
        "status": (
            "generated_not_evaluated"
            if execution_mode == "heldout_matrix"
            else "smoke_test_generated_not_evaluated"
        ),
        "is_final_run": False,
        "execution_mode": execution_mode,
        "cell_id": cell_id,
        "attack": {
            "family": attack_family,
            "intensity": intensity,
            "poison_rate": 1.0,
        },
        "seed_protocol": {
            "query_selection_seed": FROZEN_RUNTIME_SEED,
            "retrieval_and_generation_seed": FROZEN_RUNTIME_SEED,
            "poison_seed": poison_seed,
            "varied_randomness": "poison-generation seed only",
        },
        "dataset": {
            "name": "hotpotqa/hotpot_qa",
            "config": "distractor",
            "revision": rcd_config["dataset_revision"],
            "split": rcd_config["dataset_split"],
            "heldout_manifest_fingerprint": heldout_fingerprint,
            "selected_query_ids": selected_ids,
            "query_count": len(selected_ids),
            "query_set_fingerprint": query_set_fingerprint(clean_data["queries"]),
            "clean_corpus_fingerprint": corpus_fingerprint(clean_data["corpus"]),
        },
        "poison_documents": [
            {"doc_id": document["doc_id"], "text": document["text"]}
            for document in poisoned_data["corpus"]
            if document["doc_id"] not in clean_ids
        ],
        "query_poison_associations": _associations(poisoned_data),
        "poison_instance_fingerprint": poison_fingerprint,
        "configs": {
            "sha256": config_hashes,
            "dense": _frozen_retriever_config(dense_config),
            "rcd": _frozen_retriever_config(rcd_config),
            "rcd_configuration": _rcd_config(rcd_config),
        },
        "generator": {
            "backend": rcd_config["generator_backend"],
            "model_identifier": rcd_config["generator_model"],
            "evaluation_max_tokens": int(rcd_config["max_tokens"]),
        },
        "git": {
            "commit_sha": git_sha,
            "relevant_tracked_inputs_dirty": git_dirty,
            "dirty_check_scope": "relevant tracked source and configuration files",
        },
    }


def replay_cell_manifest(clean_data: dict, manifest: dict) -> dict:
    """Fail closed while reconstructing a manifest's immutable poison snapshot."""
    if manifest.get("schema") != CELL_SCHEMA:
        raise ValueError("Unsupported held-out matrix cell manifest schema.")
    attack = manifest.get("attack", {})
    if (
        attack.get("family") not in MATRIX_ATTACKS
        or attack.get("intensity") not in MATRIX_INTENSITIES
        or attack.get("poison_rate") != 1.0
    ):
        raise ValueError("Cell manifest has invalid attack metadata.")
    selected_ids = manifest.get("dataset", {}).get("selected_query_ids")
    actual_ids = [query["query_id"] for query in clean_data["queries"]]
    execution_mode = manifest.get("execution_mode")
    if execution_mode not in {"heldout_matrix", "smoke_test"}:
        raise ValueError("Cell manifest has an invalid execution mode.")
    if selected_ids != actual_ids or not actual_ids:
        raise ValueError("Cell manifest query IDs do not match loaded data.")
    if manifest["dataset"].get("query_count") != len(actual_ids):
        raise ValueError("Cell manifest query count does not match loaded data.")
    if execution_mode == "heldout_matrix" and len(actual_ids) != MATRIX_QUERY_COUNT:
        raise ValueError("Held-out cell manifest must contain exactly 300 queries.")
    if manifest["dataset"].get("query_set_fingerprint") != query_set_fingerprint(
        clean_data["queries"]
    ):
        raise ValueError("Cell manifest query fingerprint does not match loaded data.")
    if manifest["dataset"].get("clean_corpus_fingerprint") != corpus_fingerprint(
        clean_data["corpus"]
    ):
        raise ValueError("Cell manifest clean corpus fingerprint does not match.")
    associations = manifest.get("query_poison_associations")
    documents = manifest.get("poison_documents")
    if not isinstance(associations, list) or not isinstance(documents, list):
        raise ValueError("Cell manifest lacks poison documents or associations.")
    association_by_id = {item.get("query_id"): item for item in associations}
    if len(association_by_id) != len(associations) or set(association_by_id) != set(actual_ids):
        raise ValueError("Cell manifest associations do not cover each query exactly once.")
    poisoned_data = {
        "corpus": [dict(document) for document in clean_data["corpus"]] + copy.deepcopy(documents),
        "queries": [],
    }
    for query in clean_data["queries"]:
        association = association_by_id[query["query_id"]]
        poisoned_data["queries"].append(
            {
                **query,
                "attack_family": association.get("attack_family"),
                "poison_doc_ids": list(association.get("poison_doc_ids", [])),
                "poison_target_answer": association.get("poison_target_answer"),
            }
        )
    fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    if fingerprint != manifest.get("poison_instance_fingerprint"):
        raise ValueError("Cell manifest poison-instance fingerprint does not match.")
    validation = validate_poisoned_dataset(
        clean_data, poisoned_data, expected_n_poison=attack["intensity"], expected_poison_rate=1.0
    )
    if not validation["valid"]:
        raise ValueError(f"Cell manifest failed poison validation: {validation['checks']}")
    if any(query["attack_family"] != attack["family"] for query in poisoned_data["queries"]):
        raise ValueError("Cell manifest association attack family differs from cell metadata.")
    return poisoned_data


def evaluate_cell(
    *,
    clean_data: dict,
    poisoned_data: dict,
    dense_config: dict,
    rcd_config: dict,
    generator: Any,
    manifest: dict,
    results_path: Path,
) -> dict:
    """Evaluate the two frozen pipelines against a single replayed snapshot."""
    all_rows: dict[str, list[dict]] = {}
    retrievers = build_matched_retrievers(dense_config, rcd_config, clean_data, poisoned_data)
    records_written = 0
    retrieval_seconds = 0.0
    generation_seconds = 0.0
    with results_path.open("x", encoding="utf-8") as output:
        for pipeline, (clean_retriever, poisoned_retriever) in retrievers.items():
            rows = evaluate_pipeline(
                pipeline=pipeline,
                clean_retriever=clean_retriever,
                poisoned_retriever=poisoned_retriever,
                clean_data=clean_data,
                poisoned_data=poisoned_data,
                generator=generator,
                top_k=int(dense_config["top_k"]),
                max_tokens=int(dense_config["max_tokens"]),
            )
            all_rows[pipeline] = rows
            for row in rows:
                for record in flatten_query_result_records(row):
                    retrieval_seconds += record["retrieval_elapsed_seconds"]
                    generation_seconds += record["generation"]["elapsed_seconds"]
                    output.write(
                        json.dumps(
                            {
                                **record,
                                "cell_id": manifest["cell_id"],
                                "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    output.flush()
                    records_written += 1
    return {
        "pipelines": {pipeline: summarize_pipeline(rows) for pipeline, rows in all_rows.items()},
        "paired_dense_minus_rcd": paired_differences(all_rows["dense"], all_rows["rcd"]),
        "execution_evidence": {
            "raw_record_count": records_written,
            "expected_raw_record_count": len(clean_data["queries"]) * 4,
            "retrieval_elapsed_seconds": retrieval_seconds,
            "generation_elapsed_seconds": generation_seconds,
        },
    }


def run_matrix(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    experiment_id: str,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
    resume: bool = False,
) -> dict:
    """Execute cells not already completed in a compatible matrix directory."""
    if not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be a non-empty filename-safe value.")
    preflight_data = preflight(
        heldout_path=heldout_path,
        dense_config_path=dense_config_path,
        rcd_config_path=rcd_config_path,
    )
    if not (
        preflight_data["runtime_requirements"]["mlx_available"]
        and preflight_data["runtime_requirements"]["mlx_lm_available"]
    ):
        raise RuntimeError("MLX and mlx-lm are required for the real held-out matrix.")
    _require_clean_relevant_inputs(require_tracked_runner=True)
    output_root = _ensure_output_outside_repository(output_dir) / experiment_id
    plan_path = output_root / "plan.json"
    if output_root.exists() and not resume:
        raise FileExistsError(f"Output directory already exists: {output_root}")
    if resume:
        plan = _read_json(plan_path)
        if plan.get("preflight") != preflight_data:
            raise ValueError("Existing matrix plan is incompatible with current frozen inputs.")
    else:
        output_root.mkdir(parents=True)
        plan = {
            "schema": PLAN_SCHEMA,
            "experiment_id": experiment_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "preflight": preflight_data,
            "status": "running",
        }
        _write_json_exclusive(plan_path, plan)

    dense_config, rcd_config, heldout_ids, heldout_fp, hashes = validate_frozen_inputs(
        heldout_path=heldout_path,
        dense_config_path=dense_config_path,
        rcd_config_path=rcd_config_path,
    )
    clean_data = load_dataset({**rcd_config, "dataset_query_ids_manifest": str(heldout_path)})
    if [query["query_id"] for query in clean_data["queries"]] != heldout_ids:
        raise ValueError("Dataset loader did not preserve frozen held-out query order.")
    set_seed(FROZEN_RUNTIME_SEED)
    generator = build_generator(rcd_config)
    completed, failed = [], []
    for attack_family, intensity, poison_seed in matrix_cells():
        cell_id = _cell_id(attack_family, intensity, poison_seed)
        cell_dir = output_root / cell_id
        manifest_path = cell_dir / "poison.manifest.json"
        results_path = cell_dir / "results.jsonl"
        summary_path = cell_dir / "summary.json"
        failure_path = cell_dir / "failure.json"
        if summary_path.exists():
            existing_summary = _read_json(summary_path)
            existing_manifest = _read_json(manifest_path)
            if (
                existing_summary.get("status")
                != "complete_heldout_cell_not_statistically_conclusive"
                or existing_summary.get("cell_id") != cell_id
                or existing_summary.get("poison_instance_fingerprint")
                != existing_manifest.get("poison_instance_fingerprint")
                or not results_path.is_file()
            ):
                raise ValueError(
                    f"Existing completed cell has incompatible provenance: {cell_id}"
                )
            completed.append(cell_id)
            continue
        if cell_dir.exists():
            failed.append(cell_id)
            continue
        cell_dir.mkdir()
        started = time.perf_counter()
        try:
            attack, attack_config = _attack(attack_family, generator)
            poisoned_data = inject_poisons(
                clean_data, attack, n_poison=intensity, poison_rate=1.0,
                seed=poison_seed, attacked_query_ids=heldout_ids,
            )
            manifest = build_cell_manifest(
                cell_id=cell_id, clean_data=clean_data, poisoned_data=poisoned_data,
                attack_family=attack_family, intensity=intensity, poison_seed=poison_seed,
                heldout_fingerprint=heldout_fp, config_hashes=hashes,
                dense_config=dense_config, rcd_config=rcd_config,
                git_sha=git_commit_sha(), git_dirty=False,
            )
            manifest["attack"]["configuration"] = attack_config
            _write_json_exclusive(manifest_path, manifest)
            replayed = replay_cell_manifest(clean_data, manifest)
            set_seed(FROZEN_RUNTIME_SEED)
            metrics = evaluate_cell(
                clean_data=clean_data, poisoned_data=replayed, dense_config=dense_config,
                rcd_config=rcd_config, generator=generator, manifest=manifest,
                results_path=results_path,
            )
            if (
                metrics["execution_evidence"]["raw_record_count"]
                != metrics["execution_evidence"]["expected_raw_record_count"]
            ):
                raise RuntimeError("Evaluation did not emit every expected raw record.")
            _write_json_exclusive(
                summary_path,
                {
                    "schema": CELL_SCHEMA,
                    "status": "complete_heldout_cell_not_statistically_conclusive",
                    "is_final_run": False,
                    "cell_id": cell_id,
                    "manifest_path": str(manifest_path),
                    "results_path": str(results_path),
                    "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
                    "query_count": MATRIX_QUERY_COUNT,
                    "runtime_seconds": time.perf_counter() - started,
                    **metrics,
                },
            )
            completed.append(cell_id)
        except Exception as error:
            _write_json_exclusive(
                failure_path,
                {
                    "status": "failed",
                    "cell_id": cell_id,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "partial_results_path": str(results_path) if results_path.exists() else None,
                },
            )
            failed.append(cell_id)
    return {"experiment_id": experiment_id, "output_root": str(output_root), "completed_cells": completed, "failed_or_incomplete_cells": failed}


def run_smoke_test(
    *,
    output_dir: Path,
    experiment_id: str,
    query_count: int = 2,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
) -> dict:
    """Run a real, isolated, non-final lexical smoke test on held-out IDs."""
    if not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be a non-empty filename-safe value.")
    if not 1 <= query_count < MATRIX_QUERY_COUNT:
        raise ValueError(f"smoke query_count must be in [1, {MATRIX_QUERY_COUNT - 1}].")
    preflight_data = preflight(
        heldout_path=heldout_path,
        dense_config_path=dense_config_path,
        rcd_config_path=rcd_config_path,
    )
    if not (
        preflight_data["runtime_requirements"]["mlx_available"]
        and preflight_data["runtime_requirements"]["mlx_lm_available"]
    ):
        raise RuntimeError("MLX and mlx-lm are required for the real smoke test.")
    _require_clean_relevant_inputs(require_tracked_runner=False)
    output_root = _ensure_output_outside_repository(output_dir) / experiment_id
    if output_root.exists():
        raise FileExistsError(f"Smoke-test output directory already exists: {output_root}")
    output_root.mkdir(parents=True)
    plan_path = output_root / "smoke.plan.json"
    manifest_path = output_root / "poison.manifest.json"
    results_path = output_root / "results.jsonl"
    summary_path = output_root / "summary.json"
    failure_path = output_root / "failure.json"
    started = time.perf_counter()
    try:
        dense_config, rcd_config, heldout_ids, heldout_fp, hashes = validate_frozen_inputs(
            heldout_path=heldout_path,
            dense_config_path=dense_config_path,
            rcd_config_path=rcd_config_path,
        )
        selected_ids = heldout_ids[:query_count]
        selected_config = dict(rcd_config)
        selected_config.pop("dataset_query_ids_manifest", None)
        selected_config["dataset_query_ids"] = selected_ids
        clean_data = load_dataset(selected_config)
        if [query["query_id"] for query in clean_data["queries"]] != selected_ids:
            raise ValueError("Smoke loader did not preserve the selected held-out IDs.")
        set_seed(FROZEN_RUNTIME_SEED)
        generator = build_generator(rcd_config)
        if generator.__class__.__name__ == "MockGenerator":
            raise TypeError("Smoke test requires the configured real generator.")
        attack, attack_config = _attack("lexical_influential_token", generator)
        poisoned_data = inject_poisons(
            clean_data,
            attack,
            n_poison=1,
            poison_rate=1.0,
            seed=PREDECLARED_POISON_SEEDS[0],
            attacked_query_ids=selected_ids,
        )
        manifest = build_cell_manifest(
            cell_id=f"smoke.lexical.intensity-1.seed-{PREDECLARED_POISON_SEEDS[0]}",
            clean_data=clean_data,
            poisoned_data=poisoned_data,
            attack_family="lexical_influential_token",
            intensity=1,
            poison_seed=PREDECLARED_POISON_SEEDS[0],
            heldout_fingerprint=heldout_fp,
            config_hashes=hashes,
            dense_config=dense_config,
            rcd_config=rcd_config,
            git_sha=git_commit_sha(),
            git_dirty=None,
            execution_mode="smoke_test",
        )
        manifest["attack"]["configuration"] = attack_config
        _write_json_exclusive(
            plan_path,
            {
                "schema": PLAN_SCHEMA,
                "status": "smoke_test_not_final",
                "is_final_run": False,
                "selected_query_ids": selected_ids,
                "preflight": preflight_data,
            },
        )
        _write_json_exclusive(manifest_path, manifest)
        replayed = replay_cell_manifest(clean_data, manifest)
        set_seed(FROZEN_RUNTIME_SEED)
        metrics = evaluate_cell(
            clean_data=clean_data,
            poisoned_data=replayed,
            dense_config=dense_config,
            rcd_config=rcd_config,
            generator=generator,
            manifest=manifest,
            results_path=results_path,
        )
        evidence = metrics["execution_evidence"]
        if (
            evidence["raw_record_count"] != evidence["expected_raw_record_count"]
            or evidence["retrieval_elapsed_seconds"] < 0
            or evidence["generation_elapsed_seconds"] < 0
        ):
            raise RuntimeError("Smoke test lacks complete retrieval/generation evidence.")
        summary = {
            "schema": CELL_SCHEMA,
            "status": "complete_smoke_test_not_final",
            "is_final_run": False,
            "cell_id": manifest["cell_id"],
            "manifest_path": str(manifest_path),
            "results_path": str(results_path),
            "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
            "query_count": query_count,
            "runtime_seconds": time.perf_counter() - started,
            **metrics,
        }
        _write_json_exclusive(summary_path, summary)
        return summary
    except Exception as error:
        _write_json_exclusive(
            failure_path,
            {
                "status": "smoke_test_failed",
                "is_final_run": False,
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "partial_results_path": str(results_path) if results_path.exists() else None,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--experiment-id")
    parser.add_argument("--heldout-manifest", type=Path, default=DEFAULT_HELDOUT_MANIFEST)
    parser.add_argument("--dense-config", type=Path, default=DEFAULT_DENSE_CONFIG)
    parser.add_argument("--rcd-config", type=Path, default=DEFAULT_RCD_CONFIG)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-query-count", type=int, default=2)
    args = parser.parse_args()
    if args.preflight and args.smoke_test:
        parser.error("--preflight and --smoke-test cannot be combined.")
    if args.preflight:
        result = preflight(
            heldout_path=args.heldout_manifest,
            dense_config_path=args.dense_config,
            rcd_config_path=args.rcd_config,
        )
    elif args.smoke_test:
        if not args.experiment_id:
            parser.error("--experiment-id is required for --smoke-test.")
        result = run_smoke_test(
            output_dir=args.output_dir,
            experiment_id=args.experiment_id,
            query_count=args.smoke_query_count,
            heldout_path=args.heldout_manifest,
            dense_config_path=args.dense_config,
            rcd_config_path=args.rcd_config,
        )
    else:
        if not args.experiment_id:
            parser.error("--experiment-id is required unless --preflight is used.")
        result = run_matrix(
            output_dir=args.output_dir, experiment_id=args.experiment_id,
            heldout_path=args.heldout_manifest, dense_config_path=args.dense_config,
            rcd_config_path=args.rcd_config, resume=args.resume,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
