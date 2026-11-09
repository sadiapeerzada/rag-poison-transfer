"""Synthetic tests for exact original-Qwen response reuse. No inference."""
import json
import pytest

from scripts import run_2wiki_iterative_matched_qa as it
from test_run_2wiki_iterative_matched_qa import make_plan


def test_optimized_plan_reuses_exact_74_prompts_and_requests_only_six(tmp_path):
    plan = make_plan()
    # These synthetic fixtures mimic 74 unchanged and 6 changed prompts.
    for row in plan["entries"][:74]:
        row["baseline_frozen_dense"]["original_prompt_sha256"] = row["prompt_sha256"]
    p = tmp_path / "original_private_plan.json"
    p.write_text(json.dumps(plan))
    dest = tmp_path / "optimized_private_plan.json"
    receipt = it.optimize(
        prepared_plan=p, prepared_plan_sha256=it.sha(p), out=dest
    )
    assert receipt["total_matched_arm_entries"] == 80
    assert receipt["identical_iterative_prompts_reusing_the_same_frozen_dense_answer"] == 74
    assert receipt["new_real_qwen_inference_requests_required"] == 6
    saved = json.loads(dest.read_text())
    assert it.verify_plan(saved)
    assert saved["original_prepared_plan_sha256"] == it.sha(p)
    assert saved["required_new_qa_calls"] == 6
    assert sum(r["reuse_frozen_dense_qa_for_iterative"] for r in saved["entries"]) == 74
    assert it.sha(dest) == receipt["optimized_plan_sha256"]
    with pytest.raises(ValueError, match="new private"):
        it.optimize(prepared_plan=p, prepared_plan_sha256=it.sha(p), out=dest)


def test_optimized_plan_fails_closed_on_forged_reuse_flag():
    plan = make_plan()
    plan["status"] = it.OPTIMIZED_PLAN_STATUS
    plan["original_prepared_plan_sha256"] = "0" * 64
    plan["identical_frozen_dense_qa_reuse_count"] = 1
    plan["required_new_qa_calls"] = 79
    for i,row in enumerate(plan["entries"]):
        row["reuse_frozen_dense_qa_for_iterative"] = i == 0
    with pytest.raises(ValueError, match="exact prompt/evidence parity"):
        it.verify_plan(plan)


def test_identical_sha_without_matching_evidence_ids_cannot_reuse():
    plan = make_plan()
    row = plan["entries"][0]
    row["baseline_frozen_dense"]["original_prompt_sha256"] = row["prompt_sha256"]
    row["baseline_frozen_dense"]["original_evidence_doc_ids"] = ["an_entirely_different_doc"]
    assert it.identical_frozen_prompt(row) is False


def test_unoptimized_plan_cannot_start_real_model_calls(tmp_path):
    p = tmp_path / "original_prepared_plan.json"
    p.write_text(json.dumps(make_plan()))
    with pytest.raises(ValueError, match="Optimize exact-repeat prompts"):
        it.run(
            plan_file=p, plan_sha256=it.sha(p),
            original_protocol=tmp_path / "not_needed_protocol.json",
            model_snapshot=tmp_path / "not_needed_model",
            results_dir=tmp_path / "must_not_be_created",
            execute=True,
        )
    assert not (tmp_path / "must_not_be_created").exists()


def test_optimized_zero_new_qwen_calls_entirely_reuses_original_controls(tmp_path):
    plan = make_plan()
    for row in plan["entries"]:
        row["baseline_frozen_dense"]["original_prompt_sha256"] = row["prompt_sha256"]
    original = tmp_path / "original.json"
    original.write_text(json.dumps(plan))
    optimized = tmp_path / "optimized.json"
    receipt = it.optimize(
        prepared_plan=original, prepared_plan_sha256=it.sha(original), out=optimized
    )
    assert receipt["new_real_qwen_inference_requests_required"] == 0
    assert receipt["identical_iterative_prompts_reusing_the_same_frozen_dense_answer"] == 80
