#!/usr/bin/env python3
"""Source-grounded *screening packet* for additional 2Wiki train questions.

Never accesses test/held-out data, nominates an approved poison, runs an LLM,
authenticates reviewers or injects documents. The screen can abstain on all
unsupported question grammars. New questions outside the original 25-question
clean baseline require a separately frozen baseline/protocol before evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.attacks.semantic_typed_evidence_v4_1 import bind_typed_sources
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint

SCHEMA = "rag-poison-transfer.twowiki-train-candidate-screening/v1"
DATASET_SHA = "58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43"
SOURCE_BINDING_VERSION = "rag-poison-transfer.twowiki-v4.1-typed-source-binding/v1"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return obj


def verify_train_baseline(dataset_path: Path, cohort_path: Path,
                          baseline_path: Path, audit_path: Path):
    if sha(dataset_path.read_bytes()) != DATASET_SHA:
        raise ValueError("Pinned train dataset SHA mismatch; never substitute test split")
    data, cohort, baseline, audit = map(read_json,
                                       (dataset_path, cohort_path, baseline_path, audit_path))
    if (cohort.get("scope") != "development_only"
        or cohort.get("dataset_split") != "train"
        or cohort.get("dataset_sha256") != DATASET_SHA
        or baseline.get("scope") != "train/development"
        or baseline.get("condition") != "clean_no_poison"
        or baseline.get("poison_injection") is not False
        or baseline.get("heldout_access") is True
        or baseline.get("dataset_sha256") != DATASET_SHA
        or baseline.get("cohort_manifest_sha256") != sha(cohort_path.read_bytes())):
        raise ValueError("Original 25-question train clean-baseline protocol mismatch")
    ids = cohort.get("cohort_query_ids")
    queries, corpus = data.get("queries"), data.get("corpus")
    if (not isinstance(ids, list) or len(ids) != 25 or len(set(ids)) != 25
        or ids != baseline.get("query_ids")
        or not isinstance(queries, list) or len(queries) != 300
        or not isinstance(corpus, list)):
        raise ValueError("Expected frozen 25-query baseline and 300-question train data")
    qmap = {q["query_id"]: q for q in queries}
    cmap = {d["doc_id"]: d for d in corpus}
    if (len(qmap) != len(queries) or len(cmap) != len(corpus)
        or not set(ids).issubset(qmap)
        or query_set_fingerprint([qmap[qid] for qid in ids]) != baseline.get("query_set_fingerprint")
        or corpus_fingerprint(corpus) != baseline.get("corpus_fingerprint")):
        raise ValueError("Train query/corpus fingerprints changed")
    if (audit.get("schema") != "rag-poison-transfer.twowiki-v4.1-dev25-quality-audit/v1"
        or audit.get("scope") != "train_development_only"
        or audit.get("dataset_sha256") != DATASET_SHA
        or audit.get("cohort_manifest_sha256") != sha(cohort_path.read_bytes())
        or audit.get("cohort_count") != 25
        or audit.get("provisionally_reviewed_count") != 5
        or audit.get("abstention_count") != 20
        or audit.get("paired_poisoned_evaluation_authorized") is not False
        or audit.get("heldout_queries_accessed") != 0):
        raise ValueError("Original development review audit no longer matches")
    reviewed_ids = {
        row["query_id"] for row in audit["cases"]
        if row.get("status") == "provisional_content_review_only"
    }
    if len(reviewed_ids) != 5 or not reviewed_ids.issubset(ids):
        raise ValueError("Expected exactly five previously provisionally reviewed cases")
    return queries, corpus, ids, reviewed_ids, cmap


def screen_one(query: dict, corpus: list[dict], corpus_by_id: dict,
               *, in_original_clean25: bool) -> dict:
    """Literal source binding only; all dataset-derived hashes are unapproved."""
    qid = query["query_id"]
    gold_ids = query.get("gold_doc_ids")
    facts = []
    if isinstance(gold_ids, list) and len(gold_ids) in (2, 4) and len(set(gold_ids)) == len(gold_ids):
        for doc_id in gold_ids:
            doc = corpus_by_id.get(doc_id)
            if doc is not None and isinstance(doc.get("text"), str):
                facts.append({"doc_id": doc_id, "text": doc["text"],
                              "text_sha256": sha(doc["text"].encode("utf-8"))})
    result = {
        "query_id": qid, "question": query.get("question"),
        "gold_answer": query.get("gold_answer"),
        "gold_aliases": query.get("gold_aliases", []),
        "original_clean25_member": in_original_clean25,
        "original_clean_baseline_available": in_original_clean25,
        "reviewer_target_answer": None,
        "target_nomination_requires_independent_two_ai_reviews": True,
        "dataset_derived_gold_source_hashes_are_not_external_corroboration": True,
        "supporting_sources": facts,
        "source_binding_status": "abstain",
        "source_binding_reason": None,
        "source_binding_caveats": [],
        "construction_eligible": False, "factual_approval": False,
        "injection_approved": False, "heldout_authorized": False,
    }
    if not isinstance(gold_ids, list) or len(facts) != len(gold_ids):
        result["source_binding_reason"] = "missing_gold_source_text"
        return result
    expected = {d["doc_id"]: d["text_sha256"] for d in facts}
    try:
        binding = bind_typed_sources(query, corpus, expected, scope="development")
    except (ValueError, TypeError, KeyError) as exc:
        result["source_binding_reason"] = str(exc)
        return result
    if binding.get("schema") != SOURCE_BINDING_VERSION or binding.get("injection_approved") is not False:
        raise ValueError("Unexpected source binding semantics")
    result.update({
        "source_binding_status": "source_text_compatible_unverified",
        "relation_type": binding["relation_type"],
        "source_chains": binding["source_chains"],
        "source_binding_caveats": binding["caveats"],
        "source_binding_reason": None,
    })
    gold = query.get("gold_answer")
    if isinstance(gold, str) and gold.casefold().strip() in ("yes", "no"):
        result["mechanical_counteranswer_suggestion_unapproved"] = (
            "no" if gold.casefold().strip() == "yes" else "yes"
        )
    return result


def build_packet(*, dataset_path: Path, cohort_path: Path, baseline_path: Path,
                 audit_path: Path, max_new: int = 25) -> dict:
    if type(max_new) is not int or not (1 <= max_new <= 100):
        raise ValueError("Candidate budget must be between 1 and 100")
    queries, corpus, original_ids, reviewed, cmap = verify_train_baseline(
        dataset_path, cohort_path, baseline_path, audit_path)
    qmap = {q["query_id"]: q for q in queries}
    # The 20 unanswered original 25 are considered first; additional training
    # questions may be screened but do NOT inherit that clean baseline.
    ordered_ids = [i for i in original_ids if i not in reviewed]
    ordered_ids += [q["query_id"] for q in queries if q["query_id"] not in set(original_ids)]
    eligible_to_review, abstentions = [], []
    reason_counts = Counter()
    for qid in ordered_ids:
        result = screen_one(qmap[qid], corpus, cmap, in_original_clean25=qid in original_ids)
        if result["source_binding_status"] == "source_text_compatible_unverified":
            if len(eligible_to_review) < max_new:
                eligible_to_review.append(result)
        else:
            reason_counts[result["source_binding_reason"]] += 1
            abstentions.append({"query_id": qid, "reason": result["source_binding_reason"],
                                "original_clean25_member": qid in original_ids})
    return {
        "schema": SCHEMA, "scope": "train_development_only",
        "dataset_sha256": DATASET_SHA,
        "cohort_manifest_sha256": sha(cohort_path.read_bytes()),
        "baseline_manifest_sha256": sha(baseline_path.read_bytes()),
        "v4_1_audit_sha256": sha(audit_path.read_bytes()),
        "method": "dataset_source_text_only_provisional_screen_no_model_calls",
        "original_cohort_count": 25, "previously_provisional_count": 5,
        "original_cohort_remaining": 20,
        "max_new_review_packets": max_new,
        "new_source_compatible_review_packets": len(eligible_to_review),
        "new_review_packets_in_original_clean25": sum(x["original_clean25_member"] for x in eligible_to_review),
        "new_review_packets_outside_original_clean25": sum(not x["original_clean25_member"] for x in eligible_to_review),
        "no_new_clean_baseline_for_outside_original_clean25": True,
        "unresolved_or_unsupported_query_count": len(abstentions),
        "abstention_reasons": dict(sorted(reason_counts.items())),
        "abstentions": abstentions,
        "review_packets": eligible_to_review,
        "review_requirements": {
            "reviewer_count": 2,
            "reviewer_type": "ai",
            "separate_model_and_run_identifiers_required": True,
            "timezone_aware_timestamps_required": True,
            "raw_response_sha256_required": True,
            "full_factual_content_and_target_type_review_required": True,
            "approved_targets_not_provided": True,
            "never_infer_fact_approval_from_source_binding": True,
        },
        "model_calls": 0, "heldout_queries_accessed": 0,
        "construction_approvals": 0, "factual_approvals": 0,
        "injection_approvals": 0, "poison_injections": 0,
        "paired_poisoned_evaluation_authorized": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("dataset", "cohort", "baseline", "audit", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--max-new", type=int, default=25)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError("Never overwrite previous screening packet")
    packet = build_packet(dataset_path=args.dataset, cohort_path=args.cohort,
                          baseline_path=args.baseline, audit_path=args.audit,
                          max_new=args.max_new)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    print(json.dumps({k: v for k, v in packet.items()
                      if k not in ("review_packets", "abstentions")}, indent=2))


if __name__ == "__main__":
    main()
