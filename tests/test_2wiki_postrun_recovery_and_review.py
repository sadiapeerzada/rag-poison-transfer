"""Offline tests for new 2Wiki recovery and paired audit helpers (no real data)."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import backup_2wiki_full_run as backup
from scripts import audit_2wiki_paired_cases as audit


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_full_run_archive_restore_and_tampered_pin(tmp_path, monkeypatch):
    run = tmp_path / "frozen"
    run.mkdir()
    content = {
        "protocol.json": b'{"protocol":"pinned"}',
        "execution/construction/construction.seal.json": b'{"seal":"frozen"}',
        "execution/construction/one/construction.json": b"original construction",
        "execution/evaluation/evaluation.complete.json": b'{"complete":true}',
        "execution/evaluation/one/rows.json": b"original evaluation",
        "execution/aggregate.json": b'{"aggregate":"frozen"}',
        "local/inputs.json": b"original input",
    }
    for rel, data in content.items():
        f = run / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    monkeypatch.setattr(backup, "PINS", {
        rel: digest(run / rel)
        for rel in (
            "protocol.json",
            "execution/construction/construction.seal.json",
            "execution/evaluation/evaluation.complete.json",
            "execution/aggregate.json",
        )
    })
    archive = tmp_path / "remote-staging" / "full.tar.gz"
    backup.create(run, archive)
    manifest = Path(str(archive) + ".manifest.json")
    assert archive.is_file() and manifest.is_file()
    restored = tmp_path / "independently-restored"
    backup.verify(archive, manifest, digest(archive), restored)
    for rel, data in content.items():
        assert (restored / rel).read_bytes() == data
    with pytest.raises(FileExistsError):
        backup.create(run, archive)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        backup.verify(archive, manifest, "0" * 64, tmp_path / "another-restore")
    assert not (tmp_path / "another-restore").exists()


def test_full_run_archive_rejects_source_symlink(tmp_path, monkeypatch):
    run = tmp_path / "frozen"
    run.mkdir()
    (run / "protocol.json").write_text("{}")
    monkeypatch.setattr(backup, "PINS", {"protocol.json": digest(run / "protocol.json")})
    (run / "symlink").symlink_to(run / "protocol.json")
    with pytest.raises(ValueError, match="regular files"):
        backup.create(run, tmp_path / "backup.tar.gz")


def test_audit_exports_all_paired_cases_without_running_models(tmp_path, monkeypatch):
    run = tmp_path / "frozen"
    aggregate = {"cells": {}}
    families = ("lexical_influential_token", "semantic_fluent_false_evidence")
    for family in families:
        for intensity in (1, 3):
            for seed in (42, 43, 44):
                cell = f"{family}.intensity-{intensity}.seed-{seed}"
                records = []
                rows = []
                for i in range(300):
                    qid = f"q{i:03d}"
                    # Every cell retains all 300 IDs; 240 valid and 60 explicit failed.
                    valid = i < 240
                    status = ("valid_construction" if valid else
                              "semantic_construction_failed" if family.startswith("semantic")
                              else "target_construction_failed")
                    records.append({
                        "query_id": qid, "status": status,
                        "target_answer": "false target" if valid else None,
                        "selection": {"reason": "fixture"},
                        "documents": [{"text": "fixture poison", "doc_id": qid}] if valid else [],
                        "partial_documents": [],
                        "attempt_records": [],
                    })
                    for arm in ("dense", "rcd"):
                        success = valid and ((i + (arm == "rcd")) % 5 == 0)
                        measurement = None
                        if valid:
                            measurement = {
                                "gold_answer": "true target",
                                "clean_condition": {
                                    "answer": "true target",
                                    "answer_correct": bool(i % 2 == (arm == "dense")),
                                    "generation": {"prompt": "Question? Evidence."},
                                },
                                "poisoned_condition": {
                                    "answer": "false target" if success else "other",
                                    "targeted_asr": bool(success),
                                    "poison_retrieved": bool(i % 3 != 0),
                                    "generation_evidence_doc_ids": [qid],
                                },
                            }
                        rows.append({"query_id": qid, "pipeline": arm,
                                     "construction_status": status, "measurement": measurement})
                c_path = run / "execution/construction" / cell / "construction.json"
                e_path = run / "execution/evaluation" / cell / "rows.json"
                c_path.parent.mkdir(parents=True, exist_ok=True)
                e_path.parent.mkdir(parents=True, exist_ok=True)
                c_path.write_text(json.dumps({"records": records}))
                e_path.write_text(json.dumps(rows))
                aggregate["cells"][cell] = {
                    arm: {
                        "valid": 240,
                        "end_to_end_targeted_asr": {
                            "numerator": sum(
                                bool(r["measurement"]["poisoned_condition"]["targeted_asr"])
                                for r in rows if r["pipeline"] == arm and r["measurement"] is not None
                            )
                        },
                    } for arm in ("dense", "rcd")
                }
    aggregate_path = run / "execution/aggregate.json"
    aggregate_path.write_text(json.dumps(aggregate))
    monkeypatch.setattr(audit, "AGGREGATE_SHA", digest(aggregate_path))
    out = tmp_path / "audit-export"
    audit.run_audit(run, out, 2)
    summary = json.loads((out / "audit_summary.json").read_text())
    assert summary["population_query_seed_records"] == 3600
    assert summary["selected_review_cases"] > 0
    assert (out / "paired_census.csv").exists()
    assert (out / "review_packet.jsonl").exists()
    assert (out / "human_review_template.csv").exists()
    with pytest.raises(FileExistsError):
        audit.run_audit(run, out, 2)
