"""Validate original development results against frozen manifest; no dataset downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.experiments.protocol import query_set_fingerprint, fingerprint_records

PINNED_REVISION = "1908d6afbbead072334abe2965f91bd2709910ab"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ids_fingerprint(ids: list[str]) -> str:
    return digest("\n".join(ids).encode("utf-8"))


def extract_verified(artifact: Path, manifest_path: Path) -> tuple[list[dict], dict]:
    raw = artifact.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be an object")
    if manifest.get("dataset_revision") != PINNED_REVISION or manifest.get("dataset_split") != "validation":
        raise ValueError("Manifest revision/split differs from pinned development protocol")
    rows = []
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"Malformed JSONL at line {line_no}") from exc
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("query_id", "question", "gold_answer")):
            raise ValueError(f"Missing/invalid development query fields at line {line_no}")
        if row.get("dataset_revision") != PINNED_REVISION:
            raise ValueError(f"Dataset revision mismatch at line {line_no}")
        if row.get("dataset_split") != manifest["dataset_split"]:
            raise ValueError(f"Dataset split mismatch at line {line_no}")
        if not isinstance(row.get("gold_doc_ids"), list):
            raise ValueError(f"Missing gold_doc_ids required by historical fingerprint at line {line_no}")
        rows.append(row)
    if len(rows) != manifest.get("development_query_count") or not rows:
        raise ValueError("Development record count mismatch")
    ids = [r["query_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate development query IDs")
    heldout = manifest.get("heldout_query_ids")
    if not isinstance(heldout, list) or any(not isinstance(x, str) or not x.strip() for x in heldout):
        raise ValueError("Invalid held-out IDs")
    if len(set(heldout)) != len(heldout):
        raise ValueError("Duplicate held-out query IDs")
    if len(heldout) != manifest.get("heldout_query_count"):
        raise ValueError("Held-out count mismatch")
    if ids_fingerprint(heldout) != manifest.get("heldout_query_ids_fingerprint"):
        raise ValueError("Held-out IDs fingerprint mismatch")
    overlap = set(ids) & set(heldout)
    if overlap:
        raise ValueError(f"Development/held-out overlap: {sorted(overlap)}")
    historical = {"development_query_set_fingerprint": query_set_fingerprint(rows),
                  "development_query_ids_fingerprint": ids_fingerprint(sorted(ids))}
    for key, value in historical.items():
        if manifest.get(key) != value:
            raise ValueError(f"Historical fingerprint mismatch: {key}")
    queries = [{k: r[k] for k in ("query_id", "question", "gold_answer")} for r in rows]
    report = {"schema": "verified-development-extraction/v1", "artifact": str(artifact.resolve()),
              "manifest": str(manifest_path.resolve()), "artifact_sha256": digest(raw),
              "manifest_sha256": digest(manifest_raw), "query_count": len(queries),
              "dataset_revision": PINNED_REVISION, "dataset_split": manifest["dataset_split"],
              "heldout_overlap_count": 0, **historical,
              "extracted_records_fingerprint_v1": fingerprint_records(queries),
              "fingerprint_semantics": "Existing protocol.query_set_fingerprint; SHA256 newline-joined sorted development IDs. Both reproduce frozen hashes. Original manifest creation script not found in Git history."}
    return queries, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    paths = [p.resolve() for p in (args.artifact, args.manifest, args.output, args.provenance)]
    if len(set(paths)) != 4:
        parser.error("Input and output paths must be distinct")
    queries, report = extract_verified(args.artifact, args.manifest)
    output = (json.dumps(queries, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    report["output_sha256"] = digest(output)
    args.output.write_bytes(output)
    args.provenance.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
