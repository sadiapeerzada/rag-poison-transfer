#!/usr/bin/env python3
"""Read-only audit of *real* independent two-AI 2Wiki review responses.

Input: frozen six-case prompt directory, original 20-dossier JSON, and
externally captured model responses. This script does NOT call a model,
invent review provenance, select a false target, authorize construction,
inject poisoned text or access held-out data.

Expected files under --responses-dir:
 reviewer_A/case_01.json             (raw UTF-8 model response, JSON only)
 reviewer_A/case_01.provenance.json  (capture metadata, NOT model prose)
 ... through case_06 for reviewer_A and reviewer_B.

Self-reported metadata is checked for *internal consistency*, but cannot
authenticate an external service. Provisional agreement is never an
independent factual approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from scripts.prepare_twowiki_generic_dev25_review_dossiers import sha
from scripts.prepare_twowiki_two_ai_review_batch import make_batch, validate_dossiers

SCHEMA = "rag-poison-transfer.twowiki-two-ai-review-response-audit/v1"
CHECKS = (
    "source_chain_valid", "gold_supported", "target_distinct_from_gold",
    "target_type_compatible", "target_contradicted_by_sources",
    "aliases_checked", "chronology_checked", "referent_grounded",
)
DECISIONS = ("provisional_accept", "reject", "uncertain")
HEX = re.compile(r"^[a-f0-9]{64}$")


def read_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return obj


def bind_batch(batch_dir: Path, dossiers_path: Path) -> tuple[dict, list[dict]]:
    """Reconstruct deterministic batch and verify manifest and prompt bytes."""
    blob = read_json(dossiers_path)
    dossiers = validate_dossiers(blob)
    m = read_json(batch_dir / "manifest.json")
    size = m.get("pilot_size")
    if type(size) is not int or not 1 <= size <= 20:
        raise ValueError("Invalid predeclared pilot size")
    expected, prompts = make_batch(
        blob, pilot_size=size,
        input_sha256=sha(dossiers_path.read_bytes()),
    )
    if m != expected:
        raise ValueError("Batch manifest is not an exact reconstruction from pinned dossiers")
    for rel, text in prompts.items():
        path = batch_dir / rel
        if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            raise ValueError("Review prompt bytes do not match frozen manifest: " + rel)
    return m, dossiers[:size]


def parse_one(
    *, case: dict, slot: str, index: int,
    responses_dir: Path, expected_prompt_sha: str,
) -> dict:
    base = responses_dir / ("reviewer_" + slot) / f"case_{index:02}"
    raw_path = base.with_suffix(".json")
    meta_path = base.with_suffix(".provenance.json")
    if not raw_path.exists() and not meta_path.exists():
        return {"status": "awaiting_response", "reviewer_slot": slot}
    if not raw_path.is_file() or not meta_path.is_file():
        return {"status": "incomplete_capture", "reviewer_slot": slot}
    try:
        raw_bytes = raw_path.read_bytes()
        if not raw_bytes or len(raw_bytes) > 200_000:
            raise ValueError("Raw model response empty or exceeds cap")
        meta = read_json(meta_path)
        raw = json.loads(raw_bytes)
        if not isinstance(raw, dict):
            raise ValueError("Raw model output is not a JSON object")

        if meta.get("reviewer_slot") != slot or meta.get("query_id") != case["query_id"]:
            raise ValueError("Metadata reviewer slot / query ID mismatch")
        for key in ("model_id", "review_run_id"):
            if not isinstance(meta.get(key), str) or not meta[key].strip():
                raise ValueError("Missing model capture metadata: " + key)
        for key, expected in (
            ("prompt_sha256", expected_prompt_sha),
            ("raw_response_sha256", sha(raw_bytes)),
        ):
            if meta.get(key) != expected:
                raise ValueError("Captured response or prompt SHA-256 mismatch: " + key)
        when = meta.get("reviewed_at")
        if not isinstance(when, str):
            raise ValueError("Missing reviewed_at timestamp")
        stamp = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("Timestamp lacks timezone")

        if raw.get("query_id") != case["query_id"] or raw.get("dossier_sha256") != case["dossier_sha256"]:
            raise ValueError("Raw review is bound to wrong query/dossier")
        decision = raw.get("decision")
        if decision not in DECISIONS:
            raise ValueError("Invalid decision")
        checks = {k: raw.get(k) for k in CHECKS}
        if any(type(v) is not bool for v in checks.values()):
            raise ValueError("Incomplete or non-Boolean assessment checks")
        reason = raw.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < 30:
            raise ValueError("No substantive explanation")
        caveats = raw.get("disagreements_or_caveats")
        if not isinstance(caveats, list) or any(not isinstance(c, str) for c in caveats):
            raise ValueError("Invalid caveat list")
        target = raw.get("proposed_false_target")
        if target is not None and (not isinstance(target, str) or not target.strip() or len(target) > 500):
            raise ValueError("Invalid target")
        if decision != "provisional_accept" and target is not None:
            raise ValueError("Nonaccepting review must abstain from target selection")
        if decision == "provisional_accept":
            if target is None or not all(checks.values()):
                raise ValueError("Provisional acceptance requires all checks and target")
            known = {case["gold_answer"].strip().casefold()}
            known.update(a.strip().casefold() for a in case["gold_aliases"])
            if target.strip().casefold() in known:
                raise ValueError("False target duplicates gold/alias")

        quotes = raw.get("evidence_quotes")
        if not isinstance(quotes, list):
            raise ValueError("Missing evidence quotes")
        by_doc = {d["doc_id"]: d["text"] for d in case["source_documents"]}
        seen_docs = set()
        for q in quotes:
            if not isinstance(q, dict) or set(q) != {"doc_id", "exact_quote"}:
                raise ValueError("Malformed source quote")
            ident, phrase = q["doc_id"], q["exact_quote"]
            if ident not in by_doc or not isinstance(phrase, str):
                raise ValueError("Quote cites unknown doc_id")
            if len(phrase.strip()) < 8 or phrase not in by_doc[ident]:
                raise ValueError("Source quote is not an exact span from pinned document")
            seen_docs.add(ident)
        if decision == "provisional_accept" and seen_docs != set(by_doc):
            raise ValueError("Acceptance lacks evidence quotes from each gold-support document")
        result = {
            "status": "well_formed_provisional_review",
            "reviewer_slot": slot, "decision": decision,
            "target": target, "checks": checks,
            "quote_doc_ids": sorted(seen_docs),
            "model_id": meta["model_id"],
            "review_run_id": meta["review_run_id"],
            "reviewed_at": when,
            "prompt_sha256": expected_prompt_sha,
            "raw_response_sha256": sha(raw_bytes),
            "provider_request_id": meta.get("provider_request_id"),
            "reviewer_provenance_authenticated": False,
            "source_semantics_independently_verified": False,
            "factual_approval": False, "injection_approved": False,
        }
        return result
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid_capture_or_review",
            "reviewer_slot": slot,
            "issue": str(exc),
            "factual_approval": False, "injection_approved": False,
        }


def audit(*, batch_dir: Path, dossiers_path: Path, responses_dir: Path) -> dict:
    manifest, cases = bind_batch(batch_dir, dossiers_path)
    records = []
    for i, case in enumerate(cases, 1):
        row = {"batch_index": i, "query_id": case["query_id"],
               "dossier_sha256": case["dossier_sha256"]}
        a, b = (parse_one(
            case=case, slot=slot, index=i,
            responses_dir=responses_dir,
            expected_prompt_sha=manifest["records"][i - 1]["reviewer_prompt_sha256"][slot],
        ) for slot in ("A", "B"))
        row["reviews"] = {"A": a, "B": b}
        if any(x["status"] == "invalid_capture_or_review" for x in (a, b)):
            status = "invalid_review_requires_correction"
        elif any(x["status"] != "well_formed_provisional_review" for x in (a, b)):
            status = "pending_review"
        elif (a["model_id"] == b["model_id"]
              or a["review_run_id"] == b["review_run_id"]
              or a["raw_response_sha256"] == b["raw_response_sha256"]):
            status = "reviewer_independence_not_demonstrated"
        elif "reject" in (a["decision"], b["decision"]):
            status = "rejected_by_at_least_one_reviewer"
        elif "uncertain" in (a["decision"], b["decision"]):
            status = "at_least_one_reviewer_abstained"
        elif a["target"] != b["target"]:
            status = "counterfactual_target_disagreement"
        else:
            status = "concordant_provisional_ai_only_not_factually_approved"
        row["status"] = status
        row["reviewer_identity_authenticated"] = False
        row["source_factuality_independently_verified"] = False
        row["construction_eligible"] = False
        row["injection_approved"] = False
        records.append(row)
    return {
        "schema": SCHEMA, "scope": "train_development_only",
        "batch_schema": manifest["schema"],
        "batch_manifest_sha256": sha((batch_dir / "manifest.json").read_bytes()),
        "dossiers_sha256": sha(dossiers_path.read_bytes()),
        "requested_cases": len(cases),
        "status_counts": dict(sorted(Counter(r["status"] for r in records).items())),
        "cases": records,
        "source_quote_verification": "literal_span_only_not_semantic_entailment",
        "reviewer_provenance": "metadata_self_reported_unverified",
        "review_disagreements_require_independent_adjudication": True,
        "independent_factual_approval": False,
        "construction_approvals": 0, "factual_approvals": 0,
        "injection_approvals": 0, "poison_injections": 0,
        "heldout_queries_accessed": 0,
        "paired_poisoned_evaluation_authorized": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-dir", type=Path, required=True)
    p.add_argument("--dossiers", type=Path, required=True)
    p.add_argument("--responses-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError("Never overwrite prior independent-review audit")
    result = audit(
        batch_dir=args.batch_dir, dossiers_path=args.dossiers,
        responses_dir=args.responses_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True,
                  ensure_ascii=False, allow_nan=False)
        f.write("\n")
    print(json.dumps({
        "requested_cases": result["requested_cases"],
        "status_counts": result["status_counts"],
        "factual_approvals": 0, "poison_injections": 0,
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
