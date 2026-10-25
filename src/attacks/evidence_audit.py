"""Validate and render preparer evidence assessments without granting approval.

Offline validation checks binding, coverage and review-state invariants. It does
not authenticate source access, decide factual truth or impersonate a reviewer.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date
import hashlib
import io
import json
from urllib.parse import urlparse

from src.attacks.development_review_package import SCHEMA as PACKAGE_SCHEMA, stable_json
from src.evaluation.metrics import normalize_answer
from src.experiments.protocol import fingerprint_records

SCHEMA = "answer-compatible-targets/evidence-audit-v1"
CLASSES = {"recommended_for_independent_review", "needs_revision", "reject"}
TEXT_FIELDS = ("gold_answer_assessment", "target_falsehood_assessment",
               "semantic_compatibility_assessment", "aliases_and_ambiguity", "verification_limitations")
IDENTITY_FIELDS = ("query_id", "question", "gold_answer", "proposed_target_answer", "answer_category",
                   "question_sha256", "gold_answer_sha256", "proposed_target_sha256")


def require_pending(row: dict) -> None:
    if (row.get("approved") is not False or row.get("human_review_decision") != "pending" or
        row.get("reviewer") != "" or row.get("reviewed_at") != ""):
        raise ValueError("Preparer assessments must remain pending with blank reviewer/timestamp")
    if row.get("target_answer", "") != "":
        raise ValueError("Approved target field must remain blank")
    if any(row.get(key) is not None for key in ("semantic_compatible", "factually_false", "coherent_false_evidence")):
        raise ValueError("Independent approval decisions must remain unset")


def validate_audit(audit: dict, package: dict, package_bytes: bytes, queries: list[dict], extraction_provenance: dict) -> dict:
    if (audit.get("schema") != SCHEMA or package.get("schema") != PACKAGE_SCHEMA or
        audit.get("status") != "preparer_assessments_pending_independent_review" or
        audit.get("assessment_role") != "research_assistant_preparation_not_independent_review"):
        raise ValueError("Expected pending preparer evidence-audit and development-package schemas")
    if json.loads(package_bytes) != package:
        raise ValueError("Package bytes/object mismatch")
    if hashlib.sha256(package_bytes).hexdigest() != audit.get("base_package_sha256"):
        raise ValueError("Stale base package fingerprint")
    provenance = package["development_provenance"]
    if any(extraction_provenance.get(k) != v for k, v in provenance.items()):
        raise ValueError("Development artifact/manifest extraction provenance mismatch")
    if fingerprint_records(queries) != provenance.get("extracted_records_fingerprint_v1"):
        raise ValueError("Verified development query fingerprint mismatch")
    by_id = {q["query_id"]: q for q in queries}
    if len(by_id) != len(queries):
        raise ValueError("Duplicate development query IDs")
    sources = audit.get("sources")
    if not isinstance(sources, list) or any(not isinstance(s, dict) for s in sources):
        raise ValueError("Expected evidence source objects")
    source_map = {}
    try:
        audit_day = date.fromisoformat(audit["audit_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid audit date") from exc
    for source in sources:
        for key in ("source_id", "url", "source_kind", "access_method", "accessed_on",
                    "supported_claim", "locator", "limitations"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise ValueError("Incomplete evidence-source metadata: " + key)
        if source["source_id"] in source_map:
            raise ValueError("Duplicate evidence source ID")
        url = urlparse(source["url"])
        if url.scheme != "https" or not url.netloc:
            raise ValueError("Evidence URL must be HTTPS")
        if source["access_method"] not in {"opened", "search_excerpt_only"}:
            raise ValueError("Source access scope must distinguish opened text from indexed excerpts")
        try:
            access_day = date.fromisoformat(source["accessed_on"])
        except ValueError as exc:
            raise ValueError("Invalid source access date") from exc
        if access_day > audit_day:
            raise ValueError("Source access date later than audit date")
        source_map[source["source_id"]] = source
    original = {r["nomination_id"]: r for r in package["records"]}
    rows = audit.get("records")
    if not isinstance(rows, list) or len(rows) != len(original):
        raise ValueError("Evidence audit must cover every original nomination exactly once")
    seen = set()
    for row in rows:
        nid = row.get("nomination_id")
        if nid not in original or nid in seen:
            raise ValueError("Unknown or duplicate audit nomination")
        seen.add(nid)
        base = original[nid]
        require_pending(base)
        require_pending(row)
        if any(row.get(key) != base[key] for key in IDENTITY_FIELDS):
            raise ValueError("Stale query/gold/target identity or fingerprints")
        if base["query_id"] not in by_id or any(base[k] != by_id[base["query_id"]][k] for k in ("question", "gold_answer")):
            raise ValueError("Original query is not the verified development record")
        source = by_id.get(base["candidate_source"]["query_id"])
        if source is None or source["gold_answer"] != base["proposed_target_answer"]:
            raise ValueError("Original candidate provenance mismatch")
        if row.get("classification") not in CLASSES:
            raise ValueError("Invalid preparer classification")
        if row.get("review_status") != "needs_independent_review":
            raise ValueError("Audit cannot alter independent review status")
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in TEXT_FIELDS):
            raise ValueError("Missing factual/semantic/alias assessment or verification limits")
        refs = row.get("source_ids")
        if not isinstance(refs, list) or not refs or any(sid not in source_map for sid in refs):
            raise ValueError("Missing or unknown evidence source reference")
        if row["classification"] == "recommended_for_independent_review" and not any(
            source_map[sid]["access_method"] == "opened" for sid in refs
        ):
            raise ValueError("Recommendation requires at least one opened source, not excerpts alone")
        replacement = row.get("replacement")
        if replacement is not None:
            require_pending(replacement)
            if replacement.get("evidence_status") != "unverified":
                raise ValueError("Replacement proposals must remain unverified")
            q = by_id.get(replacement.get("query_id"))
            s = by_id.get(replacement.get("candidate_source_query_id"))
            if q is None or s is None or q["query_id"] == s["query_id"]:
                raise ValueError("Replacement query/source must be different verified development records")
            if any(replacement.get(k) != q[k] for k in ("question", "gold_answer")) or replacement.get("proposed_target_answer") != s["gold_answer"]:
                raise ValueError("Replacement provenance mismatch")
            if normalize_answer(q["gold_answer"]) == normalize_answer(s["gold_answer"]):
                raise ValueError("Gold-equivalent replacement")
            if any(not isinstance(replacement.get(k), str) or not replacement[k].strip() for k in ("reason", "limitations")):
                raise ValueError("Missing replacement reasoning/limits")
    return {"schema": "answer-compatible-targets/evidence-audit-summary-v1", "count": len(rows),
            "classification_counts": dict(sorted(Counter(r["classification"] for r in rows).items())),
            "recommended_ids": [r["nomination_id"] for r in rows if r["classification"] == "recommended_for_independent_review"],
            "replacement_proposals": sum(r.get("replacement") is not None for r in rows),
            "source_access_counts": dict(sorted(Counter(s["access_method"] for s in sources).items())),
            "independently_approved_targets": 0,
            "limitation": "Offline validation verifies bindings and pending state, not factual correctness or authenticity of recorded source access."}


def render_report(audit: dict, summary: dict) -> str:
    lines = ["# Phase 4A: factual and semantic evidence audit", "", "Preparation date: " + audit["audit_date"], "",
             "These are research-assistant assessments for independent review, not reviewer decisions or approvals.",
             "All 24 original questions, gold answers and proposals are preserved. The original package remains unchanged.",
             "All human decisions remain pending; reviewer identity, review timestamp and approved target are blank.", "",
             "## Assessment summary", "", "```json", stable_json(summary).rstrip(), "```", "",
             "A recommendation means the evidence is suitable to put before an independent reviewer; it does not certify truth, entailment or experiment readiness.",
             "Credits-based exclusions are identified as inferences. Search excerpts and failed opens are explicitly distinguished from opened page text.",
             "Replacements are development-only leads, all unverified; they have not been substituted into the original package or execution pipeline.", "",
             "## Findings for all 24 nominations", ""]
    source_map = {s["source_id"]: s for s in audit["sources"]}
    for row in audit["records"]:
        lines += [f"### {row['nomination_id']}: {row['classification']}", "", f"Query ID: `{row['query_id']}`", "",
                  row["question"].rstrip(), "", f"Gold: **{row['gold_answer']}**. Proposed target: **{row['proposed_target_answer']}**.", ""]
        for key, label in zip(TEXT_FIELDS, ("Correct-answer investigation", "Candidate falsehood", "Semantic compatibility", "Aliases and ambiguity", "Verification limits")):
            lines += [f"**{label}:** {row[key]}", ""]
        lines += ["Sources: " + ", ".join(f"[{sid}]({source_map[sid]['url']})" for sid in row["source_ids"]) + ".", ""]
        if row.get("replacement"):
            r = row["replacement"]
            lines += [f"**Unverified replacement lead** — query `{r['query_id']}`:", "", r["question"].rstrip(), "",
                      f"Gold: {r['gold_answer']}; proposed target: {r['proposed_target_answer']}; development source: `{r['candidate_source_query_id']}`.", "",
                      r["reason"], "", "Limits: " + r["limitations"], ""]
    lines += ["## Accessed-source catalogue", "", "Claims below are scoped paraphrases, not copied articles. Locator sections help reviewers reopen the relevant content.", ""]
    for s in audit["sources"]:
        lines += [f"### {s['source_id']}", "", f"[Source]({s['url']}) — {s['source_kind']}; {s['access_method']}; accessed {s['accessed_on']}.", "",
                  "Claim supported: " + s["supported_claim"], "", "Locator: " + s["locator"], "", "Limits: " + s["limitations"], ""]
    lines += ["## Unavailable or incomplete access", ""]
    for entry in audit.get("access_limitations", []):
        lines += [f"- [Attempted source]({entry['url']}): {entry['outcome']}."]
    lines += ["", "## Independent review and remaining blockers", "",
              "Use the v3-reviewed approval instructions in README.md only after independent factual and semantic assessment. Do not turn preparer classifications into approval fields.",
              "Resolve weak negative evidence, subtype/genre fit, corporate timelines, institutional founding conventions and soundtrack cue coverage. Reject malformed premises rather than modifying frozen questions or gold labels.",
              "No targets are approved. The reviewed runner/manifest/replay integration remains incomplete. No held-out matrix or real-model generation was run.", ""]
    return "\n".join(lines)


def render_sheet(audit: dict, package: dict) -> str:
    """Updated sheet with original rationale/provenance and links to full findings."""
    from src.attacks.development_review_package import render_csv
    originals = list(csv.DictReader(io.StringIO(render_csv(package))))
    assessments = {r["nomination_id"]: r for r in audit["records"]}
    source_map = {s["source_id"]: s for s in audit["sources"]}
    out = io.StringIO(newline="")
    extra = ["preparer_classification", "evidence_sources", "evidence_report_section", "replacement_proposal"]
    writer = csv.DictWriter(out, fieldnames=list(originals[0]) + extra, lineterminator="\n")
    writer.writeheader()
    for original in originals:
        row = assessments[original["nomination_id"]]
        writer.writerow(original | {
                         "expected_semantic_compatibility": row["semantic_compatibility_assessment"],
                         "manual_review_flags": json.dumps([row["verification_limitations"]], ensure_ascii=False),
                         "preparer_classification": row["classification"],
                         "evidence_sources": json.dumps([{k: source_map[sid][k] for k in ("source_id", "url", "access_method")}
                                                         for sid in row["source_ids"]], ensure_ascii=False),
                         "evidence_report_section": "EVIDENCE_REPORT.md: " + row["nomination_id"],
                         "replacement_proposal": json.dumps(row["replacement"], ensure_ascii=False) if row.get("replacement") else ""})
    return out.getvalue()
