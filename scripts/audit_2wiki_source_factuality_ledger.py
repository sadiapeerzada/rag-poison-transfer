#!/usr/bin/env python3
"""Private 2Wiki source-evidence ledger: schema checks, NOT factual adjudication.

The original 131-case packet contains raw questions, gold/target answers and
poisoned text. NEVER commit either it or the review ledger to public GitHub.
This utility writes only fresh private files; no inference or network calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rag-poison-transfer.2wiki-source-cited-factuality-ledger/v1"
REPORT_SCHEMA = "rag-poison-transfer.2wiki-source-ledger-audit-aggregate/v1"
PACKET_SHA256 = "dafdfe7f6bbb7abdeb5a002e671e967480c59f6854d0fa22ca54e42a824eb153"
FACTUALITY = {"unreviewed", "unverifiable", "ambiguous", "source_contradicts_target",
              "source_supports_target", "not_applicable"}
ANSWER_TYPE = {"unreviewed", "compatible", "incompatible", "uncertain", "not_applicable"}
SOURCE_BASED = {"source_contradicts_target", "source_supports_target"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def load_jsonl(path: Path) -> list:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Every JSONL line must be an object")
    return rows


def verify_packet(path: Path, expected_sha256=PACKET_SHA256, require_frozen=True) -> list:
    if digest(path) != expected_sha256:
        raise ValueError("Original private review packet SHA-256 mismatch")
    rows = load_jsonl(path)
    if require_frozen and (len(rows) != 131 or len({r.get("query_id") for r in rows}) != 102):
        raise ValueError("Original 131-case / 102-question review population mismatch")
    ids = [r.get("case_id") for r in rows]
    if len(ids) != len(set(ids)) or any(not isinstance(x, str) or not x for x in ids):
        raise ValueError("Missing or duplicate case IDs")
    for row in rows:
        if (not row.get("query_id") or row.get("construction_status") not in
                {"valid_construction", "target_nomination_failure", "semantic_generation_failure"}):
            raise ValueError("Invalid source construction status or query ID")
    return rows


def fresh_private(path: Path) -> Path:
    out = path.expanduser().resolve(strict=False)
    root = ROOT.resolve()
    if out == root or root in out.parents or not out.parent.is_dir() or out.exists():
        raise ValueError("Use a fresh existing private parent outside Git checkout")
    return out


def initial_review(case):
    return {
        "case_id": case["case_id"],
        "review_method": "ai_assisted_source_research_not_independent_human_adjudication",
        "factuality_verdict": "unreviewed",
        "answer_type_verdict": "unreviewed",
        "citations": [],
        "source_research_date": None,
        "review_notes": "",
    }


def create_template(packet: list, output: Path):
    out = fresh_private(output)
    with out.open("x", encoding="utf-8") as stream:
        for case in packet:
            stream.write(json.dumps(initial_review(case), ensure_ascii=False) + "\n")
    return {"status": "PRIVATE_EMPTY_SOURCE_REVIEW_TEMPLATE_CREATED",
            "case_rows": len(packet), "distinct_question_ids": len({r["query_id"] for r in packet}),
            "source_adjudications_performed": 0, "output_private": str(out)}


def citation_valid(entry):
    if not isinstance(entry, dict) or set(entry) != {"url", "accessed_date", "short_quote"}:
        return False
    url = entry["url"]
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return False
    try:
        accessed = date.fromisoformat(entry["accessed_date"])
    except (TypeError, ValueError):
        return False
    return (accessed <= date.today() and
            isinstance(entry["short_quote"], str) and
            1 <= len(entry["short_quote"].strip()) <= 250)


def audit(packet: list, ledger: list, packet_sha256: str, ledger_sha256: str) -> dict:
    by_id = {r["case_id"]: r for r in packet}
    if len(ledger) != len(packet):
        raise ValueError("Ledger must have a row for every selected case")
    observed = set()
    states = Counter()
    by_construction = Counter()
    n_source_cited, cited_links = 0, 0
    n_valid_reviewed = 0
    for review in ledger:
        if set(review) != {"case_id", "review_method", "factuality_verdict",
                           "answer_type_verdict", "citations", "source_research_date", "review_notes"}:
            raise ValueError("Unexpected review fields (no silently ignored values)")
        case_id = review["case_id"]
        if not isinstance(case_id, str) or case_id not in by_id or case_id in observed:
            raise ValueError("Unknown or duplicated review case")
        observed.add(case_id)
        case = by_id[case_id]
        fact, role = review["factuality_verdict"], review["answer_type_verdict"]
        if fact not in FACTUALITY or role not in ANSWER_TYPE:
            raise ValueError("Unsupported factuality/answer-role verdict")
        if review["review_method"] != "ai_assisted_source_research_not_independent_human_adjudication":
            raise ValueError("Do not claim human or independent adjudication from this utility")
        if not isinstance(review["citations"], list) or any(not citation_valid(c) for c in review["citations"]):
            raise ValueError("Malformed or undated research source citation")
        if fact in SOURCE_BASED and not review["citations"]:
            raise ValueError("Claimed source-based verdict lacks dated URL and quotation")
        if fact == "not_applicable" and case["construction_status"] == "valid_construction":
            raise ValueError("Valid-construction cases cannot be marked nonapplicable")
        if fact != "unreviewed":
            if not isinstance(review["source_research_date"], str):
                raise ValueError("Reviewed case needs a research date")
            try:
                d = date.fromisoformat(review["source_research_date"])
                if d > date.today():
                    raise ValueError("Future source research date")
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid source research date") from exc
        elif review["citations"]:
            raise ValueError("Unreviewed record cannot claim inspected sources")
        if not isinstance(review["review_notes"], str):
            raise ValueError("Review notes must be text")
        states[fact] += 1
        by_construction[case["construction_status"]] += 1
        if fact in SOURCE_BASED:
            n_source_cited += 1
            cited_links += len(review["citations"])
        if case["construction_status"] == "valid_construction" and fact != "unreviewed":
            n_valid_reviewed += 1
    if set(by_id) != observed:
        raise ValueError("Incomplete ledger case population")
    return {
        "schema": REPORT_SCHEMA,
        "status": "SOURCE_LEDGER_POPULATED_BUT_EXTERNAL_FACTS_NOT_AUTHENTICATED"
            if states["unreviewed"] == 0 else "PARTIAL_SOURCE_LEDGER",
        "source_scope": "AI-assisted, post-hoc 2Wiki case review; no independent human or automated URL verification",
        "review_packet_sha256": packet_sha256,
        "private_ledger_sha256": ledger_sha256,
        "selected_case_rows": len(packet),
        "distinct_question_ids": len({r["query_id"] for r in packet}),
        "selected_construction_status_counts": dict(sorted(by_construction.items())),
        "factuality_review_state_counts": dict(sorted(states.items())),
        "valid_construction_cases_with_any_review": n_valid_reviewed,
        "source_cited_verdict_rows": n_source_cited,
        "source_citation_entries_recorded": cited_links,
        "independent_source_authenticity_verified_by_tool": False,
        "independent_human_adjudication_performed": False,
        "population_unbiased": False,
        "limits": [
            "Citations are only format-validated; quoted source contents, truth and independence were not checked online.",
            "No verdict in this ledger rewrites original target-match or attack success metrics.",
            "The sample is outcome-visible, selected post hoc, and repeated query IDs are not independent.",
            "Missing context for 24 sampled construction failures remains a separate source-recovery gate.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("template", "audit"))
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--packet-sha256", default=PACKET_SHA256)
    p.add_argument("--ledger", type=Path, help="Required for audit; private JSONL")
    p.add_argument("--output", type=Path, required=True, help="NEW file outside Git repo")
    args = p.parse_args()
    packet = verify_packet(args.packet, args.packet_sha256)
    if args.mode == "template":
        result = create_template(packet, args.output)
    else:
        if args.ledger is None or not args.ledger.is_file():
            p.error("audit requires an existing private --ledger")
        result = audit(packet, load_jsonl(args.ledger),
                       digest(args.packet), digest(args.ledger))
        out = fresh_private(args.output)
        with out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
