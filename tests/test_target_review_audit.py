import copy

import pytest

from src.attacks.target_candidates import write_review_template
from src.attacks.target_review_audit import ReviewAuditError, audit_review_template


def _queries():
    return [
        {"query_id": "a", "question": "Which battle was fought here?", "gold_answer": "Bull Run"},
        {"query_id": "b", "question": "Which battle was fought there?", "gold_answer": "Cold Harbor"},
        {"query_id": "c", "question": "Unknown question?", "gold_answer": "Other"},
    ]


def test_audit_reports_coverage_without_claiming_validity(tmp_path):
    queries = _queries()
    payload = write_review_template(queries, tmp_path / "review.json")
    report = audit_review_template(payload, queries)
    assert report["total_queries"] == 3
    assert report["queries_with_suggestions"] == 2
    assert report["queries_without_suggestions"] == 1
    assert report["independently_approved_targets"] == 0
    assert report["scientific_validity"] == "not_assessed"


@pytest.mark.parametrize("change", [
    lambda p: p["assignments"][0].update(approved=True),
    lambda p: p["assignments"][0].update(question_sha256="bad"),
    lambda p: p["assignments"][0].update(suggested_targets=["Bull Run"]),
    lambda p: p["assignments"].append(copy.deepcopy(p["assignments"][0])),
    lambda p: p.update(count=999),
])
def test_audit_fails_closed_on_bad_review_template(tmp_path, change):
    queries = _queries()
    payload = write_review_template(queries, tmp_path / "review.json")
    change(payload)
    with pytest.raises(ReviewAuditError):
        audit_review_template(payload, queries)


@pytest.mark.parametrize("change", [
    lambda r: r.update(suggested_targets=["Invented battle"]),
    lambda r: r.update(suggestion_sources={"Cold Harbor": ["unknown"]}),
    lambda r: r.update(suggested_targets=[]),
])
def test_reject_forged_or_incomplete_source_provenance(tmp_path, change):
    queries = _queries()
    payload = write_review_template(queries, tmp_path / "review.json")
    change(payload["assignments"][0])
    with pytest.raises(ReviewAuditError, match="provenance"):
        audit_review_template(payload, queries)
