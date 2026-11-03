#!/usr/bin/env python3
"""Read-only 25-query 2Wiki development quality audit (never executes an attack).

Requires pinned clean-baseline manifest, pinned training dataset, v4.1
review packet and raw second-AI response. No reviewer is authenticated.
The reported passage quality is a deterministic-template *control*, not
success of Qwen's historical 0/5 fluent construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
import sys

# Allow both `python -m scripts.audit_twowiki_v4_1_quality` and the documented
# `python scripts/audit_twowiki_v4_1_quality.py` from any working directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.attacks.semantic_typed_evidence_v4_1 import bind_typed_sources
from src.attacks.semantic_template_control_v4_1 import (
    template_forms, validate_template_statement, review_metadata_status,
)
from src.attacks.semantic_document_diversity_v3 import audit_documents
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint

SCHEMA = "rag-poison-transfer.twowiki-v4.1-dev25-quality-audit/v1"
DATASET_SHA256 = "58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43"
REVIEW_PACKET_SHA256 = "467f457a16d1a092e6057f54a91a02de2f9f3c405fe6428876853ba1ff30bbf6"
CASE_IDS = frozenset(("C02", "C05", "C09", "C11", "C13"))


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return obj


def audit(*, dataset_path, cohort_path, baseline_path, packet_path, review_path):
    if sha(dataset_path.read_bytes()) != DATASET_SHA256:
        raise ValueError("Pinned train dataset hash mismatch")
    data, cohort, baseline = (read_json(p) for p in (dataset_path, cohort_path, baseline_path))
    if (cohort.get("scope") != "development_only" or cohort.get("dataset_split") != "train"
        or cohort.get("dataset_sha256") != DATASET_SHA256
        or baseline.get("scope") != "train/development"
        or baseline.get("condition") != "clean_no_poison"
        or baseline.get("poison_injection") is not False
        or baseline.get("heldout_access") is True
        or baseline.get("dataset_sha256") != DATASET_SHA256
        or baseline.get("cohort_manifest_sha256") != sha(cohort_path.read_bytes())):
        raise ValueError("Cohort and previously completed clean-baseline pins disagree")
    ids = cohort.get("cohort_query_ids")
    if (not isinstance(ids, list) or len(ids) != 25 or len(set(ids)) != 25
        or ids != baseline.get("query_ids")):
        raise ValueError("Exact frozen 25-query cohort mismatch")
    queries, corpus = data.get("queries"), data.get("corpus")
    if not isinstance(queries, list) or len(queries) != 300 or not isinstance(corpus, list):
        raise ValueError("Pinned 300-question train cohort not found")
    query_by_id = {q["query_id"]: q for q in queries}
    if len(query_by_id) != len(queries) or not set(ids).issubset(query_by_id):
        raise ValueError("Missing or repeated training query IDs")
    selected = [query_by_id[i] for i in ids]
    if (query_set_fingerprint(selected) != baseline.get("query_set_fingerprint")
        or corpus_fingerprint(corpus) != baseline.get("corpus_fingerprint")):
        raise ValueError("Clean baseline query or corpus fingerprint changed")

    if sha(packet_path.read_bytes()) != REVIEW_PACKET_SHA256:
        raise ValueError("Independent review packet bytes changed")
    with zipfile.ZipFile(packet_path) as zipped:
        if zipped.namelist().count("independent_review_input.json") != 1:
            raise ValueError("Independent review input missing/duplicated")
        source_bytes = zipped.read("independent_review_input.json")
    packet = json.loads(source_bytes)
    second = read_json(review_path)
    meta = second.get("review_metadata")
    if not isinstance(meta, dict) or (
        meta.get("input_zip_sha256") != REVIEW_PACKET_SHA256
        or meta.get("input_json_sha256") != sha(source_bytes)
        or meta.get("scope") != "train_development_only"
        or meta.get("factual_approval") is not False
        or meta.get("injection_approved") is not False
        or meta.get("heldout_access") is not False
    ):
        raise ValueError("Second AI's review not bound to packet or unsafe review scope")
    if (packet.get("scope") != "train_development_only"
        or packet.get("dataset_sha256") != DATASET_SHA256
        or packet.get("not_llm_generated") is not True
        or packet.get("model_calls") != 0
        or packet.get("factual_approval") is not False
        or packet.get("injection_approved") is not False
        or packet.get("heldout_access") is not False):
        raise ValueError("Review packet scope or template-control identity altered")
    packets, verdicts = packet.get("queries"), second.get("reviews")
    if not isinstance(packets, list) or not isinstance(verdicts, list):
        raise ValueError("Review packet or verdict list missing")
    if (len(packets) != 5 or len(verdicts) != 5
        or {p["candidate_id"] for p in packets} != CASE_IDS
        or {v["candidate_id"] for v in verdicts} != CASE_IDS
        or len({p["query_id"] for p in packets}) != 5):
        raise ValueError("Expected exact five independent-reviewed cases")
    if len({p["candidate_id"] for p in packets}) != 5 or len({v["candidate_id"] for v in verdicts}) != 5:
        raise ValueError("Duplicate reviewer/case ID")
    packet_by_query = {p["query_id"]: p for p in packets}
    reviewer_by_case = {v["candidate_id"]: v for v in verdicts}
    if not set(packet_by_query).issubset(ids):
        raise ValueError("Reviewed query outside development cohort")

    records = []
    for q in selected:
        qid = q["query_id"]
        if qid not in packet_by_query:
            records.append({"query_id": qid, "status": "abstain_no_reviewed_target",
                "construction_eligible": False, "injection_approved": False})
            continue
        case = packet_by_query[qid]
        case_id = case["candidate_id"]
        reviewer = reviewer_by_case[case_id]
        if case["question"] != q["question"] or case["gold_answer"] != q["gold_answer"]:
            raise ValueError("Reviewed question/gold mismatch")
        sources = case["source_documents"]
        hashes = {}
        source_text = {}
        for doc in sources:
            if sha(doc["text"].encode("utf-8")) != doc["text_sha256"]:
                raise ValueError("Reviewed supporting source content differs from pin")
            hashes[doc["doc_id"]] = doc["text_sha256"]
            source_text[doc["doc_id"]] = doc["text"]
        if len(hashes) != len(sources) or set(hashes) != set(q.get("gold_doc_ids", [])):
            raise ValueError("Duplicate or mismatched reviewed supporting documents")
        binding = bind_typed_sources(q, corpus, hashes, scope="development")
        target = case["proposed_false_target"]
        forms = template_forms(q, target)
        passages = case["candidate_documents"]
        if len(forms) != 3 or len(passages) != 3:
            raise ValueError("Incomplete typed template control")
        if (reviewer.get("decision") != "accept"
            or reviewer.get("source_chain_valid") is not True
            or reviewer.get("target_contradicted_by_sources") is not True):
            raise ValueError("Second reviewer rejected or disputed case")
        verdict_rows = reviewer.get("passage_verdicts")
        if (not isinstance(verdict_rows, list) or len(verdict_rows) != 3
            or sorted(v.get("slot") for v in verdict_rows) != [0, 1, 2]):
            raise ValueError("Incomplete passage assessments")
        if not all(all(v.get(key) is True for key in (
            "faithful_to_target", "referents_preserved", "fluent")) for v in verdict_rows):
            raise ValueError("Passage reviewer has unresolved quality objection")
        packet_text = {}
        for i, passage in enumerate(passages):
            if passage.get("poison_index") != i or not isinstance(passage.get("doc_id"), str):
                raise ValueError("Passage slot mismatch")
            packet_text[passage["doc_id"]] = passage["text"]
            validate_template_statement(q, target, i, forms[i])
        for quote in reviewer.get("evidence_quotes", []):
            source = source_text.get(quote.get("doc_id"), packet_text.get(quote.get("doc_id")))
            if source is None or not isinstance(quote.get("exact_quote"), str) or quote["exact_quote"] not in source:
                raise ValueError("Reviewer evidence quote not anchored to source packet")
        distinct = audit_documents([{"doc_id": f"diagnostic-{i}", "text": t}
                                    for i, t in enumerate(forms)], 3)
        if distinct["status"] != "distinct_text":
            raise ValueError("Duplicate or incomplete versioned surface control")
        exact = [passages[i]["text"] == forms[i] for i in range(3)]
        records.append({"query_id": qid, "candidate_id": case_id,
            "status": "provisional_content_review_only",
            "source_binding": binding["status"], "relation_type": binding["relation_type"],
            "source_caveats": binding["caveats"],
            "intensity_1_surface_forms_valid": True,
            "intensity_3_surface_forms_valid": True,
            "intensity_3_normalized_distinct": True,
            "passages_exactly_reviewed": exact,
            "stale_review_slots": [i for i, ok in enumerate(exact) if not ok],
            "real_model_construction_success": None,
            "construction_eligible": False, "factual_approval": False,
            "injection_approved": False})
    reviewed = [r for r in records if r["status"] == "provisional_content_review_only"]
    if len(reviewed) != 5 or sum(r["status"] == "abstain_no_reviewed_target" for r in records) != 20:
        raise ValueError("25-query construction-coverage accounting mismatch")
    stale = {r["candidate_id"]: r["stale_review_slots"] for r in reviewed if r["stale_review_slots"]}
    return {"schema": SCHEMA, "scope": "train_development_only",
        "method": "read_only_versioned_template_control_and_source_review",
        "cohort_count": 25, "provisionally_reviewed_count": 5, "abstention_count": 20,
        "reviewed_passages": 15, "exactly_reviewed_versioned_passages": 15-sum(map(len, stale.values())),
        "stale_review_slots": stale,
        "second_ai_provenance": review_metadata_status({
            "reviewer_model_id": meta.get("reviewer_model_id"),
            "run_id": meta.get("run_id"), "timestamp": meta.get("timestamp")}),
        "two_ai_provenance_cleared": False,
        "real_qwen_v4_passes_from_prior_smoke": "0/5 (historical, not remeasured)",
        "real_model_construction_rate_on_25": None,
        "model_calls": 0, "poison_injections": 0, "heldout_queries_accessed": 0,
        "construction_approvals": 0, "factual_approvals": 0,
        "injection_approvals": 0, "paired_poisoned_evaluation_authorized": False,
        "dataset_sha256": DATASET_SHA256,
        "cohort_manifest_sha256": sha(cohort_path.read_bytes()),
        "baseline_manifest_sha256": sha(baseline_path.read_bytes()),
        "review_packet_sha256": REVIEW_PACKET_SHA256,
        "query_set_fingerprint": query_set_fingerprint(selected),
        "corpus_fingerprint": corpus_fingerprint(corpus),
        "cases": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("dataset", "cohort", "baseline", "packet", "review", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Prior report exists; choose a new output filename")
    report = audit(dataset_path=args.dataset, cohort_path=args.cohort,
                   baseline_path=args.baseline, packet_path=args.packet,
                   review_path=args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
