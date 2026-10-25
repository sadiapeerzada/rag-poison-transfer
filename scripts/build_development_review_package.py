"""Build Phase 4A pending review artifacts from the original verified development file."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.extract_verified_development_queries import extract_verified, digest
from src.attacks.development_review_package import build_package, write_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    # Reject output collisions before any write, including input filenames that
    # happen to match one of the generated artifact names.
    inputs = {p.resolve() for p in (args.artifact, args.manifest, args.plan)}
    outputs = {(args.output_dir / name).resolve() for name in
               ("review_package.json", "review_sheet.csv", "validation_summary.json")}
    if inputs & outputs:
        parser.error("Output paths must not overwrite inputs")
    queries, provenance = extract_verified(args.artifact, args.manifest)
    raw = args.artifact.read_bytes()
    if digest(raw) != provenance["artifact_sha256"]:
        parser.error("Development artifact changed during verification")
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    support = {r["query_id"]: r.get("gold_supporting_facts") for r in records}
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    package, summary = build_package(queries, provenance, plan, support)
    write_package(package, summary, args.output_dir)
    print(json.dumps({k: v for k, v in summary.items() if k != "rejection_ledger"}, indent=2))


if __name__ == "__main__":
    main()
