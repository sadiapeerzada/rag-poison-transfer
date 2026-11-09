"""Tests use artificial labels and synthetic diagnostics, never report real AUROC."""
import pytest

from src.evaluation.poison_detection import (
    auroc, average_precision, confusion, choose_threshold,
    evaluate, extract_labeled_candidates, query_cluster_bootstrap,
)


def synthetic_case(query_id, swap=False):
    clean = {"agreement": .96, "rank_stability": .92, "rewrite_stability": .93}
    poison = {"agreement": .05, "rank_stability": .15, "rewrite_stability": .08}
    if swap:
        poison, clean = clean, poison
    return {
        "query_id": query_id,
        "condition": "poisoned",
        "known_global_poison_doc_ids": [f"poison::{query_id}"],
        "diagnostics": {
            "consistency_signals": {
                f"poison::{query_id}": poison,
                f"clean::{query_id}": clean,
            },
            "conflict_scores": {
                f"poison::{query_id}": 1., f"clean::{query_id}": 0.,
            },
            "scores": {
                f"poison::{query_id}": {"final_score": 0.1},
                f"clean::{query_id}": {"final_score": 0.9},
            },
        }
    }


def test_valid_source_identity_labels_and_clear_suspicion_direction():
    rows, n, visible = extract_labeled_candidates(synthetic_case("q1"))
    assert len(rows) == 2 and n == visible == 1
    assert [x["label"] for x in rows] == [0, 1]
    assert rows[0]["score"] < rows[1]["score"]
    assert auroc(rows) == 1.
    assert average_precision(rows) == 1.


def test_dev_threshold_frozen_and_no_false_positive_on_synthetic_test():
    result = evaluate([synthetic_case("dev_a"), synthetic_case("dev_b")],
                      [synthetic_case("test_a"), synthetic_case("test_b")])
    assert result["status"] == "POISON_IDENTITY_DETECTION_EVALUATED_EXPLORATORY"
    assert result["threshold_selected_only_on_development"] is True
    assert result["test"]["n_positive_observations"] == 2
    assert result["test"]["auroc"] == 1.
    assert result["test"]["average_precision"] == 1.
    assert result["test"]["at_threshold"]["f1"] == 1.
    assert result["test"]["at_threshold"]["false_positive_rate"] == 0.
    assert result["document_disjoint"] is True


def test_ties_use_half_credit_for_roc():
    examples = [{"label": 1, "score": .5}, {"label": 0, "score": .5}]
    assert auroc(examples) == .5
    assert average_precision(examples) == .5
    assert confusion(examples, 1.)["f1"] == 0.
    assert choose_threshold(examples) == .5


def test_development_test_overlap_rejected():
    with pytest.raises(ValueError, match="question IDs overlap"):
        evaluate([synthetic_case("q1")], [synthetic_case("q1")])


def test_corrupt_or_missing_signals_fail_closed():
    row = synthetic_case("q1")
    del row["diagnostics"]["consistency_signals"]["clean::q1"]
    with pytest.raises(ValueError, match="Missing diagnostic signal"):
        extract_labeled_candidates(row)


def test_needs_both_classes_and_rejects_false_zero_auc():
    row = synthetic_case("q1")
    row["known_global_poison_doc_ids"] = []
    with pytest.raises(ValueError, match="Both poison and clean"):
        evaluate([row], [synthetic_case("q2")])


def test_real_doc_id_overlap_disclosed_and_optional_fail():
    d = synthetic_case("dev")
    t = synthetic_case("test")
    t["diagnostics"]["scores"]["clean::dev"] = t["diagnostics"]["scores"].pop("clean::test")
    t["diagnostics"]["consistency_signals"]["clean::dev"] = t["diagnostics"]["consistency_signals"].pop("clean::test")
    t["diagnostics"]["conflict_scores"]["clean::dev"] = t["diagnostics"]["conflict_scores"].pop("clean::test")
    result = evaluate([d], [t])
    assert result["n_shared_candidate_document_ids_across_cohorts"] == 1
    assert result["document_disjoint"] is False
    with pytest.raises(ValueError, match="candidate documents overlap"):
        evaluate([d], [t], forbid_shared_documents=True)



def test_heldout_query_cluster_ci_has_fixed_dev_threshold_and_defined_replicates():
    result = evaluate([synthetic_case("dev_a"), synthetic_case("dev_b")],
                      [synthetic_case("test_a"), synthetic_case("test_b")],
                      bootstrap_replicates=100, bootstrap_seed=123)
    boot = result["test_query_cluster_bootstrap_ci95"]
    assert boot["resampling_unit"] == "whole questions with all candidate observations"
    assert boot["threshold_refit_on_test"] is False
    assert boot["bootstrap_replicates"] == 100
    assert boot["metrics"]["auroc"]["defined_replicates"] == 100
    assert boot["metrics"]["auroc"]["ci95_percentile"] == [1.0, 1.0]
    assert boot["metrics"]["false_positive_rate"]["ci95_percentile"] == [0.0, 0.0]


def test_query_bootstrap_is_deterministic_and_rejects_duplicate_clusters():
    rows = [synthetic_case("a"), synthetic_case("b", swap=True), synthetic_case("c")]
    first = query_cluster_bootstrap(rows, threshold=.5, reps=100, seed=7)
    second = query_cluster_bootstrap(rows, threshold=.5, reps=100, seed=7)
    assert first == second
    assert 0 <= first["metrics"]["f1"]["ci95_percentile"][0] <= 1
    with pytest.raises(ValueError, match="Repeated question cluster"):
        query_cluster_bootstrap([rows[0], rows[0]], threshold=.5, reps=100)
    with pytest.raises(ValueError, match="replicates"):
        query_cluster_bootstrap(rows, threshold=.5, reps=2)
