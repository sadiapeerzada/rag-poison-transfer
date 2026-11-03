"""No-model tests of v6 CLI, manifest loading and summary boundaries."""
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts import run_twowiki_v6_grounded_diversity as driver
from test_semantic_fluent_development_v6 import synthetic_case
from src.attacks.semantic_fluent_development_v6 import triage


def test_direct_cli_help_from_outside_worktree(tmp_path):
    script = Path(driver.__file__).resolve()
    r = subprocess.run([sys.executable, "-B", str(script), "--help"], cwd=tmp_path,
                       text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    assert "--v5-summary" in r.stdout and "--preflight" in r.stdout


def test_v6_summary_not_poison_approval():
    case = synthetic_case("C11")
    passage = ('The 1999 film "The Idiot Returns" was directed by Saša Gedeon. '
               'Saša Gedeon, director of "The Idiot Returns", was born in Avignon.')
    results = [{"candidate_id": "C11", "query_id": case["query_id"],
                "slot": 0, "attempt": 1, "raw_response": passage,
                "triage": triage(case, 0, passage)}]
    s = driver.summarize(results)
    assert s["recorded_model_calls"] == 1
    assert s["surface_review_candidates"] == 1
    assert s["three_context_candidate_cases"] == 0
    assert s["construction_approvals"] == s["poison_injections"] == 0
    assert s["paired_poisoned_evaluation_authorized"] is False


def test_v5_comparison_mismatch_is_rejected(tmp_path, monkeypatch):
    # Strict provenance behavior is checked on synthetic substitute, not
    # actual development question text (none is distributed in the repo).
    case_ids = sorted(driver.ANCHORS)
    cases = [synthetic_case(cid) for cid in case_ids]
    for c in cases:
        c["candidate_documents"] = [{"poison_index": i, "text": "control"}
                                    for i in range(3)]
        c["factual_approval"] = False
        c["injection_approved"] = False
    packet_obj = {
        "scope": "train_development_only",
        "dataset_sha256": driver.DATASET_SHA,
        "not_llm_generated": True,
        "factual_approval": False,
        "injection_approved": False,
        "heldout_access": False,
        "queries": cases,
    }
    zpath = tmp_path / "packet.zip"
    with ZipFile(zpath, "w") as zipped:
        zipped.writestr("independent_review_input.json", json.dumps(packet_obj))
    monkeypatch.setattr(driver, "PACKET_SHA", driver.digest(zpath.read_bytes()))
    summary = {
        "schema": driver.V5_SCHEMA, "scope": "train_development_only",
        "model_calls_recorded": 30, "intensity_3_distinct_candidate_cases": 0,
        "poison_injections": 0, "injection_approvals": 0,
        "heldout_queries_accessed": 0,
    }
    manifest = {
        "schema": driver.V5_SCHEMA, "scope": "train_development_only",
        "dataset_sha256": driver.DATASET_SHA,
        "packet_sha256": driver.PACKET_SHA,
        "model_revision": driver.MODEL_REVISION,
        "max_tokens": 150, "attempts_per_slot": 2,
        "same_seed_policy_as_v4": True, "heldout_access": False,
    }
    sp = tmp_path / "summary.json"
    mp = tmp_path / "manifest.json"
    sp.write_text(json.dumps(summary))
    mp.write_text(json.dumps(manifest))
    loaded, _, _ = driver.load_inputs(zpath, sp, mp)
    assert len(loaded) == 5
    summary["intensity_3_distinct_candidate_cases"] = 5
    sp.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="V5 comparator"):
        driver.load_inputs(zpath, sp, mp)
    summary["intensity_3_distinct_candidate_cases"] = 0
    sp.write_text(json.dumps(summary))
    packet_obj["heldout_access"] = True
    # Changing packet bytes without changing its pin MUST fail closed.
    with ZipFile(zpath, "w") as zipped:
        zipped.writestr("independent_review_input.json", json.dumps(packet_obj))
    with pytest.raises(ValueError, match="packet hash"):
        driver.load_inputs(zpath, sp, mp)


def test_model_calls_not_in_preflight():
    # Runner imports MLX only after preflight validation and output creation.
    import inspect
    src = inspect.getsource(driver.main)
    assert src.index("if args.preflight:") < src.index("from src.pipelines.generator import MLXGenerator")
    assert src.index("write_new(output / \"manifest.json\"") < src.index("from src.pipelines.generator import MLXGenerator")
