"""Synthetic fixture tests only. No held-out questions or real case IDs."""
import csv
import json
from pathlib import Path

import pytest

from scripts.prepare_2wiki_independent_review import prepare, validate


def make_inputs(tmp_path):
    packet = tmp_path / "packet.jsonl"
    triage = tmp_path / "triage.json"
    cases = []
    source = []
    for i in range(131):
        cid = f"synthetic_case_{i:03d}"
        qid = f"synthetic_query_{i % 102:03d}"
        valid = i < 107
        status = "valid_construction" if valid else "target_construction_failed"
        source.append({
            "case_id": cid,
            "query_id": qid,
            "construction_status": status,
            "sampling_stratum": "both_target" if valid else "target_failure",
            "family": "semantic_fluent_false_evidence" if valid else "lexical_influential_token",
            "intensity": 1,
            "seed": 42,
            "source_construction_path": "private/synthetic-only",
            "target_answer": f"target_{i}" if valid else None,
            "accepted_poison_documents": [
                {"text": f"Synthetic candidate statement {i}; untrusted."}
            ] if valid else [],
        })
        cases.append({
            "case_id": cid,
            "question": f"Who is synthetic entity {i}?" if valid else None,
            "gold_answer": f"gold_{i}" if valid else None,
        })
    packet.write_text("".join(json.dumps(r) + "\n" for r in source), encoding="utf-8")
    triage.write_text(json.dumps({
        "cases": cases,
        "source_aggregate_sha256": "a" * 64,
    }), encoding="utf-8")
    return packet, triage


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_blinded_reviewer_packets_and_no_overwrite(tmp_path):
    packet, triage = make_inputs(tmp_path)
    output = tmp_path / "output"
    manifest = prepare(packet, triage, output)
    assert manifest["n_selected_cases"] == 131
    assert manifest["n_distinct_questions"] == 102
    assert manifest["n_reviewable"] == 107
    assert manifest["n_requires_original_context"] == 24
    reviewer_a = read_rows(output / "reviewer_A.csv")
    reviewer_b = read_rows(output / "reviewer_B.csv")
    assert len(reviewer_a) == len(reviewer_b) == 107
    assert len(read_rows(output / "coordinator_mapping_PRIVATE.csv")) == 107
    assert len(read_rows(output / "pending_original_context_PRIVATE.csv")) == 24
    assert reviewer_a[0]["review_item"] != reviewer_b[0]["review_item"]
    assert [r["question"] for r in reviewer_a] != [r["question"] for r in reviewer_b]
    for r in reviewer_a + reviewer_b:
        assert "source_construction_path" not in r
        assert "query_id" not in r
        assert "dense_target_success" not in r
        assert "preliminary_flags" not in r
        assert not r["target_factuality"]
        assert r["candidate_evidence_UNTRUSTED"].startswith("[CANDIDATE EVIDENCE")
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        prepare(packet, triage, output)


def test_blank_reviewer_verdicts_fail_closed(tmp_path):
    packet, triage = make_inputs(tmp_path)
    output = tmp_path / "output"
    prepare(packet, triage, output)
    with pytest.raises(ValueError, match="incomplete/invalid reviewer fields"):
        validate(output / "reviewer_A.csv")


def test_case_set_mismatch_is_rejected(tmp_path):
    packet, triage = make_inputs(tmp_path)
    data = json.loads(triage.read_text())
    data["cases"].pop()
    triage.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Case IDs do not match"):
        prepare(packet, triage, tmp_path / "output")
