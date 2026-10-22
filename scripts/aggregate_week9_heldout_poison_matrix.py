#!/usr/bin/env python3
"""Validate and aggregate completed Week 9 held-out poisoning matrix cells."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import scripts.aggregate_week9_multiseed_results as multiseed
from scripts.run_week9_heldout_poison_matrix import (
    CELL_SCHEMA,
    MATRIX_ATTACKS,
    MATRIX_INTENSITIES,
    MATRIX_QUERY_COUNT,
    _cell_id,
    matrix_cells,
)
from src.evaluation.metrics import exact_match


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}.")
    return value


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


def validate_completed_cell(cell_dir: Path) -> dict:
    """Validate a complete cell's immutable manifest, summary, and raw records."""
    manifest_path = cell_dir / "poison.manifest.json"
    summary_path = cell_dir / "summary.json"
    results_path = cell_dir / "results.jsonl"
    if not all(path.is_file() for path in (manifest_path, summary_path, results_path)):
        raise ValueError(f"Cell is incomplete: {cell_dir}")
    manifest, summary, rows = (
        _read_json(manifest_path),
        _read_json(summary_path),
        _read_jsonl(results_path),
    )
    if manifest.get("schema") != CELL_SCHEMA or summary.get("schema") != CELL_SCHEMA:
        raise ValueError(f"Cell uses an unsupported schema: {cell_dir}")
    if summary.get("status") != "complete_heldout_cell_not_statistically_conclusive":
        raise ValueError(f"Cell summary is not complete: {cell_dir}")
    if summary.get("is_final_run") is not False:
        raise ValueError("A cell must not claim final statistical conclusions.")
    cell_id = manifest.get("cell_id")
    attack = manifest.get("attack", {})
    if cell_id != _cell_id(attack.get("family"), attack.get("intensity"), manifest.get("seed_protocol", {}).get("poison_seed")):
        raise ValueError(f"Cell ID does not match its attack metadata: {cell_dir}")
    selected_ids = manifest.get("dataset", {}).get("selected_query_ids")
    if not isinstance(selected_ids, list) or len(selected_ids) != MATRIX_QUERY_COUNT or len(set(selected_ids)) != len(selected_ids):
        raise ValueError("Cell manifest must contain exactly 300 unique query IDs.")
    if summary.get("cell_id") != cell_id or summary.get("query_count") != len(selected_ids):
        raise ValueError("Cell summary identity or query count differs from manifest.")
    fingerprint = manifest.get("poison_instance_fingerprint")
    if summary.get("poison_instance_fingerprint") != fingerprint:
        raise ValueError("Cell summary poison fingerprint differs from manifest.")
    expected_count = len(multiseed.PIPELINES) * len(multiseed.CONDITIONS) * len(selected_ids)
    if len(rows) != expected_count:
        raise ValueError(f"Cell has {len(rows)} records; expected {expected_count}.")
    indexed = {}
    for row in rows:
        key = (row.get("pipeline"), row.get("query_id"), row.get("condition"))
        if key in indexed:
            raise ValueError(f"Duplicate matrix record: {key}.")
        if key[0] not in multiseed.PIPELINES or key[1] not in selected_ids or key[2] not in multiseed.CONDITIONS:
            raise ValueError(f"Invalid matrix record identity: {key}.")
        if row.get("cell_id") != cell_id or row.get("poison_instance_fingerprint") != fingerprint:
            raise ValueError("Raw record provenance differs from its cell manifest.")
        if row.get("answer_correct") is not bool(exact_match(row.get("answer", ""), row.get("gold_answer", ""))):
            raise ValueError("Raw answer correctness is inconsistent.")
        indexed[key] = row
    for pipeline in multiseed.PIPELINES:
        for query_id in selected_ids:
            clean = indexed.get((pipeline, query_id, "clean"))
            poisoned = indexed.get((pipeline, query_id, "poisoned"))
            if clean is None or poisoned is None:
                raise ValueError("Cell is missing a paired clean/poisoned record.")
            if clean["gold_answer"] != poisoned["gold_answer"] or clean["poison_doc_ids"] != poisoned["poison_doc_ids"]:
                raise ValueError("Paired records disagree on ground truth or poison instances.")
            if clean["query_untargeted_degradation"] != poisoned["query_untargeted_degradation"]:
                raise ValueError("Paired degradation is inconsistent.")
            expected_degradation = bool(clean["answer_correct"] and not poisoned["answer_correct"])
            if clean["query_untargeted_degradation"] is not expected_degradation:
                raise ValueError("Query degradation is not computed from its clean/poison pair.")
            if poisoned["targeted_asr"] is not bool(exact_match(poisoned["answer"], poisoned["poison_target_answer"])):
                raise ValueError("Targeted ASR is inconsistent.")
            for cutoff in multiseed.EXPECTED_CUTOFFS:
                expected_prr = float(bool(set(poisoned["poison_doc_ids"]) & set(poisoned["retrieved_doc_ids"][:cutoff])))
                if poisoned.get("prr_at_k", {}).get(str(cutoff)) != expected_prr:
                    raise ValueError(f"Poison retrieval rate at {cutoff} is inconsistent.")
    return {"manifest": manifest, "summary": summary, "rows": indexed, "selected_ids": selected_ids}


def aggregate_matrix(root: Path, *, bootstrap_replicates: int = multiseed.BOOTSTRAP_REPLICATES) -> dict:
    """Aggregate all 12 cells; incomplete, missing, or corrupt cells fail closed."""
    root = root.expanduser().resolve()
    cells = {}
    for attack_family, intensity, seed in matrix_cells():
        cell_id = _cell_id(attack_family, intensity, seed)
        cells[(attack_family, intensity, seed)] = validate_completed_cell(root / cell_id)
    groups = []
    for attack_family in MATRIX_ATTACKS:
        for intensity in MATRIX_INTENSITIES:
            seed_cells = [cells[(attack_family, intensity, seed)] for seed in multiseed.EXPECTED_SEEDS]
            reference = seed_cells[0]
            selected_ids = reference["selected_ids"]
            for cell in seed_cells[1:]:
                if cell["selected_ids"] != selected_ids:
                    raise ValueError("Seeds in a matrix condition have mismatched query IDs.")
                if cell["manifest"]["dataset"] != reference["manifest"]["dataset"]:
                    raise ValueError("Seeds in a matrix condition have mismatched dataset provenance.")
                if cell["manifest"]["attack"] != reference["manifest"]["attack"]:
                    raise ValueError("Seeds in a matrix condition have mismatched attack provenance.")
            all_rows = {
                (seed, pipeline, query_id, condition): cells[(attack_family, intensity, seed)]["rows"][(pipeline, query_id, condition)]
                for seed in multiseed.EXPECTED_SEEDS
                for pipeline in multiseed.PIPELINES
                for query_id in selected_ids
                for condition in multiseed.CONDITIONS
            }
            groups.append(
                {
                    "attack_family": attack_family,
                    "intensity": intensity,
                    "poison_seeds": list(multiseed.EXPECTED_SEEDS),
                    "query_count_per_seed": len(selected_ids),
                    "query_seed_observation_count": len(selected_ids) * len(multiseed.EXPECTED_SEEDS),
                    "repeated_queries_are_independent": False,
                    "poison_instance_fingerprints": [
                        cell["manifest"]["poison_instance_fingerprint"] for cell in seed_cells
                    ],
                    "per_seed": [
                        {
                            "poison_seed": seed,
                            "pipelines": {
                                pipeline: multiseed._pipeline_metrics(cell["rows"], pipeline, selected_ids)
                                for pipeline in multiseed.PIPELINES
                            },
                        }
                        for seed, cell in zip(multiseed.EXPECTED_SEEDS, seed_cells)
                    ],
                    "pooled_query_seed_observations": multiseed._pooled_metrics(
                        all_rows, multiseed.EXPECTED_SEEDS, selected_ids
                    ),
                    "pooled_paired_dense_minus_rcd": multiseed._pooled_paired(
                        all_rows, multiseed.EXPECTED_SEEDS, selected_ids
                    ),
                    "paired_bootstrap": multiseed.bootstrap_paired_intervals(
                        rows=all_rows,
                        seeds=multiseed.EXPECTED_SEEDS,
                        query_ids=selected_ids,
                        replicates=bootstrap_replicates,
                    ),
                }
            )
    return {
        "schema": "rag-poison-transfer.week9-heldout-poison-matrix-aggregate/v1",
        "status": "complete_heldout_matrix_not_statistically_conclusive",
        "is_final_run": False,
        "expected_cell_count": len(matrix_cells()),
        "completed_cell_count": len(cells),
        "groups": groups,
        "limitations": (
            "Each group reuses the same 300 query IDs across three poison seeds. "
            "The bootstrap resamples query-ID clusters retaining all seeds and both "
            "pipelines; 900 query-seed observations are not 900 independent queries. "
            "A zero-width interval is not proof of equivalence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-replicates", type=int, default=multiseed.BOOTSTRAP_REPLICATES)
    args = parser.parse_args()
    result = aggregate_matrix(args.matrix_root, bootstrap_replicates=args.bootstrap_replicates)
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Aggregate output already exists: {output}")
    with output.open("x", encoding="utf-8") as sink:
        json.dump(result, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
