import json

import pytest

from scripts.extract_verified_development_queries import (
    PINNED_REVISION, extract_verified, ids_fingerprint,
)
from src.experiments.protocol import query_set_fingerprint


def inputs(tmp_path):
    rows = [{"query_id": "a", "question": "Who won?", "gold_answer": "Alice",
             "gold_doc_ids": ["d"], "dataset_revision": PINNED_REVISION,
             "dataset_split": "validation"}]
    manifest = {"dataset_revision": PINNED_REVISION, "dataset_split": "validation",
                "development_query_count": 1, "heldout_query_count": 1,
                "heldout_query_ids": ["b"], "heldout_query_ids_fingerprint": ids_fingerprint(["b"]),
                "development_query_ids_fingerprint": ids_fingerprint(["a"]),
                "development_query_set_fingerprint": query_set_fingerprint(rows)}
    return rows, manifest


def run(tmp_path, rows, manifest):
    artifact, frozen = tmp_path / "dev.jsonl", tmp_path / "manifest.json"
    artifact.write_text("\n".join(json.dumps(r) for r in rows))
    frozen.write_text(json.dumps(manifest))
    return extract_verified(artifact, frozen)


def test_valid_extraction(tmp_path):
    queries, provenance = run(tmp_path, *inputs(tmp_path))
    assert queries == [{"query_id": "a", "question": "Who won?", "gold_answer": "Alice"}]
    assert provenance["heldout_overlap_count"] == 0


@pytest.mark.parametrize("defect,match", [
    ("duplicate", "Duplicate development"), ("overlap", "overlap"),
    ("revision", "revision"), ("split", "split"), ("missing", "Missing/invalid"),
    ("fingerprint", "Historical fingerprint"), ("heldout_duplicate", "Duplicate held-out"),
    ("count", "count mismatch"), ("question", "Historical fingerprint"),
])
def test_reject_bad_provenance(tmp_path, defect, match):
    rows, m = inputs(tmp_path)
    if defect == "duplicate":
        rows.append(dict(rows[0])); m["development_query_count"] = 2
    elif defect == "overlap":
        m["heldout_query_ids"] = ["a"]; m["heldout_query_ids_fingerprint"] = ids_fingerprint(["a"])
    elif defect == "revision": rows[0]["dataset_revision"] = "wrong"
    elif defect == "split": rows[0]["dataset_split"] = "train"
    elif defect == "missing": del rows[0]["query_id"]
    elif defect == "fingerprint": m["development_query_ids_fingerprint"] = "wrong"
    elif defect == "question": rows[0]["question"] = "Stale question"
    elif defect == "heldout_duplicate": m["heldout_query_ids"] = ["b", "b"]
    elif defect == "count": m["development_query_count"] = 2
    with pytest.raises(ValueError, match=match): run(tmp_path, rows, m)


def test_malformed_jsonl(tmp_path):
    rows, m = inputs(tmp_path)
    run(tmp_path, rows, m)
    (tmp_path / "dev.jsonl").write_text('{"broken":')
    with pytest.raises(ValueError, match="Malformed JSONL at line 1"):
        extract_verified(tmp_path / "dev.jsonl", tmp_path / "manifest.json")
