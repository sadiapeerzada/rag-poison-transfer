"""Offline rendering of recorded source assessments; does not fetch or verify web facts."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.extract_verified_development_queries import extract_verified
from src.attacks.development_review_package import stable_json
from src.attacks.evidence_audit import validate_audit, render_report, render_sheet


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    inputs = {path.resolve() for path in (args.artifact, args.manifest, args.package, args.audit)}
    names = ("EVIDENCE_REPORT.md", "review_sheet_audited.csv", "evidence_audit_summary.json")
    if inputs & {(args.output_dir / name).resolve() for name in names}:
        p.error("Generated output must not overwrite an input")
    queries, extraction = extract_verified(args.artifact, args.manifest)
    raw = args.package.read_bytes()
    package, audit = json.loads(raw), json.loads(args.audit.read_text(encoding="utf-8"))
    summary = validate_audit(audit, package, raw, queries, extraction)
    rendered = (render_report(audit, summary), render_sheet(audit, package), stable_json(summary))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in zip(names, rendered):
        (args.output_dir / name).write_text(value, encoding="utf-8")
    print(stable_json(summary), end="")


if __name__ == "__main__":
    main()
