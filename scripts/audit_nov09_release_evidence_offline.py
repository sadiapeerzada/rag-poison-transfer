#!/usr/bin/env python3
"""Read-only local release-evidence check; never calls a model or alters study inputs.

The output is a private, aggregate-only verification receipt. Passing this
mechanical audit does NOT certify factual truth, exposure independence,
dataset/model licensing, remote backup provenance or a final research GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path.home() / "Documents" / "rag-research-results"
INVENTORY = "paper/results/reproducibility_gate_2026-11-09/public_evidence_inventory.json"

NQ_PINS = {
    "nq-stage3-lexical-I1-qa-plan-v1_PRIVATE.json":
        "66104bd1b922bd79a465593cb134b12820b71271fba08567c4bc529dd912f6c6",
    "nq-stage3-lexical-I1-qa-aggregate-v1_PRIVATE.json":
        "0126f5998d07b5f0430d93f1fcf610dc7118b819b385065bcca60e02188b9ac9",
    "nq-stage3-lexical-I3-qa-plan-v1_PRIVATE.json":
        "53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2e7b5",
    "nq-stage3-lexical-I3-qa-aggregate-v1_PRIVATE.json":
        "146cb2749ab01bb5e5d70c06c2041f34dcf36db0fafa2443c3deb021f50e8dc5",
}
ARCHIVE_NAME = "2wiki-full-run-20261109.tar.gz"
ARCHIVE_SHA256 = "faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82"

# High-confidence credential-like sequences, never echoed or saved to report.
CREDENTIALS = [
    ("private_key_block", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_classic_token", re.compile(rb"ghp_[A-Za-z0-9]{30,}")),
    ("github_fine_grained_token", re.compile(rb"github_pat_[A-Za-z0-9_]{20,}")),
    ("openai_looking_key", re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}")),
    ("google_api_key", re.compile(rb"AIza[A-Za-z0-9_-]{30,}")),
    ("assigned_sensitive_env_variable", re.compile(
        rb"(?im)^\s*(?:AWS_SECRET_ACCESS_KEY|HF_TOKEN|OPENAI_API_KEY|GITHUB_TOKEN)\s*[:=]\s*['\"]?[A-Za-z0-9_+./=-]{16,}"
    )),
]
TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".csv", ".tsv", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".sh", ".env",
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def command(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)


def detect_credentials(content: bytes) -> list[str]:
    return [name for name, pattern in CREDENTIALS if pattern.search(content)]


def tracked_inventory(repo: Path) -> dict:
    names = [x.decode("utf-8", "replace") for x in command(repo, "ls-files", "-z").split(b"\0") if x]
    risky_files = []
    credential_file_counts = {}
    scanned = 0
    oversized = 0
    for name in names:
        path = repo / name
        if not path.is_file() or path.is_symlink():
            continue
        if name.startswith("results/") and path.suffix.lower() in {".json", ".jsonl", ".csv", ".txt"}:
            risky_files.append(name)
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {".gitignore", ".env"}:
            continue
        # Never ingest or print an unbounded result corpus.
        if path.stat().st_size > 8 * 1024 * 1024:
            oversized += 1
            continue
        scanned += 1
        matches = detect_credentials(path.read_bytes())
        for match in matches:
            credential_file_counts[match] = credential_file_counts.get(match, 0) + 1
    return {
        "tracked_files": len(names),
        "scanned_text_files": scanned,
        "skipped_oversized_text_files": oversized,
        "high_confidence_credential_pattern_file_counts": credential_file_counts,
        "tracked_results_files_requiring_dataset_privacy_and_license_review": len(risky_files),
        "tracked_result_file_examples": risky_files[:12],
        "scope_note": "Heuristic lexical screening only; no repository-wide licensing, personal-data or secret certification.",
    }


def public_evidence(repo: Path) -> dict:
    path = repo / INVENTORY
    if not path.is_file():
        return {"state": "MISSING_RELEASE_INVENTORY", "matched_blobs": 0}
    obj = json.loads(path.read_text(encoding="utf-8"))
    files = obj.get("evidence_files", [])
    if len(files) != 8 or len(obj.get("checks", [])) != 9:
        return {"state": "INVALID_RELEASE_INVENTORY_SCHEMA", "matched_blobs": 0}
    matched, mismatched = 0, []
    for item in files:
        rel = item["path"]
        # Public GitHub blob SHA-1; not equivalent to frozen private SHA-256.
        local = repo / rel
        if not local.is_file() or local.is_symlink():
            mismatched.append(rel)
            continue
        actual = command(repo, "hash-object", "--", rel).decode().strip()
        if actual == item["git_blob_sha1"]:
            matched += 1
        else:
            mismatched.append(rel)
    return {
        "state": "MATCHED" if not mismatched and matched == 8 else "CHANGED_OR_MISSING",
        "matched_blobs": matched,
        "expected_blobs": 8,
        "changed_or_missing_relative_paths": mismatched[:15],
    }


def private_artifacts(root: Path, downloads: Path) -> dict:
    observed = {}
    for name, expected in NQ_PINS.items():
        path = root / name
        if not path.is_file() or path.is_symlink():
            observed[name] = "NOT_LOCATED"
        else:
            observed[name] = "MATCH" if sha256(path) == expected else "HASH_MISMATCH"
    archive = downloads / ARCHIVE_NAME
    if archive.is_file() and not archive.is_symlink():
        backup = "MATCH" if sha256(archive) == ARCHIVE_SHA256 else "HASH_MISMATCH"
    else:
        backup = "NOT_LOCATED"
    return {
        "nq_original_plan_and_aggregate_sha256": observed,
        "twowiki_archived_run_sha256": backup,
        "archive_external_custody_independently_certified": False,
        "snapshot_and_dataset_cache_independently_restorable": "NOT_CHECKED",
        "source_factuality_adjudicated": False,
        "historical_cohort_unexposed_certified": False,
    }


def audit(repo: Path, root: Path, downloads: Path) -> dict:
    repo = repo.expanduser().resolve(strict=True)
    root = root.expanduser().resolve(strict=True)
    git_root = Path(command(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if repo != git_root:
        raise ValueError("Repository path is not the actual Git worktree root")
    tracked = tracked_inventory(repo)
    published = public_evidence(repo)
    private = private_artifacts(root, downloads.expanduser())
    checks = list(private["nq_original_plan_and_aggregate_sha256"].values())
    risks = bool(tracked["high_confidence_credential_pattern_file_counts"])
    full_local = published["state"] == "MATCHED" and all(x == "MATCH" for x in checks) and private["twowiki_archived_run_sha256"] == "MATCH"
    return {
        "schema": "rag-poison-transfer.local-release-evidence-audit/v1",
        "status": (
            "PUBLIC_RELEASE_REVIEW_REQUIRED" if risks
            else "LOCAL_MECHANICAL_EVIDENCE_MATCH_WITH_OPEN_SCIENTIFIC_GATES" if full_local
            else "INCOMPLETE_LOCAL_RELEASE_EVIDENCE"
        ),
        "git_head": command(repo, "rev-parse", "HEAD").decode().strip(),
        "checked_out_branch": command(repo, "branch", "--show-current").decode().strip(),
        "working_tree_clean": not bool(command(repo, "status", "--porcelain")),
        "public_result_inventory": published,
        "tracked_file_safety_screen": tracked,
        "local_original_hashes": private,
        "outstanding_human_and_scientific_gates": [
            "Public tracked results need independent privacy and dataset redistribution-rights review.",
            "Original 2Wiki historical exposure remains risk-disclosed; V3 fresh cohort is NO-GO.",
            "Semantic false target assertions have not been independently source-adjudicated.",
            "2Wiki archived run restore does not establish independent cloud origin or preserved model/data caches.",
            "HotpotQA optional candidate-inventory check was absent from the previous raw audit.",
            "Final GitHub CI and supervisor publication approval are separate requirements.",
        ],
        "no_model_inference_or_original_data_mutation": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--output", type=Path, required=True, help="NEW private JSON path under --root; never overwritten")
    args = parser.parse_args()
    report = audit(args.repo, args.root, args.downloads)
    out = args.output.expanduser().resolve(strict=False)
    private_root = args.root.expanduser().resolve(strict=True)
    if out == private_root or private_root not in out.parents or not out.parent.is_dir():
        raise ValueError("Output must be a NEW file in an existing private root subdirectory")
    with out.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status": report["status"],
        "public_evidence": report["public_result_inventory"]["state"],
        "nq_source_hash_checks": report["local_original_hashes"]["nq_original_plan_and_aggregate_sha256"],
        "twowiki_backup_sha256": report["local_original_hashes"]["twowiki_archived_run_sha256"],
        "credential_pattern_file_counts": report["tracked_file_safety_screen"]["high_confidence_credential_pattern_file_counts"],
        "tracked_results_needing_license_review": report["tracked_file_safety_screen"]["tracked_results_files_requiring_dataset_privacy_and_license_review"],
        "private_report_saved": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
