#!/usr/bin/env python3
"""Prepare and execute a *new*, private, fixed-evidence second-model replay.

The original 2Wiki frozen protocol/results remain untouched. The replay fixes
the original generator prompts and evidence; it does NOT test transfer to a
new retriever, regenerated poisons, or model-invariant RCD behavior.
Prepare is read-only; run uses a separately pinned local MLX non-Qwen model.

Example commands: docs/NOV09_FOUR_RESEARCH_GATES.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from src.evaluation.metrics import exact_match
from src.evaluation.qa_records import extract_answer

TWOWIKI_COMPLETION_SHA256 = "db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519"
FAMILIES = ("lexical_influential_token", "semantic_fluent_false_evidence")
ARMS = ("dense", "rcd")
CONDITIONS = ("clean", "poisoned")


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1 << 20),b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def outside_repo(path):
    repo=Path(__file__).resolve().parents[1]
    p=Path(path).expanduser().resolve()
    if p==repo or repo in p.parents:
        raise ValueError("Private held-out material must remain outside the public repository")
    return p


def prepare(evaluation, output, n=10, seed=42):
    evaluation=Path(evaluation).resolve()
    output=outside_repo(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Plan output must be new with a preexisting parent directory")
    if n < 1 or seed not in (42,43,44):
        raise ValueError("Invalid per-stratum selection size or seed")
    completion_file=evaluation/"evaluation.complete.json"
    if sha(completion_file)!=TWOWIKI_COMPLETION_SHA256:
        raise ValueError("Frozen 2Wiki evaluation completion SHA-256 mismatch")
    completion=json.loads(completion_file.read_text())
    entries=[]
    for family in FAMILIES:
        for intensity in (1,3):
            cid=f"{family}.intensity-{intensity}.seed-{seed}"
            relative=f"{cid}/rows.json"
            if sha(evaluation/relative)!=completion["rows_sha256"][cid]:
                raise ValueError("Frozen row digest mismatch: "+relative)
            raw=json.loads((evaluation/relative).read_text())
            arms={}
            for arm in ARMS:
                rows=[r for r in raw if r.get("pipeline")==arm and r.get("construction_status")=="valid_construction"]
                arms[arm]={r["query_id"]:r for r in rows}
            available=set(arms["dense"]) & set(arms["rcd"])
            selected=sorted(available,key=lambda q:hashlib.sha256(f"2wiki-second-model-v1|{family}|{intensity}|{seed}|{q}".encode()).hexdigest())[:n]
            if len(selected)!=n:
                raise ValueError("Insufficient valid matched records in stratum")
            for q in selected:
                for arm in ARMS:
                    row=arms[arm][q]
                    measurement=row.get("measurement")
                    if not measurement:
                        raise ValueError("Valid matched row lacks measurement")
                    gold=measurement["gold_answer"]
                    target=measurement["poison_target_answer"]
                    if not isinstance(gold,str) or not isinstance(target,str):
                        raise ValueError("Missing gold/poison target")
                    for condition in CONDITIONS:
                        obs=measurement[f"{condition}_condition"]
                        prompt=obs["generation"]["prompt"]
                        prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()
                        if prompt_hash != obs["generation"]["prompt_sha256"]:
                            raise ValueError("Original stored prompt SHA mismatch")
                        identity=canonical([family,intensity,seed,q,arm,condition])[:24]
                        entries.append({
                            "id":identity,"family":family,"intensity":intensity,"seed":seed,
                            "query_id":q,"arm":arm,"condition":condition,
                            "prompt":prompt,"prompt_sha256":prompt_hash,
                            "gold_answer":gold,"target_answer":target,
                        })
    expected=4*n*len(ARMS)*len(CONDITIONS)
    if len(entries)!=expected or len({x["id"] for x in entries})!=expected:
        raise ValueError("Duplicate or missing replay items")
    obj={
        "schema":"rag-poison-transfer.private-fixed-evidence-second-model-plan/v1",
        "evidence_run":"2Wiki 300-query Dense/RCD, original Qwen prompt replay",
        "purpose":"Exploratory second-generator contrast; no re-retrieval or poison construction",
        "evaluation_completion_sha256":TWOWIKI_COMPLETION_SHA256,
        "sampling":"SHA256 deterministic valid-only matched question subset, seed chosen before new-model outcomes; original study outcomes previously inspected",
        "selected_queries_per_stratum":n,
        "row_count":len(entries),"entries":entries,
    }
    output.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
    return {"status":"PRIVATE_PLAN_CREATED_NO_INFERENCE","plan":str(output),"sha256":sha(output),"replay_items":len(entries)}


def snapshot_pin(path):
    path=Path(path).expanduser().resolve(strict=True)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("Model snapshot must be a real local directory")
    config=json.loads((path/"config.json").read_text())
    family=str(config.get("model_type","")).lower()
    if not family or "qwen" in family:
        raise ValueError("Use a locally pinned non-Qwen model family for validation")
    files={}
    for file in sorted(path.rglob("*")):
        if file.is_symlink():
            raise ValueError("Symlinked model file: use an actual materialized snapshot")
        if file.is_file():
            files[file.relative_to(path).as_posix()]=sha(file)
    return family,canonical(files)


def execute(plan_path, plan_sha256, model_snapshot, model_sha256, output, max_tokens=128):
    plan_path=Path(plan_path).expanduser().resolve(strict=True)
    output=outside_repo(output)
    if sha(plan_path)!=plan_sha256:
        raise ValueError("Private plan pin mismatch")
    plan=json.loads(plan_path.read_text())
    if plan.get("schema")!="rag-poison-transfer.private-fixed-evidence-second-model-plan/v1":
        raise ValueError("Unsupported replay plan")
    family, actual_pin=snapshot_pin(model_snapshot)
    if actual_pin!=model_sha256:
        raise ValueError("Model snapshot hash differs from independent pin")
    if max_tokens<1 or max_tokens>512:
        raise ValueError("Bounded max_tokens required (1..512)")
    if output.exists() and not output.is_dir():
        raise ValueError("Output path must be a directory")
    output.mkdir(parents=True,exist_ok=True)
    manifest={"schema":"rag-poison-transfer.second-model-replay-run/v1",
              "plan_sha256":plan_sha256,"model_snapshot_sha256":model_sha256,
              "model_family":family,"max_tokens":max_tokens,
              "sampling_note":"Exploratory, post hoc prompt replay; distinct model family",
              "model_seed_each_call":42}
    marker=output/"run_manifest.json"
    if marker.exists():
        if json.loads(marker.read_text())!=manifest:
            raise ValueError("Resume manifest differs from recorded run")
    else:
        marker.write_text(json.dumps(manifest,indent=2)+"\n")
    from src.pipelines.generator import MLXGenerator
    model=MLXGenerator(model_name=str(Path(model_snapshot).expanduser().resolve()))
    for row in plan["entries"]:
        ident=row["id"]
        if not isinstance(ident,str) or len(ident)!=24 or not all(c in "0123456789abcdef" for c in ident):
            raise ValueError("Invalid item ID")
        result_path=output/(ident+".json")
        if result_path.exists():
            previous=json.loads(result_path.read_text())
            if previous["prompt_sha256"]!=row["prompt_sha256"] or previous["plan_sha256"]!=plan_sha256 or previous["model_snapshot_sha256"]!=model_sha256:
                raise ValueError("Corrupt or wrong-model resume record")
            continue
        model.seed(42)
        generated=model.generate(row["prompt"],max_tokens=max_tokens)
        answer=extract_answer(generated.text)
        record={
            "id":ident,"plan_sha256":plan_sha256,"model_snapshot_sha256":model_sha256,
            "prompt_sha256":row["prompt_sha256"],
            "raw_response":generated.text,"extracted_answer":answer,
            "gold_em":float(exact_match(answer,row["gold_answer"])),
            "target_match":bool(exact_match(answer,row["target_answer"])),
            "prompt_tokens":generated.prompt_tokens,"completion_tokens":generated.completion_tokens,
            "generator_latency_seconds":generated.latency_seconds,
        }
        # Atomic write: interrupted model calls cannot look completed.
        with tempfile.NamedTemporaryFile(mode="w",dir=output,prefix="inflight-",suffix=".tmp",delete=False) as tmp:
            json.dump(record,tmp,ensure_ascii=False)
            name=tmp.name
        os.replace(name,result_path)
    return {"status":"REPLAY_COMPLETE","entries":len(plan["entries"]),"out":str(output)}


def aggregate(plan_path, plan_sha256, results, output):
    if sha(plan_path)!=plan_sha256:
        raise ValueError("Plan pin mismatch")
    plan=json.loads(Path(plan_path).read_text())
    results=Path(results)
    manifest=json.loads((results/"run_manifest.json").read_text())
    if manifest["plan_sha256"]!=plan_sha256:
        raise ValueError("Run/plan pin mismatch")
    by_group=defaultdict(lambda:{"n":0,"gold_em":0.,"target_matches":0})
    for row in plan["entries"]:
        result_path=results/(row["id"]+".json")
        data=json.loads(result_path.read_text())
        if data["id"]!=row["id"] or data["prompt_sha256"]!=row["prompt_sha256"] or data["plan_sha256"]!=plan_sha256 or data["model_snapshot_sha256"]!=manifest["model_snapshot_sha256"]:
            raise ValueError("Record binding mismatch")
        if data["extracted_answer"]!=extract_answer(data["raw_response"]):
            raise ValueError("Answer extraction mismatch")
        gold=float(exact_match(data["extracted_answer"],row["gold_answer"]))
        target=bool(exact_match(data["extracted_answer"],row["target_answer"]))
        if data["gold_em"]!=gold or data["target_match"] is not target:
            raise ValueError("Output scoring mismatch")
        key=f"{row['family']}|{row['intensity']}|{row['arm']}|{row['condition']}"
        t=by_group[key];t["n"]+=1;t["gold_em"]+=gold;t["target_matches"]+=int(target)
    summary={
      "schema":"rag-poison-transfer.second-model-prompt-replay-aggregate/v1",
      "analysis_scope":"exploratory valid-only selected subset, source evidence fixed",
      "new_model_family":manifest["model_family"],"model_snapshot_sha256":manifest["model_snapshot_sha256"],
      "plan_sha256":plan_sha256,
      "groups":{key:{"n":v["n"],"gold_em_rate":v["gold_em"]/v["n"],"target_match_rate":v["target_matches"]/v["n"]} for key,v in sorted(by_group.items())},
      "limitations":["No new retrieval, candidate construction or query-level population estimate",
                     "Subset drawn after original Qwen outcomes were inspected, not a prospective held-out confirmation",
                     "Qwen-vs-new-model differences combine model and tokenizer/chat-template effects",
                     "Raw prompts and model outputs remain private; no claims about human semantic verification"],
    }
    output=outside_repo(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Aggregate output must be new")
    output.write_text(json.dumps(summary,indent=2)+"\n")
    return {"status":"AGGREGATED","groups":len(summary["groups"]),"output":str(output)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="stage",required=True)
    p=sub.add_parser("prepare");p.add_argument("--evaluation-dir",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--n-per-stratum",type=int,default=10);p.add_argument("--seed",type=int,default=42)
    pin=sub.add_parser("pin-model");pin.add_argument("--model-snapshot",type=Path,required=True)
    run=sub.add_parser("run");run.add_argument("--plan",type=Path,required=True);run.add_argument("--plan-sha256",required=True);run.add_argument("--model-snapshot",type=Path,required=True);run.add_argument("--model-sha256",required=True);run.add_argument("--output",type=Path,required=True);run.add_argument("--max-tokens",type=int,default=128);run.add_argument("--execute",action="store_true")
    agg=sub.add_parser("aggregate");agg.add_argument("--plan",type=Path,required=True);agg.add_argument("--plan-sha256",required=True);agg.add_argument("--results",type=Path,required=True);agg.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if a.stage=="prepare": result=prepare(a.evaluation_dir,a.output,a.n_per_stratum,a.seed)
    elif a.stage=="pin-model":
        family,pin=snapshot_pin(a.model_snapshot)
        result={"status":"MODEL_PIN_RECORDED_NO_INFERENCE","model_family":family,"snapshot_sha256":pin}
    elif a.stage=="run":
        if not a.execute: raise ValueError("Model inference requires explicit --execute flag")
        result=execute(a.plan,a.plan_sha256,a.model_snapshot,a.model_sha256,a.output,a.max_tokens)
    else: result=aggregate(a.plan,a.plan_sha256,a.results,a.output)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
