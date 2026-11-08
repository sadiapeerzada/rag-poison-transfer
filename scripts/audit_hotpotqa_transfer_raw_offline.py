#!/usr/bin/env python3
"""Fail-closed, read-only HotpotQA source-crafted transfer audit.

The original private runtime tree must be present on the operator's computer.
No model is loaded and no inference runs. No held-out examples are exported.

CLI example is in docs/NOV09_FOUR_RESEARCH_GATES.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from src.evaluation.metrics import exact_match
from src.evaluation.qa_records import validate_qa

PROTOCOL_PIN = "94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa"
SELECTION_PIN = "3f9217c83a7c1309763468be1cf2e57ebcd0ecd726a44c57b4eaa4d61ab3b750"
COMPLETION_PIN = "72343b04134f8d6f24815d731af52c644d517dba042754236f9e7f089316c191"
AGGREGATE_PIN = "43f3f652460ac365fefdf2e516d227c66aae9fb124df8ca028874327e9335adc"
FAMILIES = {"lexical_influential_token", "semantic_fluent_false_evidence"}
SOURCES = {"bm25", "dense", "hybrid", "reranker"}
TARGETS = SOURCES | {"rcd"}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require_pin(path, pin):
    if not Path(path).is_file() or sha256(path) != pin:
        raise ValueError("Missing/pin mismatch: " + str(path))


def verify_inventory(root, manifest, *, exclude):
    """Reject additional/missing files, symlinks and content deviations."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Missing or symlink stage root: " + str(root))
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Symlink present in immutable stage: " + str(root))
    expected = manifest.get("files_sha256")
    if not isinstance(expected, dict):
        raise ValueError("Missing file inventory: " + str(root))
    actual = {
        p.relative_to(root).as_posix(): sha256(p)
        for p in root.rglob("*")
        if p.is_file() and p.name not in exclude
    }
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        changed = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])
        raise ValueError(f"Inventory mismatch at {root}: missing={len(missing)}, extra={len(extra)}, changed={len(changed)}")
    return len(actual)


def check_qa(measurement, gold, target):
    if measurement["gold_answer"] != gold or measurement["poison_target_answer"] != target:
        raise ValueError("Gold/target pairing mismatch")
    for condition in ("clean", "poisoned"):
        obs = measurement[f"{condition}_condition"]
        validate_qa(obs["generation"], obs["answer"])
        if not math.isclose(float(obs["em"]), float(exact_match(obs["answer"], gold)), abs_tol=1e-12):
            raise ValueError("Gold-answer EM mismatch")
    success = bool(exact_match(measurement["poisoned_condition"]["answer"], target))
    if measurement["poisoned_condition"]["targeted_asr"] is not success:
        raise ValueError("Targeted ASR mismatch")
    return success


def cell_id(c):
    return f"{c['family']}.intensity-{c['intensity']}.seed-{c['seed']}"


def audit(protocol, selected, evaluation, original, public, candidates=None):
    for path, pin in ((protocol, PROTOCOL_PIN), (selected / "selection.seal.json", SELECTION_PIN),
                      (evaluation / "transfer.complete.json", COMPLETION_PIN), (original, AGGREGATE_PIN)):
        require_pin(path, pin)
    public_json = load_json(public)
    pins = public_json.get("provenance", {})
    for field, pin in (
        ("protocol_sha256", PROTOCOL_PIN), ("selection_seal_sha256", SELECTION_PIN),
        ("evaluation_completion_sha256", COMPLETION_PIN), ("original_aggregate_sha256", AGGREGATE_PIN)
    ):
        if pins.get(field) != pin:
            raise ValueError("Public provenance pin mismatch: " + field)
    proto, seal, complete = load_json(protocol), load_json(selected / "selection.seal.json"), load_json(evaluation / "transfer.complete.json")
    original_json = load_json(original)
    if seal.get("protocol_sha256") != PROTOCOL_PIN or complete.get("protocol_sha256") != PROTOCOL_PIN:
        raise ValueError("Stage protocol mismatch")
    if complete.get("selection_seal_sha256") != SELECTION_PIN:
        raise ValueError("Evaluation is bound to a different source selection")
    if original_json.get("protocol_sha256") != PROTOCOL_PIN or original_json.get("selection_seal_sha256") != SELECTION_PIN or original_json.get("completion_sha256") != COMPLETION_PIN:
        raise ValueError("Original aggregate provenance mismatch")
    if proto.get("scope") != "heldout":
        raise ValueError("Expected frozen held-out scope")
    selected_count = verify_inventory(selected, seal, exclude={"selection.seal.json"})
    evaluation_count = verify_inventory(evaluation, complete, exclude={"transfer.complete.json"})
    candidate_count = None
    if candidates is not None:
        manifest = load_json(candidates / "candidates.complete.json")
        if manifest.get("protocol_sha256") != PROTOCOL_PIN:
            raise ValueError("Candidate library protocol mismatch")
        candidate_count = verify_inventory(candidates, manifest, exclude={"candidates.complete.json"})
    expected = original_json.get("per_cell")
    if not isinstance(expected, list) or len(expected) != 240 or public_json.get("per_cell") != expected:
        raise ValueError("Original/public 240-cell results do not match")
    if original_json.get("atr_query_cluster_intervals") != public_json.get("atr_query_cluster_intervals"):
        raise ValueError("Original/public bootstrap intervals do not match")
    if len(public_json["atr_query_cluster_intervals"]) != 80:
        raise ValueError("Expected 80 source/target grouped intervals")
    if original_json.get("execution_accounting") != public_json.get("execution_accounting"):
        raise ValueError("Execution accounting mismatch")
    unique_cells, queries_by_condition, q_observations = set(), {}, 0
    for c in expected:
        key = (c["family"], c["intensity"], c["seed"], c["source"], c["target"])
        if key in unique_cells:
            raise ValueError("Duplicate condition: " + repr(key))
        unique_cells.add(key)
        if c["family"] not in FAMILIES or c["intensity"] not in (1, 3) or c["seed"] not in (42, 43, 44) or c["source"] not in SOURCES or c["target"] not in TARGETS or c["population"] != 300:
            raise ValueError("Unexpected condition outside frozen 240-cell matrix")
        cid, src, tgt = cell_id(c), c["source"], c["target"]
        ledger = load_json(selected / "selected" / cid / f"{src}.json")["records"]
        s_rows = load_json(evaluation / "rows" / cid / src / f"{src}.json")
        t_rows = load_json(evaluation / "rows" / cid / src / f"{tgt}.json")
        ids = [x.get("query_id") for x in ledger]
        if len(ids) != 300 or len(set(ids)) != 300 or ids != [x.get("query_id") for x in s_rows] or ids != [x.get("query_id") for x in t_rows]:
            raise ValueError("Source/target/selection query alignment mismatch")
        qkey = (c["family"], c["intensity"], c["seed"])
        if qkey in queries_by_condition and queries_by_condition[qkey] != ids:
            raise ValueError("Source queries differ within a seeded condition")
        queries_by_condition[qkey] = ids
        valid = ss = ts = transferred = 0
        for l, s, t in zip(ledger, s_rows, t_rows):
            status = l["status"]
            if s["construction_status"] != status or t["construction_status"] != status:
                raise ValueError("Construction status differs across source/target")
            if status != "valid_construction":
                if s["measurement"] is not None or t["measurement"] is not None:
                    raise ValueError("Construction failure has invented QA")
                continue
            valid += 1
            sm, tm = s["measurement"], t["measurement"]
            if not isinstance(sm, dict) or not isinstance(tm, dict):
                raise ValueError("Valid construction missing paired measurement")
            target, docs = l["target_answer"], l["documents"]
            gold = sm["gold_answer"]
            if not target or not docs or {d["doc_id"] for d in docs} != set(sm["poison_doc_ids"]) or set(sm["poison_doc_ids"]) != set(tm["poison_doc_ids"]):
                raise ValueError("Source-selected poison replay mismatch")
            x = check_qa(sm, gold, target)
            y = check_qa(tm, gold, target)
            ss += int(x)
            ts += int(y)
            transferred += int(x and y)
            q_observations += 1
        values = {"valid": valid, "source_successes": ss, "target_successes": ts, "transferred": transferred}
        if any(c[k] != v for k, v in values.items()):
            raise ValueError(f"Raw per-cell counts differ from aggregate at {key}: {values}")
        if c["target_end_to_end_asr"] != ts / 300 or c["target_conditional_asr"] != (ts / valid if valid else None) or c["atr"] != (transferred / ss if ss else None):
            raise ValueError("Raw per-cell rate mismatch")
    if len(unique_cells) != 240 or len(queries_by_condition) != 12:
        raise ValueError("Incomplete frozen transfer matrix")
    return {
        "status": "PASS_RAW_TRANSFER_AUDIT", "verified_condition_cells": 240,
        "unique_question_ids_per_cell": 300, "seeded_condition_cells": 12,
        "source_target_qa_pairs_checked": q_observations,
        "selected_inventory_files_checked": selected_count,
        "evaluation_inventory_files_checked": evaluation_count,
        "candidate_inventory_files_checked": candidate_count,
        "pins": {"protocol": PROTOCOL_PIN, "selection": SELECTION_PIN, "completion": COMPLETION_PIN, "original_aggregate": AGGREGATE_PIN},
        "notes": ["Read-only; no inference; aggregate arithmetic and stored QA verified.",
                  "Evidence origin/factuality and external model weights are not certified.",
                  "No query-level identifiers or prompts written to the report."],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--selected-dir", type=Path, required=True)
    ap.add_argument("--evaluation-dir", type=Path, required=True)
    ap.add_argument("--original-aggregate", type=Path, required=True)
    ap.add_argument("--public-aggregate", type=Path, default=Path("paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json"))
    ap.add_argument("--candidate-dir", type=Path)
    ap.add_argument("--report-out", type=Path, required=True)
    a = ap.parse_args()
    result = audit(a.protocol, a.selected_dir, a.evaluation_dir, a.original_aggregate, a.public_aggregate, a.candidate_dir)
    if a.report_out.exists():
        raise ValueError("Refusing to overwrite an existing audit report")
    if not a.report_out.parent.is_dir() or any(str(a.report_out.resolve()).startswith(str(x.resolve()) + os.sep) for x in (a.selected_dir, a.evaluation_dir)):
        raise ValueError("Report must be in a preexisting directory outside the experiment stages")
    a.report_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
