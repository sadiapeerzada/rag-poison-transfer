"""No web, dataset downloads, generator calls, or real reviewer data."""
import copy
import csv
import io
import json
from pathlib import Path

import pytest

from src.attacks.compatible_targets import TargetAssignmentError, load_reviewed_assignments, select_reviewed_target
from src.attacks.development_review_package import (
    PLAN_SCHEMA, build_package, render_csv, screen_nomination, sha, stable_json, write_package,
)
from src.experiments.protocol import fingerprint_records


def fixture():
    queries, specs, support = [], [], {}
    for i in range(24):
        q = {"query_id": f"q{i}", "question": f"Who won acting award {i}?", "gold_answer": f"Actor Gold {i}"}
        s = {"query_id": f"s{i}", "question": f"Who won award {i}?", "gold_answer": f"Actor Alternative {i}"}
        queries += [q, s]
        support[q["query_id"]] = [{"title": "Synthetic supporting article", "sent_id": 0}]
        specs.append({"nomination_id": str(i), "query_id": q["query_id"], "candidate_source_query_id": s["query_id"],
                      "answer_category": "person", "expected_semantic_compatibility": "Both are actor-shaped test answers.",
                      "factual_claim_to_verify": "A synthetic award credit requires checking.",
                      "manual_review_flags": ["Test fixture, not real evidence."], "evidence": []})
    provenance = {"schema": "verified-development-extraction/v1", "artifact_sha256": "a" * 64,
                  "manifest_sha256": "b" * 64, "query_count": len(queries), "dataset_revision": "test-revision",
                  "dataset_split": "validation", "heldout_overlap_count": 0,
                  "development_query_set_fingerprint": "c" * 64, "development_query_ids_fingerprint": "d" * 64,
                  "extracted_records_fingerprint_v1": fingerprint_records(queries)}
    plan = {"schema": PLAN_SCHEMA, "development_artifact_sha256": provenance["artifact_sha256"],
            "selection_method": "Explicit synthetic test nominations", "nominations": specs}
    return queries, provenance, plan, support


def test_reproducible_pending_outputs_and_csv(tmp_path):
    q, p, plan, support = fixture()
    package, summary = build_package(q, p, plan, support)
    assert (package, summary) == build_package(list(reversed(q)), p, copy.deepcopy(plan), support)
    assert summary["selected_questions"] == 24
    assert summary["package_sha256"] == sha(stable_json(package))
    for row in package["records"]:
        assert row["approved"] is False
        assert row["reviewer"] == row["reviewed_at"] == row["target_answer"] == ""
        assert row["human_review_decision"] == "pending"
        assert row["evidence_status"] == "unverified"
        assert row["factually_false"] is None
    rows = list(csv.DictReader(io.StringIO(render_csv(package))))
    assert len(rows) == 24
    assert rows[0]["question"] == q[0]["question"]
    write_package(package, summary, tmp_path)
    assert json.loads((tmp_path / "review_package.json").read_text()) == package


@pytest.mark.parametrize("defect", ["query", "artifact", "overlap", "schema"])
def test_provenance_fail_closed(defect):
    q, p, plan, support = fixture()
    if defect == "query": q[0]["question"] = "Changed"
    if defect == "artifact": plan["development_artifact_sha256"] = "wrong"
    if defect == "overlap": p["heldout_overlap_count"] = 1
    if defect == "schema": p["schema"] = "unverified"
    with pytest.raises(ValueError, match="provenance|artifact"):
        build_package(q, p, plan, support)


def test_inconsistent_support_provenance():
    q, p, plan, support = fixture()
    support["q0"] = []
    with pytest.raises(ValueError, match="supporting-fact provenance"):
        build_package(q, p, plan, support)


@pytest.mark.parametrize("defect,reason", [
    ("gold", "gold_equivalent_target"), ("alias", "gold_equivalent_target"),
    ("missing", "missing_candidate_source"), ("type", "candidate_category_mismatch"),
    ("chronology", "unsupported_or_ambiguous_question"), ("duplicate", "duplicate_query_nomination"),
    ("duplicate_alias", "duplicate_or_normalized_alias_target"),
])
def test_screening_rejections(defect, reason):
    q, _, plan, _ = fixture()
    by = {r["query_id"]: r for r in q}
    spec = plan["nominations"][0]
    seen_q, seen_t = set(), set()
    if defect == "gold": spec["candidate_source_query_id"] = "q0"
    if defect == "alias": by["s0"]["gold_answer"] = "THE ACTOR GOLD 0!"
    if defect == "missing": spec["candidate_source_query_id"] = "absent"
    if defect == "type": by["s0"] = {"query_id": "s0", "question": "In what year?", "gold_answer": "1987"}
    if defect == "chronology": by["q0"]["question"] = "Who was born first, Alice or Bob?"
    if defect == "duplicate": seen_q.add("q0")
    if defect == "duplicate_alias": seen_t.add("actor alternative 0")
    assert reason in screen_nomination(spec, by, seen_q, seen_t)


def test_no_evidence_or_input_approval_can_approve_package(tmp_path):
    q, p, plan, support = fixture()
    plan["nominations"][0].update(approved=True, reviewer="must not propagate", reviewed_at="must not propagate")
    package, _ = build_package(q, p, plan, support)
    path = tmp_path / "pending.json"
    path.write_text(stable_json(package))
    with pytest.raises(TargetAssignmentError): load_reviewed_assignments(path)
    row = package["records"][0]
    with pytest.raises(TargetAssignmentError, match="Unapproved"):
        select_reviewed_target(q[0], {"q0": row})
    path.write_text(json.dumps({"protocol_version": "answer-compatible-targets/v3-reviewed", "assignments": package["records"]}))
    with pytest.raises(TargetAssignmentError, match="Unapproved"):
        load_reviewed_assignments(path)


def test_malformed_evidence_rejected():
    q, p, plan, support = fixture()
    plan["nominations"][0]["evidence"] = [{"url": "fabricated"}]
    with pytest.raises(ValueError, match="evidence"):
        build_package(q, p, plan, support)


def test_subset_size_and_nomination_identity_guards():
    q, p, plan, support = fixture()
    plan["nominations"] = plan["nominations"][:19]
    with pytest.raises(ValueError, match="20–30"):
        build_package(q, p, plan, support)
    plan["nominations"].append(copy.deepcopy(plan["nominations"][0]))
    with pytest.raises(ValueError, match="nomination IDs"):
        build_package(q, p, plan, support)


def test_committed_package_reproduces_from_verified_original():
    from scripts.extract_verified_development_queries import extract_verified
    root = Path(__file__).resolve().parents[1]
    artifact = root / "results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl"
    queries, provenance = extract_verified(artifact, root / "configs/exp_027_hotpotqa_heldout_manifest.json")
    raw = [json.loads(line) for line in artifact.read_text().splitlines()]
    support = {r["query_id"]: r["gold_supporting_facts"] for r in raw}
    plan = json.loads((root / "configs/phase4a_development_review_plan.json").read_text())
    package, summary = build_package(queries, provenance, plan, support)
    directory = root / "docs/reviews/phase4a"
    assert (directory / "review_package.json").read_text() == stable_json(package)
    assert (directory / "validation_summary.json").read_text() == stable_json(summary)
    assert (directory / "review_sheet.csv").read_text() == render_csv(package)
    assert summary["selected_questions"] == 24
    assert summary["rejected_nominations"] == 8
