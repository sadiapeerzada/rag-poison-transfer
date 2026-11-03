#!/usr/bin/env python3
"""Read-only v6 *passage-level* post-hoc screening of 30 saved 2Wiki answers.

This is NOT a relabeling of the frozen v6 experiment. Positive screens mean
"requires independent content review" only. Zero model calls/injections and
no held-out data or reviewer-provenance claims. Run on an uploaded v6 bundle.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from src.attacks.semantic_fluent_development_v5 import relation_parts
from src.attacks.semantic_fluent_development_v6 import (
    ANCHORS, DIRECTORS, source_anchors,
)

SCHEMA = "rag-poison-transfer.twowiki-v6-passage-posthoc-screen/v1"
INPUT_SCHEMA = "rag-poison-transfer.twowiki-v6-qwen-grounded-diversity-diagnostic/v1"
PACKET_SHA256 = "467f457a16d1a092e6057f54a91a02de2f9f3c405fe6428876853ba1ff30bbf6"
DATASET_SHA256 = "58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43"
ALLOWED_CASES = frozenset(ANCHORS)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _match(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I))


def _sentences(text: str) -> list[str]:
    """Count sentence boundaries, not a single alphabetic initial's period."""
    if not isinstance(text, str):
        return []
    return [s.strip().rstrip(".") for s in re.split(
        r"(?<!\b[A-Z])\.\s+(?=[A-Z\"“])", text.strip().rstrip("."))
        if s.strip()]


def _claimed(text: str, kind: str, target: str) -> bool:
    target_pattern = re.escape(target.strip())
    if kind == "birth":
        return bool(re.search(r"\b(?:was|were)\s+born\s+in\s+" + target_pattern + r"\b", text, re.I))
    if kind == "death":
        return bool(re.search(r"\bdied\s+in\s+" + target_pattern + r"\b", text, re.I))
    if kind == "country_no":
        return bool(re.search(r"\b(?:different\s+countries|not\s+(?:from|of)\s+the\s+same\s+country)\b", text, re.I))
    if kind == "nationality_yes":
        return bool(re.search(r"\b(?:share\s+the\s+same\s+nationality|of\s+the\s+same\s+nationality)\b", text, re.I))
    return False


def inspect_passage(case: dict, slot: int, raw: str) -> dict:
    """Revision-v1 syntax/content-risk screen; never a semantic approval."""
    if type(slot) is not int or slot not in (0, 1, 2):
        raise ValueError("Invalid development slot")
    anchors = source_anchors(case)
    spec = relation_parts(case, case["proposed_false_target"])
    kind, target, titles = spec["kind"], spec["target"], spec["referents"]
    reasons, caveats = [], []
    sentences = _sentences(raw)
    if len(sentences) != 2 or "\n" in raw or "?" in raw:
        reasons.append("not_two_complete_sentences")
    if len(raw) < 70 or len(raw) > 1500:
        reasons.append("passage_length_outside_diagnostic_band")
    if not _match(raw, anchors[slot]["anchor"]):
        reasons.append("source_anchor_absent")
    if len(sentences) == 2 and not _match(sentences[0], anchors[slot]["anchor"]):
        reasons.append("context_anchor_not_in_first_sentence")
    if any(marker.casefold() in raw.casefold() for marker in
           ("<|im_start|>", "<|im_end|>", "reference answer:", "assistant:")):
        reasons.append("prompt_leakage")
    # Unlike v6, first and second sentences may share referents via anaphora.
    if len(sentences) == 2:
        first, claim = sentences
        if not _claimed(claim, kind, target):
            reasons.append("final_sentence_does_not_assert_target_relation")
        if re.search(r"^\s*(?:yes|no),", raw, re.I) and kind in ("birth", "death"):
            reasons.append("place_question_with_boolean_marker")
        if re.search(r"\b(?:not|never|didn't|wasn't|did not)\b", claim, re.I):
            reasons.append("negative_or_self_contradictory_final_claim")
        if not all(_match(raw, director) for director in DIRECTORS[case["candidate_id"]]):
            reasons.append("named_director_missing_in_passage")
        if not any(_match(claim, d) for d in DIRECTORS[case["candidate_id"]]):
            reasons.append("director_missing_from_final_claim")
        for title in titles:
            if not _match(first, title):
                # An unambiguous year-disambiguated title sometimes appears in
                # source text without the benchmark's "(1933 Film)" suffix.
                stem = re.sub(r"\s*\(\d{4}\s+[Ff]ilm\)$", "", title)
                year = re.search(r"\((\d{4})\s+[Ff]ilm\)$", title)
                if year and _match(first, stem) and year.group(1) in first:
                    caveats.append("nonliteral_but_year_disambiguated_film_title")
                else:
                    reasons.append("film_referent_missing_from_context")
        if kind in ("birth", "death") and _match(raw, case["gold_answer"]):
            reasons.append("competing_gold_location_mentioned")
        if kind == "country_no" and re.search(
            r"\b(?:both|also)\s+(?:are|an?|American|from)\b[^.]*\bAmerican\b", raw, re.I
        ):
            reasons.append("supports_same_country_instead_of_target")
        if kind == "country_no" and re.search(r"\bboth\s+(?:films?\s+)?(?:were\s+)?released\s+in\s+2016\b", raw, re.I):
            reasons.append("fabricated_both_films_2016_context")
        if kind == "nationality_yes":
            if re.search(r"\b(?:both|same|share)\b[^.]{0,130}\b(?:German|American|Germany)\b", raw, re.I):
                reasons.append("unsupported_specific_nationality_side_claim")
            if "Nicolas Cage" in raw and re.search(r"\bboth\s+(?:feature|star|include)\b[^.]{0,60}\bNicolas Cage\b", raw, re.I):
                reasons.append("unsupported_cast_transfer")
    else:
        reasons.append("final_claim_not_separately_evaluable")
    reasons = sorted(set(reasons))
    return {
        "status": "needs_independent_content_review" if not reasons else "rejected_by_passage_screen",
        "reasons": reasons, "referent_caveats": sorted(set(caveats)),
        "raw_text_sha256": sha(raw.encode("utf-8")), "candidate_id": case["candidate_id"],
        "slot": slot, "source_anchor": anchors[slot]["anchor"],
        "source_anchor_sha256": anchors[slot]["source_sha256"],
        "source_doc_id": anchors[slot]["source_doc_id"],
        "context_claim_independently_verified": False,
        "semantic_validity": "unassessed",
        "factual_approval": False, "construction_approved": False,
        "injection_approved": False, "heldout_authorized": False,
    }


def audit_bundle(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        members = z.namelist()
        if len(members) != len(set(members)):
            raise ValueError("Duplicate ZIP member")
        if "original_review_packet.zip" not in members or "summary.json" not in members or "manifest.json" not in members:
            raise ValueError("Incomplete v6 bundle")
        summary = json.loads(z.read("summary.json"))
        manifest = json.loads(z.read("manifest.json"))
        if (summary.get("schema") != INPUT_SCHEMA or manifest.get("schema") != INPUT_SCHEMA
            or summary.get("recorded_model_calls") != 30
            or summary.get("surface_review_candidates") != 0
            or summary.get("three_context_candidate_cases") != 0
            or summary.get("heldout_queries_accessed") != 0
            or summary.get("poison_injections") != 0
            or manifest.get("scope") != "train_development_only"
            or manifest.get("dataset_sha256") != DATASET_SHA256
            or manifest.get("source_packet_sha256") != PACKET_SHA256
            or manifest.get("heldout_access") is not False):
            raise ValueError("Invalid or non-frozen v6 record")
        packet_bytes = z.read("original_review_packet.zip")
        if sha(packet_bytes) != PACKET_SHA256:
            raise ValueError("Pinned packet SHA-256 mismatch")
        with zipfile.ZipFile(io.BytesIO(packet_bytes)) as pz:
            if pz.namelist().count("independent_review_input.json") != 1:
                raise ValueError("Missing pinned source packet")
            packet = json.loads(pz.read("independent_review_input.json"))
        cases = packet.get("queries")
        if (packet.get("scope") != "train_development_only"
            or packet.get("dataset_sha256") != DATASET_SHA256
            or not isinstance(cases, list) or len(cases) != 5
            or {c["candidate_id"] for c in cases} != ALLOWED_CASES
            or any(c.get("injection_approved") is not False for c in cases)):
            raise ValueError("Packet is not pinned 5-case development sample")
        case_map = {c["candidate_id"]: c for c in cases}
        if len(case_map) != 5:
            raise ValueError("Repeated case")
        expected_files = {
            f"responses/{cid}.slot-{slot}.attempt-{attempt}.json"
            for cid in ALLOWED_CASES for slot in range(3) for attempt in (1, 2)
        }
        if set(x for x in members if x.startswith("responses/")) != expected_files:
            raise ValueError("Response count/names do not match 30-call comparator")
        results = []
        for cid in sorted(ALLOWED_CASES):
            case = case_map[cid]
            for slot in range(3):
                records = []
                for attempt in (1, 2):
                    r = json.loads(z.read(f"responses/{cid}.slot-{slot}.attempt-{attempt}.json"))
                    raw = r["raw_response"]
                    if (r.get("schema") != INPUT_SCHEMA
                        or r.get("candidate_id") != cid
                        or r.get("query_id") != case["query_id"]
                        or r.get("slot") != slot or r.get("attempt") != attempt
                        or not isinstance(raw, str)
                        or r.get("raw_response_sha256") != sha(raw.encode("utf-8"))
                        or r.get("triage", {}).get("status") != "rejected_by_conservative_triage"):
                        raise ValueError("Response provenance mismatch")
                    records.append(raw)
                result = inspect_passage(case, slot, records[0])
                result["attempts"] = 2
                result["identical_attempts"] = records[0] == records[1]
                result["attempt_two_raw_text_sha256"] = sha(records[1].encode("utf-8"))
                if not result["identical_attempts"]:
                    # This script intentionally does not silently choose a
                    # winner or overwrite either of two distinct attempts.
                    raise ValueError("Unexpected nonidentical v6 attempt pair")
                results.append(result)
    counts = Counter(r["status"] for r in results)
    per_case = {}
    for cid in sorted(ALLOWED_CASES):
        rows = [r for r in results if r["candidate_id"] == cid]
        per_case[cid] = {
            "review_candidate_slots": [r["slot"] for r in rows
                                       if r["status"] == "needs_independent_content_review"],
            "three_review_candidate_slots": all(
                r["status"] == "needs_independent_content_review" for r in rows
            ),
            "reason_counts": dict(sorted(Counter(
                reason for r in rows for reason in r["reasons"]).items())),
        }
    return {
        "schema": SCHEMA, "scope": "five_previously_tuned_train_cases",
        "source_bundle_sha256": sha(path.read_bytes()),
        "source_packet_sha256": PACKET_SHA256,
        "frozen_v6_model_calls": 30,
        "frozen_v6_surface_triage_passes": 0,
        "frozen_v6_three_context_cases": 0,
        "posthoc_unique_slot_results": len(results),
        "posthoc_review_candidate_slots": counts["needs_independent_content_review"],
        "posthoc_screened_out_slots": counts["rejected_by_passage_screen"],
        "posthoc_three_review_candidate_case_count": sum(
            x["three_review_candidate_slots"] for x in per_case.values()),
        "per_case": per_case,
        "per_slot": results,
        "method": "deterministic_read_only_posthoc_passage_level_triage",
        "historical_v6_results_modified": False,
        "reviewer_metadata_authenticated": False,
        "human_review_required": False,
        "ai_review_pending": True,
        "independent_semantic_validity": "unassessed",
        "construction_approvals": 0, "factual_approvals": 0,
        "injection_approvals": 0, "poison_injections": 0,
        "heldout_queries_accessed": 0,
        "paired_poisoned_evaluation_authorized": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError("Never overwrite an existing post-hoc report")
    report = audit_bundle(args.bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("per_case", "per_slot")}, indent=2))


if __name__ == "__main__":
    main()
