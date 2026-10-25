"""Audit an unapproved development target-review template; no model calls."""
import argparse
import json
from pathlib import Path

from src.attacks.target_review_audit import audit_review_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-queries", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_review_files(args.development_queries, args.template, args.output), indent=2))


if __name__ == "__main__":
    main()
