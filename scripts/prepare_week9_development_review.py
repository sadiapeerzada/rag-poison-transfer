#!/usr/bin/env python3
"""Prepare unapproved development drafts or validate a privately completed review.

No models, held-out text, approval creation, signing, or evidence collection.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_week9_development_smoke as smoke
from src.attacks.reviewed_target_artifact import HASH, read_pinned

TEMPLATE = ROOT / "docs/reviews/week9_development_smoke/pending_targets.json"
SUGGESTIONS = dict(zip(smoke.DEVELOPMENT_QUERY_IDS, ("Alfonso Ribeiro", "1804")))
NEXT = ('Pending templates and candidate drafts are not approved.\n'
        'Prepare: .venv/bin/python scripts/prepare_week9_development_review.py prepare --output /private/tmp/week9-candidate-review.json\n'
        'After genuine independent review, validate: .venv/bin/python scripts/prepare_week9_development_review.py validate '
        '--targets "$WEEK9_DEV_REVIEW_FILE" --targets-sha256 "$WEEK9_DEV_REVIEW_SHA256"')


def input_errors(path, digest):
    errors = []
    if path is None:
        errors.append("Missing --targets: supply the genuinely completed review file.")
    elif not Path(path).is_file():
        errors.append("--targets file is absent or is not a regular file.")
    if not digest:
        errors.append("Missing --targets-sha256: the trusted hash is unset.")
    elif not isinstance(digest, str) or not HASH.fullmatch(digest):
        errors.append("--targets-sha256 must be an externally trusted 64-character lowercase hexadecimal SHA-256.")
    return errors


def prepare(output):
    queries = smoke._verified_development()[0]
    template = json.loads(TEMPLATE.read_text())
    # Bind the template back to the verified development artifact before copying.
    if (template.get("schema") != smoke.TARGET_SCHEMA or template.get("scope") != "development" or
        template.get("status") != "pending_human_review" or
        template.get("protocol_version") != smoke.PROTOCOL_VERSION or
        template.get("development_artifact_sha256") != smoke.PINNED_ARTIFACT_SHA256 or
        template.get("query_set_fingerprint") != smoke.query_set_fingerprint(queries)):
        raise ValueError("Pending template provenance mismatch")
    rows = template.get("assignments", [])
    if len(rows) != 2 or [r.get("query_id") for r in rows] != list(smoke.DEVELOPMENT_QUERY_IDS):
        raise ValueError("Pending template query identities mismatch")
    for row, query in zip(rows, queries):
        for key in ("query_id", "question", "gold_answer", "gold_doc_ids"):
            if row.get(key) != query[key]:
                raise ValueError("Pending template development identity mismatch")
        for field, key in (("question_sha256", "question"), ("gold_answer_sha256", "gold_answer")):
            if row.get(field) != hashlib.sha256(query[key].encode()).hexdigest():
                raise ValueError("Pending template question/gold hash mismatch")
        if row.get("approved") is not False or row.get("target_answer") or row.get("review_status") != "pending":
            raise ValueError("Preparation requires an unapproved, empty-target template")
    draft = copy.deepcopy(template)
    for row in draft["assignments"]:
        row["candidate_suggestion"] = {"answer": SUGGESTIONS[row["query_id"]],
                                       "status": "unverified_suggestion_not_an_approval",
                                       "source": "User-supplied nomination; not fact-checked by this tool"}
        row["candidate_review_notes"] = ""
    output = Path(output).expanduser().resolve()
    if output == TEMPLATE.resolve():
        raise ValueError("Never overwrite the pending template")
    with output.open("x", encoding="utf-8") as handle:
        json.dump(draft, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return {"status": "pending_human_review", "assignment_count": 2, "approvals_created": 0}


def validate(path, digest):
    errors = input_errors(path, digest)
    if errors:
        return {"valid": False, "errors": errors}
    try:
        payload = read_pinned(path, digest)
    except (ValueError, OSError):
        # Do not echo private paths, JSON fragments, identities, evidence or exceptions.
        return {"valid": False, "errors": ["Cannot read pinned JSON: check permissions, exact-byte SHA-256, JSON syntax and duplicate keys."]}
    queries = smoke._verified_development()[0]
    for key, expected in (("schema", smoke.TARGET_SCHEMA), ("scope", "development"),
                          ("status", "reviewed_diagnostic_only"), ("protocol_version", smoke.PROTOCOL_VERSION),
                          ("development_artifact_sha256", smoke.PINNED_ARTIFACT_SHA256),
                          ("query_set_fingerprint", smoke.query_set_fingerprint(queries))):
        if payload.get(key) != expected:
            errors.append("Invalid or pending header field: " + key)
    rows = payload.get("assignments")
    if not isinstance(rows, list) or len(rows) != 2 or any(not isinstance(r, dict) for r in rows):
        errors.append("assignments must contain exactly two objects")
    else:
        ids = [r.get("query_id") for r in rows]
        if any(not isinstance(qid, str) for qid in ids) or sorted(ids) != sorted(smoke.DEVELOPMENT_QUERY_IDS):
            errors.append("assignments.query_id: missing, duplicate or modified development identities")
        for index, row in enumerate(rows):
            prefix = f"assignments[{index}]."
            for key in ("reviewer", "nominator", "reviewed_at", "review_evidence", "target_answer", "reviewed_target_sha256"):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    errors.append(prefix + key + ": missing")
            for key in ("approved", "semantic_compatible", "factually_false", "coherent_false_evidence", "alias_check_complete"):
                if row.get(key) is not True:
                    errors.append(prefix + key + ": explicit genuine positive review required")
            for key, expected in (("review_status", "approved"), ("ambiguity_status", "resolved"),
                                  ("evidence_status", "independently_verified")):
                if row.get(key) != expected:
                    errors.append(prefix + key + ": pending or invalid")
            for key in ("gold_aliases", "evidence_references"):
                if not isinstance(row.get(key), list) or not row[key]:
                    errors.append(prefix + key + ": missing or empty")
            query = next((q for q in queries if q["query_id"] == row.get("query_id")), None)
            if query:
                try:
                    smoke.select_reviewed_target(query, {query["query_id"]: row})
                except (ValueError, TypeError, KeyError):
                    errors.append(prefix + "shared approval/hash/timestamp/gold-exclusion validation failed")
                try:
                    smoke._review_annotations(row, query)
                except (ValueError, TypeError, KeyError, AttributeError) as error:
                    # Annotation messages contain fixed field names only, never values.
                    errors.append(prefix + str(error) if isinstance(error, ValueError) else prefix + "malformed review annotations")
    if not errors:
        # The runner's authoritative loader remains the final acceptance boundary.
        try:
            smoke.load_development_targets(path, digest, queries)
        except (ValueError, TypeError, KeyError, OSError):
            errors.append("Authoritative development loader rejected the artifact")
    return {"valid": not errors, "errors": errors,
            "scope": "development", "inference_executed": False,
            "limitation": "Structural validation cannot establish reviewer independence or factual truth."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    draft = modes.add_parser("prepare")
    draft.add_argument("--output", required=True, type=Path)
    check = modes.add_parser("validate")
    check.add_argument("--targets", type=Path)
    check.add_argument("--targets-sha256")
    args = parser.parse_args()
    try:
        result = prepare(args.output) if args.mode == "prepare" else validate(args.targets, args.targets_sha256)
    except (ValueError, OSError):
        print("Review preparation/validation failed; check template provenance and use a fresh writable output file.\n" + NEXT, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    if result.get("valid") is False:
        print(NEXT, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
