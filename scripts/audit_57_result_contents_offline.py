#!/usr/bin/env python3
"""Read-only, field-level release-rights triage for 57 tracked research files.

This provides a *content-structure* inventory, NOT a legal, privacy or
independent dataset/model-custody certification. Never echoes benchmark text,
questions, prompts, responses, emails, credentials or dataset passages.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = Path.home() / "Documents" / "rag-research-results"
INVENTORY = "paper/release/nov09_tracked_result_rights_inventory.json"
SCHEMA = "rag-poison-transfer.tracked-raw-result-rights-content-audit/v1"
MAX_FILE_BYTES = 8 * 1024 * 1024
RAW_FIELD_NAMES = {
    "question", "questions", "query_text", "gold_answer", "answer",
    "target_answer", "poison_target_answer", "generated_text",
    "generated_answer", "raw_response", "model_response", "generation",
    "prompt", "raw_prompt", "source_evidence_json", "context", "passage",
    "passages", "text", "retrieved_text", "retrieved_passages",
    "input_text", "output_text", "source_text", "evidence_text",
    "original_text", "candidate_text", "doc_text", "document_text",
    "accepted_poison_documents", "poison_documents",
}
EMAIL_PATTERN = re.compile(rb"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
CREDENTIAL_PATTERNS = {
    "private_key_block": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_classic_token": re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    "github_fine_grained_token": re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    "openai_looking_key": re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"),
    "google_api_key": re.compile(rb"AIza[A-Za-z0-9_-]{30,}"),
}
DATASET_SOURCES = {
    "hotpotqa": {
        "upstream_license_declaration": "CC BY-SA 4.0",
        "upstream_source": "https://hotpotqa.github.io/",
        "note": "Source dataset license does not automatically clear model output or modified passages.",
    },
    "2wikimultihopqa": {
        "upstream_license_declaration": "Apache-2.0 on the upstream repository",
        "upstream_source": "https://github.com/Alab-NII/2wikimultihop",
        "note": "Source repository license is not an audit of each republished derived text.",
    },
    "natural_questions": {
        "upstream_license_declaration": "Creative Commons Share-Alike 3.0 (official NQ download page)",
        "upstream_source": "https://ai.google.com/research/NaturalQuestions/download",
        "note": "Check text/Wikipedia and derivative reuse; do not assume dataset attribution clears all contents.",
    },
}
ALLOWED_EXTENSIONS = {".json", ".jsonl", ".csv"}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL
    ).decode("utf-8").strip()


def walk_fields(obj, keys: Counter[str], *, depth=0):
    """Count only field names; ignore every raw value and dynamic object key.

    Stop at a conservative depth to avoid arbitrary recursive payloads.
    """
    if depth > 18:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                name = key.casefold()
                if name in RAW_FIELD_NAMES:
                    keys[name] += 1
            if isinstance(value, (dict, list)):
                walk_fields(value, keys, depth=depth + 1)
    elif isinstance(obj, list):
        for value in obj:
            if isinstance(value, (dict, list)):
                walk_fields(value, keys, depth=depth + 1)


def inspect_content(content: bytes, suffix: str) -> dict:
    """Parse complete tracked file and emit *only* aggregate indicators."""
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported tracked result format")
    emails_present = bool(EMAIL_PATTERN.search(content))
    credentials_present = sorted(
        key for key, regex in CREDENTIAL_PATTERNS.items() if regex.search(content)
    )
    counters: Counter[str] = Counter()
    number_records = 0
    try:
        text = content.decode("utf-8")
        if suffix == ".jsonl":
            for line in text.splitlines():
                if not line.strip():
                    continue
                number_records += 1
                walk_fields(json.loads(line), counters)
        elif suffix == ".json":
            obj = json.loads(text)
            number_records = len(obj) if isinstance(obj, list) else 1
            walk_fields(obj, counters)
        else:
            stream = __import__("io").StringIO(text, newline="")
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise ValueError("CSV missing headers")
            for name in reader.fieldnames:
                if name and name.casefold() in RAW_FIELD_NAMES:
                    counters[name.casefold()] += 1
            for _ in reader:
                number_records += 1
    except (UnicodeError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        # Never print raw offending row contents from parser exceptions.
        raise ValueError("Tracked file failed structured UTF-8 parsing") from None
    return {
        "parse_status": "PARSED",
        "record_count": number_records,
        "raw_text_field_names_present": sorted(counters),
        "raw_text_field_key_occurrences": sum(counters.values()),
        "possible_email_pattern_present": emails_present,
        "high_confidence_credential_pattern_classes": credentials_present,
        "preliminary_content_class": (
            "RAW_OR_MIXED_TEXT_REVIEW_REQUIRED" if counters
            else "NO_NAMED_RAW_FIELDS_REVIEW_STILL_REQUIRED"
        ),
        "publication_rights_cleared": False,
        "human_privacy_review_completed": False,
    }


def dataset_hint(name: str) -> str:
    low = name.casefold()
    if "hotpot" in low:
        return "hotpotqa"
    if "2wiki" in low:
        return "2wikimultihopqa"
    if "nq_" in low or "natural_question" in low:
        return "natural_questions"
    return "UNDETERMINED_FROM_FILENAME"


def _load_inventory(repo: Path) -> list[dict]:
    inventory = json.loads((repo / INVENTORY).read_text(encoding="utf-8"))
    items = inventory.get("per_file_review")
    if inventory.get("counts", {}).get("total") != 57 or not isinstance(items, list) or len(items) != 57:
        raise ValueError("Pinned 57-file review inventory is absent or altered")
    seen = set()
    for item in items:
        path = item.get("path")
        if (not isinstance(path, str) or path in seen or
            not path.startswith("results/") or Path(path).suffix not in ALLOWED_EXTENSIONS or
            Path(path).is_absolute() or ".." in Path(path).parts):
            raise ValueError("Invalid or duplicate tracked result path in inventory")
        seen.add(path)
    return items


def audit(repo: Path) -> dict:
    repo = repo.expanduser().resolve(strict=True)
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("Not at Git repository root")
    items = _load_inventory(repo)
    result = []
    for item in items:
        name = item["path"]
        path = repo / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing or symlinked pinned research file")
        if git(repo, "hash-object", "--", name) != item.get("git_blob_sha1"):
            raise ValueError("Tracked research blob differs from pinned release inventory")
        size = path.stat().st_size
        if size != item.get("size_bytes"):
            raise ValueError("Tracked source-file size differs from pinned release inventory")
        if size > MAX_FILE_BYTES:
            raise ValueError("Tracked research file exceeds bounded audit size")
        info = inspect_content(path.read_bytes(), path.suffix.lower())
        result.append({
            "path": name,
            "size_bytes": size,
            "git_blob_sha1": item["git_blob_sha1"],
            "dataset_hint_from_filename_only": dataset_hint(name),
            **info,
        })
    by_dataset = Counter(x["dataset_hint_from_filename_only"] for x in result)
    by_content = Counter(x["preliminary_content_class"] for x in result)
    possible_email = [x["path"] for x in result if x["possible_email_pattern_present"]]
    credentials = [x["path"] for x in result
                   if x["high_confidence_credential_pattern_classes"]]
    return {
        "schema": SCHEMA,
        "status": "CONTENT_TRIAGE_COMPLETE_RELEASE_RIGHTS_AND_CUSTODY_OPEN",
        "source_inventory": INVENTORY,
        "source_git_commit": git(repo, "rev-parse", "HEAD"),
        "n_files_checked": len(result),
        "total_bytes_checked": sum(x["size_bytes"] for x in result),
        "content_classes_count": dict(sorted(by_content.items())),
        "dataset_filename_hints_count": dict(sorted(by_dataset.items())),
        "possible_email_pattern_file_count": len(possible_email),
        "possible_email_pattern_paths": possible_email,
        "credential_pattern_file_count": len(credentials),
        "credential_pattern_paths": credentials,
        "upstream_license_reference_only": DATASET_SOURCES,
        "raw_results_redistribution_cleared": False,
        "external_backup_origin_attested": False,
        "model_weights_dataset_caches_recoverable_off_device": "NOT_CHECKED",
        "scope_note": (
            "Field names, pattern presence and Git blob SHA-1 are not legal rights, "
            "PII clearance, complete source lineage or independent backup provenance. "
            "An absent known raw field cannot prove no raw text resides under arbitrary keys."
        ),
        "per_file_review": result,
    }


def fresh_private_path(repo: Path, root: Path, output: Path):
    repo = repo.resolve(strict=True)
    root = root.expanduser().resolve(strict=True)
    out = output.expanduser().resolve(strict=False)
    if (out == root or root not in out.parents or repo == out or repo in out.parents
        or out.exists() or not out.parent.is_dir()):
        raise ValueError("Choose a NEW private report file under an existing private research directory")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.repo)
    out = fresh_private_path(args.repo, args.private_root, args.out)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({
        "status": report["status"],
        "files": report["n_files_checked"],
        "bytes": report["total_bytes_checked"],
        "content_classes_count": report["content_classes_count"],
        "dataset_filename_hints_count": report["dataset_filename_hints_count"],
        "possible_email_pattern_file_count": report["possible_email_pattern_file_count"],
        "credential_pattern_file_count": report["credential_pattern_file_count"],
        "rights_cleared": report["raw_results_redistribution_cleared"],
        "report_path_private": str(out),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
