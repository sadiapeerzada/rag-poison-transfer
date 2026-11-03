"""No-model capture helper regressions."""
import json
from pathlib import Path

import pytest

from test_twowiki_two_ai_review_response_audit import fixture
from scripts.record_twowiki_two_ai_review_response import capture
from scripts.audit_twowiki_two_ai_review_responses import audit


def test_capture_persists_exact_bytes_and_no_auto_approval(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    original = b'{"raw":"unvalidated model output"}\n'
    answer = tmp_path / "model_result.txt"
    answer.write_bytes(original)
    result = capture(
        batch_dir=bd, dossiers=dp, responses_dir=rp,
        case_index=1, reviewer_slot="A", raw_response_file=answer,
        model_id="synthetic-model-A", review_run_id="synthetic-run-A-1",
        reviewed_at="2026-11-03T17:15:00+05:30",
    )
    assert result["status"] == "captured_not_validated"
    assert not result["factual_approval"]
    assert (rp / "reviewer_A/case_01.json").read_bytes() == original
    provenance = json.loads((rp / "reviewer_A/case_01.provenance.json").read_text())
    assert provenance["model_id"] == "synthetic-model-A"
    assert provenance["model_id_and_run_id_are_operator_supplied_not_authenticated"]
    assert provenance["raw_response_sha256"] == result["raw_response_sha256"]
    # The arbitrary example response is *not* a valid reviewer judgment.
    report = audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert report["cases"][0]["status"] == "invalid_review_requires_correction"


def test_capture_refuses_overwrite_even_if_run_is_changed(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    answer = tmp_path / "model_result.txt"
    answer.write_text("{}")
    kwargs = dict(batch_dir=bd, dossiers=dp, responses_dir=rp,
                  case_index=1, reviewer_slot="A",
                  raw_response_file=answer,
                  model_id="synthetic-model-A", review_run_id="synthetic-run",
                  reviewed_at="2026-11-03T17:15:00+05:30")
    capture(**kwargs)
    with pytest.raises(FileExistsError):
        capture(**kwargs)


def test_capture_requires_timezone_and_source_identity(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    answer = tmp_path / "model_result.txt"
    answer.write_text("{}")
    kwargs = dict(batch_dir=bd, dossiers=dp, responses_dir=rp,
                  case_index=1, reviewer_slot="B",
                  raw_response_file=answer,
                  model_id="synthetic-model-B", review_run_id="synthetic-run-B",
                  reviewed_at="2026-11-03T17:15:00")
    with pytest.raises(ValueError, match="time zone"):
        capture(**kwargs)
    kwargs["reviewed_at"] = "2026-11-03T17:15:00+05:30"
    kwargs["case_index"] = 7
    with pytest.raises(ValueError, match="case index"):
        capture(**kwargs)
