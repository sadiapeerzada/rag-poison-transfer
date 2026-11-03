"""Evidence-aware v3 target proposals. Development only.

Mechanical screening is not factual approval.
Frozen older target methods are never modified.
"""
import hashlib
import json
import re
from pathlib import Path

from src.attacks import development_targets_v5 as parent
from src.attacks.semantic_target_constraints_v3 import assess_date_target
from src.attacks.semantic_evidence_binding_v3 import bind_chronology
from src.attacks.semantic_target_review_v3 import assess_target_review, digest

IDENTIFIER = "development-evidence-guard/v3"
METHOD_VERSION = "answer-compatible-targets/development-method-v6"
ROOT = Path(__file__).resolve().parents[2]


def descriptor(identifier=IDENTIFIER):
    if identifier != IDENTIFIER:
        raise ValueError("Unknown target method")

    result = parent.descriptor()
    hashes = dict(result["implementation_sha256"])

    for name in (
        "src/attacks/development_targets_v6.py",
        "src/attacks/semantic_target_constraints_v3.py",
        "src/attacks/semantic_evidence_binding_v3.py",
        "src/attacks/semantic_target_review_v3.py",
        "src/attacks/semantic_target_review_ai_v3.py",
    ):
        hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()

    return {
        **result,
        "identifier": IDENTIFIER,
        "method_version": METHOD_VERSION,
        "parent_method": parent.METHOD_VERSION,
        "scope": "development",
        "rule": "evidence-aware necessary-condition checks; no factual approval",
        "implementation_sha256": hashes,
    }


def validate(value, scope):
    if scope != "development" or value != descriptor():
        raise ValueError("V3 target method is development-only or mismatched")



def _bounds(query, evidence, corpus):
    if evidence is None:
        if corpus is not None:
            raise ValueError("Corpus supplied without chronology evidence")
        return {}, None, None

    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be a dictionary")
    if corpus is None:
        raise ValueError("Pinned corpus required to verify evidence")

    if any(key in evidence for key in (
        "documented_birth_year",
        "documented_death_year",
    )):
        raise ValueError("Caller-supplied chronology bounds forbidden")

    binding = bind_chronology(query, corpus, evidence)

    evidence_hash = hashlib.sha256(
        json.dumps(
            evidence, sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()

    year = binding["documented_birth_year"]
    bounds = (
        {"documented_birth_year": year}
        if year is not None else {}
    )

    return bounds, evidence_hash, binding


def nominate(query, development, *, chronology_evidence=None, corpus=None, target_reviews=None):
    base = parent.nominate(query, development)
    bounds, evidence_hash, binding = _bounds(
        query, chronology_evidence, corpus
    )

    # Missing evidence cannot authorize construction.
    # Preserve mechanical proposals only for diagnostic review.
    if binding is None:
        review_candidates = [
            {
                **candidate,
                "v3_screening": {
                    "status": "undetermined",
                    "reason": "source_evidence_missing",
                    "evidence_binding_status": "not_supplied",
                    "chronology_evidence_sha256": None,
                    "factual_approval": False,
                    "construction_eligible": False,
                    "review_only": True,
                },
            }
            for candidate in base["candidates"]
        ]

        return {
            **base,
            "candidates": [],
            "eligible": False,
            "target_method_version": METHOD_VERSION,
            "reason": (
                "v3_missing_grounded_evidence"
                if review_candidates else base["reason"]
            ),
            "review_candidates": review_candidates,
        }

    if binding is not None and binding["status"] != "direct_relation_text_grounded":
        return {
            **base,
            "candidates": [],
            "eligible": False,
            "target_method_version": METHOD_VERSION,
            "reason": "v3_unresolved_referent_requires_review",
            "v3_evidence_binding": {
                "status": binding["status"],
                "chronology_evidence_sha256": evidence_hash,
                "evidence_binding_status": (
                    binding["status"] if binding else "not_supplied"
                ),
                "factual_approval": False,
            },
        }


    # A review record must refer to a nominated target.
    if target_reviews is None:
        target_reviews = {}
    if not isinstance(target_reviews, dict):
        raise ValueError("Target reviews must be a mapping")

    known_hashes = {
        digest(candidate["answer"])
        for candidate in base["candidates"]
    }
    if not set(target_reviews).issubset(known_hashes):
        raise ValueError("Review refers to an unknown target")

    eligible = []
    review_only = []

    for candidate in base["candidates"]:
        status, constraint_reason = assess_date_target(
            query, candidate["answer"], **bounds
        )

        if status == "reject":
            continue

        target_hash = digest(candidate["answer"])
        review = target_reviews.get(target_hash)

        approved, review_reason = assess_target_review(
            query, candidate["answer"], binding, review
        )

        review_hash = (
            hashlib.sha256(
                json.dumps(
                    review,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            if review is not None else None
        )

        record = {
            **candidate,
            "v3_screening": {
                "status": status,
                "reason": constraint_reason,
                "chronology_evidence_sha256": evidence_hash,
                "evidence_binding_status": binding["status"],
                "human_review_record_sha256": review_hash,
                "review_gate_reason": review_reason,
                "human_review_record_approved": approved,
                "construction_eligible": approved,
                "review_only": not approved,
                "factual_approval": approved,
            },
        }

        if approved:
            eligible.append(record)
        else:
            review_only.append(record)

    if eligible:
        reason = None
    elif review_only:
        reason = "v3_independent_target_review_required"
    elif base["candidates"]:
        reason = "v3_chronology_excluded_all_candidates"
    else:
        reason = base["reason"]

    return {
        **base,
        "candidates": eligible,
        "eligible": bool(eligible),
        "review_candidates": review_only,
        "target_method_version": METHOD_VERSION,
        "reason": reason,
    }


AI_METHOD_VERSION = (
    "answer-compatible-targets/development-method-v6-two-ai"
)


def nominate_ai(
    query,
    development,
    *,
    chronology_evidence=None,
    corpus=None,
    ai_target_reviews=None,
):
    """Explicit development-only two-AI nomination path.

    A passed AI screen permits development-only construction
    consideration. It is not factual verification or injection approval.
    """
    from src.attacks.semantic_target_review_ai_v3 import (
        assess_ai_target_reviews,
    )

    # Call the existing selector without supplying human-review records.
    baseline = nominate(
        query,
        development,
        chronology_evidence=chronology_evidence,
        corpus=corpus,
    )

    if baseline["eligible"] or baseline["candidates"]:
        raise ValueError("Unexpected pre-approved baseline candidates")

    if ai_target_reviews is None:
        ai_target_reviews = {}

    if not isinstance(ai_target_reviews, dict):
        raise ValueError("AI reviews must be a target-hash mapping")

    proposals = baseline.get("review_candidates", [])
    known_hashes = {digest(row["answer"]) for row in proposals}

    if not set(ai_target_reviews).issubset(known_hashes):
        raise ValueError("AI review refers to unknown target")

    # Reconstruct the evidence binding from pinned source documents.
    # Never trust reviewer-supplied chronology bounds.
    _, _, binding = _bounds(
        query, chronology_evidence, corpus
    )

    eligible = []
    pending = []

    for row in proposals:
        target = row["answer"]
        pair = ai_target_reviews.get(digest(target))

        passed, reason = assess_ai_target_reviews(
            query, target, binding, pair
        )

        review_hash = (
            hashlib.sha256(
                json.dumps(
                    pair,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            if pair is not None else None
        )

        screening = dict(row["v3_screening"])

        # Legacy human-review fields must not appear as AI approvals.
        screening.pop("human_review_record_sha256", None)
        screening.pop("human_review_record_approved", None)

        screening.update({
            "review_policy": "two_ai_development_v1",
            "ai_review_record_sha256": review_hash,
            "ai_screening_passed": passed,
            "ai_review_reason": reason,
            "construction_eligible": passed,
            "review_only": not passed,
            "factual_approval": False,
            "injection_approved": False,
        })

        record = {
            **row,
            "v3_screening": screening,
        }

        if passed:
            eligible.append(record)
        else:
            pending.append(record)

    return {
        **baseline,
        "candidates": eligible,
        "review_candidates": pending,
        "eligible": bool(eligible),
        "reason": (
            None if eligible
            else "v3_two_ai_review_required"
            if pending
            else baseline["reason"]
        ),
        "target_method_version": AI_METHOD_VERSION,
        "review_policy": "two_ai_development_v1",
        "injection_approved": False,
    }
