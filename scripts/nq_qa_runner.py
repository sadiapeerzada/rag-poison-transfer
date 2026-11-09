#!/usr/bin/env python3
"""Private, manual, checkpointed Natural Questions lexical QA (exploratory).

Two-phase workflow: PREPARE real Dense/RCD retrieval requests from sealed
300-query NQ lexical constructions; RUN real Qwen MLX inference from that
immutable plan with fail-closed per-call journaling; AGGREGATE only completed
matched pairs. All question data, prompts and responses remain outside git.

Example (from rag-poison-transfer repo root on Mac):
 python ~/Downloads/nq_stage3_manual_sealed_qa_v1.py --help

This does NOT support semantic-fluent attack construction, official NQ-open
retrieval, target factuality certification, or a confirmatory unexposed split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.cwd().resolve()
sys.path.insert(0, str(REPO))

COHORT_SHA = "1b99fe49fff3b1224c6351fb20f58897e0e664a69c33a6400b4a56855c05f8c7"
MODEL_REV = "c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
PLAN_SCHEMA = "rag-poison-transfer.nq-manual-sealed-lexical-qa-plan/v1"
OUTPUT_SCHEMA = "rag-poison-transfer.nq-manual-sealed-lexical-qa-observation/v1"
SOURCE_DIR = Path.home() / "Documents/rag-research-results/nq-singlehop-v1-private"
PRIVATE_ROOT = Path.home() / "Documents/rag-research-results"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(buf)
    return sha.hexdigest()


def sha_json(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_path(path: Path):
    path = path.expanduser().resolve()
    if path == REPO or REPO in path.parents:
        raise ValueError("Private output/input must not be within the repository")
    return path


def newfile(path: Path, obj):
    """Exclusive create: an existing filename is always an error."""
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def model_path():
    return (Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots" / MODEL_REV)


def model_seals(path):
    if not (path / "config.json").is_file():
        raise FileNotFoundError("Expected pinned MLX Qwen snapshot: " + str(path))
    # Seal all available model-weight shards and critical tokenizer/config files.
    names = []
    for p in path.rglob("*"):
        if p.is_file() and (p.suffix == ".safetensors" or p.name in {
            "config.json", "generation_config.json", "tokenizer.json",
            "tokenizer_config.json", "special_tokens_map.json", "vocab.json",
            "merges.txt", "model.safetensors.index.json",
        }):
            names.append(p)
    if not any(p.suffix == ".safetensors" for p in names):
        raise ValueError("No safetensors files available in pinned model snapshot")
    return {str(p.relative_to(path)): digest(p) for p in sorted(names)}


def prepare(args):
    from scripts.nq_singlehop_v1_freeze import verify
    from scripts.nq_stage3_lexical_construction_v1 import verify_lexical
    from src.attacks.asr import build_prompt
    from src.defenses.rcd.retriever import RCDRetriever
    from src.retrieval.bm25 import BM25Retriever
    from src.retrieval.dense import DenseRetriever, SentenceTransformerEmbedder

    src = safe_path(args.cohort_dir)
    output = safe_path(args.output_plan)
    target_file = safe_path(args.targets)
    construction_file = safe_path(args.construction)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Use a new private plan file path whose parent already exists")
    if verify(src, args.cohort_sha)["status"] != "PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY":
        raise RuntimeError("Cohort verification did not pass")
    verified = verify_lexical(src, args.cohort_sha, target_file, args.targets_sha,
                             construction_file, args.construction_sha)
    if verified["status"] != "PASS_PRIVATE_NQ_LEXICAL_CONSTRUCTION_INTEGRITY_ONLY":
        raise RuntimeError("Lexical construction verification did not pass")
    clean = read(src / "evaluation_validation.json")
    sealed = read(construction_file)
    intensity = sealed["intensity"]
    if intensity != args.intensity:
        raise ValueError("Intensity mismatch against verified construction")
    associations = {r["query_id"]: r for r in sealed["question_poison_associations_private"]}
    new_docs = sealed["poison_documents_private"]
    if len(clean["queries"]) != 300 or len(associations) != 300:
        raise ValueError("Requires the complete 300-question frozen evaluation cohort")
    if not 1 <= args.limit <= 300:
        raise ValueError("--limit must be 1..300")
    clean_corpus = clean["corpus"]
    poisoned_corpus = [*clean_corpus, *new_docs]

    embedder = SentenceTransformerEmbedder("BAAI/bge-small-en-v1.5")
    def build(corpus):
        dense = DenseRetriever(embedder)
        sparse = BM25Retriever()
        rcd = RCDRetriever(
            dense, sparse_retriever=sparse, dense_retriever=dense,
            candidate_k=10, output_k=3, rewrite_count=3,
            consistency_weight=0.45, redundancy_weight=0.0,
            conflict_weight=0.10, base_rank_weight=0.45)
        rcd.build(corpus)
        return {"dense": dense, "rcd": rcd}

    print("Building clean NQ Dense/RCD indexes...", flush=True)
    clean_index = build(clean_corpus)
    print("Building sealed poisoned NQ Dense/RCD indexes...", flush=True)
    poisoned_index = build(poisoned_corpus)
    requests = []
    # Preserve QA call order and query selection, exactly the first N frozen
    # evaluation queries. --limit allows retrieval/Qwen preflight only.
    for qi, q in enumerate(clean["queries"][:args.limit]):
        a = associations[q["query_id"]]
        poison_ids = set(a["poison_doc_ids"])
        if len(poison_ids) != intensity or not poison_ids:
            raise ValueError("Poison association count mismatch")
        for arm in ("dense", "rcd"):
            for condition, indexes in (("clean", clean_index), ("poisoned", poisoned_index)):
                r = indexes[arm]
                start = time.perf_counter()
                retrieved = r.retrieve(q["question"], top_k=10)
                elapsed = time.perf_counter() - start
                ids = [doc.doc_id for doc in retrieved]
                if len(ids) != len(set(ids)):
                    raise ValueError("Duplicate document in retrieval results")
                di = getattr(r, "last_diagnostics", None)
                inner_calls = di.get("retrieval_call_count") if isinstance(di, dict) else 1
                if condition == "clean" and poison_ids.intersection(ids):
                    raise ValueError("Injected poison appeared in original clean corpus")
                request = {
                    "key": f"i{intensity}_{arm}_{qi:03d}_{condition}",
                    "query_id": q["query_id"], "query_index": qi,
                    "question": q["question"],
                    "gold_answer": q["gold_answer"],
                    "target_answer": a["target_answer"],
                    "intensity": intensity, "arm": arm, "condition": condition,
                    "prompt": build_prompt(q["question"], [d.text for d in retrieved[:3]]),
                    "retrieved_doc_ids_top10": ids,
                    "evidence_doc_ids_top3": ids[:3],
                    "gold_visible_top3": bool(set(q["gold_doc_ids"]) & set(ids[:3])),
                    "poison_visible_top3": bool(poison_ids & set(ids[:3])),
                    "poison_rank_top10": next((i + 1 for i, docid in enumerate(ids) if docid in poison_ids), None),
                    "retrieval_elapsed_seconds": elapsed,
                    "inner_retrieval_calls": inner_calls,
                }
                requests.append(request)
        if (qi + 1) % 25 == 0 or qi + 1 == args.limit:
            print(f"Prepared {qi + 1}/{args.limit} evaluation questions", flush=True)
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    plan = {
        "schema": PLAN_SCHEMA,
        "status": "PREPARED_REAL_RETRIEVAL_NO_NEW_QA_INFERENCE",
        "created_utc": now(), "intensity": intensity,
        "cohort_sha256": args.cohort_sha,
        "targets_sha256": args.targets_sha,
        "construction_sha256": args.construction_sha,
        "poison_fingerprint": verified["poison_instance_fingerprint"],
        "retrieval_corpus_scope": "pooled NQ long-answer candidate passages, not Wikipedia open-domain",
        "selected_evaluation_questions": args.limit,
        "selection": "first N frozen evaluation questions; N<300 is a nonconfirmatory preflight",
        "git_commit": git_sha, "git_dirty": dirty,
        "script_sha256": digest(Path(__file__).resolve()),
        "embedder": "BAAI/bge-small-en-v1.5",
        "embedder_weight_hashes_verified": False,
        "generator_model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "generator_snapshot_revision": MODEL_REV,
        "generator_max_tokens": 64, "evidence_k": 3, "diagnostic_k": 10,
        "rcd_weights": {"consistency": 0.45, "redundancy": 0.0, "conflict": 0.10, "base_rank": 0.45},
        "planned_model_calls": len(requests),
        "study_status": "EXPLORATORY_NOT_UNEXPOSED; non-gold target not independently source-certified",
        "requests_private": requests,
    }
    newfile(output, plan)
    print(json.dumps({"status": plan["status"], "plan_sha256": digest(output),
                      "n_questions": args.limit, "planned_qa_calls": len(requests),
                      "output_private": str(output)}, indent=2), flush=True)


def load_plan(path, expected_sha):
    path = safe_path(path)
    if digest(path) != expected_sha:
        raise ValueError("Private prepared retrieval plan SHA-256 mismatch")
    plan = read(path)
    if (plan.get("schema") != PLAN_SCHEMA or
            plan.get("script_sha256") != digest(Path(__file__).resolve()) or
            plan.get("generator_snapshot_revision") != MODEL_REV):
        raise ValueError("Plan schema/script/model mismatch; do not silently change protocol")
    records = plan.get("requests_private")
    if not isinstance(records, list) or len(records) != plan.get("planned_model_calls"):
        raise ValueError("Prepared plan has invalid call count")
    keys = [r["key"] for r in records]
    if len(keys) != len(set(keys)) or not all(k.replace("_", "").isalnum() for k in keys):
        raise ValueError("Invalid duplicate/unsafe request keys")
    if plan.get("generator_max_tokens") != 64:
        raise ValueError("Generator protocol mismatch")
    return plan


def request_fingerprint(request):
    return sha_json(request)


def validate_result(path, expected_request):
    from src.evaluation.qa_records import validate_qa
    data = read(path)
    if (data.get("schema") != OUTPUT_SCHEMA or
            data.get("key") != expected_request["key"] or
            data.get("request_sha256") != request_fingerprint(expected_request)):
        raise ValueError("Completed response belongs to another request")
    qa = data["qa_measurement"]
    validate_qa(qa, qa["extracted_answer"])
    if qa["prompt_sha256"] != hashlib.sha256(expected_request["prompt"].encode()).hexdigest():
        raise ValueError("Response QA prompt hash differs from frozen retrieval plan")
    return data


def run(args):
    from src.pipelines.generator import MLXGenerator
    from src.evaluation.qa_records import generate_qa
    plan = load_plan(args.plan, args.plan_sha256)
    out = safe_path(args.output_dir)
    if args.max_calls < 1:
        raise ValueError("--max-calls must be >=1")
    manifest_file = out / "run_manifest.json"
    if args.resume:
        if not manifest_file.is_file():
            raise ValueError("--resume requires an existing run directory/manifest")
        manifest = read(manifest_file)
        if (manifest.get("plan_sha256") != args.plan_sha256 or
                manifest.get("script_sha256") != plan["script_sha256"] or
                manifest.get("schema") != OUTPUT_SCHEMA):
            raise ValueError("Existing output directory bound to different plan/script")
    else:
        if out.exists() or not out.parent.is_dir():
            raise ValueError("First run requires a NEW private output directory")
        out.mkdir(mode=0o700)
        (out / "intents").mkdir()
        (out / "responses").mkdir()
        manifest = {
            "schema": OUTPUT_SCHEMA, "started_utc": now(),
            "plan_sha256": args.plan_sha256,
            "script_sha256": plan["script_sha256"],
            "git_commit": plan["git_commit"],
            "qwen_snapshot": str(model_path()),
            "qwen_local_file_sha256": model_seals(model_path()),
            "generator_seed_on_process_start": 20261109,
            "max_new_tokens": 64,
            "note": "If an intent exists without a valid response, do NOT automatically rerun that call. Escalate to manual audit.",
        }
        newfile(manifest_file, manifest)
    requests = plan["requests_private"]
    pending = []
    for req in requests:
        response = out / "responses" / (req["key"] + ".json")
        intent = out / "intents" / (req["key"] + ".json")
        if response.is_file():
            validate_result(response, req)
        elif intent.exists():
            raise RuntimeError(f"Unresolved prior inference intent: {intent}. Inspect; no automatic duplicate call.")
        else:
            pending.append(req)
    if not pending:
        print(json.dumps({"status":"ALL_QA_REQUESTS_ALREADY_VERIFIED", "completed":len(requests),
                          "output_private":str(out)}, indent=2), flush=True)
        return
    # Load the Qwen model only when there are outstanding requests.
    print("Loading pinned Qwen MLX snapshot...", flush=True)
    generator = MLXGenerator(model_name=str(model_path()))
    generator.seed(20261109)
    completed_now = 0
    for req in pending[:args.max_calls]:
        intent = out / "intents" / (req["key"] + ".json")
        response = out / "responses" / (req["key"] + ".json")
        newfile(intent, {"status":"REQUEST_STARTED_OUTCOME_UNCERTAIN_UNTIL_RESPONSE_FILE",
                         "request_sha256":request_fingerprint(req), "started_utc":now()})
        obs = generate_qa(generator, req["prompt"], 64,
                          context={"study":"nq_sealed_lexical_v1", "request_key":req["key"]})
        result = {"schema":OUTPUT_SCHEMA, "key":req["key"],
                  "request_sha256":request_fingerprint(req), "completed_utc":now(),
                  "qa_measurement":obs}
        newfile(response, result)
        validate_result(response, req)
        completed_now += 1
        print(f"Completed {req['key']} ({completed_now}/{min(args.max_calls, len(pending))} this session)", flush=True)
    done = sum((out / "responses" / (r["key"] + ".json")).exists() for r in requests)
    print(json.dumps({"status":"PARTIAL" if done < len(requests) else "ALL_QA_REQUESTS_VERIFIED",
                      "completed": done, "planned": len(requests),
                      "remaining":len(requests)-done, "output_private":str(out)}, indent=2))


def aggregate(args):
    from src.evaluation.metrics import exact_match, f1_score
    plan = load_plan(args.plan, args.plan_sha256)
    out = safe_path(args.output_dir)
    manifest = read(out / "run_manifest.json")
    if manifest.get("plan_sha256") != args.plan_sha256:
        raise ValueError("Aggregation plan SHA mismatch")
    requests = plan["requests_private"]
    observations = {}
    for req in requests:
        path = out / "responses" / (req["key"] + ".json")
        if not path.exists():
            raise RuntimeError("Incomplete planned QA responses. Refusing final aggregate: " + req["key"])
        observations[req["key"]] = validate_result(path, req)
    groups = {}
    for arm in ("dense", "rcd"):
        matched_pairs = {}
        for r in requests:
            if r["arm"] != arm:
                continue
            key = (r["query_id"], r["condition"])
            if key in matched_pairs:
                raise ValueError("Duplicate question/condition")
            answer = observations[r["key"]]["qa_measurement"]["extracted_answer"]
            matched_pairs[key] = {"req":r, "answer":answer}
        n = plan["selected_evaluation_questions"]
        if len(matched_pairs) != n*2:
            raise ValueError("Unpaired results for arm " + arm)
        clean_correct = poisoned_correct = poisoned_f1_sum = clean_f1_sum = asr = exposed = flips = 0
        for query_id in {r["query_id"] for r in requests}:
            c, p = matched_pairs[(query_id,"clean")], matched_pairs[(query_id,"poisoned")]
            gold, target = c["req"]["gold_answer"], p["req"]["target_answer"]
            cc = bool(exact_match(c["answer"], gold))
            pc = bool(exact_match(p["answer"], gold))
            clean_correct += cc
            poisoned_correct += pc
            clean_f1_sum += f1_score(c["answer"], gold)
            poisoned_f1_sum += f1_score(p["answer"], gold)
            asr += bool(exact_match(p["answer"], target))
            exposed += bool(p["req"]["poison_visible_top3"])
            flips += (cc and not pc)
        groups[arm] = {
            "n_pairs": n, "clean_em":clean_correct/n,
            "poisoned_em":poisoned_correct/n,
            "clean_f1":clean_f1_sum/n, "poisoned_f1":poisoned_f1_sum/n,
            "targeted_asr":asr/n, "poison_visible_top3":exposed/n,
            "clean_correct_to_poison_wrong":flips,
            "asr_numerator":asr, "poison_exposure_numerator":exposed,
        }
    summary = {
        "schema":"rag-poison-transfer.nq-manual-sealed-lexical-qa-aggregate/v1",
        "status":"COMPLETE_EXPLORATORY_SEALED_NQ_LEXICAL_QA",
        "plan_sha256":args.plan_sha256,
        "run_manifest_sha256":digest(out / "run_manifest.json"),
        "intensity":plan["intensity"],
        "n_questions":plan["selected_evaluation_questions"],
        "qa_calls_verified":len(requests),
        "groups":groups,
        "limitations":["Pooled NQ candidate corpus; not standard NQ open-domain benchmark",
                       "Non-gold cross-query target assignments not source/factuality certified",
                       "Historical prior exposure unverified; exploratory, not confirmatory",
                       "Single NQ short-answer label may omit alternative correct answers",
                       "No confidence intervals or claim of statistically significant defense advantage"],
    }
    dest = safe_path(args.aggregate_output)
    if dest.exists() or not dest.parent.is_dir():
        raise ValueError("Aggregate output requires a new private file")
    newfile(dest, summary)
    print(json.dumps({"status":summary["status"], "qa_calls_verified":len(requests),
                      "groups":groups, "aggregate_sha256":digest(dest),
                      "output_private":str(dest)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Seal retrieval prompts using verified private lexical corpus")
    prep.add_argument("--cohort-dir", type=Path, default=SOURCE_DIR)
    prep.add_argument("--cohort-sha", default=COHORT_SHA)
    prep.add_argument("--targets", type=Path, required=True)
    prep.add_argument("--targets-sha", required=True)
    prep.add_argument("--construction", type=Path, required=True)
    prep.add_argument("--construction-sha", required=True)
    prep.add_argument("--intensity", type=int, choices=(1,3), required=True)
    prep.add_argument("--limit", type=int, default=300)
    prep.add_argument("--output-plan", type=Path, required=True)
    prep.set_defaults(fn=prepare)
    r = commands.add_parser("run", help="Execute a bounded batch of real Qwen calls; fail closed on uncertain calls")
    r.add_argument("--plan", type=Path, required=True)
    r.add_argument("--plan-sha256", required=True)
    r.add_argument("--output-dir", type=Path, required=True)
    r.add_argument("--max-calls", type=int, default=8)
    r.add_argument("--resume", action="store_true")
    r.set_defaults(fn=run)
    a = commands.add_parser("aggregate", help="Produce aggregate ONLY after all planned calls are verified")
    a.add_argument("--plan", type=Path, required=True)
    a.add_argument("--plan-sha256", required=True)
    a.add_argument("--output-dir", type=Path, required=True)
    a.add_argument("--aggregate-output", type=Path, required=True)
    a.set_defaults(fn=aggregate)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
