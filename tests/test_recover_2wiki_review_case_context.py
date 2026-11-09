"""Synthetic only: no private case text or source adjudication in fixtures."""
from collections import Counter
from pathlib import Path

import pytest

from scripts import recover_2wiki_review_case_context as recovery


def synthetic_cases():
    cases = []
    for n in range(131):
        status = (
            recovery.VALID if n < 107
            else recovery.TARGET_FAILED if n < 123 else recovery.SEMANTIC_FAILED
        )
        family = ("semantic_fluent_false_evidence"
                  if status == recovery.SEMANTIC_FAILED
                  else "lexical_influential_token")
        cid = f"{family}.intensity-1.seed-42"
        cases.append({
            "case_id": f"case{n}",
            "query_id": f"qid{n}",
            "family": family,
            "intensity": 1,
            "seed": 42,
            "construction_status": status,
            "source_construction_path":
                f"execution/construction/{cid}/construction.json",
            "target_answer": None if status == recovery.TARGET_FAILED
            else f"target{n}",
            "gold_answer": f"gold{n}" if status == recovery.VALID else "",
        })
    return cases


def patch_sealed_context(monkeypatch, tmp_path, cases):
    queries = {
        c["query_id"]: {
            "query_id": c["query_id"],
            "question": "Synthetic question; no real benchmark content",
            "gold_answer": f"gold{n}",
        } for n, c in enumerate(cases)
    }
    cells = {}
    for item in cases:
        key = f"{item['family']}.intensity-{item['intensity']}.seed-{item['seed']}"
        cells.setdefault(key, {})[item["query_id"]] = {
            "status": item["construction_status"],
            "target_answer": item["target_answer"],
        }
    monkeypatch.setattr(recovery, "sealed_inputs", lambda run, local_data=None: (
        Path(run), queries, {"cells": dict.fromkeys(cells)}, {}, "abc" * 21 + "a"
    ))
    monkeypatch.setattr(recovery, "source_cell",
                        lambda run, seal, evaluation, cid: (cells[cid], "sha-" + cid))


def test_recovers_exactly_24_failures_without_claiming_facts(monkeypatch, tmp_path):
    cases = synthetic_cases()
    patch_sealed_context(monkeypatch, tmp_path, cases)
    rows, report = recovery.recover(cases, tmp_path)
    assert len(rows) == 24
    assert report["selected_packet_rows_verified"] == 131
    assert report["target_nomination_failures"] == 16
    assert report["semantic_construction_failures"] == 8
    assert report["factuality_verdicts_performed"] == 0
    assert report["original_construction_cells_verified"] == 2
    assert Counter(x["construction_status"] for x in rows) == {
        recovery.TARGET_FAILED: 16, recovery.SEMANTIC_FAILED: 8
    }
    assert all(x["original_question"] and x["original_gold_answer"] for x in rows)
    assert all(x["context_recovered_from_original_sealed_input"] for x in rows)
    assert all(x["factuality_verdict"] == "unreviewed" for x in rows)
    assert all(x["original_target_answer"] is None
               for x in rows if x["construction_status"] == recovery.TARGET_FAILED)
    assert all(x["original_target_answer"] is not None
               for x in rows if x["construction_status"] == recovery.SEMANTIC_FAILED)


def test_mutated_packet_status_cannot_silently_claim_recovery(monkeypatch, tmp_path):
    cases = synthetic_cases()
    patch_sealed_context(monkeypatch, tmp_path, cases)
    cases[10]["construction_status"] = recovery.TARGET_FAILED
    with pytest.raises(ValueError, match="107 valid"):
        recovery.recover(cases, tmp_path)


def test_sealed_source_status_mismatch_aborts(monkeypatch, tmp_path):
    cases = synthetic_cases()
    patch_sealed_context(monkeypatch, tmp_path, cases)
    cases[0]["target_answer"] = "Different target than sealed original"
    with pytest.raises(ValueError, match="target differs"):
        recovery.recover(cases, tmp_path)


def test_sealed_gold_disagreement_aborts(monkeypatch, tmp_path):
    cases = synthetic_cases()
    patch_sealed_context(monkeypatch, tmp_path, cases)
    cases[0]["gold_answer"] = "Wrong alias invented"
    with pytest.raises(ValueError, match="gold answer differs"):
        recovery.recover(cases, tmp_path)


def test_no_private_output_in_frozen_run_even_if_new(monkeypatch, tmp_path):
    cases = synthetic_cases()
    patch_sealed_context(monkeypatch, tmp_path, cases)
    original = tmp_path / "frozen"
    original.mkdir()
    packet = tmp_path / "review.jsonl"
    packet.write_text("Mock packet to be verified in fixture only")
    monkeypatch.setattr(recovery, "verify_packet", lambda *args, **kwargs: cases)
    output = original / "bad.jsonl"
    with pytest.raises(ValueError, match="outside the frozen"):
        recovery.run(packet_file=packet, frozen_run=original, output=output)
    assert not output.exists()


def test_new_private_output_contains_only_missing_contexts(monkeypatch, tmp_path):
    cases = synthetic_cases()
    patch_sealed_context(monkeypatch, tmp_path, cases)
    original = tmp_path / "frozen"
    original.mkdir()
    packet = tmp_path / "review.jsonl"
    packet.write_text("Mock verified original packet for synthetic unit test")
    monkeypatch.setattr(recovery, "verify_packet", lambda *args, **kwargs: cases)
    private = tmp_path / "private"
    private.mkdir()
    output = private / "new_recovery.jsonl"
    receipt = recovery.run(packet_file=packet, frozen_run=original, output=output)
    assert receipt["failed_case_contexts_recovered"] == 24
    assert receipt["factuality_verdicts_performed"] == 0
    assert len(output.read_text().splitlines()) == 24
    assert "Synthetic question" not in str(receipt)
    with pytest.raises(ValueError, match="fresh"):
        recovery.run(packet_file=packet, frozen_run=original, output=output)
