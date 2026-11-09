"""Offline regression checks for read-only research release-evidence scanner."""
from __future__ import annotations

import hashlib
import json
import subprocess

from scripts import audit_nov09_release_evidence_offline as gate


def test_credential_patterns_do_not_return_secret_text():
    secret = b"ghp_" + b"A" * 35
    found = gate.detect_credentials(secret)
    assert found == ["github_classic_token"]
    assert secret.decode() not in str(found)
    assert gate.detect_credentials(b"OPENAI_API_KEY is merely documented.") == []


def test_sha256_file(tmp_path):
    p = tmp_path / "immutable.json"
    p.write_bytes(b'{"ok": true}')
    assert gate.sha256(p) == hashlib.sha256(b'{"ok": true}').hexdigest()


def test_tracked_scan_detects_result_artifacts_without_content(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "example.jsonl").write_text('{"question": "private"}\n')
    (tmp_path / "safe.py").write_text("value = 4\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "results/example.jsonl", "safe.py"],
        check=True
    )
    receipt = gate.tracked_inventory(tmp_path)
    assert receipt["tracked_results_files_requiring_dataset_privacy_and_license_review"] == 1
    assert receipt["high_confidence_credential_pattern_file_counts"] == {}
    assert "private" not in json.dumps(receipt)


def test_private_hashes_are_checked_without_data_exposure(monkeypatch, tmp_path):
    name = "sealed-plan.json"
    original = b"original private question material"
    (tmp_path / name).write_bytes(original)
    monkeypatch.setattr(gate, "NQ_PINS", {name: hashlib.sha256(original).hexdigest()})
    monkeypatch.setattr(gate, "ARCHIVE_NAME", "missing.tar.gz")
    receipt = gate.private_artifacts(tmp_path, tmp_path)
    assert receipt["nq_original_plan_and_aggregate_sha256"][name] == "MATCH"
    assert receipt["twowiki_archived_run_sha256"] == "NOT_LOCATED"
    assert "original private question material" not in json.dumps(receipt)


def test_public_manifest_detects_changes(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "data").mkdir()
    entries = []
    for i in range(8):
        name = f"data/result_{i}.json"
        (tmp_path / name).write_text(json.dumps({"sample": i}))
        digest = gate.command(tmp_path, "hash-object", "--", name).decode().strip()
        entries.append({"path": name, "git_blob_sha1": digest})
    monkeypatch.setattr(gate, "INVENTORY", "inventory.json")
    (tmp_path / "inventory.json").write_text(json.dumps({
        "evidence_files": entries,
        "checks": [{"status": "PASS"}] * 9,
    }))
    assert gate.public_evidence(tmp_path)["state"] == "MATCHED"
    (tmp_path / "data/result_2.json").write_text("changed")
    changed = gate.public_evidence(tmp_path)
    assert changed["state"] == "CHANGED_OR_MISSING"
    assert changed["changed_or_missing_relative_paths"] == ["data/result_2.json"]
