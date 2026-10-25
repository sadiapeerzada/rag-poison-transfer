"""Preparation tests use IDs/development data and synthetic category examples only.

No held-out dataset/text, human approval records, keys or signatures are created.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import src.attacks.review_handoff as handoff
from scripts.extract_verified_development_queries import extract_verified
from src.attacks.compatible_targets import load_reviewed_assignments
from src.attacks.development_review_package import stable_json

MANIFEST = Path("configs/exp_027_hotpotqa_heldout_manifest.json")
DEVELOPMENT = Path("results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl")
DIRECTORY = Path("docs/reviews/phase4c")
SCRIPT = "scripts/prepare_phase4c_review_handoff.py"


def build():
    return handoff.build_handoff(manifest_path=MANIFEST, development_artifact=DEVELOPMENT,
                                 method_paths=list(handoff.METHOD_PATHS))


def write(directory, files):
    for name, value in files.items():
        (directory / name).write_text(stable_json(value), encoding="utf-8")
    (directory / "review_sheet_blank.csv").write_text(handoff.render_sheet(files["review_handoff.json"]))
    (directory / "candidate_review_log_blank.csv").write_text(handoff.render_log_header())


def test_build_is_metadata_only_and_preserves_every_frozen_id(monkeypatch):
    import run
    monkeypatch.setattr(run, "load_dataset", lambda *a, **k: pytest.fail("Held-out loader forbidden"))
    files = build()
    slots = files["review_handoff.json"]["review_slots"]
    manifest = json.loads(MANIFEST.read_bytes())
    assert [s["query_id"] for s in slots] == manifest["heldout_query_ids"]
    assert len(slots) == 300
    for slot in slots:
        assert slot["review_decision"] == "pending"
        assert all(slot[k] == "" for k in (*handoff.TEXT_FIELDS, *handoff.AUTH_FIELDS))
    prereg = files["preregistration_draft.json"]
    assert prereg["status"] == "draft_not_frozen"
    assert prereg["dataset"]["query_set_fingerprint"] is None
    assert prereg["fingerprint_bootstrap_resolution"] is None
    assert "reviewers" not in prereg and "registered_at" not in prereg


def test_heldout_counts_remain_unknown_and_development_is_labelled_separately():
    report = build()["coverage_metadata_only.json"]
    assert report["unassessed"] == 300
    assert report["mechanically_supported"] is None
    assert report["unsupported_or_uncertain"] is None
    assert report["category_counts"] == {}
    assert report["heldout_question_text_accessed"] is False
    assert report["heldout_gold_answers_accessed"] is False
    development = report["development_only_method_check"]
    assert development["mechanically_supported"] == 114
    assert development["unsupported_or_uncertain"] == 186
    assert sum(development["category_counts"].values()) == 300
    assert sum(development["reason_counts"].values()) == 186
    assert report["independently_approved"] == 0


def test_pool_uses_only_genuine_verified_development_answer_sources():
    queries, provenance = extract_verified(DEVELOPMENT, MANIFEST)
    pool = handoff.candidate_pool(queries, provenance)
    by_id = {q["query_id"]: q for q in queries}
    for candidate in pool["candidates"]:
        for source_id in candidate["source_development_query_ids"]:
            assert candidate["answer"] == by_id[source_id]["gold_answer"]
            assert candidate["answer_category"] == handoff.expected_category(
                by_id[source_id]["question"], by_id[source_id]["gold_answer"])
    assert pool == handoff.candidate_pool(list(reversed(queries)), provenance)


def test_byte_pins_match_files_and_source_bindings():
    files = build()
    prereg = files["preregistration_draft.json"]
    assert prereg["development_pool_fingerprint"] == handoff.sha(stable_json(files["candidate_pool.json"]).encode())
    assert files["review_handoff.json"]["preregistration_draft_sha256"] == handoff.sha(stable_json(prereg).encode())
    for name, digest in prereg["method_source_sha256"].items():
        assert handoff.sha(Path(name).read_bytes()) == digest


def test_fixed_first_five_order_and_normalized_alias_dedup():
    query = {"query_id": "synthetic", "question": "Who wrote it?", "gold_answer": "Alpha"}
    names = ["The Alpha", "Ｔarget", "Target", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf"]
    pool = {"candidates": [{"answer_category": "person", "answer": name} for name in names]}
    first = handoff.ordered_candidates(query, pool)
    assert len(first) == 5
    assert [r["answer"] for r in first] == ["Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
    pool["candidates"].reverse()
    assert handoff.ordered_candidates(query, pool) == first
    pool["candidates"] = [{"answer_category": "person", "answer": name} for name in names[:3]]
    assert len(handoff.ordered_candidates(query, pool)) == 1


@pytest.mark.parametrize("question,gold,category,reason", [
    ("Which person was older?", "Alpha", "person", "unsupported_category_or_question_pattern"),
    ("How far away?", "10 miles", "distance", "unsupported_category_or_question_pattern"),
    ("When was it built?", "March 2000", "date", "unsupported_gold_answer_shape"),
    ("Who wrote it?", "Alpha", "person", "no_non_gold_candidate_in_frozen_pool"),
])
def test_mechanical_abstention_is_not_approval(question, gold, category, reason):
    report = handoff.screen_queries([{"query_id": "synthetic", "question": question, "gold_answer": gold}],
                                    {"candidates": [{"answer_category": category, "answer": gold}]})
    assert report["mechanically_supported"] == 0
    assert report["unsupported_or_uncertain"] == 1
    assert report["reason_counts"] == {reason: 1}
    assert report["semantic_and_factual_review_pending"] == 1


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered", "text", "reviewer", "decision", "coverage", "pool", "source"])
def test_reconstructing_validator_rejects_any_edited_draft(tmp_path, mutation):
    files = copy.deepcopy(build())
    slots = files["review_handoff.json"]["review_slots"]
    if mutation == "missing":
        slots.pop()
    elif mutation == "duplicate":
        slots[1]["query_id"] = slots[0]["query_id"]
    elif mutation == "reordered":
        slots.reverse()
    elif mutation == "text":
        slots[0]["question"] = "Synthetic edit, not held-out text"
    elif mutation == "reviewer":
        slots[0]["reviewer"] = None  # Invalid value, no invented identity.
    elif mutation == "decision":
        slots[0]["review_decision"] = None
    elif mutation == "coverage":
        files["coverage_metadata_only.json"]["mechanically_supported"] = 300
    elif mutation == "pool":
        files["candidate_pool.json"]["candidates"].pop()
    else:
        files["preregistration_draft.json"]["method_source_sha256"]["run.py"] = "0" * 64
    write(tmp_path, files)
    with pytest.raises(ValueError, match="Draft handoff mismatch"):
        handoff.validate_handoff(tmp_path, manifest_path=MANIFEST, development_artifact=DEVELOPMENT,
                                 method_paths=list(handoff.METHOD_PATHS))


@pytest.mark.parametrize("name", ["review_sheet_blank.csv", "candidate_review_log_blank.csv"])
def test_sheet_and_log_cannot_silently_change(tmp_path, name):
    write(tmp_path, build())
    with (tmp_path / name).open("a") as output:
        output.write("unexpected\n")
    with pytest.raises(ValueError, match="mismatch"):
        handoff.validate_handoff(tmp_path, manifest_path=MANIFEST, development_artifact=DEVELOPMENT,
                                 method_paths=list(handoff.METHOD_PATHS))


@pytest.mark.parametrize("authorized,pin_ok", [(False, True), (True, False), (True, True)])
def test_coverage_cannot_open_any_text_before_genuine_freeze(tmp_path, monkeypatch, authorized, pin_ok):
    draft = tmp_path / "draft.json"
    draft.write_text(stable_json(build()["preregistration_draft.json"]))
    forbidden = tmp_path / "forbidden-query-file.json"
    original = Path.read_bytes
    def guarded_read(path):
        if path == forbidden:
            pytest.fail("Held-out text must not be opened before preregistration freeze")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    digest = hashlib.sha256(draft.read_bytes()).hexdigest() if pin_ok else "0" * 64
    with pytest.raises(ValueError, match="authorization|fingerprint mismatch|Genuinely frozen"):
        handoff.coverage_after_freeze(preregistration_path=draft, preregistration_sha256=digest,
            queries_path=forbidden, pool_path=tmp_path / "pool.json", manifest_path=MANIFEST,
            authorized=authorized)
    assert not forbidden.exists()


def test_handoff_cannot_be_loaded_as_approved_assignment(tmp_path):
    path = tmp_path / "handoff.json"
    path.write_text(stable_json(build()["review_handoff.json"]))
    with pytest.raises(ValueError, match="Unsupported target assignment protocol"):
        load_reviewed_assignments(path)


def test_metadata_cli_forbids_text_arguments_and_never_creates_them(tmp_path):
    forbidden = tmp_path / "no-text.json"
    result = subprocess.run([sys.executable, SCRIPT, "build", "--queries", str(forbidden)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert "forbidden in metadata-only" in result.stderr
    assert not forbidden.exists()


def test_committed_package_is_exactly_reproducible():
    report = handoff.validate_handoff(DIRECTORY, manifest_path=MANIFEST, development_artifact=DEVELOPMENT,
                                     method_paths=list(handoff.METHOD_PATHS))
    assert report == {"valid": True, "status": "draft_only_not_approved", "heldout_ids": 300,
                      "heldout_unassessed": 300, "independently_approved": 0}


def test_exact_byte_validation_rejects_line_ending_changes(tmp_path):
    files = build()
    write(tmp_path, files)
    path = tmp_path / "candidate_pool.json"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="Draft handoff mismatch"):
        handoff.validate_handoff(tmp_path, manifest_path=MANIFEST, development_artifact=DEVELOPMENT,
                                 method_paths=list(handoff.METHOD_PATHS))


def test_builder_refuses_to_overwrite_even_blank_review_materials(tmp_path):
    for _ in range(2):
        result = subprocess.run([sys.executable, SCRIPT, "build", "--directory", str(tmp_path)],
                                capture_output=True, text=True)
        if _ == 0:
            assert result.returncode == 0, result.stderr
            original = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
        else:
            assert result.returncode == 2
            assert "Refusing to overwrite" in result.stderr
            assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == original


@pytest.mark.parametrize("mutation", [None, "order", "content", "count", "revision", "source-pin", "pool-scope"])
def test_postfreeze_validation_below_mocked_registration_boundary(tmp_path, monkeypatch, mutation):
    # No registration/approval file is created. Mock the external registration
    # boundary, then test only synthetic q0..q299 data, never HotpotQA text.
    queries = [{"query_id": f"synthetic-{i}", "question": f"Is synthetic item {i} marked?",
                "gold_answer": "yes", "gold_doc_ids": ["synthetic-doc"]} for i in range(300)]
    ids = [q["query_id"] for q in queries]
    config = {"dataset_revision": "synthetic-revision", "dataset_split": "synthetic-split"}
    hashes = {"heldout": "a" * 64, "dense": "b" * 64, "rcd": "c" * 64}
    pool = {"schema": handoff.POOL_SCHEMA, "scope": "development", "candidates": [
        {"answer_category": "yes_no", "answer": "yes"}, {"answer_category": "yes_no", "answer": "no"}]}
    methods = {str(p): handoff.sha(p.read_bytes()) for p in handoff.METHOD_PATHS}
    registration_double = {"schema": handoff.PREREG_SCHEMA, "scope": "heldout", "status": "frozen_preregistered",
        "fingerprint_bootstrap_resolution": "preexisting_auditable_fingerprint",
        "bootstrap_resolution_reference": "Mocked test boundary; not an actual registration",
        "human_decisions_required": [], "supported_categories": sorted(handoff.SUPPORTED_CATEGORIES),
        "max_candidates_per_query": 5, "max_review_rounds": 2,
        "candidate_order": "casefold_then_exact_then_normalized_alias_dedup",
        "failure_policy": "stop_if_any_of_300_lacks_genuine_independent_approval",
        "method_source_sha256": methods, "nomination_protocol_sha256": methods[str(handoff.METHOD_PATHS[0])],
        "development_pool_fingerprint": handoff.sha(stable_json(pool).encode()), "query_count": 300,
        "frozen_config_sha256": hashes, "dataset": {
            "name": "hotpotqa/hotpot_qa", "config": "distractor", "revision": "synthetic-revision",
            "split": "synthetic-split", "heldout_manifest_sha256": hashes["heldout"],
            "heldout_manifest_fingerprint": "d" * 64,
            "query_set_fingerprint": handoff.query_set_fingerprint(queries)}}
    export = {"dataset_revision": "synthetic-revision", "dataset_split": "synthetic-split", "queries": queries}
    if mutation == "order":
        queries.reverse()
    elif mutation == "content":
        queries[0]["question"] = "Changed synthetic text?"
    elif mutation == "count":
        queries.pop()
    elif mutation == "revision":
        export["dataset_revision"] = "changed"
    elif mutation == "source-pin":
        methods["run.py"] = "0" * 64
    elif mutation == "pool-scope":
        pool["scope"] = "synthetic-wrong-scope"
    path = tmp_path / "synthetic-queries.json"
    path.write_text(json.dumps(export))
    monkeypatch.setattr(handoff, "read_pinned", lambda p, digest: registration_double if p.name == "registration-boundary" else pool)
    monkeypatch.setattr(handoff, "validate_frozen_inputs", lambda **k: ({}, config, ids, "d" * 64, hashes))
    if mutation in {"source-pin", "pool-scope"}:
        original = Path.read_bytes
        def guard(p):
            if p == path:
                pytest.fail("Invalid source/pool must fail before query input is opened")
            return original(p)
        monkeypatch.setattr(Path, "read_bytes", guard)
    options = dict(preregistration_path=Path("registration-boundary"), preregistration_sha256="0" * 64,
                   queries_path=path, pool_path=Path("pool-boundary"), manifest_path=Path("manifest-boundary"),
                   authorized=True)
    if mutation:
        with pytest.raises(ValueError):
            handoff.coverage_after_freeze(**options)
    else:
        report = handoff.coverage_after_freeze(**options)
        assert report["mechanically_supported"] == 300
        assert report["unsupported_or_uncertain"] == 0
        assert report["semantic_and_factual_review_pending"] == 300
        assert report["independently_approved"] == 0
        assert "queries" not in report
