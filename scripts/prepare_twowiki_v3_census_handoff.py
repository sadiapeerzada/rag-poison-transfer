#!/usr/bin/env python3
"""Make an auditable 2Wiki V3 metadata handoff. No cohort selection or inference.

Train ID capacity can be GO while scientific experiment authorization remains
NO_GO. An ID census cannot certify historical nonexposure or reviewer identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_twowiki_v3_train_pool import _read_pinned, assess

SCHEMA = "twowiki-v3-census-handoff/v1"
ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def prepare(train: dict, registry: dict, *, train_sha: str, registry_sha: str,
            review: dict | None = None, review_sha: str | None = None):
    """Validate supplied metadata and return full pool IDs plus aggregate handoff.

    No query IDs are output in the handoff report. The full list is only a
    reusable all-train metadata export, NOT a selected or certified cohort.
    """
    census = assess(train, registry)
    ids = train["query_ids"]
    if not all(ID_PATTERN.fullmatch(item) for item in ids):
        raise ValueError("Expected canonical 32-character 2Wiki query IDs")
    if not all(ID_PATTERN.fullmatch(item) for item in registry["excluded_query_ids"]):
        raise ValueError("Noncanonical exclusion ID")
    if review is not None:
        expected = {
            "dataset_revision": census["revision"],
            "train_export_sha256": train_sha,
            "registry_sha256": registry_sha,
            "total_training_ids": census["train_id_count"],
            "known_exclusions": census["excluded_id_count"],
            "training_overlap": census["overlap_count"],
            "potentially_eligible_ids": census["potentially_id_eligible_count"],
            "prospective_v3_go": False,
            "cohort_selected": False,
            "model_calls_authorized": False,
        }
        if not isinstance(review, dict) or any(
            review.get(k) != value for k, value in expected.items()
        ):
            raise ValueError("Independent census and supplied review disagree")
    # Original train metadata, not a freshly chosen 25-case subset.
    all_train_ids = sorted(ids)
    pool_bytes = (json.dumps(all_train_ids, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    handoff = {
        "schema": SCHEMA,
        "dataset": census["dataset"],
        "config": census["config"],
        "revision": census["revision"],
        "split": "train",
        "train_export_sha256": train_sha,
        "known_exclusion_registry_sha256": registry_sha,
        "scientific_review_sha256": review_sha,
        "all_train_ids_sha256": digest(pool_bytes),
        "train_id_count": census["train_id_count"],
        "known_exclusion_count": census["excluded_id_count"],
        "known_overlap_count": census["overlap_count"],
        "potentially_id_eligible_count": census["potentially_id_eligible_count"],
        "historical_registry_gaps_count": census["historical_exposure_gaps_count"],
        "reported_unresolved_history_items": len(review.get("unresolved_evidence", [])) if review is not None else None,
        "decision": {
            "train_id_capacity": "GO" if census["at_least_25_by_id"] else "NO_GO",
            "fresh_unexposed_cohort": "NO_GO",
            "prospective_v3_construction": "NO_GO",
            "full_2wiki_heldout_replication": "NO_GO",
            "nonprospective_construction_diagnostic": "SEPARATE_PROTOCOL_AND_APPROVAL_REQUIRED",
        },
        "cohort_selected": False,
        "historical_exposure_certified": False,
        "human_target_review_completed": False,
        "model_inference_authorized": False,
        "heldout_content_inspected": False,
        "explanation": "An externally pinned training-ID census proves only available ID count. "
                       "Unrecovered historical sweep provenance, complete custody, target review "
                       "and explicit authorization remain independent prerequisites.",
    }
    return pool_bytes, handoff


def _publish_new(path: Path, data: bytes):
    """Write-once, exclusive-create; never overwrite an existing scientific record."""
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        import os
        os.fsync(f.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-ids", type=Path, required=True)
    parser.add_argument("--train-sha256", required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--review-report", type=Path)
    parser.add_argument("--review-sha256")
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.review_report) != bool(args.review_sha256):
        parser.error("--review-report and --review-sha256 are required together")
    train = _read_pinned(args.train_ids, args.train_sha256)
    registry = _read_pinned(args.registry, args.registry_sha256)
    review = _read_pinned(args.review_report, args.review_sha256) if args.review_report else None
    pool, handoff = prepare(train, registry,
                            train_sha=args.train_sha256.lower(),
                            registry_sha=args.registry_sha256.lower(),
                            review=review,
                            review_sha=args.review_sha256.lower() if args.review_sha256 else None)
    out = args.output_directory
    if out.exists() or out.is_symlink():
        raise FileExistsError("New output namespace required: " + str(out))
    out.mkdir(parents=True, exist_ok=False)
    _publish_new(out / "all_train_pool.ids.json", pool)
    _publish_new(out / "READINESS_HANDOFF.json",
                 (json.dumps(handoff, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({"output_directory": str(out), **handoff}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
