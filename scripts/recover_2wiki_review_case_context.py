#!/usr/bin/env python3
"""Recover 24 missing 2Wiki review-case question/gold contexts from sealed inputs.

Read-only: 131-case packet, original 2Wiki heldout input, original sealed
construction cells. Writes a NEW private JSONL containing *only the 24 cases
whose construction failed*, with their original question and gold context.
No generative inference, source citation invention or factual adjudication.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.audit_2wiki_source_factuality_ledger import (
    PACKET_SHA256, digest, fresh_private, verify_packet
)
from scripts.prepare_2wiki_rcd_ablation_plan import ORIGINAL_PINS

SCHEMA = "rag-poison-transfer.2wiki-selected-failure-original-context/v1"
VALID = "valid_construction"
TARGET_FAILED = "target_construction_failed"
SEMANTIC_FAILED = "semantic_construction_failed"
EXPECTED = {VALID: 107, TARGET_FAILED: 16, SEMANTIC_FAILED: 8}


def sealed_json(path: Path, sha256: str) -> dict:
    path = Path(path)
    if not path.is_file() or path.is_symlink() or digest(path) != sha256:
        raise ValueError("Missing or checksum-mismatched original sealed input")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Original sealed JSON must contain a top-level object")
    return value


def sealed_inputs(run: Path, *, local_data: Path | None = None):
    run = Path(run).expanduser().resolve(strict=True)
    protocol = sealed_json(run / "protocol.json", ORIGINAL_PINS["protocol.json"])
    seal = sealed_json(
        run / "execution/construction/construction.seal.json",
        ORIGINAL_PINS["execution/construction/construction.seal.json"]
    )
    evaluation = sealed_json(
        run / "execution/evaluation/evaluation.complete.json",
        ORIGINAL_PINS["execution/evaluation/evaluation.complete.json"]
    )
    if (protocol.get("binding", {}).get("scope") != "heldout"
        or seal.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"]
        or evaluation.get("protocol_sha256") != ORIGINAL_PINS["protocol.json"]
        or evaluation.get("construction_seal_sha256")
            != ORIGINAL_PINS["execution/construction/construction.seal.json"]):
        raise ValueError("Original protocol/construction/evaluation provenance differs")

    replication = protocol.get("replication", {})
    if not isinstance(replication.get("local_data_sha256"), str):
        raise ValueError("Original input-data SHA-256 is missing")
    source = Path(local_data or replication["local_data"]).expanduser()
    data = sealed_json(source, replication["local_data_sha256"])
    queries = data.get("queries")
    if (not isinstance(queries, list) or len(queries) != 300
        or len({q.get("query_id") for q in queries}) != 300
        or any(not isinstance(q.get("query_id"), str)
               or not isinstance(q.get("question"), str)
               or not isinstance(q.get("gold_answer"), str)
               for q in queries)):
        raise ValueError("Not the pinned original 300-question 2Wiki input")

    query_ids = [q["query_id"] for q in queries]
    if protocol.get("binding", {}).get("query_ids") != query_ids:
        raise ValueError("Question IDs/order disagree with frozen original 2Wiki cohort")

    # Reconfirm exact frozen corpus and query identity, not just a file name.
    from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint
    bound = seal.get("plan", {})
    if (bound.get("query_set_fingerprint") != query_set_fingerprint(queries)
        or bound.get("clean_corpus_fingerprint") != corpus_fingerprint(data["corpus"])):
        raise ValueError("Pinned construction corpus/query fingerprints differ")

    return run, {q["query_id"]: q for q in queries}, seal, evaluation, source


def source_cell(run: Path, seal: dict, evaluation: dict, cell_name: str):
    metadata = seal.get("cells", {}).get(cell_name)
    if not isinstance(metadata, dict):
        raise ValueError("Sample contains unknown original 2Wiki construction cell")
    expected_path = f"{cell_name}/construction.json"
    if (metadata.get("path") != expected_path
        or not isinstance(metadata.get("sha256"), str)
        or not isinstance(evaluation.get("rows_sha256", {}).get(cell_name), str)):
        raise ValueError("Original construction/evaluation cell seal incomplete")
    cell = sealed_json(run / "execution/construction" / expected_path,
                       metadata["sha256"])
    records = cell.get("records")
    if (not isinstance(records, list) or len(records) != 300
        or len({r.get("query_id") for r in records}) != 300):
        raise ValueError("Original 300-query cell construction is incomplete")
    return {r["query_id"]: r for r in records}, metadata["sha256"]


def recover(packet: list[dict], run: Path, *, local_data: Path | None = None):
    if len(packet) != 131:
        raise ValueError("Expected exactly 131 original selected source cases")
    counts = Counter(row["construction_status"] for row in packet)
    if dict(counts) != EXPECTED:
        raise ValueError("Original selected 107 valid / 16 target / 8 semantic status counts differ")

    run, queries, seal, evaluation, source = sealed_inputs(
        run, local_data=local_data
    )
    cache = {}
    recovered = []
    full_checked = 0
    for case in packet:
        qid = case["query_id"]
        if qid not in queries:
            raise ValueError("Review packet query missing from frozen 300-question input")
        name = f"{case['family']}.intensity-{case['intensity']}.seed-{case['seed']}"
        if (case.get("source_construction_path")
            != f"execution/construction/{name}/construction.json"):
            raise ValueError("Review case original construction path does not match cell identity")
        if name not in cache:
            cache[name] = source_cell(run, seal, evaluation, name)
        by_query, cell_pin = cache[name]
        original = by_query.get(qid)
        if original is None or original["status"] != case["construction_status"]:
            raise ValueError("Review packet selected case status differs from sealed construction")
        if (case.get("target_answer") is not None
            and case["target_answer"] != original.get("target_answer")):
            raise ValueError("Review packet target differs from sealed source")
        original_query = queries[qid]
        if (case["construction_status"] == VALID
            and case.get("gold_answer") != original_query["gold_answer"]):
            raise ValueError("Valid case gold answer differs from frozen original")
        full_checked += 1
        if case["construction_status"] == VALID:
            continue

        # Nomination can fail before any target exists; preserve None exactly.
        recovered.append({
            "schema": SCHEMA,
            "case_id": case["case_id"],
            "query_id": qid,
            "source_cell": name,
            "construction_status": case["construction_status"],
            "original_question": original_query["question"],
            "original_gold_answer": original_query["gold_answer"],
            "original_target_answer": original.get("target_answer"),
            "source_original_construction_sha256": cell_pin,
            "source_original_local_input_sha256":
                digest(source),
            "factuality_verdict": "unreviewed",
            "answer_type_verdict": "unreviewed",
            "context_recovered_from_original_sealed_input": True,
            "warning": (
                "No nominated target may exist for target failures. "
                "Recovered context is not independent truth, validation, "
                "or a semantic/source adjudication."
            )
        })
    if full_checked != 131 or len(recovered) != 24:
        raise ValueError("Selected case census or 24-failure recovery incomplete")
    if (sum(x["construction_status"] == TARGET_FAILED for x in recovered) != 16
        or sum(x["construction_status"] == SEMANTIC_FAILED for x in recovered) != 8):
        raise ValueError("Failure classes changed unexpectedly")
    return recovered, {"selected_packet_rows_verified": full_checked,
                       "failed_case_contexts_recovered": len(recovered),
                       "target_nomination_failures": 16,
                       "semantic_construction_failures": 8,
                       "distinct_failed_question_ids": len({x["query_id"] for x in recovered}),
                       "original_construction_cells_verified": len(cache),
                       "factuality_verdicts_performed": 0,
                       "full_packet_remaining_source_review_cases": 131,
                       "status": "SEALED_FAILURE_CONTEXT_RECOVERED_NO_SEMANTIC_FACT_CHECK"}


def run(*, packet_file: Path, frozen_run: Path, output: Path,
        local_data: Path | None = None):
    packet_file = packet_file.expanduser().resolve(strict=True)
    packet = verify_packet(packet_file, PACKET_SHA256)
    recovered, summary = recover(packet, frozen_run, local_data=local_data)
    dest = fresh_private(output)
    if dest == packet_file or dest == Path(frozen_run).expanduser().resolve(strict=True):
        raise ValueError("No source files may be overwritten")
    with dest.open("x", encoding="utf-8") as stream:
        for record in recovered:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {**summary,
            "original_review_packet_sha256": PACKET_SHA256,
            "private_recovered_context_sha256": digest(dest),
            "private_recovered_context_path": str(dest)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True,
                   help="Frozen authorized-matrix root with original protocol and execution/")
    p.add_argument("--local-data", type=Path,
                   help="Optional relocated original clean snapshot, original SHA must match")
    p.add_argument("--out", type=Path, required=True,
                   help="NEW private JSONL file outside Git checkout and frozen run")
    a = p.parse_args()
    print(json.dumps(run(packet_file=a.packet, frozen_run=a.run,
                         local_data=a.local_data, output=a.out), indent=2))


if __name__ == "__main__":
    main()
