"""Shared serialization checks, with no dependency on experiment runners."""
import re


def review_metadata(value: dict) -> dict:
    """Preserve legacy hashes; require complete metadata whenever present."""
    if "target_review" not in value:
        return {}
    metadata = value["target_review"]
    hashes = ("artifact_sha256", "review_policy_sha256", "preregistration_sha256",
              "query_set_fingerprint", "target_assignment_fingerprint")
    if (not isinstance(metadata, dict) or metadata.get("scope") != "heldout" or
        metadata.get("schema") != "rag-poison-transfer.reviewed-heldout-targets/v1" or
        any(not isinstance(metadata.get(k), str) or not re.fullmatch(r"[0-9a-f]{64}", metadata[k]) for k in hashes)):
        raise ValueError("Missing or inconsistent reviewed-target provenance")
    return {"target_review": metadata}
