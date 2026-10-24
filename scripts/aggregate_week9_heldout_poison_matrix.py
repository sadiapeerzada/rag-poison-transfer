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
    DEFAULT_DENSE_CONFIG,
    DEFAULT_HELDOUT_MANIFEST,
    DEFAULT_RCD_CONFIG,
    MATRIX_ATTACKS,
    MATRIX_INTENSITIES,
    FrozenMatrixInputs,
    _cell_id,
    load_frozen_matrix_inputs,
    matrix_cells,
    validate_completed_cell,
)

__all__ = ["aggregate_matrix", "validate_completed_cell", "main"]


def aggregate_matrix(
    root: Path,
    *,
    frozen_inputs: FrozenMatrixInputs | None = None,
    bootstrap_replicates: int = multiseed.BOOTSTRAP_REPLICATES,
) -> dict:
    """Aggregate all 12 cells; incomplete, missing, or corrupt cells fail closed.

    The frozen inputs (held-out manifest, configs, clean dataset) are loaded
    once by the caller and every cell's poison provenance is verified against
    them independently of anything the cell itself claims.
    """
    if frozen_inputs is None:
        raise ValueError(
            "aggregate_matrix requires frozen_inputs so that poison provenance "
            "can be verified independently; see load_frozen_matrix_inputs()."
        )
    root = root.expanduser().resolve()
    cells = {}
    for attack_family, intensity, seed in matrix_cells():
        cell_id = _cell_id(attack_family, intensity, seed)
        cells[(attack_family, intensity, seed)] = validate_completed_cell(
            root / cell_id, frozen_inputs=frozen_inputs
        )
    # Provenance must agree across the WHOLE matrix, not just within a seed group:
    # one commit and one source fingerprint produced all 12 cells.
    commits = {cell["git_commit_sha"] for cell in cells.values()}
    fingerprints = {cell["source_fingerprint"] for cell in cells.values()}
    if len(commits) != 1:
        raise ValueError(f"Matrix cells were produced at different Git commits: {sorted(commits)}.")
    if len(fingerprints) != 1:
        raise ValueError("Matrix cells were produced from different source fingerprints.")
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
        "git_commit_sha": next(iter(commits)),
        "source_fingerprint": next(iter(fingerprints)),
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
    parser.add_argument("--heldout-manifest", type=Path, default=DEFAULT_HELDOUT_MANIFEST)
    parser.add_argument("--dense-config", type=Path, default=DEFAULT_DENSE_CONFIG)
    parser.add_argument("--rcd-config", type=Path, default=DEFAULT_RCD_CONFIG)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Aggregate output already exists: {output}")
    frozen_inputs = load_frozen_matrix_inputs(
        heldout_path=args.heldout_manifest,
        dense_config_path=args.dense_config,
        rcd_config_path=args.rcd_config,
    )
    result = aggregate_matrix(
        args.matrix_root,
        frozen_inputs=frozen_inputs,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    with output.open("x", encoding="utf-8") as sink:
        json.dump(result, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
