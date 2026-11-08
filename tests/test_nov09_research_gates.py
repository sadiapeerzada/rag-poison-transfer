"""Offline research-gate tests. Synthetic data only: no benchmark text or model calls."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import audit_hotpotqa_transfer_raw_offline as raw
from scripts import rcd_offline_scoring_ablations as abl
from scripts import second_model_prompt_replay as replay


def test_transfer_inventory_detects_tampering_and_extra_files(tmp_path):
    root=tmp_path/"sealed";root.mkdir()
    (root/"x.json").write_text('{"ok":1}')
    digest=raw.sha256(root/"x.json")
    assert raw.verify_inventory(root,{"files_sha256":{"x.json":digest}},exclude={"marker.json"}) == 1
    (root/"x.json").write_text('{"ok":2}')
    with pytest.raises(ValueError,match="Inventory mismatch"):
        raw.verify_inventory(root,{"files_sha256":{"x.json":digest}},exclude={"marker.json"})
    (root/"x.json").write_text('{"ok":1}')
    (root/"unrecorded.json").write_text("{}")
    with pytest.raises(ValueError,match="Inventory mismatch"):
        raw.verify_inventory(root,{"files_sha256":{"x.json":digest}},exclude={"marker.json"})


def test_transfer_rejects_nonexistent_pinned_file(tmp_path):
    with pytest.raises(ValueError,match="Missing/pin mismatch"):
        raw.require_pin(tmp_path/"not-found","a"*64)


def test_rcd_score_only_replay_and_rejects_unavailable_diagnostics():
    d={"scores":{
        "d1":{"consistency":.9,"redundancy":0.,"conflict":1.,"base_rank_score":.5},
        "d2":{"consistency":.75,"redundancy":0.,"conflict":0.,"base_rank_score":.5}},
        "consistency_signals":{
            "d1":{"agreement":.9,"rank_stability":.9,"rewrite_stability":.9},
            "d2":{"agreement":.75,"rank_stability":.75,"rewrite_stability":.75}},
        "selected_doc_ids":["d2","d1"]}
    assert abl.ranking(d,"full")==["d2","d1"]
    assert abl.ranking(d,"no_conflict_penalty")==["d1","d2"]
    s=abl.summarize([{"condition":"poisoned","query_id":"synthetic_q1",
                      "poison_doc_ids":["d1"],"diagnostics":d}],top_k=1)
    assert s["variants"]["poisoned|no_conflict_penalty"]["changed_evidence_order_rows"]==1
    assert s["variants"]["poisoned|no_conflict_penalty"]["variant_poison_visible_rows"]==1
    assert s["variants"]["poisoned|full"]["baseline_poison_visible_rows"]==0
    with pytest.raises(ValueError,match="Missing full"):
        abl.score_all({}, "full")
    with pytest.raises(ValueError,match="Baseline rankings disagree"):
        abl.summarize([{"condition":"poisoned","query_id":"q1",
                        "poison_doc_ids":["d1"],"diagnostics":{**d,"selected_doc_ids":["d1","d2"]}}],top_k=1)


def test_second_model_rejects_qwen_and_pins_immutable_snapshot(tmp_path):
    model=tmp_path/"model";model.mkdir()
    (model/"config.json").write_text(json.dumps({"model_type":"qwen2"}))
    with pytest.raises(ValueError,match="non-Qwen"):
        replay.snapshot_pin(model)
    (model/"config.json").write_text(json.dumps({"model_type":"llama"}))
    (model/"weights.txt").write_text("synthetic weights fixture")
    family,digest=replay.snapshot_pin(model)
    assert family=="llama" and len(digest)==64
    (model/"weights.txt").write_text("tampered weights fixture")
    assert replay.snapshot_pin(model)[1] != digest


def make_synthetic_second_model_eval(tmp_path,monkeypatch):
    evaldir=tmp_path/"original-evaluation";evaldir.mkdir()
    pins={}; expected=[]
    for family in replay.FAMILIES:
        for intensity in (1,3):
            cid=f"{family}.intensity-{intensity}.seed-42"
            directory=evaldir/cid;directory.mkdir()
            rows=[]
            for arm in ("dense","rcd"):
                for i in range(3):
                    prompt=f"Evidence for synthetic query {i} in {arm} {family} intensity {intensity}"
                    gener={"prompt":prompt,"prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest()}
                    rows.append({
                        "pipeline":arm,"query_id":f"synthetic-{i}","construction_status":"valid_construction",
                        "measurement":{"gold_answer":"correct","poison_target_answer":"incorrect",
                        "clean_condition":{"generation":gener},"poisoned_condition":{"generation":gener}}
                    })
            path=directory/"rows.json"
            path.write_text(json.dumps(rows))
            pins[cid]=replay.sha(path)
    completion=evaldir/"evaluation.complete.json"
    completion.write_text(json.dumps({"rows_sha256":pins}))
    monkeypatch.setattr(replay,"TWOWIKI_COMPLETION_SHA256",replay.sha(completion))
    return evaldir


def test_second_model_private_plan_and_mocked_replay(tmp_path,monkeypatch):
    evaluation=make_synthetic_second_model_eval(tmp_path,monkeypatch)
    plan=tmp_path/"private-plan.json"
    status=replay.prepare(evaluation,plan,n=1,seed=42)
    assert status["replay_items"]==16
    assert plan.exists()
    assert len(json.loads(plan.read_text())["entries"])==16
    with pytest.raises(ValueError,match="Plan output must be new"):
        replay.prepare(evaluation,plan,n=1)
    model=tmp_path/"model";model.mkdir()
    (model/"config.json").write_text(json.dumps({"model_type":"llama"}))
    (model/"weights.txt").write_text("synthetic-not-a-real-model")
    pin=replay.snapshot_pin(model)[1]
    import src.pipelines.generator as generator_module
    class FakeMLX:
        calls=0
        def __init__(self,model_name):self.model_name=model_name
        def seed(self,x): assert x==42
        def generate(self,prompt,max_tokens):
            FakeMLX.calls+=1
            return SimpleNamespace(text="correct",prompt_tokens=12,completion_tokens=1,latency_seconds=.1)
    monkeypatch.setattr(generator_module,"MLXGenerator",FakeMLX)
    out=tmp_path/"replay-results"
    assert replay.execute(plan,status["sha256"],model,pin,out)["entries"]==16
    assert FakeMLX.calls==16
    assert replay.execute(plan,status["sha256"],model,pin,out)["entries"]==16
    assert FakeMLX.calls==16  # Resume has no repeated inference.
    summary_file=tmp_path/"summary.json"
    info=replay.aggregate(plan,status["sha256"],out,summary_file)
    assert info["groups"]==16
    summary=json.loads(summary_file.read_text())
    assert all(g["gold_em_rate"]==1. for g in summary["groups"].values())
    with pytest.raises(ValueError,match="Plan pin mismatch"):
        replay.aggregate(plan,"0"*64,out,tmp_path/"bad.json")
