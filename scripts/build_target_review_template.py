"""Generate UNAPPROVED target suggestions from an explicitly supplied development JSON.

Usage:
 python scripts/build_target_review_template.py --development-queries dev_queries.json --output review.json

The input must be a JSON list of {query_id, question, gold_answer} records.
Do not use held-out queries for tuning candidate selection.
"""
import argparse
import json
from pathlib import Path

from src.attacks.target_candidates import write_review_template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-queries", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    queries = json.loads(args.development_queries.read_text(encoding="utf-8"))
    if not isinstance(queries, list):
        parser.error("development-queries must contain a JSON list")
    required = {"query_id", "question", "gold_answer"}
    if any(not isinstance(q, dict) or not required <= q.keys() for q in queries):
        parser.error("Each query needs query_id, question, gold_answer")
    summary = write_review_template(queries, args.output)
    print(json.dumps({"status": summary["status"], "count": summary["count"],
                      "categories": summary["categories"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
