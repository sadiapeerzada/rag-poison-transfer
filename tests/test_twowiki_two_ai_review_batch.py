"""Blinded 2Wiki two-AI review-pack creation: synthetic, no model."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from scripts import prepare_twowiki_two_ai_review_batch as review
from scripts.prepare_twowiki_generic_dev25_review_dossiers import make_dossier


def fake_blob():
    doc = {
        "a": {"doc_id": "a", "text": "An original fictional event took place in A."},
        "b": {"doc_id": "b", "text": "Fictional person B was connected to the event."},
    }
    cases = []
    for i in range(20):
        q = {
            "query_id": f"synthetic-train-{i:02}",
            "question": f"Where did fictional event {i} take place?",
            "gold_answer": "A",
            "gold_aliases": ["Alternate name for A"],
            "gold_doc_ids": ["a", "b"],
        }
        cases.append(make_dossier(q, doc))
    return {
        "schema": review.DOSSIER_SCHEMA, "scope": "train_development_only",
        "selection": "unreviewed_20_from_frozen_25_query_clean_baseline",
        "dataset_sha256": review.DATASET_SHA,
        "new_review_dossier_count": 20,
        "source_complete_review_dossier_count": 20,
        "source_blocked_dossier_count": 0,
        "model_calls": 0, "reviewers_ran": 0,
        "independent_reviews_completed": 0,
        "poison_injections": 0, "heldout_queries_accessed": 0,
        "paired_poisoned_evaluation_authorized": False,
        "review_dossiers": cases,
    }


def test_first_six_are_predeclared_and_prompts_are_blinded():
    blob = fake_blob()
    manifest, prompts = review.make_batch(
        blob, pilot_size=6, input_sha256="0" * 64
    )
    assert manifest["pilot_size"] == 6
    assert len(manifest["records"]) == 6
    assert len(prompts) == 12
    assert [x["query_id"] for x in manifest["records"]] == [
        f"synthetic-train-{i:02}" for i in range(6)
    ]
    assert all(x.startswith("reviewer_A/") or x.startswith("reviewer_B/")
               for x in prompts)
    assert manifest["reviewer_model_ids"] is None
    assert manifest["reviews_submitted"] == 0
    assert manifest["factual_approvals"] == 0
    assert manifest["poison_injections"] == 0
    assert manifest["heldout_queries_accessed"] == 0
    for name, text in prompts.items():
        assert "UNTRUSTED SOURCE DATA" in text
        assert "abstain" in text.lower()
        assert "Never output reviewer model ID" in text
        assert "source_documents" in text
        assert "synthetic-train" in text


def test_prompt_hashes_bind_exact_utf8():
    manifest, prompts = review.make_batch(
        fake_blob(), pilot_size=2, input_sha256="1" * 64
    )
    for r in manifest["records"]:
        i = r["batch_index"]
        for slot in ("A", "B"):
            txt = prompts[f"reviewer_{slot}/case_{i:02}.txt"]
            assert r["reviewer_prompt_sha256"][slot] == hashlib.sha256(
                txt.encode("utf-8")
            ).hexdigest()
    assert prompts["reviewer_A/case_01.txt"] != prompts["reviewer_B/case_01.txt"]


def test_dossier_change_or_source_change_rejected():
    b = fake_blob()
    b["review_dossiers"][0]["gold_answer"] = "tampered"
    with pytest.raises(ValueError, match="canonical payload"):
        review.make_batch(b, pilot_size=6, input_sha256="0" * 64)
    b = fake_blob()
    b["review_dossiers"][0]["source_documents"][0]["text"] = "tampered"
    # Detect the full dossier hash and not just document text.
    with pytest.raises(ValueError):
        review.make_batch(b, pilot_size=6, input_sha256="0" * 64)


@pytest.mark.parametrize("bad", (0, -1, 21, "6", True))
def test_size_refuses_invalid_pilot(bad):
    with pytest.raises(ValueError):
        review.make_batch(fake_blob(), pilot_size=bad, input_sha256="0" * 64)


def test_missing_unapproved_boundary_fails():
    b = fake_blob()
    b["review_dossiers"][0]["review_approval"] = True
    with pytest.raises(ValueError):
        review.validate_dossiers(b)
    b = fake_blob()
    b["reviewers_ran"] = 2
    with pytest.raises(ValueError):
        review.validate_dossiers(b)
    b = fake_blob()
    b["source_complete_review_dossier_count"] = 19
    with pytest.raises(ValueError):
        review.validate_dossiers(b)


def test_only_frozen_twenty_not_test_or_new_benchmark():
    b = fake_blob()
    b["review_dossiers"].pop()
    with pytest.raises(ValueError):
        review.validate_dossiers(b)
    b = fake_blob()
    b["scope"] = "heldout"
    with pytest.raises(ValueError):
        review.validate_dossiers(b)


def test_output_never_overwritten(tmp_path):
    m, prompts = review.make_batch(fake_blob(), pilot_size=1,
                                    input_sha256="0" * 64)
    output = tmp_path / "review_batch"
    review.write_batch(output, m, prompts)
    assert (output / "manifest.json").exists()
    assert len(list((output / "reviewer_A").glob("*.txt"))) == 1
    with pytest.raises(FileExistsError):
        review.write_batch(output, m, prompts)


def test_reviewers_not_executed_or_impersonated():
    m, prompts = review.make_batch(fake_blob(), pilot_size=3,
                                    input_sha256="0" * 64)
    assert m["reviewer_run_ids"] is None
    assert m["reviewer_model_ids"] is None
    assert m["reviews_verified"] == 0
    assert "run_id" not in m["records"][0]
    assert all("proposed_false_target\": null" not in t for t in prompts.values())
