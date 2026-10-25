#!/usr/bin/env python3
"""Verified-development-only v3 audit. No held-out dataset, model or review calls."""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_phase4d_development_coverage import (
    DEFAULT_ARTIFACT, DEFAULT_MANIFEST, PINNED_ARTIFACT_SHA256, PINNED_MANIFEST_SHA256,
    structure, label_shape,
)
from scripts.extract_verified_development_queries import extract_verified
from src.attacks.development_review_package import stable_json
from src.attacks import development_targets_v2 as v2
from src.attacks.development_targets_v3 import METHOD_VERSION, nominate

METHOD_FILES = ("src/attacks/development_targets_v3.py", "scripts/audit_phase4e_development_coverage.py",
                "src/attacks/development_targets_v2.py", "scripts/audit_phase4d_development_coverage.py",
                "scripts/extract_verified_development_queries.py", "src/attacks/reviewed_target_artifact.py",
                "src/attacks/development_review_package.py", "src/attacks/target_candidates.py",
                "src/evaluation/metrics.py", "src/experiments/protocol.py")
REQUEST_TERMS = ("heritage", "descent", "religion", "genre", "novel", "memoir", "show", "series",
                 "license", "instrument", "relationship", "name", "language", "empire", "brewery",
                 "airport", "river", "arena", "school", "award", "party", "career", "team", "league",
                 "tournament", "event", "family", "game", "height", "population", "channel", "countries")


def audit(artifact=DEFAULT_ARTIFACT, manifest=DEFAULT_MANIFEST):
    if (hashlib.sha256(artifact.read_bytes()).hexdigest() != PINNED_ARTIFACT_SHA256 or
        hashlib.sha256(manifest.read_bytes()).hexdigest() != PINNED_MANIFEST_SHA256):
        raise ValueError("Pinned development artifact or ID manifest mismatch")
    queries, provenance = extract_verified(artifact, manifest)
    pool = v2.build_pool(queries)
    records = []
    for query in queries:
        before = v2.status(query, pool)
        after = nominate(query, queries, pool)
        records.append({**query, "question_sha256": hashlib.sha256(query["question"].encode()).hexdigest(),
                        "gold_answer_sha256": hashlib.sha256(query["gold_answer"].encode()).hexdigest(),
                        "question_structure": structure(query["question"]), "gold_label_shape": label_shape(query["gold_answer"]),
                        "request_terms": [term for term in REQUEST_TERMS if re.search(r"\b" + term + r"\b", query["question"], re.I)],
                        "before": before, "after": after})
    failures = [row for row in records if not row["before"]["eligible"]]
    count = lambda values: dict(sorted(Counter(values).items()))
    after_count = sum(row["after"]["eligible"] for row in records)
    summary = {"schema": "rag-poison-transfer.phase4e-development-audit/v1", "scope": "verified_development_only",
               "method_version": METHOD_VERSION, "query_count": len(queries),
               "provenance": {k: v for k, v in provenance.items() if k not in {"artifact", "manifest"}},
               "method_source_sha256": {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in METHOD_FILES},
               "before": {"mechanically_eligible": len(queries) - len(failures), "unsupported_or_uncertain": len(failures)},
               "after": {"mechanically_eligible": after_count, "unsupported_or_uncertain": len(queries) - after_count,
                         "gained": sum(not r["before"]["eligible"] and r["after"]["eligible"] for r in records),
                         "lost": sum(r["before"]["eligible"] and not r["after"]["eligible"] for r in records),
                         "new_nomination_mechanisms": count(r["after"]["method_family"] for r in failures if r["after"]["eligible"]),
                         "remaining_exact_causes": count(r["after"]["reason"] for r in records if not r["after"]["eligible"])},
               "original_145_failure_analysis": {"count": len(failures),
                   "v2_causes": count(r["before"]["failure_reason"] for r in failures),
                   "structure": count(r["question_structure"] for r in failures),
                   "gold_label_shape": count(r["gold_label_shape"] for r in failures),
                   "v3_diagnosis_families": count(r["after"]["method_family"] for r in failures)},
               "independent_semantic_verification": {"verified_pairs": 0, "accuracy": None,
                   "status": "unmeasured_not_zero_percent_accuracy"},
               "all_300_targeted_support_demonstrated": False, "heldout_coverage": None,
               "heldout_question_or_gold_accessed": False, "runtime_protocol_promoted": False,
               "additional_external_factual_sources_admitted": 0}
    return {"summary.json": summary, "development_analysis.json": {
        "schema": "rag-poison-transfer.phase4e-development-case-ledger/v1", "scope": "verified_development_only",
        "records": records}}


def failure_csv(records):
    stream = io.StringIO(newline="")
    fields = ("query_id", "question", "gold_answer", "question_structure", "gold_label_shape", "request_terms",
              "v2_category", "v2_failure", "v3_family", "v3_exact_cause", "v3_eligible", "pending_candidate_count")
    writer = csv.DictWriter(stream, fields, lineterminator="\n")
    writer.writeheader()
    for row in records:
        if row["before"]["eligible"]:
            continue
        value = {k: row[k] for k in fields if k in row}
        value.update(request_terms="|".join(row["request_terms"]), v2_category=row["before"]["category"],
                     v2_failure=row["before"]["failure_reason"], v3_family=row["after"]["method_family"],
                     v3_exact_cause=row["after"]["reason"], v3_eligible=row["after"]["eligible"],
                     pending_candidate_count=len(row["after"]["candidates"]))
        writer.writerow(value)
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/reviews/phase4e"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = audit(args.artifact, args.manifest)
    contents = {name: stable_json(value) for name, value in files.items()}
    contents["original_145_failures.csv"] = failure_csv(files["development_analysis.json"]["records"])
    if args.check:
        for name, text in contents.items():
            if (args.output_dir / name).read_bytes() != text.encode():
                raise ValueError("Phase 4E audit mismatch: " + name)
    else:
        if any((args.output_dir / name).exists() for name in contents):
            parser.error("Refusing overwrite; use --check or a fresh directory")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, text in contents.items():
            with (args.output_dir / name).open("x", encoding="utf-8", newline="") as output:
                output.write(text)
    print(json.dumps(files["summary.json"], sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
