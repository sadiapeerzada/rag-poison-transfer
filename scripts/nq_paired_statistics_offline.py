#!/usr/bin/env python3
"""Fail-closed local NQ I1/I3 paired Dense–RCD QA analysis (no inference).

Reads private, frozen plans, private source aggregates and sealed response records.
Recomputes aggregate means, then calculates nominal 95% question-cluster bootstrap
intervals. Prints ONLY aggregated statistics; never outputs or copies private
questions, targets, prompts, raw responses, or individual query IDs.

This is an exploratory follow-up, not a certified untouched evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import re
import string

PLAN_SCHEMA = "rag-poison-transfer.nq-manual-sealed-lexical-qa-plan/v1"
OUTPUT_SCHEMA = "rag-poison-transfer.nq-manual-sealed-lexical-qa-observation/v1"
AGG_SCHEMA = "rag-poison-transfer.nq-manual-sealed-lexical-qa-aggregate/v1"
KEYS = ("clean_em", "poisoned_em", "clean_f1", "poisoned_f1", "target_match", "poison_visible_top3", "clean_correct_to_poison_wrong")
METRICS_FROM_AGG = {"clean_em":"clean_em", "poisoned_em":"poisoned_em", "clean_f1":"clean_f1", "poisoned_f1":"poisoned_f1", "target_match":"targeted_asr", "poison_visible_top3":"poison_visible_top3"}


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def request_sha(obj):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_equal(a,b,label):
    if a != b:
        raise ValueError(label + " mismatch")


def normalized(s):
    if not isinstance(s,str):
        raise ValueError("QA gold, target, and extracted answers must be text")
    s = s.lower()
    s = "".join(ch for ch in s if ch not in string.punctuation)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def em(a,b):
    return float(normalized(a)==normalized(b))


def f1(a,b):
    x,y = normalized(a).split(),normalized(b).split()
    if not x or not y:
        return float(x==y)
    overlap=sum((Counter(x)&Counter(y)).values())
    if not overlap:
        return 0.0
    precision,recall=overlap/len(x),overlap/len(y)
    return 2*precision*recall/(precision+recall)


def mean(v):
    return sum(v)/len(v)


def percentile(values,p):
    z=sorted(values)
    x=(len(z)-1)*p
    lo=int(math.floor(x));hi=int(math.ceil(x))
    return z[lo]+(x-lo)*(z[hi]-z[lo])


def bootstrap(values,seed=20261109,n=2000):
    if len(values)<2 or n<100:
        raise ValueError("Need at least two questions and 100 bootstrap replicates")
    rng=random.Random(seed)
    N=len(values)
    sam=[]
    for _ in range(n):
        sam.append(sum(values[rng.randrange(N)] for _ in range(N))/N)
    return {"estimate":mean(values),"nominal_95pct_CI":[percentile(sam,.025),percentile(sam,.975)],"n_question_clusters":N,"bootstrap_replicates":n}


def load_study(intensity,plan_path,expected_plan_sha,run_dir,agg_path,expected_agg_sha):
    check_equal(sha(plan_path),expected_plan_sha,f"I{intensity} frozen plan SHA-256")
    check_equal(sha(agg_path),expected_agg_sha,f"I{intensity} original private aggregate SHA-256")
    plan=read_json(plan_path)
    agg=read_json(agg_path)
    check_equal(plan.get("schema"),PLAN_SCHEMA,"plan schema")
    check_equal(agg.get("schema"),AGG_SCHEMA,"aggregate schema")
    check_equal(plan.get("intensity"),intensity,"plan intensity")
    check_equal(agg.get("intensity"),intensity,"aggregate intensity")
    check_equal(agg.get("plan_sha256"),expected_plan_sha,"aggregate plan SHA")
    check_equal(agg.get("status"),"COMPLETE_EXPLORATORY_SEALED_NQ_LEXICAL_QA","aggregate status")
    manifest_path=run_dir/"run_manifest.json"
    manifest=read_json(manifest_path)
    check_equal(manifest.get("plan_sha256"),expected_plan_sha,"run manifest plan SHA")
    check_equal(agg.get("run_manifest_sha256"),sha(manifest_path),"aggregate run manifest SHA")
    requests=plan.get("requests_private")
    n=plan.get("selected_evaluation_questions")
    if not isinstance(requests,list) or not isinstance(n,int) or n<2 or len(requests)!=n*4:
        raise ValueError(f"I{intensity} plan does not contain 4 complete observations per question")
    check_equal(agg.get("qa_calls_verified"),n*4,"original aggregate call count")
    rows={}
    for req in requests:
        check_equal(req.get("intensity"),intensity,"request intensity")
        key=req["key"]
        arm=req["arm"]
        cond=req["condition"]
        if arm not in ("dense","rcd") or cond not in ("clean","poisoned"):
            raise ValueError("unexpected arm or condition")
        qid=req["query_id"]
        k=(qid,arm,cond)
        if k in rows:
            raise ValueError("duplicate question/arm/condition")
        source=run_dir/"responses"/(key+".json")
        obs=read_json(source)
        check_equal(obs.get("schema"),OUTPUT_SCHEMA,"response schema")
        check_equal(obs.get("key"),key,"response key")
        check_equal(obs.get("request_sha256"),request_sha(req),"response request fingerprint")
        qa=obs["qa_measurement"]
        check_equal(qa.get("prompt_sha256"),hashlib.sha256(req["prompt"].encode("utf-8")).hexdigest(),"response prompt fingerprint")
        if not isinstance(qa.get("extracted_answer"),str):
            raise ValueError("missing extracted response")
        if qa.get("elapsed_seconds") is not None:
            if not isinstance(qa["elapsed_seconds"],(int,float)) or not math.isfinite(qa["elapsed_seconds"]) or qa["elapsed_seconds"]<0:
                raise ValueError("invalid generation latency")
        rows[k]={"req":req,"qa":qa}
    qids=sorted({q for q,a,c in rows})
    if len(qids)!=n or len(rows)!=4*n:
        raise ValueError("incomplete unique-question pairing")
    out={}
    for q in qids:
        cells=[rows[(q,a,c)] for a in ("dense","rcd") for c in ("clean","poisoned")]
        for c in cells:
            if (c["req"]["question"],c["req"]["gold_answer"],c["req"]["target_answer"]) != (cells[0]["req"]["question"],cells[0]["req"]["gold_answer"],cells[0]["req"]["target_answer"]):
                raise ValueError("question/gold/target mismatch among matched arms")
        out[q]={}
        for arm in ("dense","rcd"):
            clean=rows[(q,arm,"clean")]
            poison=rows[(q,arm,"poisoned")]
            gold=clean["req"]["gold_answer"]
            target=clean["req"]["target_answer"]
            ca=clean["qa"]["extracted_answer"]
            pa=poison["qa"]["extracted_answer"]
            cm=em(ca,gold);pm=em(pa,gold)
            out[q][arm]={
                "clean_em":cm,"poisoned_em":pm,"clean_f1":f1(ca,gold),
                "poisoned_f1":f1(pa,gold),"target_match":em(pa,target),
                "poison_visible_top3":float(poison["req"]["poison_visible_top3"]),
                "clean_correct_to_poison_wrong":float(bool(cm) and not bool(pm)),
                "clean_generation_seconds":clean["qa"].get("elapsed_seconds"),
                "poisoned_generation_seconds":poison["qa"].get("elapsed_seconds"),
                "clean_retrieval_seconds":clean["req"].get("retrieval_elapsed_seconds"),
                "poisoned_retrieval_seconds":poison["req"].get("retrieval_elapsed_seconds"),
                "clean_inner_retrieval_calls":clean["req"].get("inner_retrieval_calls"),
                "poisoned_inner_retrieval_calls":poison["req"].get("inner_retrieval_calls"),
                "clean_completion_tokens":clean["qa"].get("completion_tokens"),
                "poisoned_completion_tokens":poison["qa"].get("completion_tokens"),
                "clean_prompt_tokens":clean["qa"].get("prompt_tokens"),
                "poisoned_prompt_tokens":poison["qa"].get("prompt_tokens"),
            }
    # Stop on ANY disagreement with original private aggregates.
    for arm in ("dense","rcd"):
        original=agg["groups"][arm]
        check_equal(original["n_pairs"],n,"private aggregate n_pairs")
        for metric,source_field in METRICS_FROM_AGG.items():
            observed=mean([out[q][arm][metric] for q in qids])
            if abs(observed-original[source_field])>1e-10:
                raise ValueError(f"I{intensity} {arm}/{metric}: recomputed private source aggregate differs")
        ccw=sum(out[q][arm]["clean_correct_to_poison_wrong"] for q in qids)
        check_equal(int(ccw),original["clean_correct_to_poison_wrong"],"clean→wrong flips")
        check_equal(int(sum(out[q][arm]["target_match"] for q in qids)),original["asr_numerator"],"target numerator")
        check_equal(int(sum(out[q][arm]["poison_visible_top3"] for q in qids)),original["poison_exposure_numerator"],"poison visibility numerator")
    return {"n":n,"qids":qids,"rows":out,"sha":{"plan":expected_plan_sha,"aggregate":expected_agg_sha,"manifest":sha(manifest_path)},"raw_plan":plan}


def summarize(i1,i3,reps,seed):
    qids=i1["qids"]
    check_equal(qids,i3["qids"],"I1/I3 question ID set")
    check_equal(i1["n"],i3["n"],"I1/I3 population size")
    p1,p3=i1["raw_plan"],i3["raw_plan"]
    check_equal(p1.get("targets_sha256"),p3.get("targets_sha256"),"I1/I3 target assignment SHA")
    check_equal(p1.get("cohort_sha256"),p3.get("cohort_sha256"),"I1/I3 cohort SHA")
    # Same gold and target and text for every q in both plans.
    def anchors(plan):
        out={}
        for r in plan["requests_private"]:
            q=r["query_id"]
            value=(r["question"],r["gold_answer"],r["target_answer"])
            if q in out and out[q]!=value:
                raise ValueError("inconsistent question anchor")
            out[q]=value
        return out
    check_equal(anchors(p1),anchors(p3),"I1/I3 frozen anchors")
    result={
        "status":"VERIFIED_OFFLINE_PAIRED_NQ_ANALYSIS_EXPLORATORY",
        "verification":"Original two private source aggregates and all response fingerprints cross-checked; no inference performed",
        "distinct_question_clusters":len(qids),
        "logical_qa_calls_verified":len(qids)*8,
        "bootstrap_seed":seed,
        "bootstrap_replicates":reps,
        "uncertainty":"Nominal, percentile, paired question-cluster bootstrap, unadjusted for multiple comparisons",
        "interpretation":"Target-answer match is not independent factual-falsehood certification; frozen historically unexposed cohort not verified",
        "source_sha256":{"intensity_1":i1["sha"],"intensity_3":i3["sha"]},
        "groups":{},"comparisons":{},"resource_accounting":{},
    }
    for label,study in (("intensity_1",i1),("intensity_3",i3)):
        result["groups"][label]={}
        result["comparisons"][label]={}
        for arm in ("dense","rcd"):
            result["groups"][label][arm]={k:mean([study["rows"][q][arm][k] for q in qids]) for k in KEYS}
            perf={}
            for k in ("clean_generation_seconds","poisoned_generation_seconds","clean_retrieval_seconds","poisoned_retrieval_seconds","clean_inner_retrieval_calls","poisoned_inner_retrieval_calls","clean_completion_tokens","poisoned_completion_tokens","clean_prompt_tokens","poisoned_prompt_tokens"):
                vs=[study["rows"][q][arm][k] for q in qids]
                perf[k]={"available":sum(v is not None for v in vs),"n":len(vs),"mean_if_complete":mean(vs) if all(isinstance(v,(int,float)) for v in vs) else None}
            result["resource_accounting"].setdefault(label,{})[arm]=perf
        # Same-question RCD vs Dense within each intensity.
        for k in KEYS:
            deltas=[study["rows"][q]["rcd"][k]-study["rows"][q]["dense"][k] for q in qids]
            result["comparisons"][label]["rcd_minus_dense_"+k]=bootstrap(deltas,seed,reps)
    result["comparisons"]["intensity_3_minus_intensity_1"]={}
    result["comparisons"]["difference_in_differences"]={}
    for arm in ("dense","rcd"):
        for k in KEYS:
            deltas=[i3["rows"][q][arm][k]-i1["rows"][q][arm][k] for q in qids]
            result["comparisons"]["intensity_3_minus_intensity_1"][arm+"_"+k]=bootstrap(deltas,seed,reps)
    for k in KEYS:
        deltas=[(i3["rows"][q]["rcd"][k]-i3["rows"][q]["dense"][k])-(i1["rows"][q]["rcd"][k]-i1["rows"][q]["dense"][k]) for q in qids]
        result["comparisons"]["difference_in_differences"]["rcd_minus_dense_change_"+k]=bootstrap(deltas,seed,reps)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path.home()/"Documents/rag-research-results")
    p.add_argument("--reps",type=int,default=2000)
    p.add_argument("--seed",type=int,default=20261109)
    p.add_argument("--output",type=Path,help="Optional NEW, private JSON report path; otherwise stdout summary only")
    args=p.parse_args()
    root=args.root.expanduser().resolve()
    if not root.is_dir() or args.reps<100:
        raise ValueError("private root must exist; bootstrap replicates must be >= 100")
    settings={
        1: ("nq-stage3-lexical-I1-qa-plan-v1_PRIVATE.json", "66104bd1b922bd79a465593cb134b12820b71271fba08567c4bc529dd912f6c6", "nq-stage3-lexical-I1-qa-run-v1_PRIVATE", "nq-stage3-lexical-I1-qa-aggregate-v1_PRIVATE.json", "0126f5998d07b5f0430d93f1fcf610dc7118b819b385065bcca60e02188b9ac9"),
        3: ("nq-stage3-lexical-I3-qa-plan-v1_PRIVATE.json", "53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2b8f46d968a2e7b5", "nq-stage3-lexical-I3-qa-run-v1_PRIVATE", "nq-stage3-lexical-I3-qa-aggregate-v1_PRIVATE.json", "146cb2749ab01bb5e5d70c06c2041f34dcf36db0fafa2443c3deb021f50e8dc5"),
    }
    studies={}
    for intensity,(pn,ps,rd,an,ass) in settings.items():
        studies[intensity]=load_study(intensity,root/pn,ps,root/rd,root/an,ass)
    report=summarize(studies[1],studies[3],args.reps,args.seed)
    if args.output:
        out=args.output.expanduser().resolve()
        if root!=out.parent and root not in out.parents:
            raise ValueError("Private analysis report must be under private root")
        if out.exists():
            raise ValueError("Refusing to overwrite existing report")
        with out.open("x",encoding="utf-8") as f:
            json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
            f.write("\n")
        print(json.dumps({"status":report["status"],"n_question_clusters":report["distinct_question_clusters"],"bootstrap_replicates":args.reps,"private_analysis_saved_to":str(out)},indent=2))
    else:
        # Print essential metrics only. Full results require --output to private root.
        print(json.dumps({"status":report["status"],"n_questions":report["distinct_question_clusters"],"calls":report["logical_qa_calls_verified"],"source_verified":True,
         "groups":report["groups"],"rcd_minus_dense_poisoned_em_CI":{k:v["rcd_minus_dense_poisoned_em"] for k,v in report["comparisons"].items() if "rcd_minus_dense_poisoned_em" in v},
         "rcd_minus_dense_target_match_CI":{k:v["rcd_minus_dense_target_match"] for k,v in report["comparisons"].items() if "rcd_minus_dense_target_match" in v},
         "i3_minus_i1_target_match_CI":{k:v for k,v in report["comparisons"]["intensity_3_minus_intensity_1"].items() if k.endswith("target_match")},
         "limitations":report["uncertainty"]+"; "+report["interpretation"]},indent=2))

if __name__=="__main__":
    main()
