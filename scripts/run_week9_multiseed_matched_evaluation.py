#!/usr/bin/env python3
"""Orchestrate the predeclared exploratory Dense-vs-RCD poison-seed runs.

Query selection and retrieval/generation retain frozen seed 42. Only the
lexical poison-generation RNG varies across poison seeds 42, 43, and 44.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from run import _load_heldout_manifest
from scripts.run_week9_matched_poison_comparison import (
    DEFAULT_DENSE_CONFIG,
    DEFAULT_RCD_CONFIG,
    _frozen_retriever_config,
    _rcd_config,
)
from scripts.run_week9_poison_pilot import (
    DEFAULT_HELDOUT_MANIFEST,
    PILOT_QUERY_COUNT,
    PILOT_SEED,
    POISON_RATE,
    N_POISON,
    ATTACK_REPEAT_FACTOR,
    RETRIEVAL_METRIC_K,
    _metadata_for_pilot,
    _load_config_and_clean_data,
    _ensure_output_outside_repository,
    build_pilot_manifest,
    select_pilot_attacked_ids,
    select_pilot_query_ids,
    write_json_exclusive,
)
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.utils.config import load_config
from src.utils.env_info import _git_dirty
from src.experiments.protocol import git_commit_sha, poison_instances_fingerprint

PREDECLARED_POISON_SEEDS = (42, 43, 44)
QUERY_SELECTION_SEED = PILOT_SEED
FROZEN_RUNTIME_SEED = 42
EXPECTED_CONFIG_HASHES = {
    "heldout": "2a2b8ea61bb1bca14f0321696e606108053d073c7c79aa6c5f7acc1a636b2bf3",
    "dense": "2d731de7934497e87ee912bba41d2c0c5728a50866454f037e7f0d222df790a8",
    "rcd": "ec8fd1542b04c7e81b476840ef0b411f95287388c22639ead5f2660720e44701",
}
EXPECTED_HELDOUT_FINGERPRINT = (
    "76671f6b9a70140578f2b0b6ac405eb3199235bc4d051e62d5896c715454e2df"
)
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads/rag-rcd-week9-final-results/multiseed"
COMPARISON_SCRIPT = REPOSITORY_ROOT / "scripts/run_week9_matched_poison_comparison.py"
AGGREGATION_SCRIPT = REPOSITORY_ROOT / "scripts/aggregate_week9_multiseed_results.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_frozen_inputs(
    *,
    heldout_path: Path,
    dense_config_path: Path,
    rcd_config_path: Path,
) -> tuple[dict, dict, list[str], str, dict[str, str]]:
    paths = {
        "heldout": heldout_path.expanduser().resolve(),
        "dense": dense_config_path.expanduser().resolve(),
        "rcd": rcd_config_path.expanduser().resolve(),
    }
    hashes = {name: sha256_file(path) for name, path in paths.items()}
    if hashes != EXPECTED_CONFIG_HASHES:
        raise ValueError(
            "Frozen config or held-out manifest hash mismatch; "
            f"expected {EXPECTED_CONFIG_HASHES}, got {hashes}."
        )
    dense = load_config(str(paths["dense"]))
    rcd = load_config(str(paths["rcd"]))
    if dense["seed"] != FROZEN_RUNTIME_SEED or rcd["seed"] != FROZEN_RUNTIME_SEED:
        raise ValueError("Frozen runtime/retrieval seed is not 42.")
    if rcd["retriever"] != "rcd" or dense["retriever"] != "dense":
        raise ValueError("Frozen Dense/RCD retriever configurations changed.")
    rcd_manifest_config = dict(rcd)
    rcd_manifest_config["dataset_query_ids_manifest"] = str(paths["heldout"])
    heldout = _load_heldout_manifest(rcd_manifest_config)
    if heldout is None or heldout[1] != EXPECTED_HELDOUT_FINGERPRINT:
        raise ValueError("Validated held-out query fingerprint differs from frozen.")
    return dense, rcd, heldout[0], heldout[1], hashes


def create_seed_poison_manifest(
    *,
    clean_data: dict,
    config: dict,
    selected_query_ids: list[str],
    heldout_fingerprint: str,
    heldout_manifest_path: Path,
    poison_seed: int,
    experiment_id: str,
    git_sha: str,
    git_dirty: bool,
) -> dict:
    """Create one immutable poison snapshot with an independent attack RNG seed."""
    if config.get("seed") != FROZEN_RUNTIME_SEED:
        raise ValueError("Frozen runtime/retrieval seed must remain 42.")
    actual_ids = [query["query_id"] for query in clean_data["queries"]]
    if (
        len(actual_ids) != PILOT_QUERY_COUNT
        or selected_query_ids != actual_ids
        or len(selected_query_ids) != len(set(selected_query_ids))
    ):
        raise ValueError("Seed manifest requires the fixed ordered ten-query set.")
    attacked_ids = select_pilot_attacked_ids(
        clean_data["queries"], poison_rate=POISON_RATE, seed=poison_seed
    )
    poisoned_data = inject_poisons(
        clean_data,
        LexicalInfluentialTokenAttack(repeat_factor=ATTACK_REPEAT_FACTOR),
        n_poison=N_POISON,
        poison_rate=POISON_RATE,
        seed=poison_seed,
        attacked_query_ids=attacked_ids,
    )
    validation = validate_poisoned_dataset(
        clean_data,
        poisoned_data,
        expected_n_poison=N_POISON,
        expected_poison_rate=POISON_RATE,
    )
    if not validation["valid"]:
        raise ValueError(f"Poisoned dataset validation failed: {validation['checks']}")
    fingerprint = poison_instances_fingerprint(clean_data, poisoned_data)
    metadata = _metadata_for_pilot(
        experiment_id=experiment_id,
        config=config,
        clean_data=clean_data,
        heldout_manifest_fingerprint=heldout_fingerprint,
        attacked_query_ids=attacked_ids,
        poison_fingerprint=fingerprint,
        git_sha=git_sha,
        git_dirty=git_dirty,
        attack_version=f"git:{git_sha}",
    )
    seed_protocol = {
        "query_selection_seed": QUERY_SELECTION_SEED,
        "poison_seed": poison_seed,
        "retrieval_and_generation_seed": FROZEN_RUNTIME_SEED,
        "semantics": {
            "query_selection_seed": "Selects the fixed ten held-out query IDs.",
            "poison_seed": (
                "Seeds inject_poisons' local RNG for target-answer/poison "
                "instance generation; the selected query IDs remain fixed."
            ),
            "retrieval_and_generation_seed": (
                "Retained from both frozen configs and seeds retrieval/model "
                "runtime; not varied in this exploratory evaluation."
            ),
        },
    }
    metadata["seed_protocol"] = seed_protocol
    manifest = build_pilot_manifest(
        experiment_id=experiment_id,
        clean_data=clean_data,
        poisoned_data=poisoned_data,
        metadata=metadata,
        selected_query_ids=selected_query_ids,
        attacked_query_ids=attacked_ids,
        heldout_manifest_fingerprint=heldout_fingerprint,
        dataset_revision=config["dataset_revision"],
        dataset_split=config["dataset_split"],
        seed=FROZEN_RUNTIME_SEED,
        poison_rate=POISON_RATE,
        n_poison=N_POISON,
        attack_repeat_factor=ATTACK_REPEAT_FACTOR,
        attack_version=metadata["attack_version"],
        generator_backend=config["generator_backend"],
        generator_model=config["generator_model"],
        generator_max_tokens=int(config.get("max_tokens", 64)),
        top_k=int(config["top_k"]),
        retrieval_metric_k=RETRIEVAL_METRIC_K,
        retriever_config=_frozen_retriever_config(config),
        rcd_config=_rcd_config(config),
        heldout_manifest_path=str(heldout_manifest_path.resolve()),
    )
    manifest["seed_protocol"] = seed_protocol
    manifest["poison_seed"] = poison_seed
    return manifest


def execute_comparisons(
    *,
    runs: list[dict],
    journal_path: Path,
    failure_path: Path,
    run_subprocess=subprocess.run,
) -> None:
    """Run comparisons sequentially; never remove completed output on failure."""
    completed_seeds = []
    with journal_path.open("x", encoding="utf-8") as journal:
        for run in runs:
            record = {
                **run["provenance"],
                "seed": run["seed"],
                "command": run["command"],
                "status": "started",
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            journal.write(json.dumps(record, sort_keys=True) + "\n")
            journal.flush()
            try:
                run_subprocess(run["command"], check=True)
            except Exception as error:
                record.update(
                    {
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "completed_seed_ids": completed_seeds,
                        "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                        "traceback": traceback.format_exc(),
                    }
                )
                journal.write(json.dumps(record, sort_keys=True) + "\n")
                journal.flush()
                write_json_exclusive(
                    failure_path,
                    {
                        "status": "failed",
                        "seed": run["seed"],
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "completed_seed_ids": completed_seeds,
                        "journal_path": str(journal_path),
                    },
                )
                raise
            record.update(
                {
                    "status": "completed",
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
            journal.write(json.dumps(record, sort_keys=True) + "\n")
            journal.flush()
            completed_seeds.append(run["seed"])


def run_multiseed(
    *,
    seeds: tuple[int, ...] = PREDECLARED_POISON_SEEDS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    experiment_id: str | None = None,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
) -> dict:
    output_dir = _ensure_output_outside_repository(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Provide a non-empty list of unique poison seeds.")
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError("All poison seeds must be integers.")
    if tuple(seeds) != PREDECLARED_POISON_SEEDS:
        raise ValueError(
            "The initial exploratory protocol is predeclared for seeds 42, 43, and 44."
        )
    if experiment_id is None:
        experiment_id = datetime.now(timezone.utc).strftime(
            "week9_multiseed_%Y%m%dT%H%M%SZ"
        )
    if Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be filename-safe.")
    run_root = output_dir / experiment_id
    if run_root.exists():
        raise FileExistsError(f"Multi-seed output directory already exists: {run_root}")
    commit = git_commit_sha(default="")
    dirty = _git_dirty()
    if not commit or commit == "unknown" or dirty is None:
        raise RuntimeError("Unable to capture Git commit and dirty state.")

    dense_config, rcd_config, heldout_ids, heldout_fp, config_hashes = (
        validate_frozen_inputs(
            heldout_path=heldout_path,
            dense_config_path=dense_config_path,
            rcd_config_path=rcd_config_path,
        )
    )
    # Reuse the existing loader path, which selects and loads the fixed
    # ten-query subset with the frozen query-selection seed 42.
    rcd_config, clean_data, selected_ids, loaded_fp = _load_config_and_clean_data(
        config_path=rcd_config_path,
        heldout_manifest_path=heldout_path,
        replay_manifest=None,
    )
    if (
        selected_ids != select_pilot_query_ids(heldout_ids, seed=QUERY_SELECTION_SEED)
        or loaded_fp != heldout_fp
        or len(clean_data["queries"]) != PILOT_QUERY_COUNT
    ):
        raise ValueError("Loaded pilot query subset differs from the fixed protocol.")

    plan_path = run_root / f"{experiment_id}.plan.json"
    commands_path = run_root / f"{experiment_id}.commands.json"
    execution_journal_path = run_root / f"{experiment_id}.execution.jsonl"
    failure_path = run_root / f"{experiment_id}.failure.json"
    aggregation_path = run_root / f"{experiment_id}.summary.json"
    comparison_runs = []
    expected_paths = [
        plan_path,
        commands_path,
        execution_journal_path,
        failure_path,
        aggregation_path,
    ]
    for seed in seeds:
        source_name = f"{experiment_id}.poison-seed-{seed}"
        compare_name = f"{experiment_id}.comparison-seed-{seed}"
        expected_paths.extend(
            [
                run_root / f"{source_name}.manifest.json",
                run_root / f"{compare_name}.manifest.json",
                run_root / f"{compare_name}.jsonl",
                run_root / f"{compare_name}.summary.json",
                run_root / f"{compare_name}.failure.json",
            ]
        )
    collisions = [str(path) for path in expected_paths if path.exists()]
    if collisions:
        raise FileExistsError(f"Output collisions: {collisions}")
    run_root.mkdir()

    aggregation_command = [
        sys.executable,
        str(AGGREGATION_SCRIPT),
        "--output",
        str(aggregation_path),
        *[
            arg
            for seed in seeds
            for arg in (
                "--run",
                str(run_root / f"{experiment_id}.comparison-seed-{seed}.manifest.json"),
                str(run_root / f"{experiment_id}.comparison-seed-{seed}.summary.json"),
                str(run_root / f"{experiment_id}.comparison-seed-{seed}.jsonl"),
            )
        ],
    ]
    plan = {
        "schema": "rag-poison-transfer.week9-multiseed-plan/v1",
        "experiment_id": experiment_id,
        "status": "exploratory_not_final",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "predeclared_poison_seeds": list(seeds),
        "seed_protocol": {
            "query_selection_seed": QUERY_SELECTION_SEED,
            "poison_seeds": list(seeds),
            "retrieval_and_generation_seed": FROZEN_RUNTIME_SEED,
        },
        "selected_query_ids": selected_ids,
        "query_set_fingerprint": None,
        "heldout_manifest_fingerprint": heldout_fp,
        "config_sha256": config_hashes,
        "git": {
            "commit_sha": commit,
            "worktree_dirty": dirty,
        },
        "output_root": str(run_root),
        "aggregation_method": (
            "Query-cluster bootstrap; resample unique query IDs with replacement "
            "and retain all seeds/pipelines within each sampled query cluster."
        ),
        "bootstrap_seed": 20261022,
    }
    from src.experiments.protocol import query_set_fingerprint

    plan["query_set_fingerprint"] = query_set_fingerprint(clean_data["queries"])
    write_json_exclusive(plan_path, plan)

    generated_manifest_seeds = []
    for seed in seeds:
        source_name = f"{experiment_id}.poison-seed-{seed}"
        compare_name = f"{experiment_id}.comparison-seed-{seed}"
        source_path = run_root / f"{source_name}.manifest.json"
        try:
            manifest = create_seed_poison_manifest(
                clean_data=clean_data,
                config=rcd_config,
                selected_query_ids=selected_ids,
                heldout_fingerprint=heldout_fp,
                heldout_manifest_path=heldout_path,
                poison_seed=seed,
                experiment_id=source_name,
                git_sha=commit,
                git_dirty=dirty,
            )
            write_json_exclusive(source_path, manifest)
            generated_manifest_seeds.append(seed)
        except Exception as error:
            write_json_exclusive(
                failure_path,
                {
                    "status": "poison_manifest_generation_failed",
                    "seed": seed,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "completed_poison_manifest_seeds": generated_manifest_seeds,
                    "plan_path": str(plan_path),
                },
            )
            raise
        comparison_command = [
            sys.executable,
            str(COMPARISON_SCRIPT),
            "--source-manifest",
            str(source_path),
            "--dense-config",
            str(dense_config_path.resolve()),
            "--rcd-config",
            str(rcd_config_path.resolve()),
            "--output-dir",
            str(run_root),
            "--experiment-id",
            compare_name,
        ]
        provenance = {
            "source_manifest_path": str(source_path),
            "source_manifest_sha256": sha256_file(source_path),
            "poison_instance_fingerprint": manifest[
                "poison_instance_fingerprint"
            ],
            "query_set_fingerprint": manifest["dataset"][
                "query_set_fingerprint"
            ],
            "config_sha256": config_hashes,
            "git_commit_sha": commit,
            "git_dirty": dirty,
        }
        comparison_runs.append(
            {
                "seed": seed,
                "command": comparison_command,
                "provenance": provenance,
                "summary": run_root / f"{compare_name}.summary.json",
                "manifest": run_root / f"{compare_name}.manifest.json",
                "results": run_root / f"{compare_name}.jsonl",
            }
        )

    write_json_exclusive(
        commands_path,
        {
            "event": "plan",
            "comparison_commands": [
                {"seed": item["seed"], "command": item["command"]}
                for item in comparison_runs
            ],
            "aggregation_command": aggregation_command,
        },
    )
    execute_comparisons(
        runs=comparison_runs,
        journal_path=execution_journal_path,
        failure_path=failure_path,
    )
    try:
        subprocess.run(aggregation_command, check=True)
    except Exception as error:
        write_json_exclusive(
            failure_path,
            {
                "status": "aggregation_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "aggregation_command": aggregation_command,
                "completed_comparison_seeds": list(seeds),
                "execution_journal_path": str(execution_journal_path),
            },
        )
        raise
    return {
        "experiment_id": experiment_id,
        "status": "complete_exploratory_not_final",
        "output_root": str(run_root),
        "plan_path": str(plan_path),
        "commands_path": str(commands_path),
        "journal_path": str(execution_journal_path),
        "aggregation_path": str(aggregation_path),
        "commands": [item["command"] for item in comparison_runs]
        + [aggregation_command],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=list(PREDECLARED_POISON_SEEDS),
        help="Independent poison-generation seeds (default: 42 43 44).",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--experiment-id")
    parser.add_argument("--heldout-manifest", type=Path, default=DEFAULT_HELDOUT_MANIFEST)
    parser.add_argument("--dense-config", type=Path, default=DEFAULT_DENSE_CONFIG)
    parser.add_argument("--rcd-config", type=Path, default=DEFAULT_RCD_CONFIG)
    args = parser.parse_args()
    print(
        json.dumps(
            run_multiseed(
                seeds=tuple(args.seeds),
                output_dir=args.output_dir,
                experiment_id=args.experiment_id,
                heldout_path=args.heldout_manifest,
                dense_config_path=args.dense_config,
                rcd_config_path=args.rcd_config,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
