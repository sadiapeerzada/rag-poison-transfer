#!/usr/bin/env python3
"""Run the frozen 300-query Week 9 held-out poisoning matrix.

This is intentionally separate from the ten-query exploratory pilot.  Each
cell creates one immutable poison snapshot and reuses it for both Dense and
RCD.  Output is append-only and must be outside the repository.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from run import build_generator, load_dataset
import scripts.aggregate_week9_multiseed_results as multiseed
from scripts.run_week9_matched_poison_comparison import (
    RETRIEVAL_METRIC_K,
    _frozen_retriever_config,
    _rate,
    _rcd_config,
    build_matched_retrievers,
    diagnostic_retrieval_required,
    evaluate_pipeline,
    flatten_query_result_records,
    paired_differences,
    summarize_pipeline,
    validate_shared_pipeline_settings,
    validated_top_k,
)
from scripts.run_week9_multiseed_matched_evaluation import (
    FROZEN_RUNTIME_SEED,
    PREDECLARED_POISON_SEEDS,
    validate_frozen_inputs,
)
from src.attacks.base import poison_doc_id
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.attacks.semantic_fluent import SemanticFluentFalseEvidenceAttack
from src.evaluation.metrics import exact_match
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
# Every tracked file whose content can change a held-out result.  The list
# covers the runners, frozen configs, attack and poison code, the exact
# prompt/answer-extraction code, the retrievers and the RCD defense, the
# metrics, and the data loader.  Any uncommitted change here blocks a final
# run, and every listed path must exist and be tracked.
RELEVANT_TRACKED_PATHS = (
    "run.py",
    "configs/exp_027_hotpotqa_heldout_manifest.json",
    "configs/exp_030_hotpotqa_dense_heldout_mlx.yaml",
    "configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml",
    "scripts/run_week9_heldout_poison_matrix.py",
    "scripts/run_week9_matched_poison_comparison.py",
    "scripts/run_week9_multiseed_matched_evaluation.py",
    "scripts/run_week9_poison_pilot.py",
    "src/attacks/asr.py",
    "src/attacks/base.py",
    "src/attacks/injection.py",
    "src/attacks/lexical.py",
    "src/attacks/semantic_fluent.py",
    "src/data/loaders.py",
    "src/defenses/rcd/conflict.py",
    "src/defenses/rcd/core.py",
    "src/defenses/rcd/redundancy.py",
    "src/defenses/rcd/retriever.py",
    "src/defenses/rcd/rewrites.py",
    "src/defenses/rcd/scoring.py",
    "src/evaluation/metrics.py",
    "src/experiments/protocol.py",
    "src/pipelines/generator.py",
    "src/retrieval/bm25.py",
    "src/retrieval/dense.py",
    "src/utils/config.py",
    "src/utils/seeding.py",
)
PLAN_SCIENTIFIC_STATUS = "not_final_not_statistically_conclusive"
CELL_COMPLETE_STATUS = "complete_heldout_cell_not_statistically_conclusive"


def _write_json_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
        output.write("\n")


def _write_json_atomic(path: Path, value: dict) -> None:
    """Replace ``path`` atomically; a failed write leaves the old file intact.

    The new content is written and fsynced to a uniquely named temporary file
    in the same directory and then moved over the target with ``os.replace``,
    so readers never observe a partial plan and a crash or write error cannot
    corrupt a previously valid one.
    """
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _git(*arguments: str) -> subprocess.CompletedProcess:
    """Run Git against THIS repository regardless of the caller's cwd."""
    return subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
        cwd=str(REPOSITORY_ROOT),
    )


GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIRTY_CHECK_SCOPE = "relevant tracked source and configuration files"
_NON_SOURCE_PARTS = {"tests", "site-packages", "dist-packages", ".venv", "venv", "__pycache__"}


def _loaded_repository_sources() -> list[str]:
    """Repository ``.py`` files actually imported by this process.

    ``RELEVANT_TRACKED_PATHS`` is maintained by hand and can fall behind the
    code.  The interpreter knows exactly which repository modules the run
    executes, so those are added to the guarded set automatically.  Test
    modules and third-party/virtualenv code are not experiment inputs.
    """
    root = REPOSITORY_ROOT.resolve()
    found = set()
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str) or not filename.endswith(".py"):
            continue
        try:
            relative = Path(filename).resolve().relative_to(root)
        except (ValueError, OSError):
            continue
        if _NON_SOURCE_PARTS & set(relative.parts):
            continue
        found.add(relative.as_posix())
    return sorted(found)


def relevant_input_paths() -> tuple[str, ...]:
    """Declared relevant paths plus every repository module imported at run time."""
    return tuple(sorted(set(RELEVANT_TRACKED_PATHS) | set(_loaded_repository_sources())))


def compute_source_fingerprint() -> str:
    """SHA-256 over the path and byte content of every relevant input.

    A commit SHA identifies a commit, not the working tree: a dirty file keeps
    the same ``HEAD``.  The guard below rejects dirty relevant inputs, and this
    fingerprint additionally pins the exact executed content so that cells
    produced from different source states can be detected afterwards.
    Unrelated untracked artifacts are not part of it.
    """
    digest = hashlib.sha256()
    for relative in relevant_input_paths():
        path = REPOSITORY_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"Relevant experiment input is missing: {relative}")
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def _require_clean_relevant_inputs(*, require_tracked_runner: bool) -> None:
    """Reject changed experiment inputs but ignore unrelated untracked artifacts.

    Git always runs inside ``REPOSITORY_ROOT``: running from another checkout
    must neither pass vacuously nor record a foreign commit.  Failure to
    inspect Git state fails closed.  The guarded set is the declared
    ``RELEVANT_TRACKED_PATHS`` plus every repository module imported by the
    running process (``relevant_input_paths``).  For final execution every
    guarded path must also be tracked, because ``--untracked-files=no`` status
    cannot see a relevant but untracked file.  Untracked files that are not
    imported or declared (results, notes, backups) are deliberately ignored.
    """
    paths = relevant_input_paths()
    try:
        status = _git("status", "--porcelain=v1", "--untracked-files=no", "--", *paths)
        if status.returncode:
            raise RuntimeError("Unable to inspect relevant tracked experiment inputs.")
        if status.stdout:
            raise RuntimeError(
                "Held-out execution requires clean relevant tracked inputs: "
                f"{status.stdout.strip()}"
            )
        if require_tracked_runner:
            tracked = _git("ls-files", "--error-unmatch", "--", *paths)
            if tracked.returncode:
                raise RuntimeError(
                    "Final held-out execution requires the matrix runner and every "
                    "relevant or imported input to be tracked in Git; commit them before "
                    f"executing the final matrix. Git reported: {tracked.stderr.strip()}"
                )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Unable to inspect relevant tracked experiment inputs.") from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_git_provenance(manifest: dict) -> dict:
    """Require complete, well-formed Git/source provenance in a held-out cell manifest.

    Nothing is defaulted: a missing, empty, wrongly typed or dirty record is an
    error.  Returns ``{"commit_sha", "source_fingerprint"}``.
    """
    git = manifest.get("git")
    if not isinstance(git, dict):
        raise ValueError("Cell manifest lacks Git provenance.")
    commit = git.get("commit_sha")
    if not isinstance(commit, str) or not GIT_SHA_PATTERN.fullmatch(commit):
        raise ValueError("Cell manifest Git commit_sha is missing or not a 40-character hex SHA.")
    if git.get("relevant_tracked_inputs_dirty") is not False:
        raise ValueError("Cell manifest does not record clean relevant tracked inputs.")
    if git.get("dirty_check_scope") != DIRTY_CHECK_SCOPE:
        raise ValueError("Cell manifest Git dirty-check scope is missing or unexpected.")
    fingerprint = git.get("source_fingerprint")
    if not isinstance(fingerprint, str) or not SHA256_PATTERN.fullmatch(fingerprint):
        raise ValueError("Cell manifest source_fingerprint is missing or not a SHA-256 digest.")
    return {"commit_sha": commit, "source_fingerprint": fingerprint}


def matrix_cells() -> list[tuple[str, int, int]]:
    return [
        (attack, intensity, seed)
        for attack in MATRIX_ATTACKS
        for intensity in MATRIX_INTENSITIES
        for seed in PREDECLARED_POISON_SEEDS
    ]


def estimate_workload(
    dense_config: dict,
    rcd_config: dict,
    *,
    query_count: int,
    cell_count: int | None = None,
) -> dict:
    """Derive the model/retrieval workload from the validated runtime configs.

    Every figure is computed from the same quantities the evaluation loop
    uses (``top_k``, ``RETRIEVAL_METRIC_K`` through
    ``diagnostic_retrieval_required``, and the pipeline/condition lists), so
    preflight cannot drift from runtime.  Per (cell, pipeline, query):

    * one generation and one normal retrieval for each condition
      (clean, poisoned);
    * one additional poisoned diagnostic retrieval, executed only when the
      diagnostic cutoff exceeds ``top_k`` (needed for PRR@k beyond the
      evidence the generator sees).

    ``retrieval_calls`` is the total (normal + diagnostic).  Calls are
    *outer* ``retriever.retrieve`` invocations; RCD additionally performs
    several inner retrievals per call, reported separately as bounds.
    """
    validate_shared_pipeline_settings(dense_config, rcd_config)
    if isinstance(query_count, bool) or not isinstance(query_count, int) or query_count < 1:
        raise ValueError(f"query_count must be a positive integer, got {query_count!r}.")
    cells = len(matrix_cells()) if cell_count is None else cell_count
    if isinstance(cells, bool) or not isinstance(cells, int) or cells < 1:
        raise ValueError(f"cell_count must be a positive integer, got {cells!r}.")
    top_k = validated_top_k(dense_config, "Dense")
    pipelines = tuple(multiseed.PIPELINES)
    conditions = tuple(multiseed.CONDITIONS)
    if not pipelines or not conditions:
        raise ValueError("Cannot estimate workload without pipelines and conditions.")
    diagnostic_per_query = 1 if diagnostic_retrieval_required(top_k) else 0
    pipeline_queries = cells * query_count  # per pipeline
    generations = pipeline_queries * len(pipelines) * len(conditions)
    normal = pipeline_queries * len(pipelines) * len(conditions)
    diagnostic = pipeline_queries * len(pipelines) * diagnostic_per_query
    rcd_outer = pipeline_queries * (len(conditions) + diagnostic_per_query)
    try:
        rewrites = int(rcd_config["rcd_rewrite_count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("RCD config needs an integer rcd_rewrite_count.") from error
    if rewrites < 0:
        raise ValueError("rcd_rewrite_count must be non-negative.")
    return {
        "cells": cells,
        "queries_per_cell": query_count,
        "pipelines": list(pipelines),
        "conditions": list(conditions),
        "generation_top_k": top_k,
        "diagnostic_retrieval_top_k": RETRIEVAL_METRIC_K,
        "diagnostic_retrieval_per_pipeline_query": diagnostic_per_query,
        "evaluation_generation_calls": generations,
        "normal_retrieval_calls": normal,
        "diagnostic_retrieval_calls": diagnostic,
        "retrieval_calls": normal + diagnostic,
        "per_pipeline": {
            name: {
                "generation_calls": pipeline_queries * len(conditions),
                "normal_retrieval_calls": pipeline_queries * len(conditions),
                "diagnostic_retrieval_calls": pipeline_queries * diagnostic_per_query,
            }
            for name in pipelines
        },
        "inner_retrieval_operations": {
            "dense_per_call": 1,
            "rcd_per_call_minimum": 2,
            "rcd_per_call_maximum": 2 + rewrites,
            "rcd_total_minimum": rcd_outer * 2,
            "rcd_total_maximum": rcd_outer * (2 + rewrites),
            "note": (
                "RCD issues a primary and a sparse retrieval plus one per "
                "distinct query rewrite; duplicates of the original are "
                "dropped, so the true count is query-dependent. Observed "
                "counts are stored per raw record."
            ),
        },
    }


def preflight(
    *,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
) -> dict:
    """Validate immutable inputs without loading a model or dataset."""
    dense_config, rcd_config, heldout_ids, heldout_fingerprint, hashes = validate_frozen_inputs(
        heldout_path=heldout_path,
        dense_config_path=dense_config_path,
        rcd_config_path=rcd_config_path,
    )
    if len(heldout_ids) != MATRIX_QUERY_COUNT:
        raise ValueError(
            f"Expected frozen held-out manifest to contain {MATRIX_QUERY_COUNT} "
            f"queries, found {len(heldout_ids)}."
        )
    workload = estimate_workload(dense_config, rcd_config, query_count=len(heldout_ids))
    semantic_documents = (
        len(PREDECLARED_POISON_SEEDS)
        * len(heldout_ids)
        * sum(MATRIX_INTENSITIES)
    )
    return {
        "schema": PLAN_SCHEMA,
        "cell_count": len(matrix_cells()),
        "query_count_per_cell": len(heldout_ids),
        "poison_generation_calls": {
            "lexical": 0,
            "semantic_fluent": semantic_documents,
        },
        "evaluation_generation_calls": workload["evaluation_generation_calls"],
        "retrieval_calls": workload["retrieval_calls"],
        "normal_retrieval_calls": workload["normal_retrieval_calls"],
        "diagnostic_retrieval_calls": workload["diagnostic_retrieval_calls"],
        "workload": workload,
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
    source_fingerprint: str | None = None,
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
    if execution_mode == "heldout_matrix" and (
        not isinstance(source_fingerprint, str) or not SHA256_PATTERN.fullmatch(source_fingerprint)
    ):
        raise ValueError("Held-out cell manifest requires a SHA-256 source_fingerprint.")
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
            "dirty_check_scope": DIRTY_CHECK_SCOPE,
            "source_fingerprint": source_fingerprint,
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


ATTACK_CONFIGURATIONS = {
    "lexical_influential_token": {"repeat_factor": 4},
    "semantic_fluent_false_evidence": {"max_tokens": 150},
}


@dataclass(frozen=True)
class FrozenMatrixInputs:
    """The frozen scientific inputs every cell must be verified against.

    Loaded ONCE per run/aggregation through the repository's own validated
    loaders, never from a cell's own (possibly corrupted) artifacts.
    """

    clean_data: dict
    heldout_ids: list
    heldout_fingerprint: str
    config_hashes: dict
    dense_config: dict
    rcd_config: dict


def load_frozen_matrix_inputs(
    *,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
) -> FrozenMatrixInputs:
    """Load and validate the frozen configs, held-out manifest and clean data."""
    dense_config, rcd_config, heldout_ids, heldout_fp, hashes = validate_frozen_inputs(
        heldout_path=heldout_path,
        dense_config_path=dense_config_path,
        rcd_config_path=rcd_config_path,
    )
    if len(heldout_ids) != MATRIX_QUERY_COUNT:
        raise ValueError(
            f"Frozen held-out manifest must contain {MATRIX_QUERY_COUNT} queries, "
            f"found {len(heldout_ids)}."
        )
    clean_data = load_dataset({**rcd_config, "dataset_query_ids_manifest": str(heldout_path)})
    if [query["query_id"] for query in clean_data["queries"]] != heldout_ids:
        raise ValueError("Dataset loader did not preserve frozen held-out query order.")
    return FrozenMatrixInputs(
        clean_data=clean_data,
        heldout_ids=list(heldout_ids),
        heldout_fingerprint=heldout_fp,
        config_hashes=dict(hashes),
        dense_config=dense_config,
        rcd_config=rcd_config,
    )


def verify_cell_provenance(manifest: dict, frozen: FrozenMatrixInputs) -> dict:
    """Independently verify a cell manifest and return its replayed poison data.

    Nothing here trusts a stored fingerprint: the poison documents and
    associations are replayed over the independently loaded frozen clean data
    and the poison-instance fingerprint is recomputed from scratch.  Callers
    then compare that recomputed value with every stored copy.
    """
    if not isinstance(manifest, dict):
        raise ValueError("Cell manifest must be a JSON object.")
    attack = manifest.get("attack")
    if not isinstance(attack, dict):
        raise ValueError("Cell manifest lacks attack metadata.")
    family, intensity = attack.get("family"), attack.get("intensity")
    seed = manifest.get("seed_protocol", {}).get("poison_seed")
    if family not in MATRIX_ATTACKS or intensity not in MATRIX_INTENSITIES:
        raise ValueError("Cell manifest has an attack family or intensity outside the matrix.")
    if seed not in PREDECLARED_POISON_SEEDS:
        raise ValueError(f"Cell poison seed {seed!r} is not a predeclared seed.")
    if manifest.get("cell_id") != _cell_id(family, intensity, seed):
        raise ValueError("Cell ID does not match its attack metadata.")
    if attack.get("configuration") != ATTACK_CONFIGURATIONS[family]:
        raise ValueError("Cell attack configuration differs from the frozen protocol.")
    protocol = manifest.get("seed_protocol", {})
    if (
        protocol.get("query_selection_seed") != FROZEN_RUNTIME_SEED
        or protocol.get("retrieval_and_generation_seed") != FROZEN_RUNTIME_SEED
    ):
        raise ValueError("Cell seed protocol differs from the frozen runtime seeds.")

    dataset = manifest.get("dataset")
    rcd = frozen.rcd_config
    if not isinstance(dataset, dict):
        raise ValueError("Cell manifest lacks dataset metadata.")
    expected_dataset = {
        "name": "hotpotqa/hotpot_qa",
        "config": "distractor",
        "revision": rcd["dataset_revision"],
        "split": rcd["dataset_split"],
        "heldout_manifest_fingerprint": frozen.heldout_fingerprint,
    }
    for key, value in expected_dataset.items():
        if dataset.get(key) != value:
            raise ValueError(f"Cell dataset {key} differs from the frozen inputs.")
    if dataset.get("selected_query_ids") != frozen.heldout_ids:
        raise ValueError("Cell query IDs or order differ from the frozen held-out manifest.")

    configs = manifest.get("configs")
    if not isinstance(configs, dict):
        raise ValueError("Cell manifest lacks configuration provenance.")
    if configs.get("sha256") != frozen.config_hashes:
        raise ValueError("Cell configuration hashes differ from the frozen inputs.")
    if (
        configs.get("dense") != _frozen_retriever_config(frozen.dense_config)
        or configs.get("rcd") != _frozen_retriever_config(rcd)
        or configs.get("rcd_configuration") != _rcd_config(rcd)
    ):
        raise ValueError("Cell retriever configuration differs from the frozen inputs.")
    generator = manifest.get("generator")
    if generator != {
        "backend": rcd["generator_backend"],
        "model_identifier": rcd["generator_model"],
        "evaluation_max_tokens": int(rcd["max_tokens"]),
    }:
        raise ValueError("Cell generator settings differ from the frozen inputs.")

    _verify_poison_document_identity(manifest, family, int(intensity))
    # Canonical replay: recomputes the fingerprint and validates the dataset.
    poisoned = replay_cell_manifest(frozen.clean_data, manifest)
    if family == "lexical_influential_token":
        # Lexical poison is a pure, deterministic function of the frozen clean
        # data, the seed and the intensity, so it can be regenerated offline
        # (no model, no randomness beyond the seeded RNG) and compared.  This
        # also catches a manifest whose documents AND fingerprint were edited
        # consistently.  Semantic-fluent poison comes from an LLM and cannot be
        # regenerated here; it is verified by replay and document identity only.
        regenerated = inject_poisons(
            frozen.clean_data,
            LexicalInfluentialTokenAttack(
                repeat_factor=ATTACK_CONFIGURATIONS[family]["repeat_factor"]
            ),
            n_poison=int(intensity),
            poison_rate=1.0,
            seed=seed,
            attacked_query_ids=frozen.heldout_ids,
        )
        if poison_instances_fingerprint(frozen.clean_data, regenerated) != (
            poison_instances_fingerprint(frozen.clean_data, poisoned)
        ):
            raise ValueError(
                "Lexical poison instances differ from their deterministic regeneration."
            )
    return poisoned


def _verify_poison_document_identity(manifest: dict, family: str, intensity: int) -> None:
    """Each poison ID must equal the canonical ID derived from its own text."""
    documents = manifest.get("poison_documents")
    associations = manifest.get("query_poison_associations")
    if not isinstance(documents, list) or not isinstance(associations, list):
        raise ValueError("Cell manifest lacks poison documents or associations.")
    text_by_id = {}
    for document in documents:
        doc_id = document.get("doc_id") if isinstance(document, dict) else None
        if not isinstance(doc_id, str) or doc_id in text_by_id:
            raise ValueError("Cell manifest has missing or duplicate poison document IDs.")
        text_by_id[doc_id] = document.get("text")
    referenced = []
    for association in associations:
        query_id = association.get("query_id")
        if association.get("attack_family") != family:
            raise ValueError("Association attack family differs from cell metadata.")
        ids = association.get("poison_doc_ids")
        if not isinstance(ids, list) or len(ids) != intensity:
            raise ValueError(f"Query {query_id!r} does not have exactly {intensity} poison documents.")
        indexes = []
        for doc_id in ids:
            text = text_by_id.get(doc_id)
            prefix = f"poison::{family}::{query_id}::"
            if not isinstance(text, str) or not doc_id.startswith(prefix):
                raise ValueError(f"Poison document {doc_id!r} is not scoped to its query and family.")
            index = doc_id[len(prefix):].split("::", 1)[0]
            if not index.isdigit() or poison_doc_id(family, query_id, int(index), text) != doc_id:
                raise ValueError(f"Poison document {doc_id!r} does not match its content hash.")
            indexes.append(int(index))
        if sorted(indexes) != list(range(intensity)):
            raise ValueError(f"Query {query_id!r} poison indexes are not 0..{intensity - 1}.")
        if family == "semantic_fluent_false_evidence":
            target = association.get("poison_target_answer")
            if not isinstance(target, str) or not target.strip():
                raise ValueError(f"Query {query_id!r} has no semantic poison target.")
            for doc_id in ids:
                if target.casefold() not in text_by_id[doc_id].casefold():
                    raise ValueError(f"Semantic poison document {doc_id!r} omits its target answer.")
        referenced.extend(ids)
    if sorted(referenced) != sorted(text_by_id):
        raise ValueError("Manifest poison documents do not match the associations exactly.")


def _require_field(row: dict, field: str) -> Any:
    """Return ``row[field]``; an absent key is an error, a present ``None`` is data."""
    if field not in row:
        raise ValueError(f"Raw record is missing required field {field!r}.")
    return row[field]


def _require_doc_ids(row: dict, field: str) -> list[str]:
    value = _require_field(row, field)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"Raw record field {field!r} must be a list of non-empty strings.")
    return value


def _validate_retrieval_record(row: dict, poison_set: set[str]) -> None:
    """Strictly validate one raw row's retrieval fields and poison metrics.

    Schema (written for BOTH conditions by ``evaluate_pipeline``): every row
    carries ``retrieved_doc_ids`` (ranked diagnostic window),
    ``generation_evidence_doc_ids`` (what the generator saw; a prefix of the
    window), ``poison_retrieved`` (bool: poison in the generator's evidence),
    ``poison_rank`` (None, or the 1-based best poison rank in the window) and
    ``prr_at_k`` (exactly the expected cutoffs, numeric).  Clean rows are the
    same schema over the clean corpus, so they must contain no poison
    document.  A ``None`` rank is legitimate data; an absent key is not.
    Nothing is coerced or defaulted.
    """
    retrieved = _require_doc_ids(row, "retrieved_doc_ids")
    generation = _require_doc_ids(row, "generation_evidence_doc_ids")
    if retrieved[: len(generation)] != generation:
        raise ValueError(
            "Generation evidence is not a prefix of the diagnostic ranking; "
            "PRR@k and ASR would describe different retrievals."
        )
    if row.get("condition") == "clean" and poison_set & (set(retrieved) | set(generation)):
        raise ValueError("A clean-condition record contains poison documents.")

    poison_retrieved = _require_field(row, "poison_retrieved")
    if not isinstance(poison_retrieved, bool):
        raise ValueError("poison_retrieved must be a boolean.")
    if poison_retrieved is not bool(poison_set & set(generation)):
        raise ValueError("poison_retrieved is inconsistent with generation evidence.")

    rank = _require_field(row, "poison_rank")
    if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool) or rank < 1):
        raise ValueError("poison_rank must be None or a positive integer.")
    ranks = [index + 1 for index, doc_id in enumerate(retrieved) if doc_id in poison_set]
    if rank != (min(ranks) if ranks else None):
        raise ValueError("Poison rank is inconsistent with the retrieved ranking.")

    prr = _require_field(row, "prr_at_k")
    if not isinstance(prr, dict):
        raise ValueError("prr_at_k must be an object keyed by cutoff.")
    expected_keys = {str(cutoff) for cutoff in multiseed.EXPECTED_CUTOFFS}
    if set(prr) != expected_keys:
        raise ValueError(
            f"prr_at_k cutoffs {sorted(prr)} differ from the expected {sorted(expected_keys, key=int)}."
        )
    for cutoff in multiseed.EXPECTED_CUTOFFS:
        value = prr[str(cutoff)]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"prr_at_k[{cutoff}] must be a number.")
        if value != float(bool(poison_set & set(retrieved[:cutoff]))):
            raise ValueError(f"Poison retrieval rate at {cutoff} is inconsistent.")


def validate_completed_cell(
    cell_dir: Path,
    *,
    frozen_inputs: FrozenMatrixInputs | None = None,
    expected_provenance: dict | None = None,
) -> dict:
    """Validate a complete cell, independently re-verifying its poison provenance.

    ``frozen_inputs`` is mandatory: a cell is never accepted merely because
    its summary, manifest and raw rows agree with one another, since all of
    them could carry the same wrong fingerprint.  The raw-results file must
    also match the SHA-256 recorded in the summary (a byte-integrity check
    only; the semantic checks below are what establish correctness).  When
    ``expected_provenance`` is given (resume), the cell must have been produced
    at that exact commit and source fingerprint.  Summaries written before the
    results hash existed are rejected rather than silently trusted.
    """
    if frozen_inputs is None:
        raise ValueError(
            "Independent poison-provenance verification requires the frozen "
            "inputs (held-out manifest, configs and clean dataset); refusing "
            "to trust fingerprints stored inside the cell."
        )
    manifest_path = cell_dir / "poison.manifest.json"
    summary_path = cell_dir / "summary.json"
    results_path = cell_dir / "results.jsonl"
    if not all(path.is_file() for path in (manifest_path, summary_path, results_path)):
        raise ValueError(f"Cell is incomplete: {cell_dir}")
    manifest = _read_json(manifest_path)
    summary = _read_json(summary_path)
    if manifest.get("schema") != CELL_SCHEMA or summary.get("schema") != CELL_SCHEMA:
        raise ValueError(f"Cell uses an unsupported schema: {cell_dir}")
    if summary.get("status") != CELL_COMPLETE_STATUS:
        raise ValueError(f"Cell summary is not complete: {cell_dir}")
    if summary.get("is_final_run") is not False or manifest.get("is_final_run") is not False:
        raise ValueError("A cell must not claim final statistical conclusions.")
    if manifest.get("execution_mode") != "heldout_matrix":
        raise ValueError("Only held-out matrix cells can be aggregated, not smoke tests.")
    provenance = validate_git_provenance(manifest)
    if expected_provenance is not None and provenance != {
        key: expected_provenance.get(key) for key in provenance
    }:
        raise ValueError(
            "Cell was produced at a different commit or source fingerprint than the current run."
        )
    recorded_hash = summary.get("results_sha256")
    if not isinstance(recorded_hash, str) or not SHA256_PATTERN.fullmatch(recorded_hash):
        raise ValueError(
            "Cell summary lacks a valid results_sha256; results.jsonl integrity cannot be established."
        )
    if _sha256_file(results_path) != recorded_hash:
        raise ValueError("results.jsonl does not match the SHA-256 recorded in the summary.")
    rows = _read_jsonl(results_path)  # parsed only once its bytes are known to match

    poisoned = verify_cell_provenance(manifest, frozen_inputs)
    recomputed = poison_instances_fingerprint(frozen_inputs.clean_data, poisoned)
    cell_id = manifest["cell_id"]
    if cell_dir.name != cell_id:
        raise ValueError(f"Cell directory name {cell_dir.name!r} differs from its cell ID {cell_id!r}.")
    for label, stored in (
        ("manifest", manifest.get("poison_instance_fingerprint")),
        ("summary", summary.get("poison_instance_fingerprint")),
    ):
        if stored != recomputed:
            raise ValueError(f"Cell {label} poison fingerprint differs from the independently recomputed value.")
    selected_ids = manifest["dataset"]["selected_query_ids"]
    query_count = summary.get("query_count")
    if (
        summary.get("cell_id") != cell_id
        or isinstance(query_count, bool)
        or query_count != len(selected_ids)
    ):
        raise ValueError("Cell summary identity or query count differs from manifest.")
    evidence = summary.get("execution_evidence")
    raw_count = evidence.get("raw_record_count") if isinstance(evidence, dict) else None
    if isinstance(raw_count, bool) or raw_count != len(rows):
        raise ValueError("Summary execution evidence is missing or its raw record count differs from results.jsonl.")

    expected_poison = {
        query["query_id"]: (sorted(query["poison_doc_ids"]), query["poison_target_answer"])
        for query in poisoned["queries"]
    }
    expected_count = len(multiseed.PIPELINES) * len(multiseed.CONDITIONS) * len(selected_ids)
    if len(rows) != expected_count:
        raise ValueError(f"Cell has {len(rows)} records; expected {expected_count}.")
    selected_set = set(selected_ids)
    # Bind every raw row to the frozen dataset, not just its paired counterpart.
    frozen_gold_by_id = {
        query["query_id"]: query["gold_answer"] for query in frozen_inputs.clean_data["queries"]
    }
    if set(frozen_gold_by_id) != selected_set:
        raise ValueError("Frozen query IDs differ from the selected cell query IDs.")
    indexed = {}
    for row in rows:
        key = (row.get("pipeline"), row.get("query_id"), row.get("condition"))
        if not all(isinstance(part, str) for part in key):
            raise ValueError(f"Invalid matrix record identity: {key}.")
        if key in indexed:
            raise ValueError(f"Duplicate matrix record: {key}.")
        if key[0] not in multiseed.PIPELINES or key[1] not in selected_set or key[2] not in multiseed.CONDITIONS:
            raise ValueError(f"Invalid matrix record identity: {key}.")
        if row.get("cell_id") != cell_id or row.get("poison_instance_fingerprint") != recomputed:
            raise ValueError("Raw record provenance differs from the independently verified cell.")
        expected_ids, expected_target = expected_poison[key[1]]
        if sorted(row.get("poison_doc_ids", [])) != expected_ids or row.get("poison_target_answer") != expected_target:
            raise ValueError("Raw record poison documents or target differ from the replayed poison instance.")
        for text_field in ("answer", "gold_answer"):
            if not isinstance(_require_field(row, text_field), str):
                raise ValueError(f"Raw record field {text_field!r} must be a string.")
        if row["gold_answer"] != frozen_gold_by_id[key[1]]:
            raise ValueError("Raw gold answer differs from the frozen clean dataset.")
        if row.get("answer_correct") is not bool(exact_match(row["answer"], row["gold_answer"])):
            raise ValueError("Raw answer correctness is inconsistent.")
        _validate_retrieval_record(row, set(expected_ids))
        indexed[key] = row
    for pipeline in multiseed.PIPELINES:
        for query_id in selected_ids:
            clean = indexed.get((pipeline, query_id, "clean"))
            poisoned_row = indexed.get((pipeline, query_id, "poisoned"))
            if clean is None or poisoned_row is None:
                raise ValueError("Cell is missing a paired clean/poisoned record.")
            if clean["gold_answer"] != poisoned_row["gold_answer"] or clean["poison_doc_ids"] != poisoned_row["poison_doc_ids"]:
                raise ValueError("Paired records disagree on ground truth or poison instances.")
            if clean["query_untargeted_degradation"] != poisoned_row["query_untargeted_degradation"]:
                raise ValueError("Paired degradation is inconsistent.")
            expected_degradation = bool(clean["answer_correct"] and not poisoned_row["answer_correct"])
            if clean["query_untargeted_degradation"] is not expected_degradation:
                raise ValueError("Query degradation is not computed from its clean/poison pair.")
            if poisoned_row["targeted_asr"] is not bool(exact_match(poisoned_row["answer"], poisoned_row["poison_target_answer"])):
                raise ValueError("Targeted ASR is inconsistent.")
    summarized = summary.get("pipelines")
    if not isinstance(summarized, dict) or set(summarized) != set(multiseed.PIPELINES):
        raise ValueError("Cell summary lacks per-pipeline metrics for exactly the expected pipelines.")
    for pipeline in multiseed.PIPELINES:
        if summarized[pipeline] != recompute_pipeline_summary(indexed, pipeline, selected_ids):
            raise ValueError(f"Summary metrics for {pipeline!r} differ from the raw records.")
    # Recompute the paired comparison from the same raw clean/poison rows.
    paired_rows = {}
    for pipeline in multiseed.PIPELINES:
        paired_rows[pipeline] = [
            {
                "query_id": query_id,
                "clean_condition": indexed[(pipeline, query_id, "clean")],
                "poisoned_condition": indexed[(pipeline, query_id, "poisoned")],
                "query_untargeted_degradation": indexed[(pipeline, query_id, "poisoned")]["query_untargeted_degradation"],
            }
            for query_id in selected_ids
        ]
    expected_paired = paired_differences(paired_rows["dense"], paired_rows["rcd"])
    if summary.get("paired_dense_minus_rcd") != expected_paired:
        raise ValueError("Paired Dense-minus-RCD summary differs from raw paired records.")
    return {
        "manifest": manifest,
        "summary": summary,
        "rows": indexed,
        "selected_ids": selected_ids,
        "recomputed_poison_instance_fingerprint": recomputed,
        "git_commit_sha": provenance["commit_sha"],
        "source_fingerprint": provenance["source_fingerprint"],
    }


def recompute_pipeline_summary(indexed: dict, pipeline: str, query_ids: list) -> dict:
    """Recompute ``summarize_pipeline`` output from validated flat raw records.

    Mirrors ``summarize_pipeline`` exactly so a summary that disagrees with
    its own raw records is detectable.  Rows are assumed already validated.
    """
    clean = [indexed[(pipeline, query_id, "clean")] for query_id in query_ids]
    poisoned = [indexed[(pipeline, query_id, "poisoned")] for query_id in query_ids]
    total = len(query_ids)
    retrieved = [row for row in poisoned if row["poison_retrieved"]]
    prr = {
        f"prr@{k}": _rate(sum(row["prr_at_k"][str(k)] == 1.0 for row in poisoned), total)
        for k in multiseed.EXPECTED_CUTOFFS
    }
    return {
        "query_count": total,
        "clean_condition": {
            "clean_answer_accuracy": _rate(sum(row["answer_correct"] for row in clean), total),
        },
        "poisoned_condition": {
            "poisoned_answer_accuracy": _rate(sum(row["answer_correct"] for row in poisoned), total),
            "poison_retrieval_rate": prr,
            "targeted_asr": _rate(sum(row["targeted_asr"] for row in poisoned), total),
            "asr_given_poison_retrieved": _rate(
                sum(row["targeted_asr"] for row in retrieved), len(retrieved)
            ),
        },
        "query_untargeted_degradation": _rate(
            sum(row["query_untargeted_degradation"] for row in poisoned), total
        ),
    }


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                raise ValueError(f"Blank JSONL record at {path}:{number}.")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Non-object JSONL record at {path}:{number}.")
            rows.append(value)
    return rows


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
    """Evaluate the two frozen pipelines against a single replayed snapshot.

    Each pipeline is evaluated with its OWN configuration; the settings that
    must match are validated first, so any treatment difference is explicit.
    Observed retrieval/generation counts are compared with the preflight
    formula for this cell and a mismatch aborts the cell.
    """
    validate_shared_pipeline_settings(dense_config, rcd_config)
    pipeline_configs = {"dense": dense_config, "rcd": rcd_config}
    all_rows: dict[str, list[dict]] = {}
    retrievers = build_matched_retrievers(dense_config, rcd_config, clean_data, poisoned_data)
    records_written = 0
    retrieval_seconds = 0.0
    diagnostic_retrieval_seconds = 0.0
    generation_seconds = 0.0
    observed_normal = observed_diagnostic = observed_generations = 0
    inner_operations = {name: 0 for name in pipeline_configs}
    inner_operations_known = {name: True for name in pipeline_configs}
    with results_path.open("x", encoding="utf-8") as output:
        for pipeline, (clean_retriever, poisoned_retriever) in retrievers.items():
            config = pipeline_configs[pipeline]
            rows = evaluate_pipeline(
                pipeline=pipeline,
                clean_retriever=clean_retriever,
                poisoned_retriever=poisoned_retriever,
                clean_data=clean_data,
                poisoned_data=poisoned_data,
                generator=generator,
                top_k=validated_top_k(config, pipeline),
                max_tokens=int(config["max_tokens"]),
            )
            all_rows[pipeline] = rows
            for row in rows:
                for record in flatten_query_result_records(row):
                    retrieval_seconds += record["retrieval_elapsed_seconds"]
                    diagnostic_retrieval_seconds += record.get(
                        "diagnostic_retrieval_elapsed_seconds", 0.0
                    )
                    generation_seconds += record["generation"]["elapsed_seconds"]
                    accounting = record["retrieval_call_accounting"]
                    observed_normal += accounting["normal_retrieval_calls"]
                    observed_diagnostic += accounting["diagnostic_retrieval_calls"]
                    observed_generations += 1
                    for key in ("normal_inner_retrieval_operations", "diagnostic_inner_retrieval_operations"):
                        if accounting[key] is None:
                            inner_operations_known[pipeline] = False
                        else:
                            inner_operations[pipeline] += accounting[key]
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
    expected = estimate_workload(
        dense_config, rcd_config, query_count=len(clean_data["queries"]), cell_count=1
    )
    observed = {
        "evaluation_generation_calls": observed_generations,
        "normal_retrieval_calls": observed_normal,
        "diagnostic_retrieval_calls": observed_diagnostic,
        "retrieval_calls": observed_normal + observed_diagnostic,
    }
    mismatched = {
        key: {"expected": expected[key], "observed": value}
        for key, value in observed.items()
        if expected[key] != value
    }
    if mismatched:
        raise RuntimeError(
            f"Observed workload differs from the preflight estimate: {mismatched}"
        )
    return {
        "pipelines": {pipeline: summarize_pipeline(rows) for pipeline, rows in all_rows.items()},
        "paired_dense_minus_rcd": paired_differences(all_rows["dense"], all_rows["rcd"]),
        "execution_evidence": {
            "raw_record_count": records_written,
            "expected_raw_record_count": len(clean_data["queries"]) * 4,
            "retrieval_elapsed_seconds": retrieval_seconds,
            "diagnostic_retrieval_elapsed_seconds": diagnostic_retrieval_seconds,
            "generation_elapsed_seconds": generation_seconds,
            "observed_workload": observed,
            "inner_retrieval_operations": {
                name: (inner_operations[name] if inner_operations_known[name] else None)
                for name in pipeline_configs
            },
        },
    }


def _expected_cell_ids() -> list[str]:
    ids = [_cell_id(*cell) for cell in matrix_cells()]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("The matrix definition must contain unique, non-empty cell IDs.")
    return ids


def _preflight_compatible(stored: Any, current: dict) -> bool:
    """Compare a stored plan's preflight with the current one.

    Plans written before the workload accounting existed lack the new fields
    and recorded ``retrieval_calls`` as the normal count only; for those the
    legacy fields are compared and the (known-incomplete) legacy total is not.
    """
    if not isinstance(stored, dict):
        return False
    if stored == current:
        return True
    if "normal_retrieval_calls" in stored:
        return False
    return all(
        stored[key] == current.get(key) for key in set(stored) - {"retrieval_calls"}
    )


def _new_plan(
    experiment_id: str,
    preflight_data: dict,
    git_sha: str,
    expected_ids: list[str],
    source_fingerprint: str | None = None,
) -> dict:
    now = _utc_now()
    return {
        "schema": PLAN_SCHEMA,
        "experiment_id": experiment_id,
        "created_at_utc": now,
        "updated_at_utc": now,
        "status": "running",
        "scientific_status": PLAN_SCIENTIFIC_STATUS,
        "is_final_run": False,
        "git": {
            "commit_sha": git_sha,
            "dirty_check_scope": DIRTY_CHECK_SCOPE,
            "source_fingerprint": source_fingerprint,
        },
        "preflight": preflight_data,
        "expected_cell_count": len(expected_ids),
        "expected_cell_ids": list(expected_ids),
        "completed_cell_count": 0,
        "completed_cell_ids": [],
        "failed_or_incomplete_cell_count": len(expected_ids),
        "failed_or_incomplete_cell_ids": list(expected_ids),
        "cell_failures": {},
        "failure": None,
        "attempts": [],
    }


def _upgrade_legacy_plan(plan: dict, expected_ids: list[str]) -> dict:
    """Add the lifecycle fields to an older plan without changing its history."""
    upgraded = dict(plan)
    created = upgraded.get("created_at_utc") or _utc_now()
    defaults = {
        "created_at_utc": created,
        "updated_at_utc": created,
        "scientific_status": PLAN_SCIENTIFIC_STATUS,
        "is_final_run": False,
        "git": {"commit_sha": None, "dirty_check_scope": "unknown (legacy plan)"},
        "expected_cell_count": len(expected_ids),
        "expected_cell_ids": list(expected_ids),
        "completed_cell_count": 0,
        "completed_cell_ids": [],
        "failed_or_incomplete_cell_count": len(expected_ids),
        "failed_or_incomplete_cell_ids": list(expected_ids),
        "cell_failures": {},
        "failure": None,
        "attempts": [],
    }
    added = [key for key in defaults if key not in upgraded]
    for key in added:
        upgraded[key] = defaults[key]
    if added:
        upgraded["legacy_plan_upgraded_fields"] = added
    return upgraded


def _record_progress(
    plan: dict,
    plan_path: Path,
    *,
    expected_ids: list[str],
    completed: list[str],
    cell_failures: dict,
    status: str | None = None,
    failure: dict | None = None,
    attempt: dict | None = None,
) -> dict:
    """Update the persisted plan so every expected cell is accounted for once."""
    completed_unique = list(dict.fromkeys(cell for cell in completed if cell in expected_ids))
    completed_set = set(completed_unique)
    incomplete = [cell for cell in expected_ids if cell not in completed_set]
    plan["completed_cell_ids"] = [cell for cell in expected_ids if cell in completed_set]
    plan["completed_cell_count"] = len(completed_unique)
    plan["failed_or_incomplete_cell_ids"] = incomplete
    plan["failed_or_incomplete_cell_count"] = len(incomplete)
    plan["cell_failures"] = {cell: cell_failures[cell] for cell in incomplete if cell in cell_failures}
    plan["updated_at_utc"] = _utc_now()
    if failure is not None:
        plan["failure"] = failure
    if attempt is not None:
        attempt["ended_at_utc"] = plan["updated_at_utc"]
    if status is not None:
        plan["status"] = status
        if status == "complete":
            plan["completed_at_utc"] = plan["updated_at_utc"]
    _write_json_atomic(plan_path, plan)
    return plan


def _terminal_status(completed_count: int, expected_count: int) -> str:
    if completed_count == expected_count:
        return "complete"
    return "partial" if completed_count else "failed"


def _cell_failure_summary(error: BaseException) -> dict:
    return {"error_type": type(error).__name__, "error": str(error)[:1000]}


def _read_previous_failure(cell_dir: Path) -> dict | None:
    try:
        recorded = _read_json(cell_dir / "failure.json")
    except (OSError, ValueError):
        return None
    return {
        "error_type": recorded.get("error_type"),
        "error": str(recorded.get("error", ""))[:1000],
        "source": "failure.json",
    }


ARCHIVE_DIRNAME = "_recovery_archive"


class RecoveryRefused(RuntimeError):
    """Recovery of an incomplete cell is unsafe; nothing was modified."""


def _file_digests(directory: Path) -> dict[str, dict]:
    digests = {}
    for entry in sorted(directory.iterdir()):
        if entry.is_file():
            digests[entry.name] = {
                "sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
                "bytes": entry.stat().st_size,
            }
        else:
            digests[entry.name] = {"sha256": None, "bytes": None, "kind": "non_file"}
    return digests


def _archived_attempt_dirs(output_root: Path, cell_id: str) -> list[Path]:
    parent = output_root / ARCHIVE_DIRNAME / cell_id
    if not parent.is_dir():
        return []
    return sorted(path for path in parent.iterdir() if path.is_dir() and path.name.startswith("attempt_"))


def _select_reusable_manifest(
    *,
    output_root: Path,
    cell_dir: Path,
    cell_id: str,
    frozen: FrozenMatrixInputs,
    git_sha: str,
    source_fingerprint: str | None = None,
) -> dict | None:
    """Return the one verified poison manifest recorded for ``cell_id``, if any.

    Candidates are the in-place manifest and every archived one.  This only
    reads.  The original poison instance is reused ONLY if every candidate
    (a) parses, (b) passes the full independent provenance verification,
    (c) has a recomputed poison fingerprint equal to its stored one, (d) was
    written at the current commit, and (e) all candidates are the same poison
    instance.  Otherwise recovery is refused; a semantic poison instance is
    never silently regenerated when one existed.  ``None`` means no manifest
    was ever written, so no poison instance exists to preserve.
    """
    paths = [cell_dir / "poison.manifest.json"]
    paths += [attempt / "poison.manifest.json" for attempt in _archived_attempt_dirs(output_root, cell_id)]
    verified: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            manifest = _read_json(path)
            poisoned = verify_cell_provenance(manifest, frozen)
            if manifest.get("cell_id") != cell_id:
                raise ValueError("manifest belongs to a different cell")
            if poison_instances_fingerprint(frozen.clean_data, poisoned) != manifest.get(
                "poison_instance_fingerprint"
            ):
                raise ValueError("stored poison fingerprint does not match the recomputed one")
            if (manifest.get("git") or {}).get("commit_sha") != git_sha:
                raise ValueError("manifest was written at a different Git commit")
            if (manifest.get("git") or {}).get("source_fingerprint") != source_fingerprint:
                raise ValueError("manifest was written from a different source fingerprint")
        except Exception as error:
            raise RecoveryRefused(
                f"Refusing to recover {cell_id}: {path} cannot be verified against the frozen "
                f"inputs ({type(error).__name__}: {error}). Nothing was modified. Inspect the "
                "directory manually; do not delete it. Restore the frozen commit or move the "
                "directory aside yourself if you decide to discard this attempt."
            ) from error
        verified.append(manifest)
    if len({m["poison_instance_fingerprint"] for m in verified}) > 1:
        raise RecoveryRefused(
            f"Refusing to recover {cell_id}: its manifests describe different poison instances. "
            "Nothing was modified; a supervisor must decide which instance is authoritative."
        )
    return verified[0] if verified else None


def _archive_incomplete_cell(output_root: Path, cell_dir: Path, cell_id: str) -> dict:
    """Move an incomplete cell directory, intact, into an immutable attempt archive.

    ``os.rename`` is atomic and copies nothing, so every file is preserved
    byte-for-byte; an existing archive entry is never overwritten.
    """
    parent = output_root / ARCHIVE_DIRNAME / cell_id
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / f"attempt_{len(_archived_attempt_dirs(output_root, cell_id)) + 1:03d}"
    if target.exists():
        raise FileExistsError(f"Recovery archive already exists: {target}")
    digests = _file_digests(cell_dir)
    prior_failure = _read_previous_failure(cell_dir)
    os.rename(cell_dir, target)
    record = {
        "cell_id": cell_id,
        "archived_to": str(target.relative_to(output_root)),
        "archived_files": digests,
        "prior_failure": prior_failure,
        "archived_at_utc": _utc_now(),
    }
    _write_json_exclusive(parent / f"{target.name}.record.json", record)
    return record


def run_matrix(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    experiment_id: str,
    heldout_path: Path = DEFAULT_HELDOUT_MANIFEST,
    dense_config_path: Path = DEFAULT_DENSE_CONFIG,
    rcd_config_path: Path = DEFAULT_RCD_CONFIG,
    resume: bool = False,
    recover_incomplete: bool = False,
) -> dict:
    """Execute cells not already completed in a compatible matrix directory.

    The persisted ``plan.json`` always ends in an unambiguous state:
    ``complete`` (every expected cell completed AND independently validated),
    ``partial`` (some, but not all) or ``failed`` (none).  ``running`` at rest
    means the process was killed without a chance to record anything and must
    be treated as unfinished.  Interrupts and other termination signals are
    recorded and then re-raised; they are never swallowed.
    """
    if not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be a non-empty filename-safe value.")
    if recover_incomplete and not resume:
        raise ValueError("recover_incomplete requires resume=True.")
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
    git_sha = git_commit_sha(default="", repo_root=REPOSITORY_ROOT)
    if not git_sha:
        raise RuntimeError("Unable to determine the Git commit; refusing to run without provenance.")
    source_fingerprint = compute_source_fingerprint()
    expected_ids = _expected_cell_ids()
    output_root = _ensure_output_outside_repository(output_dir) / experiment_id
    plan_path = output_root / "plan.json"
    if output_root.exists() and not resume:
        raise FileExistsError(f"Output directory already exists: {output_root}")
    if resume:
        try:
            plan = _read_json(plan_path)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"Cannot resume: no matrix plan at {plan_path}.") from error
        except ValueError as error:
            raise ValueError(f"Existing matrix plan is unreadable: {plan_path}.") from error
        if plan.get("schema") != PLAN_SCHEMA or plan.get("experiment_id") not in (None, experiment_id):
            raise ValueError("Existing matrix plan has a different schema or experiment ID.")
        if not _preflight_compatible(plan.get("preflight"), preflight_data):
            raise ValueError("Existing matrix plan is incompatible with current frozen inputs.")
        recorded_commit = (plan.get("git") or {}).get("commit_sha")
        if recorded_commit is not None and recorded_commit != git_sha:
            raise ValueError(
                "Existing matrix plan was started at a different Git commit "
                f"({recorded_commit}); resuming at {git_sha} would mix code versions."
            )
        recorded_fingerprint = (plan.get("git") or {}).get("source_fingerprint")
        if recorded_fingerprint is not None and recorded_fingerprint != source_fingerprint:
            raise ValueError(
                "Existing matrix plan was started from a different source fingerprint; "
                "an executable input changed since the first attempt, so resuming would "
                "mix code versions."
            )
        plan = _upgrade_legacy_plan(plan, expected_ids)
        if plan["expected_cell_ids"] != expected_ids:
            raise ValueError("Existing matrix plan lists different expected cells.")
        if recorded_fingerprint is None:
            plan["git"] = {**plan["git"], "source_fingerprint": source_fingerprint}
            plan.setdefault("legacy_plan_upgraded_fields", []).append("git.source_fingerprint")
    else:
        output_root.mkdir(parents=True)
        plan = _new_plan(experiment_id, preflight_data, git_sha, expected_ids, source_fingerprint)
    attempt = {
        "attempt": len(plan["attempts"]) + 1,
        "resume": resume,
        "started_at_utc": _utc_now(),
        "ended_at_utc": None,
        "outcome": "running",
        "recover_incomplete": recover_incomplete,
        "recovered_cell_ids": [],
    }
    plan.setdefault("recoveries", [])
    plan["attempts"].append(attempt)
    plan["status"] = "running"
    plan["updated_at_utc"] = attempt["started_at_utc"]
    _write_json_atomic(plan_path, plan)

    completed: list[str] = []
    cell_failures: dict[str, dict] = {}
    stage = "setup"
    try:
        frozen = load_frozen_matrix_inputs(
            heldout_path=heldout_path,
            dense_config_path=dense_config_path,
            rcd_config_path=rcd_config_path,
        )
        set_seed(FROZEN_RUNTIME_SEED)
        generator = build_generator(frozen.rcd_config)
        stage = "cell_loop"
        for attack_family, intensity, poison_seed in matrix_cells():
            cell_id = _cell_id(attack_family, intensity, poison_seed)
            # Provenance must hold for the WHOLE run, not just at start.
            _require_clean_relevant_inputs(require_tracked_runner=True)
            if git_commit_sha(default="", repo_root=REPOSITORY_ROOT) != git_sha:
                raise RuntimeError("Git HEAD changed during the run; cells would mix code versions.")
            if compute_source_fingerprint() != source_fingerprint:
                raise RuntimeError("Source fingerprint changed during the run; cells would mix code versions.")
            cell_dir = output_root / cell_id
            manifest_path = cell_dir / "poison.manifest.json"
            results_path = cell_dir / "results.jsonl"
            summary_path = cell_dir / "summary.json"
            failure_path = cell_dir / "failure.json"
            if summary_path.exists():
                try:
                    validate_completed_cell(
                        cell_dir,
                        frozen_inputs=frozen,
                        expected_provenance={
                            "commit_sha": git_sha,
                            "source_fingerprint": source_fingerprint,
                        },
                    )
                except Exception as error:  # corrupt or incompatible: never accept, never delete
                    if not recover_incomplete:
                        cell_failures[cell_id] = {
                            **_cell_failure_summary(error),
                            "source": "resume_validation",
                            "hint": "Re-run with --resume --recover-incomplete to archive this "
                                    "cell intact and re-evaluate it from its verified manifest.",
                        }
                        continue
                    # Explicit opt-in: fall through to archive-and-retry below.
                else:
                    completed.append(cell_id)
                    continue
            reusable_manifest = None
            if cell_dir.exists():
                if not recover_incomplete:
                    # Incomplete artifacts from an earlier attempt are preserved.
                    cell_failures[cell_id] = _read_previous_failure(cell_dir) or {
                        "error_type": "IncompleteCell",
                        "error": "Cell directory exists without a completed summary. "
                                 "Re-run with --resume --recover-incomplete to archive it and retry.",
                        "source": "incomplete_directory",
                    }
                    continue
            if cell_dir.exists() or _archived_attempt_dirs(output_root, cell_id):
                # Also covers a crash between archiving and recreating the cell.
                try:
                    reusable_manifest = _select_reusable_manifest(
                        output_root=output_root, cell_dir=cell_dir, cell_id=cell_id,
                        frozen=frozen, git_sha=git_sha,
                        source_fingerprint=source_fingerprint,
                    )
                except RecoveryRefused as error:
                    cell_failures[cell_id] = {**_cell_failure_summary(error), "source": "recovery_refused"}
                    continue
            if cell_dir.exists():
                try:
                    record = _archive_incomplete_cell(output_root, cell_dir, cell_id)
                except Exception as error:
                    cell_failures[cell_id] = {**_cell_failure_summary(error), "source": "recovery_archive_failed"}
                    continue
                record.update(
                    attempt=attempt["attempt"],
                    manifest_reused=reusable_manifest is not None,
                    reused_poison_instance_fingerprint=(
                        reusable_manifest["poison_instance_fingerprint"] if reusable_manifest else None
                    ),
                )
                plan["recoveries"].append(record)
                attempt["recovered_cell_ids"].append(cell_id)
                _write_json_atomic(plan_path, plan)
            cell_dir.mkdir()
            started = time.perf_counter()
            try:
                if reusable_manifest is not None:
                    manifest = reusable_manifest  # the original, verified poison instance
                else:
                    attack, attack_config = _attack(attack_family, generator)
                    poisoned_data = inject_poisons(
                        frozen.clean_data, attack, n_poison=intensity, poison_rate=1.0,
                        seed=poison_seed, attacked_query_ids=frozen.heldout_ids,
                    )
                    manifest = build_cell_manifest(
                        cell_id=cell_id, clean_data=frozen.clean_data, poisoned_data=poisoned_data,
                        attack_family=attack_family, intensity=intensity, poison_seed=poison_seed,
                        heldout_fingerprint=frozen.heldout_fingerprint,
                        config_hashes=frozen.config_hashes,
                        dense_config=frozen.dense_config, rcd_config=frozen.rcd_config,
                        git_sha=git_sha, git_dirty=False,
                        source_fingerprint=source_fingerprint,
                    )
                    manifest["attack"]["configuration"] = attack_config
                # Atomic: a crash can never leave a truncated immutable manifest.
                _write_json_atomic(manifest_path, manifest)
                replayed = replay_cell_manifest(frozen.clean_data, manifest)
                set_seed(FROZEN_RUNTIME_SEED)
                metrics = evaluate_cell(
                    clean_data=frozen.clean_data, poisoned_data=replayed,
                    dense_config=frozen.dense_config, rcd_config=frozen.rcd_config,
                    generator=generator, manifest=manifest, results_path=results_path,
                )
                if (
                    metrics["execution_evidence"]["raw_record_count"]
                    != metrics["execution_evidence"]["expected_raw_record_count"]
                ):
                    raise RuntimeError("Evaluation did not emit every expected raw record.")
                # Atomic: a crash can never leave a truncated summary that looks "present".
                _write_json_atomic(
                    summary_path,
                    {
                        "schema": CELL_SCHEMA,
                        "status": CELL_COMPLETE_STATUS,
                        "is_final_run": False,
                        "cell_id": cell_id,
                        "manifest_path": str(manifest_path),
                        "results_path": str(results_path),
                        "results_sha256": _sha256_file(results_path),
                        "poison_instance_fingerprint": manifest["poison_instance_fingerprint"],
                        "query_count": MATRIX_QUERY_COUNT,
                        "runtime_seconds": time.perf_counter() - started,
                        **metrics,
                    },
                )
                # Hold fresh output to the same standard the aggregator applies.
                validate_completed_cell(
                    cell_dir,
                    frozen_inputs=frozen,
                    expected_provenance={
                        "commit_sha": git_sha,
                        "source_fingerprint": source_fingerprint,
                    },
                )
                completed.append(cell_id)
            except Exception as error:
                cell_failures[cell_id] = _cell_failure_summary(error)
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
            _record_progress(
                plan, plan_path, expected_ids=expected_ids, completed=completed,
                cell_failures=cell_failures,
            )
    except BaseException as error:
        # Record, then re-raise: KeyboardInterrupt/SystemExit must propagate and
        # must never be represented as success.
        attempt["outcome"] = "interrupted" if not isinstance(error, Exception) else "failed"
        failure = {
            "stage": stage,
            "interrupted": not isinstance(error, Exception),
            **_cell_failure_summary(error),
        }
        try:
            _record_progress(
                plan, plan_path, expected_ids=expected_ids, completed=completed,
                cell_failures=cell_failures,
                status=_terminal_status(len(set(completed)), len(expected_ids)),
                failure=failure, attempt=attempt,
            )
        except Exception as write_error:  # keep the original error primary
            if hasattr(error, "add_note"):
                error.add_note(f"Additionally, the matrix plan could not be updated: {write_error!r}")
        raise
    status = _terminal_status(len(set(completed)), len(expected_ids))
    attempt["outcome"] = status
    _record_progress(
        plan, plan_path, expected_ids=expected_ids, completed=completed,
        cell_failures=cell_failures, status=status, attempt=attempt,
    )
    return {
        "experiment_id": experiment_id,
        "output_root": str(output_root),
        "plan_path": str(plan_path),
        "status": plan["status"],
        "expected_cell_count": plan["expected_cell_count"],
        "completed_cell_count": plan["completed_cell_count"],
        "failed_or_incomplete_cell_count": plan["failed_or_incomplete_cell_count"],
        "completed_cells": list(plan["completed_cell_ids"]),
        "failed_or_incomplete_cells": list(plan["failed_or_incomplete_cell_ids"]),
    }


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
            git_sha=git_commit_sha(repo_root=REPOSITORY_ROOT),
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
            or evidence.get("diagnostic_retrieval_elapsed_seconds", 0.0) < 0
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
    parser.add_argument(
        "--recover-incomplete", action="store_true",
        help="With --resume: archive (never delete) incomplete cell directories and retry them "
             "from their verified poison manifest.",
    )
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-query-count", type=int, default=2)
    args = parser.parse_args()
    if args.preflight and args.smoke_test:
        parser.error("--preflight and --smoke-test cannot be combined.")
    if args.recover_incomplete and not args.resume:
        parser.error("--recover-incomplete requires --resume.")
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
            recover_incomplete=args.recover_incomplete,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
