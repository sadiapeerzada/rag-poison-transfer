#!/usr/bin/env python3
"""Read-only 2Wiki training-ID eligibility census; NEVER selects a cohort.

This analyzes an independently exported, externally SHA-256-pinned *IDs-only*
train inventory. It does not fetch question text, nominate targets, authorize
inference, or certify completeness of historical exposure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DATASET = "Salesforce/ContextualBench"
CONFIG = "2WikiMultihopQA"
REVISION = "9823f70484dea525100394220b0ea5184d0eeb7b"
SCHEMA = "twowiki-v3-train-id-census/v1"


def _read_pinned(path: Path, expected_sha256: str):
    if path.is_symlink():
        raise ValueError("Symlink input refused")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("An external full SHA-256 pin is required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256.lower():
        raise ValueError("Input SHA-256 does not match independent pin")
    return json.loads(raw)


def _ids(items, *, label):
    if not isinstance(items, list) or any(
        not isinstance(x, str) or not x.strip() for x in items
    ) or len(set(items)) != len(items):
        raise ValueError(f"{label}: unique nonempty string IDs required")
    return set(items)


def assess(pool, registry):
    """Return aggregate counts, NEVER the actual ID values or a selection."""
    if not isinstance(pool, dict) or set(pool) != {
        "dataset", "config", "revision", "split", "query_ids"
    }:
        raise ValueError("Source must be a strictly IDs-only metadata export")
    if (pool["dataset"], pool["config"], pool["revision"], pool["split"]) != (
        DATASET, CONFIG, REVISION, "train"
    ):
        raise ValueError("Expected exactly the pinned 2Wiki train split/revision")
    available = _ids(pool["query_ids"], label="train IDs")
    if not isinstance(registry, dict):
        raise ValueError("Invalid registry")
    exclusions = _ids(registry.get("excluded_query_ids"), label="exclusions")
    gaps = registry.get("historical_gaps")
    if not isinstance(gaps, list):
        raise ValueError("Historical gap register missing")
    certification = registry.get("certification")
    certified = (not gaps and isinstance(certification, dict)
                 and certification.get("historical_inventory_complete") is True)
    # Even when ID cardinality is sufficient, independent scientific custody,
    # target evidence, runtime pins, and authorization must be checked elsewhere.
    overlap = len(available & exclusions)
    candidates = len(available) - overlap
    return {
        "schema": SCHEMA,
        "scope": "metadata_only_train",
        "dataset": DATASET,
        "config": CONFIG,
        "revision": REVISION,
        "train_id_count": len(available),
        "excluded_id_count": len(exclusions),
        "overlap_count": overlap,
        "potentially_id_eligible_count": candidates,
        "at_least_25_by_id": candidates >= 25,
        "historical_exposure_gaps_count": len(gaps),
        "custody_status": "requires_independent_review" if certified else "incomplete_not_certified",
        "prospective_go": False,
        "cohort_selected": False,
        "model_inference_authorized": False,
        "heldout_content_read": False,
        "note": "Cardinality only; not a freshness certificate, selection, or authorization.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-ids", required=True, type=Path)
    parser.add_argument("--train-sha256", required=True, help="Externally obtained SHA-256")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--registry-sha256", required=True, help="Externally obtained SHA-256")
    args = parser.parse_args(argv)
    pool = _read_pinned(args.train_ids, args.train_sha256)
    registry = _read_pinned(args.registry, args.registry_sha256)
    print(json.dumps(assess(pool, registry), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
