#!/usr/bin/env python3
"""Capture real AI reviewer output bytes + operator-provided provenance sidecar.

This is NOT an AI model runner. Review runs must be independently performed
outside this tool, under the exact frozen prompt. Saves unmodified raw output;
never asserts model identity is authenticated. Never edits earlier captures.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.audit_twowiki_two_ai_review_responses import bind_batch
from scripts.prepare_twowiki_generic_dev25_review_dossiers import sha


def capture(*, batch_dir: Path, dossiers: Path, responses_dir: Path,
            case_index: int, reviewer_slot: str, raw_response_file: Path,
            model_id: str, review_run_id: str, reviewed_at: str,
            provider_request_id: str | None = None) -> dict:
    manifest, cases = bind_batch(batch_dir, dossiers)
    if type(case_index) is not int or not 1 <= case_index <= len(cases):
        raise ValueError("Invalid case index")
    if reviewer_slot not in ("A", "B"):
        raise ValueError("Only blinded reviewers A and B")
    for name, val in (("model_id", model_id), ("review_run_id", review_run_id)):
        if not isinstance(val, str) or not val.strip():
            raise ValueError("Real externally captured " + name + " required")
    try:
        dt = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("Time zone missing")
    except (ValueError, AttributeError) as exc:
        raise ValueError("Actual reviewed_at ISO-8601 timestamp with time zone required") from exc
    original = raw_response_file.read_bytes()
    if not original or len(original) > 200000:
        raise ValueError("Raw response empty or too large")
    case = cases[case_index - 1]
    target_dir = responses_dir / ("reviewer_" + reviewer_slot)
    raw_target = target_dir / f"case_{case_index:02}.json"
    provenance_target = target_dir / f"case_{case_index:02}.provenance.json"
    if raw_target.exists() or provenance_target.exists():
        raise FileExistsError("Already captured; never overwrite prior reviewer result")
    if responses_dir.resolve() == batch_dir.resolve() or batch_dir.resolve() in responses_dir.resolve().parents:
        raise ValueError("Never store review responses inside frozen prompt directory")
    if responses_dir.resolve() == dossiers.resolve() or dossiers.resolve() in responses_dir.resolve().parents:
        raise ValueError("Never write response into original dossier")
    meta = {
        "reviewer_slot": reviewer_slot,
        "query_id": case["query_id"],
        "model_id": model_id,
        "review_run_id": review_run_id,
        "reviewed_at": reviewed_at,
        "provider_request_id": provider_request_id,
        "prompt_sha256": manifest["records"][case_index - 1]["reviewer_prompt_sha256"][reviewer_slot],
        "raw_response_sha256": sha(original),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id_and_run_id_are_operator_supplied_not_authenticated": True,
        "independent_semantic_approval": False,
        "injection_approved": False,
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    with raw_target.open("xb") as f:
        f.write(original)
    with provenance_target.open("x", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return {
        "status": "captured_not_validated",
        "reviewer_slot": reviewer_slot,
        "case_index": case_index,
        "raw_file": str(raw_target),
        "provenance_file": str(provenance_target),
        "raw_response_sha256": sha(original),
        "model_identity_authenticated": False,
        "factual_approval": False,
        "injection_approved": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-dir", type=Path, required=True)
    p.add_argument("--dossiers", type=Path, required=True)
    p.add_argument("--responses-dir", type=Path, required=True)
    p.add_argument("--case-index", type=int, required=True)
    p.add_argument("--reviewer-slot", choices=("A", "B"), required=True)
    p.add_argument("--raw-response-file", type=Path, required=True)
    p.add_argument("--model-id", required=True)
    p.add_argument("--review-run-id", required=True)
    p.add_argument("--reviewed-at", required=True)
    p.add_argument("--provider-request-id")
    args = p.parse_args()
    result = capture(**vars(args))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
