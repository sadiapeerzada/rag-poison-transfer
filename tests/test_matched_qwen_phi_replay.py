"""Synthetic original-Qwen vs fixed-evidence Phi comparison tests; no model calls."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import second_model_prompt_replay as replay
from scripts import compare_qwen_phi_replay_offline as comparison
from src.evaluation.qa_records import generate_qa
from src.pipelines.generator import MockGenerator


def original_inputs(tmp_path, monkeypatch):
    evaluation = tmp_path / "evaluation"
    evaluation.mkdir()
    row_hashes = {}
    for family in replay.FAMILIES:
        for intensity in (1, 3):
            cell = f"{family}.intensity-{intensity}.seed-42"
            directory = evaluation / cell
            directory.mkdir()
            rows = []
            for arm in replay.ARMS:
                for j in range(2):
                    qid = f"synthetic-question-{j}"
                    obs = {}
                    for condition in replay.CONDITIONS:
                        prompt = f"synthetic query {j} {arm} {cell} {condition}"
                        generation = generate_qa(MockGenerator(), prompt, max_tokens=64)
                        obs[f"{condition}_condition"] = {
                            "generation": generation,
                            "answer": generation["extracted_answer"],
                            "em": 1.,
                        }
                    rows.append({
                        "query_id": qid, "pipeline": arm, "construction_status": "valid_construction",
                        "measurement": {
                            "gold_answer": "mock-answer", "poison_target_answer": "wrong-answer",
                            **obs,
                        },
                    })
            path = directory / "rows.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            row_hashes[cell] = replay.sha(path)
    completion_path = evaluation / "evaluation.complete.json"
    completion_path.write_text(json.dumps({"rows_sha256": row_hashes}), encoding="utf-8")
    frozen = replay.sha(completion_path)
    monkeypatch.setattr(replay, "TWOWIKI_COMPLETION_SHA256", frozen)
    monkeypatch.setattr(comparison, "TWOWIKI_COMPLETION_SHA256", frozen)
    plan_path = tmp_path / "private_plan.json"
    receipt = replay.prepare(evaluation, plan_path, n=1, seed=42)
    result_dir = tmp_path / "private_phi"
    result_dir.mkdir()
    snapshot_sha = "e" * 64
    manifest = {
        "schema": comparison.RUN_SCHEMA,
        "plan_sha256": receipt["sha256"], "model_snapshot_sha256": snapshot_sha,
        "model_family": "phi3", "max_tokens": 128,
    }
    (result_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for row in json.loads(plan_path.read_text())["entries"]:
        # Make outcomes visibly different between Qwen and Phi.
        raw = "wrong-answer" if row["condition"] == "poisoned" else "mock-answer"
        phi = {
            "id": row["id"], "plan_sha256": receipt["sha256"],
            "prompt_sha256": row["prompt_sha256"], "model_snapshot_sha256": snapshot_sha,
            "raw_response": raw, "extracted_answer": raw,
            "gold_em": 1. if raw == "mock-answer" else 0.,
            "target_match": raw == "wrong-answer",
        }
        (result_dir / (row["id"] + ".json")).write_text(json.dumps(phi), encoding="utf-8")
    return evaluation, plan_path, receipt["sha256"], result_dir


def test_real_shape_synthetic_matched_comparison(tmp_path, monkeypatch):
    evaluation, plan, pin, result_dir = original_inputs(tmp_path, monkeypatch)
    result = comparison.analyze(plan, pin, evaluation, result_dir)
    assert result["status"] == "PASS_MATCHED_QWEN_PHI_OFFLINE_COMPARISON"
    assert result["n_paired_generator_observations"] == 16
    assert result["n_distinct_selected_query_ids"] == 1
    assert len(result["groups"]) == 16
    for key, row in result["groups"].items():
        assert row["n_matched_replay_items"] == 1
        assert row["qwen_gold_em"]["rate"] == 1.
        assert row["phi_target_match"]["rate"] == (1. if key.endswith("poisoned") else 0.)
    assert result["phi_generation_max_tokens"] == 128
    assert result["qwen_generation_max_tokens_declared_in_frozen_protocol"] == 64
    assert "per-query" in result["limitations"][-1]


def test_original_modified_prompt_or_phi_reply_fails_closed(tmp_path, monkeypatch):
    evaluation, plan, pin, result_dir = original_inputs(tmp_path, monkeypatch)
    d = json.loads(plan.read_text(encoding="utf-8"))
    item = d["entries"][0]
    record_path = result_dir / (item["id"] + ".json")
    row = json.loads(record_path.read_text(encoding="utf-8"))
    row["raw_response"] = "manipulated"
    record_path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="Phi extraction inconsistent"):
        comparison.analyze(plan, pin, evaluation, result_dir)
    row["raw_response"] = row["extracted_answer"]
    record_path.write_text(json.dumps(row), encoding="utf-8")
    comparison.analyze(plan, pin, evaluation, result_dir)
    d["entries"][0]["prompt"] = "tampered"
    plan.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="plan SHA-256 mismatch"):
        comparison.analyze(plan, pin, evaluation, result_dir)


def test_extra_phi_record_rejected(tmp_path, monkeypatch):
    evaluation, plan, pin, result_dir = original_inputs(tmp_path, monkeypatch)
    (result_dir / "unplanned.json").write_text("{}")
    with pytest.raises(ValueError, match="Extra or missing"):
        comparison.analyze(plan, pin, evaluation, result_dir)
