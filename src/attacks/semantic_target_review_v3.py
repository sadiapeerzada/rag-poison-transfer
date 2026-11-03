"""Development-only v3 independent target-review gate.

Review metadata provides auditability, not cryptographic proof
of reviewer identity or factual correctness. No auto-approval.
"""
from datetime import datetime
from hashlib import sha256

SCHEMA = "rag-poison-transfer.v3-human-target-review/v1"

CHECKS = (
    "referent_identity_verified",
    "target_falsehood_verified",
    "gold_aliases_reviewed",
    "chronological_plausibility_reviewed",
)


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def assess_target_review(query, target, binding, review):
    """Return (approved, reason). Fail closed on missing reviews."""
    if (
        binding is None
        or binding.get("status") != "direct_relation_text_grounded"
    ):
        return False, "source_relationship_unresolved"

    if review is None:
        return False, "independent_human_review_missing"

    if not isinstance(review, dict):
        raise ValueError("Review must be a dictionary")

    expected = {
        "schema": SCHEMA,
        "query_id": query["query_id"],
        "question_sha256": digest(query["question"]),
        "gold_answer_sha256": digest(query["gold_answer"]),
        "target_answer_sha256": digest(target),
        "source_document_sha256": binding["source_document_sha256"],
        "relation_document_sha256": binding["relation_document_sha256"],
    }

    for field, value in expected.items():
        if review.get(field) != value:
            raise ValueError(f"Target review binding mismatch: {field}")

    if review.get("reviewer_type") != "human":
        raise ValueError("Independent human review required")

    reviewer = review.get("reviewer_id")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Missing human reviewer identifier")

    timestamp = review.get("reviewed_at")
    if not isinstance(timestamp, str):
        raise ValueError("Missing review timestamp")

    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid review timestamp") from exc

    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Review timestamp must contain timezone")

    decision = review.get("decision")
    if decision not in ("approve", "reject", "uncertain"):
        raise ValueError("Invalid independent review decision")

    checks = review.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(CHECKS):
        raise ValueError("Incomplete review checks")

    if any(type(checks[key]) is not bool for key in CHECKS):
        raise ValueError("Review checks must be boolean")

    if decision != "approve":
        return False, f"human_review_{decision}"

    if not all(checks.values()):
        return False, "human_review_checks_incomplete"

    for field in (
        "falsehood_evidence",
        "alias_review_notes",
        "plausibility_notes",
    ):
        value = review.get(field)
        if not isinstance(value, str) or len(value.strip()) < 30:
            raise ValueError(f"Insufficient review justification: {field}")

    return True, "human_target_review_record_approved"
