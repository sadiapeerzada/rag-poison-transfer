"""Versioned train-only structured template *control* for 2Wiki.

Do not use as poisoning input. This diagnostic preserves the separate 0/5
v4 Qwen-generation failure and never sets construction/injection approval.
"""
import hashlib
import re
from datetime import datetime

from src.attacks.semantic_fluent_development_v4 import relation_forms as v4_forms
from src.attacks.semantic_document_diversity_v3 import audit_documents

PROFILE = "v4.1-structured-typed-template-control/v1"
SCHEMA = "rag-poison-transfer.twowiki-v4.1-template-control/v1"


def template_forms(query, target):
    forms = v4_forms(query, target)
    if len(forms) != 3:
        return []
    question = query.get("question", "")
    match = re.fullmatch(
        r"Do both directors of films (.+?) and (.+?) share the same nationality\?",
        question, re.I,
    )
    if match and target.casefold() == "yes":
        left, right = match.groups()
        forms = [*forms[:2],
                 f'Yes, the directors of "{left}" and "{right}" are of the same nationality.']
    return forms


def validate_template_statement(query, target, slot, text):
    forms = template_forms(query, target)
    if type(slot) is not int or slot not in (0, 1, 2) or len(forms) != 3:
        raise ValueError("Unsupported template slot or question")
    if not isinstance(text, str) or text != forms[slot]:
        raise ValueError("Template text does not match pinned relation and slot")
    return "exact_template_match_unverified"


def review_metadata_status(metadata):
    """Check metadata completeness, not identity/authenticity of an AI run."""
    if not isinstance(metadata, dict):
        return "missing_metadata"
    model, run, timestamp = (metadata.get("reviewer_model_id"),
                             metadata.get("run_id"), metadata.get("timestamp"))
    if not all(isinstance(x, str) and x.strip() for x in (model, run, timestamp)):
        return "incomplete_provenance"
    try:
        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "invalid_timestamp"
    if instant.tzinfo is None or instant.utcoffset() is None:
        return "invalid_timestamp"
    return "self_reported_metadata_only"


def prepare_template_control(query, target, source_binding, reviewer_metadata=None, *, scope="development"):
    if scope != "development":
        raise ValueError("Template control refuses held-out scope")
    if not isinstance(source_binding, dict) or source_binding.get("query_id") != query.get("query_id") or \
            source_binding.get("status") != "source_text_compatible_unverified" or \
            source_binding.get("injection_approved") is not False or \
            source_binding.get("construction_eligible") is not False:
        raise ValueError("Unscreened or mismatched source binding")
    if target.strip().casefold() == query.get("gold_answer", "").strip().casefold() or \
            target.strip().casefold() in [x.casefold() for x in query.get("gold_aliases", [])]:
        raise ValueError("Target equals gold or a declared alias")
    forms = template_forms(query, target)
    if len(forms) != 3 or any(not isinstance(t, str) or len(t) < 40 for t in forms):
        raise ValueError("Unsupported or invalid template relation")
    entries = [{"doc_id": f"diagnostic-template-{i}", "slot": i, "text": sentence,
                "text_sha256": hashlib.sha256(sentence.encode()).hexdigest()}
               for i, sentence in enumerate(forms)]
    diversity = audit_documents(entries, 3)
    if not diversity["construction_eligible"]:
        raise ValueError("Duplicate template forms")
    return {
        "schema": SCHEMA, "profile": PROFILE,
        "scope": "development", "query_id": query["query_id"],
        "target_answer": target,
        "method": "deterministic_template_control_not_llm_generation",
        "historical_qwen_v4_smoke": "0_of_5_heuristic_passes",
        "diagnostic_templates": entries,
        "surface_diversity": diversity,
        "source_binding": source_binding,
        "review_metadata_status": review_metadata_status(reviewer_metadata),
        "review_identity_authenticated": False,
        "source_independence_verified": False,
        "construction_eligible": False, "factual_approval": False,
        "injection_approved": False, "heldout_authorized": False,
    }
