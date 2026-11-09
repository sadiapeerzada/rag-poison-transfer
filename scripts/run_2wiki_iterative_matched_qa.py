#!/usr/bin/env python3
"""Exploratory genuine poisoned iterative-RAG QA versus exact frozen Dense controls.

prepare: independently recreate the selected original clean/poison Dense
  evidence/prompt and require exact parity with saved original QA before
  reusing those 80 frozen Dense outcomes. Build real evidence-dependent
  two-round retrieval on identical sealed corpora and write NEW private plan.
run: require original SHA-pinned Qwen model and explicit --execute, journal
  every real iterative-only inference; unknown outcomes never auto-retried.
aggregate: verify every recorded inference, publish PRIVATE grouped metrics
  and question-cluster paired intervals; never claim confirmatory findings.

Source population = original 40 post-hoc valid-only 2Wiki ablation slots,
36 distinct questions; history/exposure/corpus reuse remain limitations.
This does NOT run on the model's cloud environment. It runs locally on Mac.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter, defaultdict
import gc
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_saved_2wiki_rcd_poison_detection import verify_ablation_sources
from scripts.prepare_2wiki_rcd_ablation_plan import ORIGINAL_PINS, require_json
from scripts.run_2wiki_rcd_ablation_qa import atomic_json, canonical
from scripts.second_model_prompt_replay import outside_repo, sha
from src.attacks.asr import build_prompt
from src.defenses.iterative.retriever import EvidenceDependentIterativeRetriever
from src.evaluation.metrics import exact_match, f1_score
from src.evaluation.qa_records import extract_answer
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint
from src.experiments.week9_construction import replay

PLAN_SCHEMA = "rag-poison-transfer.sealed-2wiki-iterative-real-qa-plan/v1"
OPTIMIZED_PLAN_STATUS = "PRIVATE_REAL_RETRIEVAL_PLAN_IDENTICAL_DENSE_PROMPTS_REUSED"
RUN_SCHEMA = "rag-poison-transfer.sealed-2wiki-iterative-real-qa-observation/v1"
REPORT_SCHEMA = "rag-poison-transfer.sealed-2wiki-iterative-qa-comparison/v1"
SEED = 42
TOKEN_CAP = 64
TOP_K = 3
CANDIDATE_K = 10
BOOTSTRAP_SEED = 20261109
FAMILIES = {"lexical_influential_token", "semantic_fluent_false_evidence"}


def canonical_sha(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def entry_id(cell_id: str, qid: str, condition: str):
    return canonical_sha([cell_id, qid, condition, "iterative_2round_v1"])[:24]


def require_original(run_root: Path, *, local_data=None):
    run_root = Path(run_root).expanduser().resolve(strict=True)
    proto = require_json(run_root / "protocol.json", ORIGINAL_PINS["protocol.json"])
    seal = require_json(run_root / "execution/construction/construction.seal.json",
                        ORIGINAL_PINS["execution/construction/construction.seal.json"])
    complete = require_json(run_root / "execution/evaluation/evaluation.complete.json",
                            ORIGINAL_PINS["execution/evaluation/evaluation.complete.json"])
    if (proto.get("binding", {}).get("scope") != "heldout"
            or seal.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"]
            or complete.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"]
            or complete.get("construction_seal_sha256")
            != ORIGINAL_PINS["execution/construction/construction.seal.json"]):
        raise ValueError("Original 2Wiki experiment seals disagree")
    data_path = local_data or proto["replication"]["local_data"]
    data = require_json(data_path, proto["replication"]["local_data_sha256"])
    q = data.get("queries")
    if not isinstance(q, list) or len(q) != 300 or len({x["query_id"] for x in q}) != 300:
        raise ValueError("Original frozen 300-question cohort differs")
    if proto["binding"]["query_ids"] != [x["query_id"] for x in q]:
        raise ValueError("Frozen 2Wiki original question order differs")
    if (seal["plan"]["clean_corpus_fingerprint"] != corpus_fingerprint(data["corpus"])
            or seal["plan"]["query_set_fingerprint"] != query_set_fingerprint(q)):
        raise ValueError("Original 2Wiki corpus/question fingerprints differ")
    embed = proto["replication"]["retrieval_snapshots"]["embedder"]
    embed_path = Path(embed["path"]).expanduser().resolve(strict=True)
    if not embed_path.is_dir():
        raise ValueError("Original pinned embedding-model snapshot directory missing")
    return proto, seal, complete, data, embed_path


def source_cell(root, seal, complete, cellid):
    metadata = seal.get("cells", {}).get(cellid)
    if (not isinstance(metadata, dict)
            or metadata.get("path") != f"{cellid}/construction.json"):
        raise ValueError("Unsealed or unexpected original construction cell")
    cell = require_json(root / "execution/construction" / metadata["path"], metadata["sha256"])
    row_sha = complete.get("rows_sha256", {}).get(cellid)
    if not row_sha:
        raise ValueError("Missing frozen evaluation-row SHA")
    rows = require_json(root / "execution/evaluation" / cellid / "rows.json", row_sha)
    by_id = {r["query_id"]: r for r in cell["records"]}
    by_arm = {(r["pipeline"], r["query_id"]): r for r in rows}
    if (len(by_id) != 300 or len(by_arm) != 600
            or any(("dense", qid) not in by_arm for qid in by_id)):
        raise ValueError("Original 300 matched QA source rows missing")
    return cell, by_id, by_arm


def check_frozen_dense(source_obs, q, retrieved):
    """Never reuse original Dense QA unless evidence AND exact prompt match."""
    ids = [d.doc_id for d in retrieved]
    expected = source_obs.get("generation_evidence_doc_ids")
    original_generation = source_obs.get("generation")
    if not isinstance(expected, list) or ids != expected:
        raise ValueError("Original Dense retrieval evidence IDs did NOT reproduce")
    if not isinstance(original_generation, dict):
        raise ValueError("Original Dense generator prompt is unavailable")
    prompt = build_prompt(q, [doc.text for doc in retrieved])
    if original_generation.get("prompt") != prompt:
        raise ValueError("Original Dense generator prompt did NOT reproduce byte-identically")
    if not isinstance(source_obs.get("answer"), str):
        raise ValueError("Original Dense answer missing")
    return {
        "original_evidence_doc_ids": ids,
        "original_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "original_gold_correct": bool(source_obs["answer_correct"]),
        "original_answer": source_obs["answer"],
        "original_target_match": source_obs.get("targeted_asr"),
        "original_poison_retrieved": source_obs.get("poison_retrieved"),
    }


def new_entry(cellid, question, poison, condition, retrieved, trace, baseline, secs):
    qid = question["query_id"]
    ids = [d.doc_id for d in retrieved]
    action = trace["final_decision"]
    if action not in {"answer", "abstain"}:
        raise ValueError("Unexpected iterative policy decision")
    if trace["selected_doc_ids"] != ids:
        raise ValueError("Iterative trace selected IDs differ from retrieved documents")
    if not 1 <= trace["retrieval_call_count"] <= 2:
        raise ValueError("Invalid actual iterative round count")
    prompt = build_prompt(question["question"], [d.text for d in retrieved]) if action == "answer" else None
    local_ids = set(poison["poison_doc_ids"])
    return {
        "id": entry_id(cellid, qid, condition),
        "cell_id": cellid,
        "family": cellid.split(".intensity-", 1)[0],
        "condition": condition,
        "query_id": qid,
        "gold_answer": question["gold_answer"],
        "target_answer": poison["poison_target_answer"],
        "poison_doc_ids": sorted(local_ids),
        "selected_evidence_doc_ids": ids,
        "poison_visible_to_generator": condition == "poisoned" and bool(local_ids & set(ids)),
        "iterative_retrieval_elapsed_seconds": secs,
        "iterative_actual_inner_retrieval_calls": trace["retrieval_call_count"],
        "policy_trace": trace,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest() if prompt else None,
        "baseline_frozen_dense": baseline,
    }


def identical_frozen_prompt(row):
    """Strict parity: source *evidence IDs AND exact prompt hash* are identical.

    The same original model response is reused as an OBSERVATION, not
    mislabeled as a new independent Qwen generation. The prepared source
    plan itself was already bound to original SHA-pinned evidence/prompt.
    """
    old = row["baseline_frozen_dense"]
    return (
        row["prompt"] is not None
        and row["policy_trace"]["final_decision"] == "answer"
        and row["selected_evidence_doc_ids"] == old["original_evidence_doc_ids"]
        and row["prompt_sha256"] == old["original_prompt_sha256"]
    )


def verify_plan(data):
    status = data.get("status") if isinstance(data, dict) else None
    optimized = status == OPTIMIZED_PLAN_STATUS
    if (not isinstance(data, dict) or data.get("schema") != PLAN_SCHEMA
            or data.get("original_pins") != ORIGINAL_PINS
            or data.get("qa_max_tokens") != TOKEN_CAP
            or status not in {"PRIVATE_REAL_RETRIEVAL_PLAN_NO_NEW_QA",
                              OPTIMIZED_PLAN_STATUS}):
        raise ValueError("Not an original-sealed iterative QA plan")
    entries = data.get("entries")
    if not isinstance(entries, list) or len(entries) != 80:
        raise ValueError("Expected 40 selected questions x 2 conditions")
    if optimized and (not isinstance(data.get("original_prepared_plan_sha256"), str)
                      or len(data["original_prepared_plan_sha256"]) != 64):
        raise ValueError("Optimized plan lacks exact original-prepared-plan SHA-256 provenance")
    seen, slots, questions, by_family, model_calls, reused = (
        set(), defaultdict(set), set(), Counter(), 0, 0
    )
    for row in entries:
        cell, qid, condition = row["cell_id"], row["query_id"], row["condition"]
        key = (cell, qid, condition)
        if (row["id"] != entry_id(cell, qid, condition) or key in seen
                or condition not in {"clean", "poisoned"}
                or row["family"] not in FAMILIES or not cell.startswith(row["family"] + ".intensity-")):
            raise ValueError("Unexpected or duplicate iterative input identity")
        seen.add(key)
        slots[(cell, qid)].add(condition)
        questions.add(qid)
        if condition == "poisoned":
            by_family[row["family"]] += 1
        trace = row["policy_trace"]
        if (type(row["iterative_actual_inner_retrieval_calls"]) is not int
                or row["iterative_actual_inner_retrieval_calls"] not in (1, 2)
                or trace["retrieval_call_count"] != row["iterative_actual_inner_retrieval_calls"]
                or trace["selected_doc_ids"] != row["selected_evidence_doc_ids"]):
            raise ValueError("Iterative retrieval trace does not match source")
        if (row["poison_visible_to_generator"] is not
            (condition == "poisoned" and bool(set(row["selected_evidence_doc_ids"]) & set(row["poison_doc_ids"])))):
            raise ValueError("Source poisoned evidence label mismatches selected IDs")
        prompt = row["prompt"]
        if trace["final_decision"] == "answer":
            if not isinstance(prompt, str) or not prompt or row["prompt_sha256"] != hashlib.sha256(prompt.encode()).hexdigest():
                raise ValueError("Actual iterative QA prompt is missing or altered")
        elif trace["final_decision"] == "abstain":
            if prompt is not None or row["prompt_sha256"] is not None or row["selected_evidence_doc_ids"]:
                raise ValueError("Abstaining policy cannot contain generator-visible evidence")
        else:
            raise ValueError("Unrecognized adaptive policy action")
        baseline = row["baseline_frozen_dense"]
        if (not isinstance(baseline["original_evidence_doc_ids"], list)
                or not isinstance(baseline["original_answer"], str)
                or not isinstance(baseline.get("original_prompt_sha256"), str)
                or len(baseline["original_prompt_sha256"]) != 64):
            raise ValueError("Frozen Dense original evidence/prompt/answer missing")
        if (bool(exact_match(baseline["original_answer"], row["gold_answer"]))
                != baseline["original_gold_correct"]):
            raise ValueError("Frozen Dense original answer correctness is inconsistent")
        if (condition == "poisoned"
                and baseline["original_target_match"] is not None
                and bool(exact_match(baseline["original_answer"], row["target_answer"]))
                != bool(baseline["original_target_match"])):
            raise ValueError("Frozen Dense original target label is inconsistent")
        if optimized:
            flag = row.get("reuse_frozen_dense_qa_for_iterative")
            if type(flag) is not bool or flag != identical_frozen_prompt(row):
                raise ValueError("Exact prompt/evidence parity does not permit indicated reuse")
            reused += int(flag)
            if prompt is not None and not flag:
                model_calls += 1
        else:
            if "reuse_frozen_dense_qa_for_iterative" in row:
                raise ValueError("Source preparation plan must not be tampered with")
            if prompt is not None:
                model_calls += 1
    if (len(slots) != 40 or any(x != {"clean", "poisoned"} for x in slots.values())
            or len(questions) != 36 or len(by_family) != 2
            or data.get("required_new_qa_calls") != model_calls):
        raise ValueError("Selected ablation population or planned QA calls disagrees")
    if optimized and data.get("identical_frozen_dense_qa_reuse_count") != reused:
        raise ValueError("Optimized reused Dense observation count disagrees")
    return entries


def optimize(*, prepared_plan, prepared_plan_sha256, out):
    """No Qwen and NO new retrieval; safe transformation of real saved plan."""
    original = load_plan(prepared_plan, prepared_plan_sha256)
    if original["status"] != "PRIVATE_REAL_RETRIEVAL_PLAN_NO_NEW_QA":
        raise ValueError("Only the unoptimized original retrieval plan may be optimized")
    out = outside_repo(out)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Choose a new private optimized output file")
    updated = copy.deepcopy(original)
    updated["status"] = OPTIMIZED_PLAN_STATUS
    updated["original_prepared_plan_sha256"] = prepared_plan_sha256
    n_reused = 0
    for item in updated["entries"]:
        match = identical_frozen_prompt(item)
        item["reuse_frozen_dense_qa_for_iterative"] = match
        n_reused += int(match)
    updated["identical_frozen_dense_qa_reuse_count"] = n_reused
    updated["required_new_qa_calls"] = sum(
        r["prompt"] is not None and not r["reuse_frozen_dense_qa_for_iterative"]
        for r in updated["entries"]
    )
    updated["limitations"].append(
        "An identical original Dense prompt is reused as ONE shared original Qwen "
        "observation, not a second independent new iterative-model trial; "
        "identical-prompt arm differences are exactly zero by design."
    )
    verify_plan(updated)
    with out.open("x", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return {
        "status": updated["status"],
        "original_real_retrieval_plan_sha256": prepared_plan_sha256,
        "total_matched_arm_entries": len(updated["entries"]),
        "original_dense_qa_observations_reused_as_control": 80,
        "identical_iterative_prompts_reusing_the_same_frozen_dense_answer": n_reused,
        "new_real_qwen_inference_requests_required": updated["required_new_qa_calls"],
        "actual_retrieval_round2_invocations": sum(
            r["iterative_actual_inner_retrieval_calls"] == 2
            for r in updated["entries"]
        ),
        "reused_answers_are_not_new_independent_model_calls": True,
        "optimized_plan_sha256": sha(out),
        "private_optimized_plan_path": str(out)
    }



def load_plan(file: Path, pin: str):
    plan = require_json(file, pin)
    verify_plan(plan)
    return plan


def prepare(*, research_root, original_run, out, local_data=None, private_ablation_plan=None,
            retriever_factory=None):
    out = outside_repo(out)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("New plan file in existing private directory required")
    plan, original_plan_sha, _, _ = verify_ablation_sources(
        Path(research_root), plan_path=private_ablation_plan
    )
    original_run = Path(original_run).expanduser().resolve(strict=True)
    proto, seal, complete, data, embedder_path = require_original(
        original_run, local_data=local_data
    )
    original_queries = {r["query_id"]: r for r in data["queries"]}
    source_full = [r for r in plan["entries"] if r["variant"] == "full_k3"]
    if len(source_full) != 80:
        raise ValueError("Frozen original RCD plan lacks expected 80 full-k3 retrieval records")
    selected = defaultdict(set)
    for row in source_full:
        selected[(row["cell_id"], row["query_id"])].add(row["condition"])
    if len(selected) != 40 or any(v != {"clean", "poisoned"} for v in selected.values()):
        raise ValueError("Frozen sample is not 40 complete selected clean/poison pairs")

    # Use the original BGE model, never the synthetic hashing embedder.
    if retriever_factory is None:
        from src.retrieval.dense import DenseRetriever, SentenceTransformerEmbedder
        encoder = SentenceTransformerEmbedder(str(embedder_path))
        retriever_factory = lambda: DenseRetriever(encoder)
    entries = []
    parity_count = 0
    for cellid in sorted({cell for cell, _ in selected}):
        cell, by_query, by_arm = source_cell(original_run, seal, complete, cellid)
        poison_data = replay(data, cell)  # Full cell union, all valid injections
        poison_q = {r["query_id"]: r for r in poison_data["queries"]}
        clean_retriever, poisoned_retriever = retriever_factory(), retriever_factory()
        clean_retriever.build(data["corpus"])
        poisoned_retriever.build(poison_data["corpus"])
        for c, qid in sorted(selected):
            if c != cellid:
                continue
            original = original_queries[qid]
            attacked = poison_q.get(qid)
            if (not attacked or by_query[qid]["status"] != "valid_construction"
                    or attacked["gold_answer"] != original["gold_answer"]
                    or attacked["question"] != original["question"]):
                raise ValueError("Selected frozen source question/corpus does not match valid attack")
            true_dense = by_arm[("dense", qid)]
            if true_dense["construction_status"] != "valid_construction" or true_dense["measurement"] is None:
                raise ValueError("Selected original Dense QA observation missing")
            measurement = true_dense["measurement"]
            if (measurement["gold_answer"] != original["gold_answer"]
                    or measurement["poison_target_answer"] != attacked["poison_target_answer"]
                    or sorted(measurement["poison_doc_ids"]) != sorted(attacked["poison_doc_ids"])):
                raise ValueError("Original Dense gold/poison association differs")
            for condition, base_retriever in (("clean", clean_retriever),
                                               ("poisoned", poisoned_retriever)):
                baseline_source = measurement[f"{condition}_condition"]
                base_docs = base_retriever.retrieve(original["question"], top_k=TOP_K)
                baseline = check_frozen_dense(baseline_source, original["question"], base_docs)
                parity_count += 1
                iterative = EvidenceDependentIterativeRetriever(
                    base_retriever, max_rounds=2,
                    candidate_k=CANDIDATE_K, output_k=TOP_K, min_coverage=0.75
                )
                started = time.perf_counter()
                docs = iterative.retrieve(original["question"], top_k=TOP_K)
                elapsed = time.perf_counter() - started
                entry = new_entry(cellid, original, attacked, condition, docs,
                                  iterative.last_diagnostics, baseline, elapsed)
                entries.append(entry)
        del clean_retriever, poisoned_retriever
        gc.collect()
    report = {
        "schema": PLAN_SCHEMA,
        "status": "PRIVATE_REAL_RETRIEVAL_PLAN_NO_NEW_QA",
        "original_pins": ORIGINAL_PINS,
        "original_480_rcd_ablation_prompt_plan_sha256": original_plan_sha,
        "original_clean_corpus_fingerprint": seal["plan"]["clean_corpus_fingerprint"],
        "original_2wiki_input_sha256": proto["replication"]["local_data_sha256"],
        "original_embedder_model_snapshot": proto["replication"]["retrieval_snapshots"]["embedder"],
        "original_qwen_model": proto["model"],
        "qa_max_tokens": TOKEN_CAP,
        "qa_seed": SEED,
        "retriever_policy": "deterministic-first-evidence-anchor-coverage/v1",
        "subset_design": "40 original post-hoc valid selected query/cell slots; 36 distinct original questions",
        "dense_baseline_parity_verified": parity_count,
        "entries": entries,
        "required_new_qa_calls": sum(e["prompt"] is not None for e in entries),
        "limitations": [
            "Historical original 2Wiki cohort was not certified prospectively unexposed.",
            "40 selected query/cell positions are valid-only and post-hoc; 36 distinct questions repeated across cells.",
            "Original Dense Qwen outcomes reused ONLY after exact evidence ID and original prompt parity checks.",
            "Iterative policy is an uncalibrated lexical question-coverage heuristic, not a learned controller.",
            "All original frozen observations and attacks remain unchanged.",
            "New generator calls are needed to measure real iterative answer effects; retrieval does not prove QA utility."
        ]
    }
    verify_plan(report)
    with out.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return {
        "status": report["status"],
        "source_evidence_parity_checks": parity_count,
        "matched_source_slots": parity_count // 2,
        "unique_questions": 36,
        "iterative_real_qa_calls_needed": report["required_new_qa_calls"],
        "second_round_invocations": sum(x["iterative_actual_inner_retrieval_calls"] == 2 for x in entries),
        "abstentions": sum(x["prompt"] is None for x in entries),
        "frozen_original_qwen_calls_reused_not_rerun": parity_count,
        "plan_sha256": sha(out),
        "private_plan_path": str(out),
    }


def validate_response(row, observation, plan_sha, binding_sha):
    if (observation.get("schema") != RUN_SCHEMA or observation.get("id") != row["id"]
            or observation.get("prompt_sha256") != row["prompt_sha256"]
            or observation.get("plan_sha256") != plan_sha
            or observation.get("model_binding_sha256") != binding_sha):
        raise ValueError("Stored real Qwen observation does not match frozen iterative prompt/model")
    if (not isinstance(observation.get("raw_response"), str)
            or observation.get("extracted_answer") != extract_answer(observation["raw_response"])):
        raise ValueError("Actual Qwen raw response/extraction disagree")
    correct = bool(exact_match(observation["extracted_answer"], row["gold_answer"]))
    target = bool(exact_match(observation["extracted_answer"], row["target_answer"]))
    if (observation.get("gold_correct") is not correct
            or observation.get("target_match") is not target
            or not math.isclose(observation.get("gold_f1", -1), f1_score(observation["extracted_answer"], row["gold_answer"]))):
        raise ValueError("Stored real answer differs from independently recomputed QA metrics")
    for k in ("generator_latency_seconds", "prompt_tokens", "completion_tokens"):
        v = observation.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0:
            raise ValueError("Actual model timing or token count missing")
    return observation


def run(*, plan_file, plan_sha256, original_protocol, model_snapshot, results_dir,
        execute=False, max_new_requests=None):
    if not execute:
        raise ValueError("Explicit --execute required for physical new Qwen inference")
    plan = load_plan(plan_file, plan_sha256)
    if plan["status"] != OPTIMIZED_PLAN_STATUS:
        raise ValueError("Optimize exact-repeat prompts before authorizing any new Qwen inference")
    protocol = require_json(original_protocol, ORIGINAL_PINS["protocol.json"])
    from scripts.run_week9_protocol_poison_matrix import model_binding
    binding = model_binding(model_snapshot, protocol["binding"]["model_identity"])
    if binding != plan["original_qwen_model"] or binding != protocol["model"]:
        raise ValueError("Model snapshot does not match frozen original Qwen identity")
    binding_sha = canonical_sha(binding)
    results_dir = outside_repo(results_dir)
    if results_dir.exists() and not results_dir.is_dir():
        raise ValueError("Private run root is not a directory")
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "intents").mkdir(exist_ok=True)
    (results_dir / "entries").mkdir(exist_ok=True)
    manifest_path = results_dir / "run_manifest.json"
    manifest = {
        "schema": RUN_SCHEMA,
        "plan_sha256": plan_sha256,
        "model_binding_sha256": binding_sha,
        "original_protocol_sha256": ORIGINAL_PINS["protocol.json"],
        "qa_max_tokens": TOKEN_CAP,
        "decoding": "explicit greedy temp=0, per-call Qwen seed 42",
        "required_new_qa_calls": plan["required_new_qa_calls"],
        "identical_frozen_dense_qa_reuse_count": plan["identical_frozen_dense_qa_reuse_count"],
        "original_prepared_plan_sha256": plan["original_prepared_plan_sha256"],
    }
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Prior iterative run manifest mismatches exact model/prompt")
    else:
        atomic_json(manifest_path, manifest)

    pending, done = [], 0
    for entry in plan["entries"]:
        if entry["prompt"] is None or entry["reuse_frozen_dense_qa_for_iterative"]:
            continue
        result = results_dir / "entries" / (entry["id"] + ".json")
        intent = results_dir / "intents" / (entry["id"] + ".json")
        if result.exists():
            recorded = require_json(result, sha(result))
            validate_response(entry, recorded, plan_sha256, binding_sha)
            if not intent.exists() or json.loads(intent.read_text()).get("id") != entry["id"]:
                raise ValueError("Completed model observation lacks correct immutable intent journal")
            done += 1
        elif intent.exists():
            raise ValueError("Unresolved generator call intent; do not retry automatically: " + entry["id"])
        else:
            pending.append(entry)
    if max_new_requests is not None:
        if type(max_new_requests) is not int or max_new_requests < 1:
            raise ValueError("Request cap must be positive")
        pending = pending[:max_new_requests]

    if pending:
        from mlx_lm.sample_utils import make_sampler
        from src.pipelines.generator import MLXGenerator
        qwen = MLXGenerator(model_name=str(Path(model_snapshot).expanduser().resolve(strict=True)))
        original = qwen._generate_fn
        greedy = make_sampler(temp=0.0)
        qwen._generate_fn = lambda *args, **kw: original(*args, **kw, sampler=greedy)
        for entry in pending:
            intent = results_dir / "intents" / (entry["id"] + ".json")
            result = results_dir / "entries" / (entry["id"] + ".json")
            atomic_json(intent, {
                "id": entry["id"], "prompt_sha256": entry["prompt_sha256"],
                "plan_sha256": plan_sha256, "model_binding_sha256": binding_sha,
                "max_tokens": TOKEN_CAP,
                "status": "INTENT_RECORDED_BEFORE_POSSIBLE_INFERENCE"
            })
            qwen.seed(SEED)
            raw = qwen.generate(entry["prompt"], max_tokens=TOKEN_CAP)
            answer = extract_answer(raw.text)
            observation = {
                "schema": RUN_SCHEMA, "id": entry["id"],
                "prompt_sha256": entry["prompt_sha256"],
                "plan_sha256": plan_sha256, "model_binding_sha256": binding_sha,
                "raw_response": raw.text, "extracted_answer": answer,
                "gold_correct": bool(exact_match(answer, entry["gold_answer"])),
                "gold_f1": f1_score(answer, entry["gold_answer"]),
                "target_match": bool(exact_match(answer, entry["target_answer"])),
                "generator_latency_seconds": raw.latency_seconds,
                "prompt_tokens": raw.prompt_tokens,
                "completion_tokens": raw.completion_tokens,
                "backend_prompt_sha256": (
                    hashlib.sha256(raw.backend_prompt.encode()).hexdigest()
                    if isinstance(raw.backend_prompt, str) else None
                )
            }
            atomic_json(result, observation)
            validate_response(entry, observation, plan_sha256, binding_sha)
            done += 1
    return {
        "status": "ITERATIVE_NEW_QWEN_COMPLETE" if done == plan["required_new_qa_calls"] else "ITERATIVE_NEW_QWEN_PARTIAL",
        "verified_real_qa_observations": done,
        "required_real_qa_observations": plan["required_new_qa_calls"],
        "identical_frozen_dense_responses_reused": plan["identical_frozen_dense_qa_reuse_count"],
        "remaining": plan["required_new_qa_calls"] - done,
        "private_run_directory": str(results_dir)
    }


def percentile_interval(values):
    ordered = sorted(values)
    n = len(ordered)
    return [ordered[int((n-1)*0.025)], ordered[int((n-1)*0.975)]]


def paired_question_cluster_interval(rows, effect_name, reps=2000):
    by_q = defaultdict(list)
    for row in rows:
        by_q[row["query_id"]].append(row)
    keys = sorted(by_q)
    if len(keys) != 36:
        raise ValueError("Expected exactly 36 independent original question clusters")
    rand = random.Random(BOOTSTRAP_SEED)
    values = []
    for _ in range(reps):
        sample = [r for _ in keys for r in by_q[keys[rand.randrange(len(keys))]]]
        values.append(sum(r[effect_name] for r in sample)/len(sample))
    return {"nominal_ci95": percentile_interval(values),
            "bootstrap_replicates": reps,
            "unit": "original question ID, all repeated-cell positions together",
            "seed": BOOTSTRAP_SEED,
            "multiplicity_adjusted": False}


def summarize_pair(clean, attacked):
    before = clean["baseline_frozen_dense"]
    b_poison = attacked["baseline_frozen_dense"]
    clean_new = clean["_new"]
    poisoned_new = attacked["_new"]
    return {
        "query_id": clean["query_id"],
        "cell_id": clean["cell_id"],
        "family": clean["family"],
        "dense_clean_correct": int(before["original_gold_correct"]),
        "dense_poisoned_correct": int(b_poison["original_gold_correct"]),
        "dense_poisoned_target": int(bool(b_poison["original_target_match"])),
        "iterative_clean_correct": int(clean_new["gold_correct"]),
        "iterative_poisoned_correct": int(poisoned_new["gold_correct"]),
        "iterative_poisoned_target": int(poisoned_new["target_match"]),
        "iterative_poison_visible": int(attacked["poison_visible_to_generator"]),
        "dense_poison_visible": int(bool(b_poison["original_poison_retrieved"])),
        "iterative_abstentions": int(clean["prompt"] is None)+int(attacked["prompt"] is None),
        "iterative_inner_retrieval_calls": (
            clean["iterative_actual_inner_retrieval_calls"]+
            attacked["iterative_actual_inner_retrieval_calls"]),
        "iterative_target_minus_dense": (
            int(poisoned_new["target_match"])-int(bool(b_poison["original_target_match"]))
        ),
        "iterative_clean_correct_minus_dense": (
            int(clean_new["gold_correct"])-int(before["original_gold_correct"])
        ),
    }


def aggregate(*, plan_file, plan_sha256, results_dir, output):
    plan = load_plan(plan_file, plan_sha256)
    if plan["status"] != OPTIMIZED_PLAN_STATUS:
        raise ValueError("Aggregate requires source-bound optimized exact-repeat prompt plan")
    results_dir = outside_repo(results_dir)
    output = outside_repo(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Aggregate must be a NEW private output in existing directory")
    manifest_path = results_dir / "run_manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Missing verified real Qwen run manifest")
    manifest = require_json(manifest_path, sha(manifest_path))
    if (manifest.get("schema") != RUN_SCHEMA
            or manifest.get("plan_sha256") != plan_sha256
            or manifest.get("required_new_qa_calls") != plan["required_new_qa_calls"]
            or manifest.get("identical_frozen_dense_qa_reuse_count") != plan["identical_frozen_dense_qa_reuse_count"]
            or manifest.get("original_prepared_plan_sha256") != plan["original_prepared_plan_sha256"]):
        raise ValueError("Real original model-run manifest disagrees with frozen inputs")
    pairs = defaultdict(dict)
    for row in plan["entries"]:
        r = dict(row)
        if row["prompt"] is None:
            r["_new"] = {"gold_correct": False, "target_match": False,
                         "gold_f1": 0.0, "observation_status": "POLICY_ABSTENTION_NO_QA"}
        elif row["reuse_frozen_dense_qa_for_iterative"]:
            original = row["baseline_frozen_dense"]
            answer = original["original_answer"]
            r["_new"] = {
                "gold_correct": original["original_gold_correct"],
                "target_match": bool(exact_match(answer, row["target_answer"])),
                "gold_f1": f1_score(answer, row["gold_answer"]),
                "observation_status": "REUSED_EXACT_SAME_FROZEN_DENSE_MODEL_RESPONSE"
            }
        else:
            result = results_dir / "entries" / (row["id"] + ".json")
            intent = results_dir / "intents" / (row["id"] + ".json")
            if not result.exists() or not intent.exists():
                raise ValueError("Missing actual Qwen response/intent; aggregation prohibited")
            obs = require_json(result, sha(result))
            if (json.loads(intent.read_text()).get("prompt_sha256")
                    != row["prompt_sha256"]):
                raise ValueError("Generator intent prompt identity changed")
            r["_new"] = validate_response(
                row, obs, plan_sha256, manifest["model_binding_sha256"]
            )
        pairs[(row["cell_id"], row["query_id"])][row["condition"]] = r
    if len(pairs) != 40 or any(set(arms) != {"clean", "poisoned"} for arms in pairs.values()):
        raise ValueError("Incomplete 40 matched clean/poison iterative/Dense pairs")
    summary_rows = [summarize_pair(arms["clean"], arms["poisoned"])
                    for _, arms in sorted(pairs.items())]
    n = len(summary_rows)
    counts = {k: sum(r[k] for r in summary_rows) for k in (
        "dense_clean_correct", "dense_poisoned_correct", "dense_poisoned_target",
        "iterative_clean_correct", "iterative_poisoned_correct",
        "iterative_poisoned_target", "iterative_poison_visible",
        "dense_poison_visible", "iterative_abstentions",
        "iterative_inner_retrieval_calls")}
    values = {name: {"count": v, "denominator": n, "rate_per_selected_position": v/n}
              for name,v in counts.items()}
    comparisons = {
        "iterative_targeted_match_minus_frozen_dense": {
            "difference": sum(r["iterative_target_minus_dense"] for r in summary_rows)/n,
            "question_cluster_interval": paired_question_cluster_interval(
                summary_rows, "iterative_target_minus_dense")
        },
        "iterative_clean_correct_minus_frozen_dense": {
            "difference": sum(r["iterative_clean_correct_minus_dense"] for r in summary_rows)/n,
            "question_cluster_interval": paired_question_cluster_interval(
                summary_rows, "iterative_clean_correct_minus_dense")
        }
    }
    report = {
        "schema": REPORT_SCHEMA,
        "status": "REAL_QWEN_ITERATIVE_MATCHED_QA_EXPLORATORY_COMPLETE",
        "source_qa_plan_sha256": plan_sha256,
        "source_model_binding_sha256": manifest["model_binding_sha256"],
        "original_frozen_evidence_pins": ORIGINAL_PINS,
        "n_selected_query_cell_pairs": n,
        "n_distinct_question_ids": len({r["query_id"] for r in summary_rows}),
        "n_actual_new_qwen_model_calls": plan["required_new_qa_calls"],
        "n_reused_original_dense_qwen_observations": 80,
        "n_identical_iterative_arm_responses_reused_from_frozen_dense": plan["identical_frozen_dense_qa_reuse_count"],
        "original_prepared_plan_sha256": plan["original_prepared_plan_sha256"],
        "summary": values,
        "paired_effects": comparisons,
        "limitations": [
            "Only 40 post-hoc valid-only question/stratum positions, 36 original query IDs; this is not a prospective full 300-query protocol.",
            "Multiple positions for a question are dependent and clustered; intervals are nominal 2000-bootstrap CIs.",
            "The original Dense control was reused after independently verifying exact original retriever IDs and prompt identity; original data unchanged.",
            "Where both arms have byte-identical prompt and exact evidence document IDs, both paired outcomes reuse ONE original Dense Qwen answer; these are not independent generation replicates.",
            "Original 2Wiki study historical exposure/custody uncertainties remain.",
            "The multi-round policy is a lexical-coverage heuristic, not a learned adaptive controller.",
            "Poison-target matching is not source-verified semantic factuality; abstentions count as answer failures.",
            "Actual resource latency covers new iterative retrieval only; original Dense generation occurred in a previous run and is not a matched-time benchmark."
        ]
    }
    with output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    return {
        "status": report["status"],
        "question_cell_pairs": n,
        "distinct_question_ids": report["n_distinct_question_ids"],
        "new_real_qwen_calls": report["n_actual_new_qwen_model_calls"],
        "same_prompt_iterative_answers_reused": report["n_identical_iterative_arm_responses_reused_from_frozen_dense"],
        "actual_iterative_target_matches": counts["iterative_poisoned_target"],
        "original_dense_target_matches": counts["dense_poisoned_target"],
        "paired_target_difference": comparisons["iterative_targeted_match_minus_frozen_dense"]["difference"],
        "paired_target_cluster_ci95": comparisons["iterative_targeted_match_minus_frozen_dense"]["question_cluster_interval"]["nominal_ci95"],
        "new_iterative_clean_correct": counts["iterative_clean_correct"],
        "frozen_dense_clean_correct": counts["dense_clean_correct"],
        "private_summary": str(output),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    prep = sub.add_parser("prepare", help="Recompute real clean and poisoned retrieval, no Qwen calls")
    prep.add_argument("--research-root", type=Path,
                      default=Path.home() / "Documents/rag-research-results")
    prep.add_argument("--original-run", type=Path, required=True)
    prep.add_argument("--local-data", type=Path)
    prep.add_argument("--private-ablation-plan", type=Path)
    prep.add_argument("--out", type=Path, required=True)
    opt = sub.add_parser("optimize", help="Reuse original Dense QA only for exact identical prompt/evidence; no inference or retrieval")
    opt.add_argument("--plan", type=Path, required=True)
    opt.add_argument("--plan-sha256", required=True)
    opt.add_argument("--out", type=Path, required=True)
    execute = sub.add_parser("run", help="Resume/perform explicit real Qwen model inference")
    execute.add_argument("--plan", type=Path, required=True)
    execute.add_argument("--plan-sha256", required=True)
    execute.add_argument("--protocol", type=Path, required=True)
    execute.add_argument("--model-snapshot", type=Path, required=True)
    execute.add_argument("--results-dir", type=Path, required=True)
    execute.add_argument("--max-new-requests", type=int)
    execute.add_argument("--execute", action="store_true")
    summ = sub.add_parser("aggregate", help="Require complete genuine QA outcomes; no inference")
    summ.add_argument("--plan", type=Path, required=True)
    summ.add_argument("--plan-sha256", required=True)
    summ.add_argument("--results-dir", type=Path, required=True)
    summ.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "prepare":
        value = prepare(research_root=args.research_root,
                        original_run=args.original_run, out=args.out,
                        local_data=args.local_data,
                        private_ablation_plan=args.private_ablation_plan)
    elif args.stage == "optimize":
        value = optimize(prepared_plan=args.plan,
                         prepared_plan_sha256=args.plan_sha256, out=args.out)
    elif args.stage == "run":
        value = run(plan_file=args.plan, plan_sha256=args.plan_sha256,
                    original_protocol=args.protocol, model_snapshot=args.model_snapshot,
                    results_dir=args.results_dir, execute=args.execute,
                    max_new_requests=args.max_new_requests)
    else:
        value = aggregate(plan_file=args.plan, plan_sha256=args.plan_sha256,
                          results_dir=args.results_dir, output=args.out)
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
