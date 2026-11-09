"""Synthetic invariants only; real Task-6 results require original private sealed run."""
import json
from pathlib import Path

import pytest

from scripts import evaluate_saved_2wiki_rcd_poison_detection as actual
from src.evaluation.poison_detection import evaluate


def _entry(qid="q1", cell="lexical_influential_token.intensity-1.seed-42"):
    sig = {
        "clean_id": {"agreement": .9, "rank_stability": .8, "rewrite_stability": .8},
        "other_query_poison": {"agreement": .1, "rank_stability": .2, "rewrite_stability": .2},
        "local_poison": {"agreement": .2, "rank_stability": .3, "rewrite_stability": .3},
    }
    scores = {
        "clean_id": {"conflict": 0.0, "final_score": .9},
        "other_query_poison": {"conflict": 0.8, "final_score": .2},
        "local_poison": {"conflict": 0.9, "final_score": .1},
    }
    return {
        "cell_id": cell, "variant": "full_k3", "query_id": qid, "condition": "poisoned",
        "poison_doc_ids": ["local_poison"],
        "candidate_consistency_features": sig,
        "candidate_scores": scores,
    }


def test_uses_full_global_poison_labels_not_just_current_query():
    source = _entry()
    row = actual.document_identity_record(
        source,
        {"local_poison", "other_query_poison"},
        {"local_poison"}, {"clean_id"},
    )
    assert row["known_global_poison_doc_ids"] == ["local_poison", "other_query_poison"]
    from src.evaluation.poison_detection import extract_labeled_candidates
    labeled, known, visible = extract_labeled_candidates(row)
    assert known == visible == 2
    assert sum(r["label"] for r in labeled) == 2
    assert not any(r["doc_id"] == "clean_id" and r["label"] for r in labeled)
    assert len(labeled) == 3


def test_missing_candidate_features_or_source_poison_mismatch_fails_closed():
    source = _entry()
    with pytest.raises(ValueError, match="poison identity"):
        actual.document_identity_record(source, {"another"}, {"local_poison"}, {"clean_id"})
    source["candidate_scores"]["unexpected"] = {"conflict": 0.1}
    with pytest.raises(ValueError, match="identities differ"):
        actual.document_identity_record(source, {"local_poison", "other_query_poison"},
                                        {"local_poison"}, {"clean_id"})
    del source["candidate_scores"]["unexpected"]
    del source["candidate_scores"]["local_poison"]["conflict"]
    with pytest.raises(ValueError, match="conflict"):
        actual.document_identity_record(source, {"local_poison", "other_query_poison"},
                                        {"local_poison"}, {"clean_id"})


def test_unknown_candidate_ids_rejected_even_if_in_score_dictionary():
    source = _entry()
    with pytest.raises(ValueError, match="Candidate document not"):
        actual.document_identity_record(source, {"local_poison"},
                                        {"local_poison"}, {"something_else"})


def test_unique_question_deduplication_prior_to_splitting():
    rows = []
    for n in range(36):
        x = _entry(qid=f"question_{n:02}")
        rows.append(x)
    for i in range(4):
        y = _entry(qid=f"question_{i:02}", cell="semantic_fluent_false_evidence.intensity-1.seed-42")
        rows.append(y)
    p = {"entries": rows}
    selected = actual.unique_full_k3(p)
    assert len(selected) == 36
    dev, test = actual.split_by_question(selected)
    assert len(dev) == len(test) == 18
    assert not set(dev) & set(test)
    assert (dev, test) == actual.split_by_question(selected)
    with pytest.raises(ValueError, match="exactly 40"):
        actual.unique_full_k3({"entries": rows[:39]})


def test_detector_workflow_uses_real_scores_and_never_claims_truth():
    source = _entry()
    actual_rows = []
    for i in range(8):
        v = dict(source)
        v["query_id"] = f"sample_{i}"
        actual_rows.append(actual.document_identity_record(
            v, {"local_poison", "other_query_poison"}, {"local_poison"}, {"clean_id"}
        ))
    result = evaluate(actual_rows[:4], actual_rows[4:],
                      forbid_shared_documents=False, bootstrap_replicates=100)
    assert result["n_shared_candidate_document_ids_across_cohorts"] == 3
    assert result["test"]["n_positive_observations"] == 8
    assert result["test"]["n_negative_observations"] == 4
    assert result["test"]["auroc"] == 1.0
    assert result["test_query_cluster_bootstrap_ci95"]["threshold_refit_on_test"] is False
    assert "NOT independently verified factual falsehood" in result["limitations"][0]


def test_synthetic_sealed_census_must_include_other_query_poison_ids(monkeypatch, tmp_path):
    root = tmp_path / "frozen"
    (root / "execution" / "construction").mkdir(parents=True)
    (root / "execution" / "evaluation").mkdir(parents=True)
    cid = "lexical_influential_token.intensity-1.seed-42"
    query_ids = [f"q{i}" for i in range(300)]
    records = [
        {"query_id": qid, "status": "valid_construction", "documents": [
            {"doc_id": f"injected_{i}", "text": "Not a real historical claim"}
        ]}
        for i, qid in enumerate(query_ids)
    ]
    proto = {"binding": {"scope": "heldout"}, "replication": {
        "local_data": str(tmp_path / "local.json"), "local_data_sha256": "pinned"}}
    seal = {"protocol_sha256": actual.ORIGINAL_PINS["protocol.json"],
            "cells": {cid: {"path": f"{cid}/construction.json", "sha256": "cellhash"}}}
    complete = {
        "protocol_sha256": actual.ORIGINAL_PINS["protocol.json"],
        "construction_seal_sha256":
            actual.ORIGINAL_PINS["execution/construction/construction.seal.json"],
        "rows_sha256": {cid: "evalhash"}}
    data = {"queries": [{"query_id": x} for x in query_ids],
            "corpus": [{"doc_id": "clean_id"}]}
    cells = {"protocol.json": proto, "construction.seal.json": seal,
             "evaluation.complete.json": complete,
             "local.json": data, "construction.json": {"records": records, "intensity": 1}}
    monkeypatch.setattr(actual, "require_json",
                        lambda path, sha: cells[Path(path).name])
    by_cell, by_query, clean = actual.global_injection_sets(root, {cid})
    assert clean == {"clean_id"}
    assert len(by_cell[cid]) == 300
    assert "injected_299" in by_cell[cid]
    assert by_query[cid]["q0"] == {"injected_0"}
    records[1]["documents"][0]["doc_id"] = "clean_id"
    with pytest.raises(ValueError, match="collided"):
        actual.global_injection_sets(root, {cid})
