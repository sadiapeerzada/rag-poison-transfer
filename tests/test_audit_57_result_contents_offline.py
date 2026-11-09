"""Structure-only release review tests; never process real private source files."""
import json
from pathlib import Path
import subprocess

import pytest

from scripts import audit_57_result_contents_offline as review


def test_jsonl_counts_raw_text_keys_without_copying_source():
    payload = (
        '{"question":"Private hypothetical question","gold_answer":"Private answer",'
        '"meta":{"generated_text":"Private generated text"}}\n'
        '{"metrics":{"accuracy":0.75},"prompt":"Private prompt"}\n'
    ).encode()
    audit = review.inspect_content(payload, ".jsonl")
    assert audit["record_count"] == 2
    assert audit["raw_text_field_names_present"] == [
        "generated_text", "gold_answer", "prompt", "question"
    ]
    assert audit["raw_text_field_key_occurrences"] == 4
    assert "Private" not in json.dumps(audit)
    assert audit["publication_rights_cleared"] is False


def test_nested_json_aggregate_and_raw_content_classification():
    summary = review.inspect_content(b'{"summary":{"accuracy":0.5}}', ".json")
    assert summary["preliminary_content_class"] == "NO_NAMED_RAW_FIELDS_REVIEW_STILL_REQUIRED"
    assert summary["publication_rights_cleared"] is False
    raw = review.inspect_content(
        b'{"items":[{"documents":[{"text":"Never emit this content"}]}]}', ".json"
    )
    assert raw["preliminary_content_class"] == "RAW_OR_MIXED_TEXT_REVIEW_REQUIRED"
    assert raw["raw_text_field_names_present"] == ["text"]


def test_csv_headings_are_sensitive_even_without_rows():
    value = review.inspect_content(b"question,em,generated_text\n", ".csv")
    assert value["record_count"] == 0
    assert value["raw_text_field_names_present"] == ["generated_text", "question"]


def test_email_and_credentials_report_patterns_not_values():
    payload = b'{"question":"Fake invented test account person@example.org", "prompt":"ghp_' + b"A" * 32 + b'"}'
    out = review.inspect_content(payload, ".json")
    assert out["possible_email_pattern_present"] is True
    assert out["high_confidence_credential_pattern_classes"] == ["github_classic_token"]
    assert "person@example.org" not in json.dumps(out)
    assert "ghp_" not in json.dumps(out)


def test_unparseable_records_fail_without_leaking_original_text():
    bad = b'{"question":"very sensitive intentionally malformed"'
    with pytest.raises(ValueError, match="failed structured UTF-8 parsing") as err:
        review.inspect_content(bad, ".jsonl")
    assert "very sensitive" not in str(err.value)


def test_file_inventory_pin_checks_all_57_and_rejects_changed_blob(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", str(repo)])
    files = []
    for n in range(57):
        path = repo / "results" / f"sample_{n:02}.jsonl"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({
            "metrics": {"recall": n / 57}, "question": "hypothetical synthetic content"
        }) + "\n")
        blob = subprocess.check_output(
            ["git", "-C", str(repo), "hash-object", "--", str(path.relative_to(repo))]
        ).decode().strip()
        files.append({"path": str(path.relative_to(repo)),
                      "git_blob_sha1": blob, "size_bytes": path.stat().st_size})
    inventory = repo / review.INVENTORY
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({"counts": {"total": 57},
                                     "per_file_review": files}))
    subprocess.check_call(["git", "-C", str(repo), "add", "."])
    subprocess.check_call(["git", "-C", str(repo), "-c", "user.name=Test",
                           "-c", "user.email=test@example.org", "commit", "-qm", "test"])
    data = review.audit(repo)
    assert data["n_files_checked"] == 57
    assert data["content_classes_count"]["RAW_OR_MIXED_TEXT_REVIEW_REQUIRED"] == 57
    assert data["raw_results_redistribution_cleared"] is False
    assert data["credential_pattern_file_count"] == 0
    p = repo / "results" / "sample_01.jsonl"
    p.write_text('{"question":"modified!"}\n')
    with pytest.raises(ValueError, match="pinned release inventory"):
        review.audit(repo)


def test_private_receipt_cannot_be_written_to_git_or_overwrite(tmp_path):
    repo = tmp_path / "repo"
    root = tmp_path / "private"
    (repo / "results").mkdir(parents=True)
    root.mkdir()
    out = root / "receipt.json"
    assert review.fresh_private_path(repo, root, out) == out
    out.write_text("{}")
    with pytest.raises(ValueError, match="NEW private report"):
        review.fresh_private_path(repo, root, out)
    with pytest.raises(ValueError, match="NEW private report"):
        review.fresh_private_path(repo, root, repo / "results" / "do-not-create.json")
