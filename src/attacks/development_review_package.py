"""Deterministic, pending-only review packages from verified development records.

This is a screening/packaging utility, not an entailment or factuality verifier.
Nominations and evidence annotations are explicit preparer input, never approvals.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from src.attacks.target_candidates import expected_category
from src.evaluation.metrics import normalize_answer
from src.experiments.protocol import fingerprint_records

SCHEMA = "answer-compatible-targets/development-review-package-v1"
PLAN_SCHEMA = "answer-compatible-targets/phase4a-nominations-v1"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def answer_shape(category: str, answer: str) -> bool:
    """Reject obvious type errors; semantic aliases/roles still need human review."""
    if category == "yes_no":
        return answer.lower() in {"yes", "no"}
    if category == "date":
        return bool(re.fullmatch(r"\d{4}", answer))
    if category == "quantity":
        # This initial set supports integer counts only, not distances/ranks/ranges.
        return bool(re.fullmatch(r"\d[\d,]*(?: members)?", answer))
    if category == "transport_place":
        return bool(re.search(r"\b(?:airport|station)\b", answer, re.I))
    return bool(normalize_answer(answer)) and not bool(re.fullmatch(r"[\d\W]+", answer))


def screen_nomination(spec: dict, by_id: dict, seen_queries: set, seen_targets: set) -> list[str]:
    reasons = []
    query = by_id.get(spec.get("query_id"))
    source = by_id.get(spec.get("candidate_source_query_id"))
    if query is None:
        reasons.append("missing_development_query")
    if source is None:
        reasons.append("missing_candidate_source")
    if reasons:
        return reasons
    category = expected_category(query["question"], query["gold_answer"])
    target = source["gold_answer"]
    if category == "unknown":
        reasons.append("unsupported_or_ambiguous_question")
    if category != spec.get("answer_category"):
        reasons.append("question_category_mismatch")
    if expected_category(source["question"], target) != category:
        reasons.append("candidate_category_mismatch")
    if not answer_shape(category, query["gold_answer"]) or not answer_shape(category, target):
        reasons.append("incompatible_answer_shape")
    if source["query_id"] == query["query_id"]:
        reasons.append("same_query_source")
    if normalize_answer(target) == normalize_answer(query["gold_answer"]):
        reasons.append("gold_equivalent_target")
    if query["query_id"] in seen_queries:
        reasons.append("duplicate_query_nomination")
    if normalize_answer(target) in seen_targets:
        reasons.append("duplicate_or_normalized_alias_target")
    for key in ("expected_semantic_compatibility", "factual_claim_to_verify"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            reasons.append("missing_" + key)
    if not isinstance(spec.get("manual_review_flags"), list) or not spec["manual_review_flags"] or any(
        not isinstance(flag, str) or not flag.strip() for flag in spec["manual_review_flags"]
    ):
        reasons.append("missing_manual_review_flags")
    return reasons


def validate_evidence(items: list) -> None:
    if not isinstance(items, list):
        raise ValueError("Evidence annotations must be a list")
    for item in items:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(k), str) or not item[k].strip()
            for k in ("url", "title", "source_statement", "checked_on", "verification_method", "scope")
        ):
            raise ValueError("Incomplete evidence annotation")
        if item.get("source_statement_status") not in {"verified", "unverified"}:
            raise ValueError("Invalid source-statement evidence status")
        parsed = urlparse(item["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Evidence requires an explicit HTTPS source URL")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["checked_on"]):
            raise ValueError("Evidence check date must be YYYY-MM-DD")


def build_package(queries: list[dict], provenance: dict, plan: dict, support: dict) -> tuple[dict, dict]:
    """Require verified extraction and explicit nominations, retaining rejected IDs."""
    if (provenance.get("schema") != "verified-development-extraction/v1" or
        provenance.get("heldout_overlap_count") != 0 or
        provenance.get("query_count") != len(queries) or
        fingerprint_records(queries) != provenance.get("extracted_records_fingerprint_v1")):
        raise ValueError("Development extraction provenance mismatch")
    if (plan.get("schema") != PLAN_SCHEMA or
        plan.get("development_artifact_sha256") != provenance.get("artifact_sha256")):
        raise ValueError("Nomination plan does not match verified development artifact")
    by_id = {q["query_id"]: q for q in queries}
    if len(by_id) != len(queries):
        raise ValueError("Duplicate development IDs")
    specs = plan.get("nominations")
    if not isinstance(specs, list) or any(not isinstance(s, dict) for s in specs):
        raise ValueError("Expected explicit nomination objects")
    nomination_ids = [s.get("nomination_id") for s in specs]
    if any(not isinstance(n, str) or not n.strip() for n in nomination_ids) or len(set(nomination_ids)) != len(specs):
        raise ValueError("Missing/duplicate nomination IDs")
    rows, rejected = [], []
    seen_queries, seen_targets = set(), set()
    for spec in specs:
        reasons = screen_nomination(spec, by_id, seen_queries, seen_targets)
        if reasons:
            rejected.append({k: spec.get(k) for k in ("nomination_id", "query_id", "candidate_source_query_id")}
                            | {"reasons": reasons})
            continue
        query = by_id[spec["query_id"]]
        source = by_id[spec["candidate_source_query_id"]]
        validate_evidence(spec.get("evidence", []))
        # Never inherit review fields or evidence-derived approval from preparer input.
        target = source["gold_answer"]
        facts = support.get(query["query_id"])
        if not isinstance(facts, list) or not facts or any(
            not isinstance(f, dict) or not isinstance(f.get("title"), str) or not f["title"].strip()
            or type(f.get("sent_id")) is not int or f["sent_id"] < 0 for f in facts
        ):
            raise ValueError("Missing/invalid development supporting-fact provenance: " + query["query_id"])
        row = {**query, "nomination_id": spec["nomination_id"], "answer_category": spec["answer_category"],
               "proposed_target_answer": target, "question_sha256": sha(query["question"]),
               "gold_answer_sha256": sha(query["gold_answer"]), "proposed_target_sha256": sha(target),
               "candidate_source": {"query_id": source["query_id"], "question": source["question"],
                                    "gold_answer": target, "record_sha256": fingerprint_records([source]),
                                    "method": "exact gold answer from a different verified development query"},
               "expected_semantic_compatibility": spec["expected_semantic_compatibility"],
               "factual_claim_to_verify": spec["factual_claim_to_verify"],
               "evidence_source_reference": {"artifact_sha256": provenance["artifact_sha256"],
                                             "query_id": query["query_id"],
                                             "field": "gold_supporting_facts", "supporting_facts": facts},
               "external_evidence": spec.get("evidence", []), "evidence_status": "unverified",
               "evidence_scope": "Full query-target falsehood and all question hops require independent verification; source-statement checks are partial only.",
               "manual_review_flags": spec["manual_review_flags"], "human_review_decision": "pending",
               "review_status": "needs_independent_review", "approved": False,
               "reviewer": "", "reviewed_at": "", "target_answer": "",
               "semantic_compatible": None, "factually_false": None, "coherent_false_evidence": None}
        rows.append(row)
        seen_queries.add(query["query_id"])
        seen_targets.add(normalize_answer(target))
    if not 20 <= len(rows) <= 30:
        raise ValueError(f"Initial review set needs 20–30 screened questions; found {len(rows)}")
    # Paths are canonical repository-relative references, not machine-specific paths.
    keys = ("schema", "artifact_sha256", "manifest_sha256", "query_count", "dataset_revision",
            "dataset_split", "heldout_overlap_count", "development_query_set_fingerprint",
            "development_query_ids_fingerprint", "extracted_records_fingerprint_v1")
    package = {"schema": SCHEMA, "status": "pending_independent_development_review",
               "selection_method": plan["selection_method"], "nomination_plan_sha256": sha(stable_json(plan)),
               "development_provenance": {k: provenance[k] for k in keys},
               "count": len(rows), "records": rows}
    counts = Counter(reason for r in rejected for reason in r["reasons"])
    summary = {"schema": "answer-compatible-targets/development-review-validation-v1",
               "package_sha256": sha(stable_json(package)), "development_count": len(queries),
               "screened_nominations": len(specs), "selected_questions": len(rows),
               "category_distribution": dict(sorted(Counter(r["answer_category"] for r in rows).items())),
               "rejected_nominations": len(rejected), "rejection_reason_counts": dict(sorted(counts.items())),
               "rejection_ledger": rejected, "evidence_status_counts": {"verified": 0, "unverified": len(rows)},
               "rows_with_partial_external_source_checks": sum(any(e["source_statement_status"] == "verified" for e in r["external_evidence"]) for r in rows),
               "independently_approved_targets": 0, "heldout_overlap_count": 0,
               "limitation": "Mechanical screening only; preparer nominations and partial source checks are not independent factual/semantic approval."}
    return package, summary


def render_csv(package: dict) -> str:
    out = io.StringIO(newline="")
    fields = ("nomination_id", "query_id", "question", "gold_answer", "proposed_target_answer",
              "answer_category", "candidate_source", "expected_semantic_compatibility", "factual_claim_to_verify",
              "evidence_source_reference", "external_evidence", "evidence_status", "manual_review_flags",
              "human_review_decision", "reviewer", "reviewed_at")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in package["records"]:
        writer.writerow({k: json.dumps(row[k], ensure_ascii=False, sort_keys=True)
                         if isinstance(row[k], (dict, list)) else row[k] for k in fields})
    return out.getvalue()


def write_package(package: dict, summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review_package.json").write_text(stable_json(package), encoding="utf-8")
    (output_dir / "review_sheet.csv").write_text(render_csv(package), encoding="utf-8")
    (output_dir / "validation_summary.json").write_text(stable_json(summary), encoding="utf-8")
