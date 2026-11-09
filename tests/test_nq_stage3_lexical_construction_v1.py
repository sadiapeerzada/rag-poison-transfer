"""Synthetic NQ targets and lexical poisons; no network or real model calls."""
import json

import pytest

from scripts import nq_stage3_lexical_construction_v1 as stage3


def synthetic_cohort(tmp_path):
    root = tmp_path / "cohort"
    root.mkdir()
    dev = {
        "queries": [
            {"query_id":"d1","question":"What is an Alpha?", "gold_answer":"Alpha",
             "gold_doc_ids":["dd1"]},
            {"query_id":"d2","question":"What is a Beta?", "gold_answer":"Beta",
             "gold_doc_ids":["dd2"]},
        ],
        "corpus": [
            {"doc_id":"dd1","text":"An Alpha example"},
            {"doc_id":"dd2","text":"A Beta example"}
        ]
    }
    evaluation = {
        "queries": [
            {"query_id":f"q{i}", "question":f"Who founded Test Group {i}?",
             "gold_answer":f"Founder {i}", "gold_doc_ids":[f"ed{i}"]}
            for i in range(4)],
        "corpus": [
            {"doc_id":f"ed{i}", "text":f"The Test Group {i} was founded by Founder {i}."}
            for i in range(4)]
    }
    (root / "dev_train.json").write_text(json.dumps(dev))
    (root / "evaluation_validation.json").write_text(json.dumps(evaluation))
    return root


def prepare(tmp_path, monkeypatch):
    cohort = synthetic_cohort(tmp_path)
    monkeypatch.setattr(stage3, "verify", lambda *args: {
        "status":"PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY"
    })
    t = tmp_path / "targets_PRIVATE.json"
    receipt = stage3.prepare_targets(cohort, "a"*64, t)
    assert receipt["status"] == "PRIVATE_NQ_NON_GOLD_TARGETS_FROZEN_NO_INFERENCE"
    assert receipt["n_queries"] == 4
    return cohort, t, receipt["targets_sha256"]


def test_lexical_intensities_have_same_target_and_different_documents(tmp_path, monkeypatch):
    cohort, t, target_sha = prepare(tmp_path, monkeypatch)
    outcomes = []
    for intensity in (1,3):
        dest = tmp_path / f"lexical-{intensity}-PRIVATE.json"
        receipt = stage3.construct_lexical(
            cohort, "a"*64, t, target_sha, dest, intensity=intensity)
        assert receipt["status"] == "PRIVATE_NQ_LEXICAL_CONSTRUCTION_SEALED_NO_QA_INFERENCE"
        assert receipt["n_queries"] == 4
        assert receipt["n_poison_documents"] == 4*intensity
        verified = stage3.verify_lexical(
            cohort, "a"*64, t, target_sha, dest, receipt["construction_sha256"])
        assert verified["status"] == "PASS_PRIVATE_NQ_LEXICAL_CONSTRUCTION_INTEGRITY_ONLY"
        assert verified["qa_executed"] is False
        outcomes.append(json.loads(dest.read_text()))
    assignments = lambda x: {r["query_id"]:r["target_answer"] for r in x["question_poison_associations_private"]}
    assert assignments(outcomes[0]) == assignments(outcomes[1])
    assert outcomes[0]["poison_instance_fingerprint"] != outcomes[1]["poison_instance_fingerprint"]
    assert outcomes[0]["validation_checks"] and all(outcomes[0]["validation_checks"].values())


def test_tampered_private_poison_seal_fails_closed(tmp_path, monkeypatch):
    cohort, t, target_sha = prepare(tmp_path, monkeypatch)
    dest = tmp_path / "lexical_PRIVATE.json"
    receipt = stage3.construct_lexical(cohort, "a"*64, t, target_sha, dest)
    payload = json.loads(dest.read_text())
    payload["poison_documents_private"][0]["text"] = "tampered"
    dest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="digest mismatch"):
        stage3.verify_lexical(cohort, "a"*64, t, target_sha,
                              dest, receipt["construction_sha256"])


def test_tampered_target_sha_fails_closed(tmp_path, monkeypatch):
    cohort, t, target_sha = prepare(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="target manifest SHA mismatch"):
        stage3.construct_lexical(cohort, "a"*64, t, "f"*64,
                                 tmp_path / "never.json")


def test_no_overwrite_of_existing_private_seal(tmp_path, monkeypatch):
    cohort, t, target_sha = prepare(tmp_path, monkeypatch)
    dest = tmp_path / "lexical_PRIVATE.json"
    stage3.construct_lexical(cohort, "a"*64, t, target_sha, dest)
    with pytest.raises(ValueError, match="new private"):
        stage3.construct_lexical(cohort, "a"*64, t, target_sha, dest)


def test_forbids_unplanned_intensity(tmp_path, monkeypatch):
    cohort, t, target_sha = prepare(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="intensity 1 and 3"):
        stage3.construct_lexical(cohort, "a"*64, t, target_sha, tmp_path / "out", intensity=5)


def test_freeze_requires_nonempty_diverse_dev_targets(tmp_path, monkeypatch):
    cohort = synthetic_cohort(tmp_path)
    monkeypatch.setattr(stage3, "verify", lambda *args: {
        "status":"PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY"})
    dev = json.loads((cohort / "dev_train.json").read_text())
    dev["queries"] = dev["queries"][:1]
    (cohort / "dev_train.json").write_text(json.dumps(dev))
    with pytest.raises(ValueError, match="At least two"):
        stage3.prepare_targets(cohort, "a"*64, tmp_path / "out")
