"""Draft-only independent-review preparation; never loads a held-out dataset.

Metadata preparation reads the frozen ID manifest and verified DEVELOPMENT
artifact. Text coverage requires an externally pinned, genuinely frozen
preregistration before its input file is opened. No approval/signing API.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

from scripts.extract_verified_development_queries import extract_verified
from scripts.run_week9_multiseed_matched_evaluation import (
    DEFAULT_DENSE_CONFIG, DEFAULT_RCD_CONFIG, validate_frozen_inputs,
)
from src.attacks.development_review_package import answer_shape, stable_json
from src.attacks.reviewed_target_artifact import (
    SUPPORTED_CATEGORIES, read_pinned, _normalized,
)
from src.attacks.target_candidates import expected_category
from src.experiments.protocol import query_set_fingerprint

SCHEMA = "rag-poison-transfer.review-handoff/v1"
PREREG_SCHEMA = "rag-poison-transfer.nomination-preregistration/v1"
POOL_SCHEMA = "rag-poison-transfer.development-candidate-pool/v1"
COVERAGE_SCHEMA = "rag-poison-transfer.review-coverage/v1"
METHOD_PATHS = tuple(Path(name) for name in (
    "docs/reviews/phase4c/PREREGISTRATION_DRAFT.md",
    "docs/reviews/phase4c/REVIEWER_INSTRUCTIONS.md",
    "docs/PHASE4B_REVIEWED_TARGET_PROTOCOL.md",
    "docs/reviews/phase4a/EVIDENCE_REPORT.md",
    "docs/reviews/phase4a/evidence_audit.json",
    "docs/reviews/phase4a/evidence_audit_summary.json",
    "scripts/prepare_phase4c_review_handoff.py",
    "scripts/extract_verified_development_queries.py",
    "scripts/run_week9_multiseed_matched_evaluation.py",
    "src/attacks/review_handoff.py",
    "src/attacks/target_candidates.py",
    "src/attacks/development_review_package.py",
    "src/attacks/reviewed_target_artifact.py",
    "src/attacks/compatible_targets.py",
    "src/evaluation/metrics.py",
    "src/experiments/protocol.py",
    "src/attacks/review_provenance.py",
    "src/utils/config.py",
    "run.py",
))
MAX_CANDIDATES = 5
MAX_ROUNDS = 2
TEXT_FIELDS = ("question", "gold_answer", "answer_category", "proposed_target", "candidate_rank",
               "gold_aliases", "source_reference", "evidence_claim", "evidence_limitations")
AUTH_FIELDS = ("reviewer", "reviewed_at", "signature", "nominator", "decision_id")
SLOT_FIELDS = ("query_id", *TEXT_FIELDS, "review_decision", *AUTH_FIELDS)
LOG_FIELDS = ("query_id", "candidate_rank", "proposed_target", "source_development_query_ids",
              "review_round", "criterion_findings", "evidence_reference", "evidence_claim",
              "evidence_limitations", "disagreement", "review_decision", *AUTH_FIELDS)


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def candidate_pool(queries: list[dict], provenance: dict) -> dict:
    grouped = {}
    for query in sorted(queries, key=lambda row: row["query_id"]):
        category = expected_category(query["question"], query["gold_answer"])
        answer = query["gold_answer"]
        if category not in SUPPORTED_CATEGORIES or not answer_shape(category, answer):
            continue
        grouped.setdefault((category, answer), []).append(query["query_id"])
    candidates = [{"answer_category": category, "answer": answer,
                   "source_development_query_ids": ids}
                  for (category, answer), ids in sorted(grouped.items())]
    return {"schema": POOL_SCHEMA, "scope": "development",
            "development_artifact_sha256": provenance["artifact_sha256"],
            "development_records_fingerprint": provenance["extracted_records_fingerprint_v1"],
            "candidates": candidates}


def ordered_candidates(query: dict, pool: dict) -> list[dict]:
    """Fixed top-five pool order, without asserting truth or compatibility."""
    category = expected_category(query["question"], query["gold_answer"])
    if category not in SUPPORTED_CATEGORIES or not answer_shape(category, query["gold_answer"]):
        return []
    eligible = sorted((row for row in pool["candidates"] if row["answer_category"] == category),
                      key=lambda row: (row["answer"].casefold(), row["answer"]))
    seen = {_normalized(query["gold_answer"])}
    result = []
    for row in eligible:
        normalized = _normalized(row["answer"])
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(row)
        if len(result) == MAX_CANDIDATES:
            break
    return result


def screen_queries(queries: list[dict], pool: dict) -> dict:
    """Pure mechanical screening; call only on development or authorized text."""
    categories, reasons = Counter(), Counter()
    supported = 0
    for query in queries:
        category = expected_category(query["question"], query["gold_answer"])
        categories[category] += 1
        if category not in SUPPORTED_CATEGORIES:
            reasons["unsupported_category_or_question_pattern"] += 1
        elif not answer_shape(category, query["gold_answer"]):
            reasons["unsupported_gold_answer_shape"] += 1
        elif not ordered_candidates(query, pool):
            reasons["no_non_gold_candidate_in_frozen_pool"] += 1
        else:
            supported += 1
    return {"mechanically_supported": supported, "unsupported_or_uncertain": len(queries) - supported,
            "category_counts": dict(sorted(categories.items())), "reason_counts": dict(sorted(reasons.items())),
            "semantic_and_factual_review_pending": len(queries),
            "limitation": "Mechanical eligibility is not factual or semantic support, approval, or expected attack success."}


def build_handoff(*, manifest_path: Path, development_artifact: Path, method_paths: list[Path]) -> dict:
    """Use the existing protocol's metadata-only frozen-input validation."""
    _, config, ids, ids_fp, hashes = validate_frozen_inputs(
        heldout_path=manifest_path, dense_config_path=DEFAULT_DENSE_CONFIG, rcd_config_path=DEFAULT_RCD_CONFIG,
    )
    development, provenance = extract_verified(development_artifact, manifest_path)
    pool = candidate_pool(development, provenance)
    methods = {str(path): sha(path.read_bytes()) for path in sorted(method_paths)}
    dataset = {"name": "hotpotqa/hotpot_qa", "config": "distractor", "revision": config["dataset_revision"],
               "split": config["dataset_split"], "heldout_manifest_sha256": hashes["heldout"],
               "heldout_manifest_fingerprint": ids_fp, "query_set_fingerprint": None}
    prereg = {"schema": PREREG_SCHEMA, "scope": "heldout", "status": "draft_not_frozen",
              "dataset": dataset, "query_count": len(ids), "frozen_config_sha256": hashes, "method_source_sha256": methods,
              "nomination_protocol_sha256": methods["docs/reviews/phase4c/PREREGISTRATION_DRAFT.md"],
              "development_pool_fingerprint": sha(stable_json(pool).encode("utf-8")),
              "supported_categories": sorted(SUPPORTED_CATEGORIES), "max_candidates_per_query": MAX_CANDIDATES,
              "max_review_rounds": MAX_ROUNDS, "candidate_order": "casefold_then_exact_then_normalized_alias_dedup",
              "failure_policy": "stop_if_any_of_300_lacks_genuine_independent_approval",
              "fingerprint_bootstrap_resolution": None, "bootstrap_resolution_reference": "",
              "human_decisions_required": ["fingerprint_bootstrap_resolution", "scientific_protocol_adoption",
                                           "independent_reviewer_registration", "external_preregistration_freeze"]}
    slots = [{**dict.fromkeys(SLOT_FIELDS, ""), "query_id": query_id, "review_decision": "pending"}
             for query_id in ids]
    package = {"schema": SCHEMA, "scope": "heldout_metadata_only", "status": "draft_not_frozen",
               "preregistration_draft_sha256": sha(stable_json(prereg).encode("utf-8")), "review_slots": slots}
    coverage = {"schema": COVERAGE_SCHEMA, "scope": "heldout_metadata_only", "query_count": len(ids),
                "heldout_question_text_accessed": False, "heldout_gold_answers_accessed": False,
                "mechanically_supported": None, "unsupported_or_uncertain": None,
                "unassessed": len(ids), "support_count_bounds": {"minimum": 0, "maximum": len(ids)},
                "category_counts": {}, "independently_approved": 0,
                "reason": "No category metadata in frozen ID manifest; text inspection prohibited before human freeze.",
                "development_only_method_check": screen_queries(development, pool)}
    return {"candidate_pool.json": pool, "preregistration_draft.json": prereg,
            "review_handoff.json": package, "coverage_metadata_only.json": coverage}


def render_sheet(package: dict) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SLOT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(package["review_slots"])
    return stream.getvalue()


def render_log_header() -> str:
    return ",".join(LOG_FIELDS) + "\n"


def validate_handoff(directory: Path, *, manifest_path: Path, development_artifact: Path,
                     method_paths: list[Path]) -> dict:
    """Reconstruct all metadata-only files; never trust editable coverage counts."""
    expected = build_handoff(manifest_path=manifest_path, development_artifact=development_artifact,
                             method_paths=method_paths)
    for name, value in expected.items():
        if (directory / name).read_bytes() != stable_json(value).encode("utf-8"):
            raise ValueError("Draft handoff mismatch: " + name)
    if (directory / "review_sheet_blank.csv").read_bytes() != render_sheet(expected["review_handoff.json"]).encode("utf-8"):
        raise ValueError("Blank review sheet mismatch")
    if (directory / "candidate_review_log_blank.csv").read_bytes() != render_log_header().encode("utf-8"):
        raise ValueError("Blank candidate log mismatch")
    return {"valid": True, "status": "draft_only_not_approved", "heldout_ids": 300,
            "heldout_unassessed": 300, "independently_approved": 0}


def coverage_after_freeze(*, preregistration_path: Path, preregistration_sha256: str,
                          queries_path: Path, pool_path: Path, manifest_path: Path,
                          authorized: bool = False) -> dict:
    """Never open a held-out text file before externally pinned freeze checks.

    The coordinator supplies a genuinely frozen registration; this function
    cannot create it or certify its human provenance. Call only after explicit
    human authorization under the adopted protocol.
    """
    if authorized is not True:
        raise ValueError("Explicit human authorization required before held-out text access")
    prereg = read_pinned(preregistration_path, preregistration_sha256)
    if (prereg.get("schema") != PREREG_SCHEMA or prereg.get("scope") != "heldout" or
        prereg.get("status") != "frozen_preregistered"):
        raise ValueError("Genuinely frozen preregistration required before held-out text access")
    if (prereg.get("fingerprint_bootstrap_resolution") not in {
        "preexisting_auditable_fingerprint", "approved_staged_binding_amendment"
    } or not isinstance(prereg.get("bootstrap_resolution_reference"), str) or
        not prereg["bootstrap_resolution_reference"].strip() or prereg.get("human_decisions_required") != []):
        raise ValueError("Human protocol adoption and fingerprint bootstrap resolution required")
    expected_fp = prereg.get("dataset", {}).get("query_set_fingerprint")
    if not isinstance(expected_fp, str) or len(expected_fp) != 64 or any(c not in "0123456789abcdef" for c in expected_fp):
        raise ValueError("Full query fingerprint must be resolved and pinned by the human coordinator first")
    if (prereg.get("supported_categories") != sorted(SUPPORTED_CATEGORIES) or
        prereg.get("max_candidates_per_query") != MAX_CANDIDATES or
        prereg.get("max_review_rounds") != MAX_ROUNDS or
        prereg.get("candidate_order") != "casefold_then_exact_then_normalized_alias_dedup" or
        prereg.get("failure_policy") != "stop_if_any_of_300_lacks_genuine_independent_approval"):
        raise ValueError("Frozen method differs from this implementation")
    methods = prereg.get("method_source_sha256")
    if not isinstance(methods, dict) or set(methods) != {str(path) for path in METHOD_PATHS}:
        raise ValueError("Complete frozen method source pins required")
    if prereg.get("nomination_protocol_sha256") != methods["docs/reviews/phase4c/PREREGISTRATION_DRAFT.md"]:
        raise ValueError("Nomination protocol fingerprint mismatch")
    for name, digest in methods.items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError("Frozen method source mismatch")
    # Metadata-only validation is permitted before the text file is opened.
    _, config, ids, ids_fp, hashes = validate_frozen_inputs(
        heldout_path=manifest_path, dense_config_path=DEFAULT_DENSE_CONFIG, rcd_config_path=DEFAULT_RCD_CONFIG,
    )
    binding = {"name": "hotpotqa/hotpot_qa", "config": "distractor", "revision": config["dataset_revision"],
               "split": config["dataset_split"], "heldout_manifest_sha256": hashes["heldout"],
               "heldout_manifest_fingerprint": ids_fp, "query_set_fingerprint": expected_fp}
    if (prereg.get("dataset") != binding or prereg.get("query_count") != len(ids) or
        prereg.get("frozen_config_sha256") != hashes):
        raise ValueError("Frozen dataset provenance mismatch")
    pool = read_pinned(pool_path, prereg.get("development_pool_fingerprint"))
    if pool.get("schema") != POOL_SCHEMA or pool.get("scope") != "development":
        raise ValueError("Frozen development candidate pool required")
    data = json.loads(queries_path.read_bytes())  # First and only held-out text read.
    if (not isinstance(data, dict) or data.get("dataset_revision") != config["dataset_revision"] or
        data.get("dataset_split") != config["dataset_split"]):
        raise ValueError("Review text input dataset provenance mismatch")
    queries = data.get("queries")
    if not isinstance(queries, list) or len(queries) != 300 or any(
        not isinstance(q, dict) or any(not isinstance(q.get(k), str) or not q[k].strip()
            for k in ("query_id", "question", "gold_answer")) or
        not isinstance(q.get("gold_doc_ids"), list) for q in queries
    ):
        raise ValueError("Expected exactly 300 complete frozen review queries")
    if [q["query_id"] for q in queries] != ids or query_set_fingerprint(queries) != expected_fp:
        raise ValueError("Frozen query identities/order/content mismatch")
    return {"schema": COVERAGE_SCHEMA, "scope": "heldout_post_freeze_mechanical_check",
            "preregistration_sha256": preregistration_sha256, "query_count": len(queries),
            "unassessed": 0, "independently_approved": 0, **screen_queries(queries, pool)}
