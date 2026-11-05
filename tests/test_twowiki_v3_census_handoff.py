"""Regression tests for separately versioned 2Wiki metadata-only handoff."""
import hashlib
import json

import pytest

from scripts.prepare_twowiki_v3_census_handoff import (
    _publish_new, digest, main, prepare,
)
from scripts.audit_twowiki_v3_train_pool import CONFIG, DATASET, REVISION


def data(n=30):
    return {"dataset": DATASET, "config": CONFIG, "revision": REVISION,
            "split": "train", "query_ids": [f"{i:032x}" for i in range(n)]}


def registry(n=3):
    return {"excluded_query_ids": [f"{i:032x}" for i in range(n)],
            "historical_gaps": ["older-run IDs unknown", "complete custody missing"],
            "certification": None}


def review(train_sha="a"*64, registry_sha="b"*64, *, n=30, excluded=3):
    return {"dataset_revision": REVISION, "train_export_sha256": train_sha,
            "registry_sha256": registry_sha,
            "total_training_ids": n, "known_exclusions": excluded,
            "training_overlap": excluded,
            "potentially_eligible_ids": n-excluded,
            "prospective_v3_go": False, "cohort_selected": False,
            "model_calls_authorized": False, "unresolved_evidence": [{"id": "HIST-25-IDS"}]}


def test_metadata_capacity_go_does_not_authorize_experiment():
    payload, h = prepare(data(), registry(), train_sha="a"*64,
                         registry_sha="b"*64,
                         review=review(), review_sha="c"*64)
    assert h["decision"]["train_id_capacity"] == "GO"
    assert h["decision"]["prospective_v3_construction"] == "NO_GO"
    assert h["decision"]["full_2wiki_heldout_replication"] == "NO_GO"
    assert h["decision"]["nonprospective_construction_diagnostic"] == "SEPARATE_PROTOCOL_AND_APPROVAL_REQUIRED"
    assert h["potentially_id_eligible_count"] == 27
    assert h["all_train_ids_sha256"] == digest(payload)
    assert len(json.loads(payload)) == 30
    assert "query_ids" not in h


def test_small_pool_no_go():
    _, h = prepare(data(3), registry(3), train_sha="a"*64, registry_sha="b"*64)
    assert h["decision"]["train_id_capacity"] == "NO_GO"


@pytest.mark.parametrize("wrong", [
    {"total_training_ids": 31}, {"potentially_eligible_ids": 30},
    {"prospective_v3_go": True}, {"model_calls_authorized": True},
    {"train_export_sha256": "wrong"}, {"registry_sha256": "wrong"},
])
def test_mismatched_review_is_rejected(wrong):
    r = review()
    r.update(wrong)
    with pytest.raises(ValueError, match="disagree"):
        prepare(data(), registry(), train_sha="a"*64,
                registry_sha="b"*64, review=r)


def test_noncanonical_ids_refused():
    d = data()
    d["query_ids"][1] = "synthetic-id"
    with pytest.raises(ValueError, match="canonical"):
        prepare(d, registry(), train_sha="a"*64, registry_sha="b"*64)


def test_write_once(tmp_path):
    output = tmp_path/"result.json"
    _publish_new(output, b"original")
    with pytest.raises(FileExistsError):
        _publish_new(output, b"replacement")
    assert output.read_bytes() == b"original"


def test_cli_writes_unique_handoff_without_cohort(tmp_path, capsys):
    d = data()
    r = registry()
    v = review()
    def pinned(name, obj):
        p = tmp_path/name
        raw = json.dumps(obj).encode()
        p.write_bytes(raw)
        return p, hashlib.sha256(raw).hexdigest()
    train, th = pinned("train.json", d)
    registry_file, rh = pinned("registry.json", r)
    v["train_export_sha256"] = th
    v["registry_sha256"] = rh
    report, vh = pinned("review.json", v)
    out = tmp_path/"new-handoff"
    command = ["--train-ids", str(train), "--train-sha256", th,
               "--registry", str(registry_file), "--registry-sha256", rh,
               "--review-report", str(report), "--review-sha256", vh,
               "--output-directory", str(out)]
    assert main(command) == 0
    packet = json.loads((out/"READINESS_HANDOFF.json").read_text())
    assert packet["decision"]["train_id_capacity"] == "GO"
    assert packet["model_inference_authorized"] is False
    assert packet["historical_exposure_certified"] is False
    assert len(json.loads((out/"all_train_pool.ids.json").read_text())) == 30
    with pytest.raises(FileExistsError):
        main(command)
