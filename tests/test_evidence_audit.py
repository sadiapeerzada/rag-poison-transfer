"""Bindings and pending-state tests; no web or factuality-model calls."""
import copy
import csv
import io
import json
from pathlib import Path

import pytest

from scripts.extract_verified_development_queries import extract_verified
from src.attacks.compatible_targets import TargetAssignmentError, load_reviewed_assignments, select_reviewed_target
from src.attacks.development_review_package import stable_json
from src.attacks.evidence_audit import validate_audit, render_report, render_sheet

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs/reviews/phase4a"


@pytest.fixture
def inputs():
    queries, meta = extract_verified(ROOT / "results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl",
                                  ROOT / "configs/exp_027_hotpotqa_heldout_manifest.json")
    raw = (DIR / "review_package.json").read_bytes()
    return json.loads((DIR / "evidence_audit.json").read_text()), json.loads(raw), raw, queries, meta


def test_all_24_covered_and_artifacts_reproduce(inputs):
    audit, package, raw, queries, meta = inputs
    summary = validate_audit(audit, package, raw, queries, meta)
    assert summary["classification_counts"] == {
        "recommended_for_independent_review": 16, "needs_revision": 5, "reject": 3}
    assert summary["count"] == 24
    assert summary["independently_approved_targets"] == 0
    assert summary["replacement_proposals"] == 7
    assert render_report(audit, summary) == (DIR / "EVIDENCE_REPORT.md").read_text()
    assert render_sheet(audit, package) == (DIR / "review_sheet_audited.csv").read_text()
    assert stable_json(summary) == (DIR / "evidence_audit_summary.json").read_text()
    rows = list(csv.DictReader(io.StringIO(render_sheet(audit, package))))
    assert all(r["human_review_decision"] == "pending" and r["reviewer"] == r["reviewed_at"] == "" for r in rows)
    p12 = next(r for r in rows if r["nomination_id"] == "p12")
    assert "Correct the earlier" in p12["manual_review_flags"]


@pytest.mark.parametrize("defect,match", [
    ("stale", "fingerprint"), ("artifact", "extraction provenance"), ("omission", "every original"), ("duplicate", "duplicate audit"),
    ("question", "identity"), ("target", "identity"), ("approved", "pending"),
    ("reviewer", "pending"), ("timestamp", "pending"), ("decision", "pending"),
    ("boolean_approval", "unset"), ("classification", "classification"),
    ("source", "source reference"), ("source_scope", "access scope"),
    ("source_date", "date"), ("source_duplicate", "Duplicate evidence"),
    ("excerpt_recommendation", "opened source"),
    ("replacement_source", "verified development"), ("replacement_target", "provenance"),
    ("replacement_approval", "pending"), ("replacement_verified", "unverified"),
])
def test_fail_closed(inputs, defect, match):
    a, p, raw, queries, meta = inputs
    row = a["records"][0]
    if defect == "stale": a["base_package_sha256"] = "0" * 64
    elif defect == "artifact": meta["artifact_sha256"] = "0" * 64
    elif defect == "omission": a["records"].pop()
    elif defect == "duplicate": a["records"][1] = copy.deepcopy(row)
    elif defect == "question": row["question"] = "Changed question"
    elif defect == "target": row["proposed_target_answer"] = "Changed target"
    elif defect == "approved": row["approved"] = True
    elif defect == "reviewer": row["reviewer"] = "invented reviewer"
    elif defect == "timestamp": row["reviewed_at"] = "2026-10-25T00:00:00Z"
    elif defect == "decision": row["human_review_decision"] = "approved"
    elif defect == "boolean_approval": row["factually_false"] = True
    elif defect == "classification": row["classification"] = "approved"
    elif defect == "source": row["source_ids"] = ["absent"]
    elif defect == "source_scope": a["sources"][0]["access_method"] = "not_accessed"
    elif defect == "source_date": a["sources"][0]["accessed_on"] = "2026-99-99"
    elif defect == "source_duplicate": a["sources"].append(copy.deepcopy(a["sources"][0]))
    elif defect == "excerpt_recommendation":
        rec = next(r for r in a["records"] if r["classification"] == "recommended_for_independent_review")
        rec["source_ids"] = ["S40"]
    elif defect == "replacement_source": row["replacement"]["candidate_source_query_id"] = "heldout-or-invented-id"
    elif defect == "replacement_target": row["replacement"]["proposed_target_answer"] = "Invented answer"
    elif defect == "replacement_approval": row["replacement"]["approved"] = True
    elif defect == "replacement_verified": row["replacement"]["evidence_status"] = "verified"
    with pytest.raises(ValueError, match=match): validate_audit(a, p, raw, queries, meta)


def test_recommendation_is_not_independent_approval(inputs, tmp_path):
    a, package, raw, queries, meta = inputs
    validate_audit(a, package, raw, queries, meta)
    row = next(r for r in a["records"] if r["classification"] == "recommended_for_independent_review")
    q = next(q for q in queries if q["query_id"] == row["query_id"])
    with pytest.raises(TargetAssignmentError, match="Unapproved"):
        select_reviewed_target(q, {q["query_id"]: row})
    path = tmp_path / "audit.json"
    path.write_text(stable_json(a))
    with pytest.raises(TargetAssignmentError): load_reviewed_assignments(path)


def test_high_risk_findings_do_not_silently_clear(inputs):
    a, _, _, _, _ = inputs
    rows = {r["nomination_id"]: r for r in a["records"]}
    assert rows["p19"]["classification"] == "reject"
    assert rows["p20"]["classification"] == "needs_revision"
    assert rows["p24"]["classification"] == "needs_revision"
    assert "does not prove" in rows["p24"]["target_falsehood_assessment"]
    assert "Franco Corelli" in rows["p12"]["gold_answer_assessment"]
