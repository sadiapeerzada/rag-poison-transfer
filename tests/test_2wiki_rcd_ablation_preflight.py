"""Synthetic evidence-only tests for bounded RCD ablation preflight.

Fixtures deliberately contain no real held-out questions or model outputs.
"""
import json
from pathlib import Path

import pytest

from scripts import prepare_2wiki_rcd_ablation_plan as stage


def json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    return stage.sha(path)


def make_original_tree(tmp_path, monkeypatch):
    root = tmp_path / "restore"
    croot = root / "execution" / "construction"
    eroot = root / "execution" / "evaluation"
    croot.mkdir(parents=True)
    eroot.mkdir(parents=True)
    questions = [
        {
            "query_id": f"q{i:03d}",
            "question": f"Synthetic question number {i}?",
            "gold_answer": f"gold_{i}",
            "gold_doc_ids": ["clean_doc"],
        }
        for i in range(300)
    ]
    data = {"corpus": [{"doc_id": "clean_doc", "text": "Synthetic evidence"}],
            "queries": questions}
    local_data = tmp_path / "private_local_data.json"
    local_sha = json_file(local_data, data)
    proto = {
        "binding": {"scope": "heldout", "query_ids": [q["query_id"] for q in questions]},
        "replication": {
            "schema": "rag-poison-transfer.2wiki-replication-inputs/v2",
            "local_data": str(local_data), "local_data_sha256": local_sha,
        },
    }
    pins = {"protocol.json": json_file(root / "protocol.json", proto)}
    cells, row_pins, entries = {}, {}, []
    for family in stage.FAMILIES:
        for intensity in (1, 3):
            cid = f"{family}.intensity-{intensity}.seed-42"
            records = []
            rows = []
            for i, q in enumerate(questions):
                valid = i < 10
                docs = [
                    {"doc_id": f"attack_doc_{cid}_{i}_{j}", "text": "Synthetic attack evidence"}
                    for j in range(intensity)
                ] if valid else []
                records.append({
                    "query_id": q["query_id"],
                    "status": "valid_construction" if valid else "target_construction_failed",
                    "target_answer": f"target_{i}" if valid else None,
                    "documents": docs,
                })
                for arm in stage.ARMS:
                    rows.append({
                        "query_id": q["query_id"],
                        "pipeline": arm,
                        "construction_status": "valid_construction" if valid else "target_construction_failed",
                        "measurement": {"poison_target_answer": f"target_{i}"} if valid else None,
                    })
                    if valid:
                        for condition in stage.CONDITIONS:
                            entries.append({
                                "family": family, "intensity": intensity, "seed": 42,
                                "query_id": q["query_id"], "arm": arm, "condition": condition,
                                "gold_answer": q["gold_answer"],
                            })
            csha = json_file(croot / cid / "construction.json", {
                "family": family, "intensity": intensity, "seed": 42,
                "records": records,
            })
            cells[cid] = {"path": f"{cid}/construction.json", "sha256": csha}
            row_pins[cid] = json_file(eroot / cid / "rows.json", rows)
    cplan = {
        "clean_corpus_fingerprint": stage.corpus_fingerprint(data["corpus"]),
        "query_set_fingerprint": stage.query_set_fingerprint(data["queries"]),
    }
    json_file(croot / "construction.plan.json", cplan)
    c_inventory = {
        p.relative_to(croot).as_posix(): stage.sha(p)
        for p in croot.rglob("*") if p.is_file()
    }
    seal = {
        "protocol_sha256": pins["protocol.json"], "scope": "heldout",
        "plan": cplan, "cells": cells, "files_sha256": c_inventory,
    }
    seal_key = "execution/construction/construction.seal.json"
    pins[seal_key] = json_file(croot / "construction.seal.json", seal)
    e_inventory = {
        p.relative_to(eroot).as_posix(): stage.sha(p)
        for p in eroot.rglob("*") if p.is_file()
    }
    complete = {
        "protocol_sha256": pins["protocol.json"], "scope": "heldout",
        "construction_seal_sha256": pins[seal_key],
        "rows_sha256": row_pins,
        "files_sha256": e_inventory,
    }
    pins["execution/evaluation/evaluation.complete.json"] = json_file(
        eroot / "evaluation.complete.json", complete
    )
    pins["execution/aggregate.json"] = json_file(root / "execution" / "aggregate.json", {
        "schema": "synthetic-original-aggregate-only",
    })
    monkeypatch.setattr(stage, "ORIGINAL_PINS", pins)
    plan = tmp_path / "phi_plan_PRIVATE.json"
    plan_sha = json_file(plan, {
        "schema": "rag-poison-transfer.private-fixed-evidence-second-model-plan/v1",
        "evaluation_completion_sha256": pins["execution/evaluation/evaluation.complete.json"],
        "entries": entries,
    })
    monkeypatch.setattr(stage, "PLAN_PIN", plan_sha)
    assert len(entries) == 160
    return root, plan, plan_sha, local_data


def test_prepares_original_hash_bound_six_variant_480_call_plan(tmp_path, monkeypatch):
    root, plan, pin, data = make_original_tree(tmp_path, monkeypatch)
    out = tmp_path / "bounded_ablations_PRIVATE.json"
    result = stage.prepare(root, plan, pin, out, data, full_stage_hashes=True)
    assert result["status"] == "PRIVATE_ABLATION_PLAN_PREPARED_NO_INFERENCE"
    assert result["planned_cells"] == 4
    assert result["planned_variants"] == 6
    assert result["planned_qa_calls"] == 480
    assert result["selected_query_slots"] == 40
    assert result["original_stage_files_checked"]["construction_file_count"] == 5
    assert result["original_stage_files_checked"]["evaluation_file_count"] == 4
    contents = json.loads(out.read_text())
    assert contents["distinct_query_ids"] == 10
    assert contents["study_design"].startswith("post-hoc exploratory")
    assert set(contents["variants"]) == set(stage.VARIANTS)
    assert any("No source-independent semantic falsehood verification" in s for s in contents["limitations"])
    with pytest.raises(ValueError, match="NEW private plan"):
        stage.prepare(root, plan, pin, out, data)


def test_tamper_fails_on_local_data_and_on_selected_original_cell(tmp_path, monkeypatch):
    root, plan, pin, data = make_original_tree(tmp_path, monkeypatch)
    data.write_text(data.read_text().replace("Synthetic evidence", "Tampered evidence"))
    with pytest.raises(ValueError, match="Evidence SHA-256 mismatch"):
        stage.prepare(root, plan, pin, tmp_path / "out1.json", data)
    # Recreate complete, correctly pinned synthetic fixture for cell tamper.
    new_dir = tmp_path / "another"
    new_dir.mkdir()
    root, plan, pin, data = make_original_tree(new_dir, monkeypatch)
    file = root / "execution" / "construction" / "lexical_influential_token.intensity-1.seed-42" / "construction.json"
    file.write_text(file.read_text().replace("Synthetic attack evidence", "Altered attack evidence"))
    with pytest.raises(ValueError, match="Sealed stage mismatch"):
        stage.prepare(root, plan, pin, new_dir / "out2.json", data)


def test_variant_weights_validation_rejects_unfrozen_variants():
    from copy import deepcopy
    variants = deepcopy(stage.VARIANTS)
    assert stage.validate_variant_matrix(variants) is True
    variants["no_conflict_k3"]["consistency_weight"] = .7
    with pytest.raises(ValueError, match="weights must sum to one"):
        stage.validate_variant_matrix(variants)
    variants = deepcopy(stage.VARIANTS)
    variants["full_k1"]["top_k"] = 10
    with pytest.raises(ValueError, match="Out-of-protocol"):
        stage.validate_variant_matrix(variants)


def test_missing_source_plan_context_not_silently_filled(tmp_path, monkeypatch):
    root, plan, pin, data = make_original_tree(tmp_path, monkeypatch)
    obj = json.loads(plan.read_text())
    obj["entries"].pop()
    plan.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="Evidence SHA-256 mismatch"):
        stage.prepare(root, plan, pin, tmp_path / "missing.json", data)
