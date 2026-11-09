"""Offline synthetic tests for separately versioned NQ cohort freezing."""
import json

import pytest

from scripts import nq_singlehop_v1_freeze as nq


def sample(count, prefix):
    queries, corpus = [], []
    for i in range(count):
        qid = f"{prefix}_{i}"
        docid = f"{prefix}_doc_{i}"
        corpus.append({"doc_id": docid, "text": f"Source candidate passage for {qid}"})
        queries.append({"query_id": qid, "question": f"Question {qid}?",
                        "gold_answer": f"Answer {qid}", "gold_doc_ids": [docid],
                        "gold_supporting_facts": []})
    return {"queries": queries, "corpus": corpus}


def sources(tmp_path, dev=2, eval=3):
    a, b = tmp_path / "train.json", tmp_path / "validation.json"
    a.write_text(json.dumps(sample(dev, "train")))
    b.write_text(json.dumps(sample(eval, "eval")))
    return a, b


def test_freeze_verify_and_private_seals(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("a" * 40, False))
    a, b = sources(tmp_path)
    out = tmp_path / "private_v1"
    receipt = nq.freeze(out, dev_n=2, eval_n=3, dev_source=a, eval_source=b)
    assert receipt["status"] == "NQ_COHORT_FROZEN_NO_RETRIEVAL_OR_INFERENCE"
    assert receipt["eval_qa_budget_if_all_valid"] == 48
    assert nq.verify(out, receipt["manifest_sha256"]) == {
        "status": "PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY",
        "dev_queries": 2, "eval_queries": 3,
        "matched_QA_completed": False, "heldout_unexposed_certified": False}
    m = json.loads((out / "cohort_manifest.json").read_text())
    assert m["dataset"]["revision"] == nq.REVISION
    assert m["dataset"]["corpus_scope"] == "pooled_NQ_long_answer_candidates_not_full_Wikipedia"
    assert m["prior_exposure_certified"] is False
    assert m["planned_new_experiment"]["expected_eval_qa_calls_if_all_constructions_valid"] == 48
    with pytest.raises(ValueError, match="Output must be a new"):
        nq.freeze(out, dev_n=2, eval_n=3, dev_source=a, eval_source=b)


def test_tamper_detected_no_false_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("b" * 40, False))
    a, b = sources(tmp_path)
    out = tmp_path / "private_v1"
    result = nq.freeze(out, dev_n=2, eval_n=3, dev_source=a, eval_source=b)
    (out / "evaluation_validation.json").write_text('{"queries":[],"corpus":[]}')
    with pytest.raises(ValueError, match="Frozen NQ private corpus changed"):
        nq.verify(out, result["manifest_sha256"])


def test_disjointness_rejects_overlap(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("b" * 40, False))
    a, b = sources(tmp_path)
    eval_data = json.loads(b.read_text())
    eval_data["queries"][0]["query_id"] = "train_0"
    b.write_text(json.dumps(eval_data))
    with pytest.raises(ValueError, match="overlap"):
        nq.freeze(tmp_path / "out", dev_n=2, eval_n=3, dev_source=a, eval_source=b)


def test_missing_gold_document_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("b" * 40, False))
    a, b = sources(tmp_path)
    eval_data = json.loads(b.read_text())
    eval_data["queries"][0]["gold_doc_ids"] = ["nonexistent"]
    b.write_text(json.dumps(eval_data))
    with pytest.raises(ValueError, match="gold document ID"):
        nq.freeze(tmp_path / "out", dev_n=2, eval_n=3, dev_source=a, eval_source=b)


def test_exposed_query_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("b" * 40, False))
    a, b = sources(tmp_path)
    exclusions = tmp_path / "exclusions.json"
    exclusions.write_text(json.dumps(["eval_0"]))
    with pytest.raises(ValueError, match="Previously exposed"):
        nq.freeze(tmp_path / "out", dev_n=2, eval_n=3,
                  dev_source=a, eval_source=b, exposure_exclusions=exclusions)


def test_dirty_git_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("b" * 40, True))
    a, b = sources(tmp_path)
    with pytest.raises(ValueError, match="clean Git"):
        nq.freeze(tmp_path / "out", dev_n=2, eval_n=3, dev_source=a, eval_source=b)


def test_incomplete_source_pair_fails_before_writes(tmp_path):
    a, b = sources(tmp_path)
    with pytest.raises(ValueError, match="both"):
        nq.freeze(tmp_path / "out", dev_n=2, eval_n=3, dev_source=a)


def test_duplicate_document_id_rejected():
    data = sample(2, "x")
    data["corpus"].append(dict(data["corpus"][0]))
    with pytest.raises(ValueError, match="duplicate candidate"):
        nq.snapshot_validate(data, 2, "test")


def test_source_file_is_untrusted_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(nq, "git_state", lambda: ("c" * 40, False))
    a, b = sources(tmp_path)
    receipt = nq.freeze(tmp_path / "out", dev_n=2, eval_n=3, dev_source=a, eval_source=b)
    m = json.loads((tmp_path / "out" / "cohort_manifest.json").read_text())
    assert m["original_source_provenance"] == "operator_supplied_local_json_revision_unverified"
    assert m["input_file_sha256"]["dev_input_sha256"] == nq.digest(a)
    assert receipt["exposure_exclusions_provided"] is False
