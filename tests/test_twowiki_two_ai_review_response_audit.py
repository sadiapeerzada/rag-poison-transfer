"""Two-AI review response auditing: synthetic fixture tests; zero model calls."""
import json
import hashlib
from pathlib import Path

import pytest

from test_twowiki_two_ai_review_batch import fake_blob
from scripts import prepare_twowiki_two_ai_review_batch as prep
from scripts import audit_twowiki_two_ai_review_responses as audit


def fixture(tmp_path):
    dossier_path = tmp_path / "dossiers.json"
    dossier_path.write_text(json.dumps(fake_blob(), ensure_ascii=False), encoding="utf-8")
    batch_dir = tmp_path / "batch"
    blob = json.loads(dossier_path.read_text(encoding="utf-8"))
    manifest, prompts = prep.make_batch(
        blob, pilot_size=2,
        input_sha256=hashlib.sha256(dossier_path.read_bytes()).hexdigest()
    )
    prep.write_batch(batch_dir, manifest, prompts)
    responses = tmp_path / "responses"
    return dossier_path, batch_dir, responses, manifest, blob["review_dossiers"]


def save_response(responses, case, manifest, n, slot, *,
                  model="synthetic-model-A", target="Fictional B",
                  decision="provisional_accept", incorrect_quote=False,
                  wrong_hash=False, reason_suffix=""):
    raw_dir = responses / f"reviewer_{slot}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / f"case_{n:02}.json"
    raw = {
        "query_id": case["query_id"],
        "dossier_sha256": case["dossier_sha256"],
        "decision": decision,
        "proposed_false_target": target if decision == "provisional_accept" else None,
        "source_chain_valid": True, "gold_supported": True,
        "target_distinct_from_gold": True,
        "target_type_compatible": True,
        "target_contradicted_by_sources": True,
        "aliases_checked": True, "chronology_checked": True,
        "referent_grounded": True,
        "evidence_quotes": [
            {"doc_id": d["doc_id"],
             "exact_quote": "This is an invented quote." if incorrect_quote else d["text"]}
            for d in case["source_documents"]
        ],
        "disagreements_or_caveats": [],
        "reason": "This synthetic test checks the recorded evidence binding thoroughly."
                  + reason_suffix,
    }
    raw_bytes = json.dumps(raw, ensure_ascii=False).encode("utf-8")
    raw_file.write_bytes(raw_bytes)
    meta = {
        "reviewer_slot": slot, "query_id": case["query_id"],
        "model_id": model,
        "review_run_id": "synthetic-run-" + slot + "-" + str(n),
        "reviewed_at": "2026-11-03T17:00:00+05:30",
        "prompt_sha256": (
            manifest["records"][n - 1]["reviewer_prompt_sha256"][slot]
        ),
        "raw_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }
    if wrong_hash:
        meta["raw_response_sha256"] = "0" * 64
    (raw_dir / f"case_{n:02}.provenance.json").write_text(json.dumps(meta))


def test_missing_review_is_explicit_pending(tmp_path):
    dp, bd, rp, _, _ = fixture(tmp_path)
    result = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert result["requested_cases"] == 2
    assert result["status_counts"] == {"pending_review": 2}
    assert result["factual_approvals"] == 0
    assert result["poison_injections"] == 0


def test_distinct_models_agree_but_no_scientific_approval(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    save_response(rp, cases[0], m, 1, "A", reason_suffix="Reviewer one")
    save_response(rp, cases[0], m, 1, "B", model="synthetic-model-B",
                  reason_suffix="Reviewer two")
    report = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    r = report["cases"][0]
    assert r["status"] == "concordant_provisional_ai_only_not_factually_approved"
    assert r["construction_eligible"] is False
    assert r["injection_approved"] is False
    assert report["factual_approvals"] == 0
    assert report["paired_poisoned_evaluation_authorized"] is False


def test_same_model_is_not_two_independent_reviewers(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    save_response(rp, cases[0], m, 1, "A", reason_suffix="first")
    save_response(rp, cases[0], m, 1, "B", reason_suffix="second")
    r = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert r["cases"][0]["status"] == "reviewer_independence_not_demonstrated"


def test_disagreeing_targets_require_adjudication(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    save_response(rp, cases[0], m, 1, "A", reason_suffix="first")
    save_response(rp, cases[0], m, 1, "B", model="synthetic-model-B",
                  target="Fictional C", reason_suffix="second")
    r = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert r["cases"][0]["status"] == "counterfactual_target_disagreement"


def test_uncertain_review_is_no_approval(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    save_response(rp, cases[0], m, 1, "A", reason_suffix="first")
    save_response(rp, cases[0], m, 1, "B", model="synthetic-model-B",
                  decision="uncertain", reason_suffix="second")
    r = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert r["cases"][0]["status"] == "at_least_one_reviewer_abstained"


@pytest.mark.parametrize("issue", ["wrong_quote", "wrong_hash", "missing_provenance"])
def test_tampered_or_partial_response_fails_closed(tmp_path, issue):
    dp, bd, rp, m, cases = fixture(tmp_path)
    save_response(rp, cases[0], m, 1, "A",
                  incorrect_quote=(issue == "wrong_quote"),
                  wrong_hash=(issue == "wrong_hash"))
    if issue == "missing_provenance":
        (rp / "reviewer_A/case_01.provenance.json").unlink()
    r = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    expected = ("pending_review" if issue == "missing_provenance"
                else "invalid_review_requires_correction")
    assert r["cases"][0]["status"] == expected
    assert r["cases"][0]["reviews"]["A"]["status"] == (
        "incomplete_capture" if issue == "missing_provenance"
        else "invalid_capture_or_review")


def test_dossier_mutation_rejected(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    blob = json.loads(dp.read_text())
    blob["review_dossiers"][0]["gold_answer"] = "TAMPERED"
    dp.write_text(json.dumps(blob))
    with pytest.raises(ValueError, match="canonical"):
        audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)


def test_prompt_mutation_rejected(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    f = bd / "reviewer_A/case_01.txt"
    f.write_text(f.read_text() + "new words")
    with pytest.raises(ValueError, match="Review prompt bytes"):
        audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)


def test_gold_alias_cannot_be_proposed_as_false_target(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    save_response(rp, cases[0], m, 1, "A",
                  target=cases[0]["gold_aliases"][0])
    r = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert r["cases"][0]["status"] == "invalid_review_requires_correction"


def test_not_allowed_to_relabel_reviewer_success_as_approval(tmp_path):
    dp, bd, rp, m, cases = fixture(tmp_path)
    r = audit.audit(batch_dir=bd, dossiers_path=dp, responses_dir=rp)
    assert r["source_quote_verification"] == "literal_span_only_not_semantic_entailment"
    assert r["reviewer_provenance"] == "metadata_self_reported_unverified"
    assert r["injection_approvals"] == r["construction_approvals"] == 0
