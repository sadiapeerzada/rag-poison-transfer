#!/usr/bin/env python3
"""Offline 2Wiki 300-query matrix readiness; never selects, constructs or evaluates.

The existing frozen 300-query dev cohort is a risk-disclosed replication design,
NOT a newly certified unexposed/prospective sample. V3's separate 25-query
prospective gates are not replaced or bypassed here.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REVISION = "9823f70484dea525100394220b0ea5184d0eeb7b"
SCHEMA = "twowiki-300-risk-disclosed-matrix-preflight/v1"
HEXDIGEST = re.compile(r"[0-9a-f]{64}\Z")
QUERY_ID = re.compile(r"[0-9a-f]{32}\Z")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_json(path: Path, pin: str | None = None):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Only regular non-symlinked evidence files are allowed")
    raw = path.read_bytes()
    if pin is not None:
        if not HEXDIGEST.fullmatch(pin.lower()) or sha(raw) != pin.lower():
            raise ValueError("Externally pinned SHA-256 mismatch")
    return json.loads(raw), sha(raw)


def matrix_constants(text: str):
    """Extract the frozen matrix dimensions without importing model dependencies."""
    tree = ast.parse(text)
    values = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"ATTACKS", "INTENSITIES", "SEEDS"}):
            values[node.targets[0].id] = ast.literal_eval(node.value)
    expected = {
        "ATTACKS": ("lexical_influential_token", "semantic_fluent_false_evidence"),
        "INTENSITIES": (1, 3),
        "SEEDS": (42, 43, 44),
    }
    if values != expected:
        raise ValueError("Unexpected frozen construction matrix dimensions")
    return expected


def assess(manifest, policy, registry, history, *, manifest_sha: str,
           policy_sha: str, registry_sha: str, history_sha: str,
           matrix_source_sha: str, dimensions: dict):
    if (manifest.get("schema") != "rag-poison-transfer.2wiki-disjoint-cohort-manifest/v1"
        or manifest.get("dataset_revision") != REVISION
        or manifest.get("policy_sha256") != policy_sha
        or manifest.get("complete_historical_nonoverlap_certified") is not False
        or manifest.get("known_historical_nonoverlap_verified") is not True
        or manifest.get("development_heldout_id_overlap") != 0
        or manifest.get("status") != "cohort_frozen_no_evaluation"):
        raise ValueError("Frozen cohort provenance/risk disclosure mismatch")
    if (policy.get("dataset") != "Salesforce/ContextualBench"
        or policy.get("config") != "2WikiMultihopQA"
        or policy.get("development_split") != "train"
        or policy.get("heldout_split") != "dev"
        or policy.get("complete_historical_nonoverlap_certified") is not False):
        raise ValueError("Historical cohort policy mismatch")
    if not isinstance(registry, dict) or registry.get("certification") is not None:
        raise ValueError("Expected current uncertified exclusion registry")
    exclusions = registry.get("excluded_query_ids")
    if (not isinstance(exclusions, list) or len(exclusions) != len(set(exclusions))
        or not all(isinstance(x, str) and QUERY_ID.fullmatch(x) for x in exclusions)):
        raise ValueError("Known exclusions must be complete-form unique metadata IDs")
    if not isinstance(registry.get("historical_gaps"), list):
        raise ValueError("Registry historical gap list missing")
    if not isinstance(history, list) or not all(
        isinstance(item, dict) and isinstance(item.get("id"), str)
        and isinstance(item.get("status"), str) for item in history
    ):
        raise ValueError("Original unresolved-history register missing")
    cohorts = manifest.get("cohorts")
    if not isinstance(cohorts, dict) or set(cohorts) != {"train", "dev"}:
        raise ValueError("Expected exactly two distinct frozen cohorts")
    cohort_ids = {}
    for split in ("train", "dev"):
        rows = cohorts[split]
        if (not isinstance(rows, list) or len(rows) != 300
            or any(not isinstance(row, dict)
                   or not isinstance(row.get("query_id"), str)
                   or not QUERY_ID.fullmatch(row["query_id"])
                   or not isinstance(row.get("question_sha256"), str)
                   or not HEXDIGEST.fullmatch(row["question_sha256"])
                   for row in rows)):
            raise ValueError("Invalid frozen 300-row cohort metadata")
        ids = [r["query_id"] for r in rows]
        if len(set(ids)) != 300:
            raise ValueError("Duplicate cohort IDs")
        if sha(canonical(rows)) != manifest.get("cohort_fingerprints", {}).get(split):
            raise ValueError("Frozen cohort fingerprint mismatch")
        cohort_ids[split] = set(ids)
    if cohort_ids["train"] & cohort_ids["dev"]:
        raise ValueError("Development versus heldout cohort IDs overlap")
    known_prior = set(policy.get("known_historical_ids", []))
    if (not all(isinstance(x, str) and QUERY_ID.fullmatch(x) for x in known_prior)
        or known_prior & (cohort_ids["train"] | cohort_ids["dev"])):
        raise ValueError("Frozen cohort has overlap with then-known historical IDs")
    excluded = set(exclusions)
    overlap = {split: len(ids & excluded) for split, ids in cohort_ids.items()}
    if overlap != {"train": 300, "dev": 300}:
        raise ValueError("Historical registry no longer records both frozen cohorts")
    cells = [{"family": family, "intensity": intensity, "seed": seed,
              "frozen_dev_queries": 300, "paired_pipelines": ["Dense", "RCD"]}
             for family in dimensions["ATTACKS"]
             for intensity in dimensions["INTENSITIES"]
             for seed in dimensions["SEEDS"]]
    if len(cells) != 12:
        raise AssertionError("Unexpected matrix size")
    unresolved = [{"id": item["id"], "status": item["status"]}
                  for item in history if item["status"] not in ("resolved", "complete")]
    return {
        "schema": SCHEMA,
        "scope": "historically-risk-disclosed-existing-frozen-2wiki-300",
        "dataset": policy["dataset"], "config": policy["config"], "revision": REVISION,
        "frozen_dev_query_count": 300, "frozen_train_development_query_count": 300,
        "matrix_cell_count": len(cells), "attack_query_cell_count": len(cells)*300,
        "planned_poisoned_pipeline_observations": len(cells)*300*2,
        "semantic_max_construction_backend_attempts": 300*len(dimensions["SEEDS"])*sum(dimensions["INTENSITIES"])*2,
        "cell_plan": cells,
        "known_registry_overlap": overlap,
        "input_pins": {"cohort_manifest_sha256": manifest_sha,
                       "cohort_policy_sha256": policy_sha,
                       "excluded_registry_sha256": registry_sha,
                       "history_register_sha256": history_sha,
                       "matrix_contract_source_sha256": matrix_source_sha},
        "unresolved_history": unresolved,
        "historical_exposure_complete": False,
        "untouched_prospective_cohort": False,
        "target_falsehood_independently_adjudicated": False,
        "scientific_model_call_authorization": "NOT_SUPPLIED",
        "runtime_model_and_replication_spec": "NOT_VERIFIED",
        "frozen_cohort_metadata_preflight": "PASS",
        "matrix_execution_go": False,
        "cohort_selected": False, "heldout_question_text_read": False,
        "model_loaded": False, "model_calls": 0, "evaluation_started": False,
        "interpretation": "This is the pre-existing 300-query replication, NOT the 25-query prospective V3 pilot. "
                          "Known exposure is documented, but historical nonexposure cannot be certified. "
                          "Approval/runtime proof and model calls require separate recorded evidence.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=ROOT/"docs/protocols/oct26_2wiki/cohort_manifest.json")
    parser.add_argument("--policy", type=Path,
                        default=ROOT/"docs/protocols/oct26_2wiki/cohort_policy.json")
    parser.add_argument("--registry", type=Path,
                        default=ROOT/"reports/twowiki_v3_exposure_reconciliation/reconciled_registry.json")
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--history", type=Path,
                        default=ROOT/"reports/twowiki_v3_exposure_reconciliation/unresolved_history_register.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest, mh = read_json(args.manifest)
    policy, ph = read_json(args.policy, manifest.get("policy_sha256"))
    registry, rh = read_json(args.registry, args.registry_sha256)
    history, hh = read_json(args.history)
    source = ROOT/"src/experiments/week9_construction.py"
    dimensions = matrix_constants(source.read_text(encoding="utf-8"))
    report = assess(manifest, policy, registry, history,
                    manifest_sha=mh, policy_sha=ph,
                    registry_sha=rh, history_sha=hh,
                    matrix_source_sha=sha(source.read_bytes()),
                    dimensions=dimensions)
    # Write exactly once, and only outside the source repository.
    output = args.output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Write reports outside the Git checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"saved_to": str(output), **{k: report[k] for k in
                     ("frozen_cohort_metadata_preflight", "matrix_execution_go",
                      "matrix_cell_count", "attack_query_cell_count",
                      "planned_poisoned_pipeline_observations",
                      "semantic_max_construction_backend_attempts")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
