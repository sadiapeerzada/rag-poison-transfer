"""Synthetic tests only: they do NOT source-check real 2Wiki claims."""
import hashlib
import json
from datetime import date

import pytest

from scripts import audit_2wiki_source_factuality_ledger as audit


def cases():
    return [
        {"case_id": "a", "query_id": "q1", "construction_status": "valid_construction"},
        {"case_id": "b", "query_id": "q2", "construction_status": "semantic_construction_failed"},
    ]


def source():
    return {"url": "https://example.org/reference", "accessed_date": date.today().isoformat(),
            "short_quote": "Placeholder quotation used only for structural unit testing"}


def ledger():
    return [audit.initial_review(x) for x in cases()]


def test_initial_private_template_reports_zero_adjudication(tmp_path):
    filename = tmp_path / "review_PRIVATE.jsonl"
    receipt = audit.create_template(cases(), filename)
    assert receipt["source_adjudications_performed"] == 0
    assert len(filename.read_text().splitlines()) == 2
    assert "gold_answer" not in filename.read_text()
    with pytest.raises(ValueError, match="fresh"):
        audit.create_template(cases(), filename)


def test_packet_sha_bound_and_not_sensitive_output(tmp_path):
    f = tmp_path / "packet_PRIVATE.jsonl"
    f.write_text("\n".join(json.dumps(v) for v in cases()) + "\n")
    dig = hashlib.sha256(f.read_bytes()).hexdigest()
    assert len(audit.verify_packet(f, dig, require_frozen=False)) == 2
    with pytest.raises(ValueError, match="SHA-256"):
        audit.verify_packet(f, "0" * 64, require_frozen=False)


def test_empty_ledger_is_never_misrepresented_as_reviewed():
    report = audit.audit(cases(), ledger(), "p" * 64, "l" * 64)
    assert report["status"] == "PARTIAL_SOURCE_LEDGER"
    assert report["selected_case_rows"] == 2
    assert report["valid_construction_cases_with_any_review"] == 0
    assert report["source_cited_verdict_rows"] == 0
    assert report["independent_human_adjudication_performed"] is False


def test_source_claim_requires_citation_and_citation_is_not_verified():
    rows = ledger()
    rows[0]["factuality_verdict"] = "source_contradicts_target"
    rows[0]["answer_type_verdict"] = "compatible"
    rows[0]["source_research_date"] = date.today().isoformat()
    with pytest.raises(ValueError, match="dated URL"):
        audit.audit(cases(), rows, "p" * 64, "l" * 64)
    rows[0]["citations"] = [source()]
    receipt = audit.audit(cases(), rows, "p" * 64, "l" * 64)
    assert receipt["source_cited_verdict_rows"] == 1
    assert receipt["independent_source_authenticity_verified_by_tool"] is False
    assert "short_quote" not in json.dumps(receipt)


def test_missing_duplicate_and_invalid_review_records_fail_closed():
    with pytest.raises(ValueError, match="row for every"):
        audit.audit(cases(), ledger()[:1], "", "")
    rows = ledger()
    rows[1]["case_id"] = "a"
    with pytest.raises(ValueError, match="Unknown or duplicated"):
        audit.audit(cases(), rows, "", "")
    rows = ledger()
    rows[0]["review_method"] = "independent_human_adjudication"
    with pytest.raises(ValueError, match="human"):
        audit.audit(cases(), rows, "", "")


def test_cannot_report_nonapplicable_for_mechanically_valid_case():
    rows = ledger()
    rows[0]["factuality_verdict"] = "not_applicable"
    rows[0]["source_research_date"] = date.today().isoformat()
    with pytest.raises(ValueError, match="nonapplicable"):
        audit.audit(cases(), rows, "", "")
