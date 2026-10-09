import hashlib
import json

import pytest

import run
from src.data import loaders


def _write_manifest(tmp_path, query_ids):
    fingerprint = hashlib.sha256(
        "\n".join(query_ids).encode("utf-8")
    ).hexdigest() if all(isinstance(q, str) for q in query_ids) else "invalid"

    manifest = {
        "heldout_query_ids": query_ids,
        "heldout_query_count": len(query_ids),
        "heldout_query_ids_fingerprint": fingerprint,
        "dataset_revision": "revision-test",
        "dataset_split": "validation",
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return str(path)


def _config(manifest_path):
    return {
        "dataset_loader": "load_hotpotqa_distractor",
        "dataset_query_ids_manifest": manifest_path,
        "dataset_revision": "revision-test",
        "dataset_split": "validation",
    }


def test_load_dataset_uses_shared_manifest_validation(tmp_path, monkeypatch):
    manifest_path = _write_manifest(tmp_path, ["q1", "q2"])
    config = _config(manifest_path)
    captured = {}

    def fake_loader(**kwargs):
        captured.update(kwargs)
        return {"corpus": [], "queries": []}

    monkeypatch.setattr(loaders, "load_hotpotqa_distractor", fake_loader)

    result = run.load_dataset(config)

    assert result == {"corpus": [], "queries": []}
    assert captured["query_ids"] == ["q1", "q2"]
    assert run._heldout_manifest_fingerprint(config) == hashlib.sha256(
        b"q1\nq2"
    ).hexdigest()


@pytest.mark.parametrize("query_ids", [[""], [None], [7]])
def test_invalid_query_ids_are_rejected_consistently(tmp_path, query_ids):
    manifest_path = _write_manifest(tmp_path, query_ids)
    config = _config(manifest_path)

    with pytest.raises(ValueError, match="invalid query IDs"):
        run._heldout_manifest_fingerprint(config)

    with pytest.raises(ValueError, match="invalid query IDs"):
        run.load_dataset(config)


def test_duplicate_query_ids_are_rejected(tmp_path):
    manifest_path = _write_manifest(tmp_path, ["q1", "q1"])
    config = _config(manifest_path)

    with pytest.raises(ValueError, match="duplicate query IDs"):
        run.load_dataset(config)


def test_manifest_fingerprint_mismatch_is_rejected(tmp_path):
    manifest_path = _write_manifest(tmp_path, ["q1"])
    manifest_path_obj = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path_obj.read_text(encoding="utf-8"))
    manifest["heldout_query_ids_fingerprint"] = "wrong"
    manifest_path_obj.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        run.load_dataset(_config(manifest_path))
