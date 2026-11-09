"""Unit tests for the no-inference, private 2Wiki RCD ablation audit."""
import pytest

from scripts.audit_2wiki_rcd_ablations_offline import (
    aggregate_row, cluster_bootstrap, guarded_path, latency_diagnostics,
)


def test_question_cluster_bootstrap_reuses_all_stratum_positions():
    differences = {"shared_question": [1, 1], "another_question": [0]}
    result = cluster_bootstrap(differences, reps=2000, seed=20261109)
    assert result["estimate"] == pytest.approx(2 / 3)
    assert result["n_distinct_question_ids"] == 2
    assert result["n_repeated_cell_positions"] == 3
    assert result == cluster_bootstrap(differences, reps=2000, seed=20261109)
    lo, hi = result["nominal_95pct_question_cluster_CI"]
    assert 0 <= lo <= result["estimate"] <= hi <= 1


def test_original_aggregate_row_matched_pair_accounting():
    row = dict(clean_em=1, poisoned_em=0, target_match=1, clean_target_match=0,
               poison_exposed=1, clean_correct_to_poisoned_wrong=1,
               clean_f1=.8, poisoned_f1=.2,
               retrieval_seconds_per_qa=.02,
               generation_seconds_per_qa=3.0,
               inner_retrieval_calls_per_qa=5)
    result = aggregate_row({f"test_{i}": row for i in range(10)})
    assert result["n_clean_correct"] == 10
    assert result["n_poisoned_correct"] == 0
    assert result["n_target_matches"] == 10
    assert result["total_inner_retrieval_calls"] == 100
    assert result["mean_generation_seconds"] == 3
    assert result["n_clean_correct_to_poisoned_wrong"] == 10


def test_original_aggregate_row_rejects_incomplete_pairs():
    with pytest.raises(ValueError, match="ten matched"):
        aggregate_row({})


def test_latency_outlier_diagnostics():
    vals = [1.0] * 78 + [31.0, 52.6]
    result = latency_diagnostics(vals)
    assert result["n_responses"] == 80
    assert result["n_over_30_seconds"] == 2
    assert result["max_seconds"] == 52.6
    assert result["median_seconds"] == 1.0


def test_private_path_cannot_be_repo_or_outside_private_root(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    assert guarded_path(private / "new_summary.json", private, must_exist=False).parent == private
    with pytest.raises(ValueError, match="under private root"):
        guarded_path(tmp_path / "elsewhere.json", private, must_exist=False)
