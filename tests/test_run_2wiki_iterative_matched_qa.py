"""Synthetic fail-closed tests; no GPU, network or original private 2Wiki QA."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from scripts import run_2wiki_iterative_matched_qa as it
from src.attacks.asr import build_prompt

CELLS = (
    "lexical_influential_token.intensity-1.seed-42",
    "lexical_influential_token.intensity-3.seed-42",
    "semantic_fluent_false_evidence.intensity-1.seed-42",
    "semantic_fluent_false_evidence.intensity-3.seed-42",
)


def make_plan(*, answered=True):
    cell_questions = [
        [f"q{n}" for n in range(0, 10)],
        [f"q{n}" for n in range(0, 4)] + [f"q{n}" for n in range(10, 16)],
        [f"q{n}" for n in range(16, 26)],
        [f"q{n}" for n in range(26, 36)],
    ]
    entries = []
    for cell, qids in zip(CELLS, cell_questions):
        for qid in qids:
            for condition in ("clean", "poisoned"):
                prompt = ("Question: What is the synthetic answer? " + qid
                          if answered else None)
                docs = ["clean_doc"] if answered else []
                trace = {
                    "final_decision": "answer" if answered else "abstain",
                    "retrieval_call_count": 2,
                    "selected_doc_ids": docs
                }
                entries.append({
                    "id": it.entry_id(cell, qid, condition),
                    "cell_id": cell, "family": cell.split(".intensity-")[0],
                    "query_id": qid, "condition": condition,
                    "gold_answer": "green", "target_answer": "red",
                    "poison_doc_ids": ["poison_doc"],
                    "selected_evidence_doc_ids": docs,
                    "poison_visible_to_generator": False,
                    "iterative_retrieval_elapsed_seconds": 0.01,
                    "iterative_actual_inner_retrieval_calls": 2,
                    "policy_trace": trace,
                    "prompt": prompt,
                    "prompt_sha256": (hashlib.sha256(prompt.encode()).hexdigest()
                                      if prompt else None),
                    "baseline_frozen_dense": {
                        "original_evidence_doc_ids": ["clean_doc"],
                        "original_prompt_sha256": "a" * 64,
                        "original_gold_correct": True,
                        "original_answer": "green",
                        "original_target_match": False,
                        "original_poison_retrieved": False
                    }
                })
    return {
        "schema": it.PLAN_SCHEMA, "status": "PRIVATE_REAL_RETRIEVAL_PLAN_NO_NEW_QA",
        "original_pins": it.ORIGINAL_PINS,
        "qa_max_tokens": 64, "entries": entries,
        "limitations": ["Synthetic-only private fixture; not a real research result."],
        "required_new_qa_calls": 80 if answered else 0
    }


def test_plan_requires_40_matched_slots_and_36_question_clusters():
    plan = make_plan()
    assert len(it.verify_plan(plan)) == 80
    assert len({e["query_id"] for e in plan["entries"]}) == 36
    assert len({(e["cell_id"], e["query_id"]) for e in plan["entries"]}) == 40


def test_plan_fails_on_unmatched_condition_and_wrong_qwen_count():
    plan = make_plan()
    plan["entries"][0]["condition"] = "poisoned"
    with pytest.raises(ValueError, match="identity"):
        it.verify_plan(plan)
    plan = make_plan()
    plan["required_new_qa_calls"] = 79
    with pytest.raises(ValueError, match="population"):
        it.verify_plan(plan)


def test_abstentions_never_create_qwen_prompts_or_poison_claims():
    plan = make_plan(answered=False)
    assert it.verify_plan(plan)
    assert all(e["prompt"] is None for e in plan["entries"])
    assert all(e["policy_trace"]["final_decision"] == "abstain" for e in plan["entries"])
    a = plan["entries"][0]
    a["selected_evidence_doc_ids"] = ["poison_doc"]
    with pytest.raises(ValueError, match="Iterative retrieval trace"):
        it.verify_plan(plan)


def test_frozen_dense_reuse_requires_exact_id_and_prompt_parity():
    question = "Who is the synthetic author?"
    docs = [SimpleNamespace(doc_id="d1", text="Synthetic evidence only")]
    true_prompt = build_prompt(question, [docs[0].text])
    source = {
        "generation_evidence_doc_ids": ["d1"],
        "generation": {"prompt": true_prompt},
        "answer": "green", "answer_correct": True, "targeted_asr": False,
    }
    record = it.check_frozen_dense(source, question, docs)
    assert record["original_gold_correct"] is True
    source["generation_evidence_doc_ids"] = ["different"]
    with pytest.raises(ValueError, match="evidence IDs"):
        it.check_frozen_dense(source, question, docs)
    source["generation_evidence_doc_ids"] = ["d1"]
    source["generation"]["prompt"] = "Altered prompt"
    with pytest.raises(ValueError, match="byte-identically"):
        it.check_frozen_dense(source, question, docs)


def test_new_entry_is_actual_trace_and_never_uses_gold_for_query():
    q = {"query_id": "q1", "question": "What is the answer?", "gold_answer": "green"}
    attacked = {"poison_target_answer": "red", "poison_doc_ids": ["p1"]}
    docs = [SimpleNamespace(doc_id="p1", text="Test document without real facts")]
    trace = {"retrieval_call_count": 2, "final_decision": "answer", "selected_doc_ids": ["p1"]}
    baseline = {"original_evidence_doc_ids": ["d1"], "original_answer": "green"}
    poisoned = it.new_entry(CELLS[0], q, attacked, "poisoned", docs, trace, baseline, 0.02)
    clean = it.new_entry(CELLS[0], q, attacked, "clean", docs, trace, baseline, 0.02)
    assert poisoned["poison_visible_to_generator"] is True
    assert clean["poison_visible_to_generator"] is False
    assert poisoned["prompt"].startswith("Answer the question using only")
    assert poisoned["prompt"] == clean["prompt"]
    with pytest.raises(ValueError, match="trace selected IDs"):
        it.new_entry(CELLS[0], q, attacked, "poisoned", [], trace, baseline, 0.02)


def test_response_recomputes_real_answer_without_trusting_stored_labels():
    e = make_plan()["entries"][0]
    raw = "green"
    response = {
        "schema": it.RUN_SCHEMA, "id": e["id"],
        "prompt_sha256": e["prompt_sha256"],
        "plan_sha256": "plan_sha", "model_binding_sha256": "model_sha",
        "raw_response": raw, "extracted_answer": "green",
        "gold_correct": True, "target_match": False, "gold_f1": 1.,
        "generator_latency_seconds": 0.5, "prompt_tokens": 50,
        "completion_tokens": 1
    }
    assert it.validate_response(e, response, "plan_sha", "model_sha") is response
    response["target_match"] = True
    with pytest.raises(ValueError, match="independently recomputed"):
        it.validate_response(e, response, "plan_sha", "model_sha")


def test_true_question_cluster_bootstrap_keeps_repeated_question_positions():
    plan = make_plan()
    rows = []
    for row in plan["entries"]:
        if row["condition"] == "poisoned":
            rows.append({
                "query_id": row["query_id"],
                "iterative_target_minus_dense": 1 if row["query_id"] == "q0" else -1,
            })
    ci = it.paired_question_cluster_interval(rows, "iterative_target_minus_dense", reps=100)
    assert ci["bootstrap_replicates"] == 100
    assert ci["unit"] == "original question ID, all repeated-cell positions together"
    assert -1 <= ci["nominal_ci95"][0] <= ci["nominal_ci95"][1] <= 1


def test_real_qwen_requires_explicit_execute_before_file_or_model_touch(tmp_path):
    with pytest.raises(ValueError, match="Explicit --execute"):
        it.run(plan_file=tmp_path / "absent_plan.json",
               plan_sha256="0" * 64,
               original_protocol=tmp_path / "absent_protocol.json",
               model_snapshot=tmp_path / "absent_weights",
               results_dir=tmp_path / "never_created",
               execute=False)
    assert not (tmp_path / "never_created").exists()


def test_aggregate_must_not_run_before_any_real_qwen_record(tmp_path):
    plan = make_plan()
    p = tmp_path / "synthetic_plan.json"
    p.write_text(json.dumps(plan))
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(ValueError):
        it.aggregate(plan_file=p, plan_sha256=it.sha(p), results_dir=private,
                     output=private / "missing_output.json")
    assert not (private / "missing_output.json").exists()


def test_single_pair_reports_true_differences_no_inference():
    plan = make_plan()
    a,b=plan["entries"][:2]
    a=dict(a); b=dict(b)
    a["_new"]={"gold_correct":False, "target_match":False}
    b["_new"]={"gold_correct":True, "target_match":True}
    row=it.summarize_pair(a,b)
    assert row["iterative_target_minus_dense"]==1
    assert row["iterative_clean_correct_minus_dense"]==-1
    assert row["iterative_abstentions"]==0
