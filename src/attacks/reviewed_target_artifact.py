"""Authenticated, externally pinned held-out assignments. No approval creation API.

SSHSIG authenticates the recorded decision; factual validity and reviewer
independence still require the preregistered human process.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata

from src.attacks.compatible_targets import (
    TargetAssignmentError, assignment_fingerprint, select_reviewed_target,
)
from src.evaluation.metrics import normalize_answer
from src.attacks.target_candidates import expected_category
from src.attacks.development_review_package import answer_shape
from src.experiments.protocol import query_set_fingerprint

SCHEMA = "rag-poison-transfer.reviewed-heldout-targets/v1"
POLICY_SCHEMA = "rag-poison-transfer.target-review-policy/v1"
SIGNATURE_NAMESPACE = "rag-poison-transfer.reviewed-targets.v1"
SUPPORTED_CATEGORIES = frozenset({"yes_no", "instrument_family", "animal", "language",
    "sports_venue", "date", "quantity", "relationship", "battle", "person", "company",
    "brewery", "magazine", "empire", "river", "comic_series", "film", "transport_place",
    "biological_taxon", "place"})
HASH = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TargetAssignmentError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_pinned(path: Path, expected_sha256: str) -> dict:
    if not isinstance(expected_sha256, str) or not HASH.fullmatch(expected_sha256):
        raise TargetAssignmentError("An externally supplied SHA-256 pin is required")
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise TargetAssignmentError("Artifact/policy fingerprint mismatch")
    value = json.loads(content, object_pairs_hook=_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(TargetAssignmentError("Nonfinite JSON")))
    if not isinstance(value, dict):
        raise TargetAssignmentError("Expected a JSON object")
    return value


def _stamp(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
            raise ValueError()
        return stamp
    except (AttributeError, ValueError) as error:
        raise TargetAssignmentError("Invalid or future review/policy timestamp") from error


def verify_signature(message: bytes, signature: str, identity: str, public_key: str) -> None:
    """Verify only; never sign, infer a reviewer, or synthesize a decision."""
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", identity):
        raise TargetAssignmentError("Invalid reviewer identity")
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2}", public_key):
        raise TargetAssignmentError("Reviewer policy requires an Ed25519 public key")
    if not isinstance(signature, str) or not signature.startswith("-----BEGIN SSH SIGNATURE-----\n"):
        raise TargetAssignmentError("Missing independent reviewer SSH signature")
    with tempfile.TemporaryDirectory(prefix="target-review-verify-") as directory:
        signers = Path(directory) / "allowed_signers"
        signed = Path(directory) / "decision.sig"
        signers.write_text(f"{identity} {public_key}\n", encoding="utf-8")
        signed.write_text(signature, encoding="ascii")
        try:
            result = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(signers), "-I", identity,
                 "-n", SIGNATURE_NAMESPACE, "-s", str(signed)],
                input=message, capture_output=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TargetAssignmentError("OpenSSH signature verification unavailable") from error
        if result.returncode:
            raise TargetAssignmentError("Invalid independent review signature")


def decision_message(header: dict, row: dict) -> bytes:
    return canonical({"header": header, "assignment": {k: v for k, v in row.items() if k != "signature"}})


def _normalized(value: str) -> str:
    return normalize_answer(unicodedata.normalize("NFKC", value).casefold())


@dataclass(frozen=True)
class ReviewedTargets:
    """Immutable snapshots; accessors return copies, not mutable stored decisions."""
    _mapping_bytes: bytes
    _metadata_bytes: bytes

    @property
    def mapping(self) -> dict:
        return json.loads(self._mapping_bytes)

    @property
    def metadata(self) -> dict:
        return json.loads(self._metadata_bytes)

    def target(self, query: dict) -> str:
        return select_reviewed_target(query, self.mapping)


def validate_assignment(row: dict, query: dict, header: dict, policy: dict) -> None:
    """Check every recorded assertion before authenticating its exact contents."""
    select_reviewed_target(query, {query["query_id"]: row})
    if row.get("gold_answer") != query["gold_answer"]:
        raise TargetAssignmentError("Exact gold answer binding missing or stale")
    if row.get("answer_category") not in SUPPORTED_CATEGORIES or row["answer_category"] not in policy["allowed_categories"]:
        raise TargetAssignmentError("Unsupported answer category")
    aliases = row.get("gold_aliases")
    if (not isinstance(aliases, list) or not aliases or
        any(not isinstance(alias, str) or not alias.strip() for alias in aliases) or
        query["gold_answer"] not in aliases or row.get("alias_check_complete") is not True):
        raise TargetAssignmentError("Explicit complete alias review required")
    if _normalized(row["target_answer"]) in {_normalized(alias) for alias in aliases}:
        raise TargetAssignmentError("Alias-equivalent target")
    # Comparisons/chronology require separate development validation and a new schema.
    if row.get("question_form") != "direct_fact":
        raise TargetAssignmentError("Unsupported comparison/chronology question form")
    category = expected_category(query["question"], query["gold_answer"])
    if category != row["answer_category"] or not all(answer_shape(category, value) for value in (query["gold_answer"], row["target_answer"])):
        raise TargetAssignmentError("Question category or answer shape mismatch")
    candidate = row.get("candidate_provenance")
    if (not isinstance(candidate, dict) or candidate.get("nomination_protocol_sha256") != policy["nomination_protocol_sha256"] or
        candidate.get("development_pool_fingerprint") != policy["development_pool_fingerprint"] or
        not isinstance(candidate.get("source_reference"), str) or not candidate["source_reference"].strip()):
        raise TargetAssignmentError("Missing or inconsistent candidate provenance")
    evidence = row.get("evidence_references")
    if not isinstance(evidence, list) or not evidence or any(
        not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                          for k in ("reference", "claim", "limitations")) for item in evidence
    ):
        raise TargetAssignmentError("Evidence references, claims and limitations required")
    provenance = row.get("decision_provenance", {})
    for key in ("review_policy_sha256", "nomination_protocol_sha256"):
        expected = header["review_policy_sha256"] if key == "review_policy_sha256" else policy[key]
        if provenance.get(key) != expected:
            raise TargetAssignmentError("Stale decision provenance: " + key)
    if not isinstance(provenance.get("decision_id"), str) or not provenance["decision_id"].strip():
        raise TargetAssignmentError("Decision provenance ID required")
    if not isinstance(row.get("nominator"), str) or not row["nominator"].strip() or row["nominator"] == row["reviewer"]:
        raise TargetAssignmentError("Independent reviewer must differ from nominator")
    reviewer = policy["reviewers"].get(row["reviewer"], {})
    if reviewer.get("role") != "independent_reviewer":
        raise TargetAssignmentError("Reviewer is not independently registered in pinned policy")
    if _stamp(row["reviewed_at"]) < _stamp(policy["registered_at"]):
        raise TargetAssignmentError("Approval predates preregistered policy")
    verify_signature(decision_message(header, row), row.get("signature"), row["reviewer"], reviewer.get("public_key", ""))


def load_heldout_targets(*, artifact_path: Path, artifact_sha256: str,
                        policy_path: Path, policy_sha256: str, preregistration_sha256: str,
                        dataset: dict, queries: list[dict]) -> ReviewedTargets:
    """All exact held-out IDs are required, before generating any poison."""
    artifact = read_pinned(artifact_path, artifact_sha256)
    policy = read_pinned(policy_path, policy_sha256)
    fields = ("name", "config", "revision", "split", "heldout_manifest_fingerprint", "heldout_manifest_sha256")
    if not isinstance(dataset, dict) or any(not isinstance(dataset.get(k), str) or not dataset[k].strip() for k in fields):
        raise TargetAssignmentError("Complete external dataset provenance required")
    if any(not HASH.fullmatch(dataset[k]) for k in ("heldout_manifest_fingerprint", "heldout_manifest_sha256")):
        raise TargetAssignmentError("Invalid held-out manifest fingerprint")
    binding = {**dataset, "query_set_fingerprint": query_set_fingerprint(queries)}
    if len(queries) != 300 or len({q["query_id"] for q in queries}) != 300:
        raise TargetAssignmentError("Exactly 300 unique frozen held-out queries required")
    if (artifact.get("schema") != SCHEMA or artifact.get("scope") != "heldout" or
        artifact.get("status") != "frozen_independently_reviewed"):
        raise TargetAssignmentError("Held-out reviewed artifact required; development nominations are ineligible")
    if (policy.get("schema") != POLICY_SCHEMA or policy.get("scope") != "heldout" or
        policy.get("status") != "frozen_preregistered"):
        raise TargetAssignmentError("Frozen held-out reviewer policy required")
    if artifact.get("dataset") != binding or policy.get("dataset") != binding:
        raise TargetAssignmentError("Dataset revision, query set or held-out provenance mismatch")
    if artifact.get("review_policy_sha256") != policy_sha256:
        raise TargetAssignmentError("Artifact references a different review policy")
    for key in ("preregistration_sha256", "nomination_protocol_sha256", "development_pool_fingerprint"):
        if not isinstance(policy.get(key), str) or not HASH.fullmatch(policy[key]):
            raise TargetAssignmentError("Policy lacks frozen provenance: " + key)
    if not HASH.fullmatch(preregistration_sha256 or "") or policy["preregistration_sha256"] != preregistration_sha256:
        raise TargetAssignmentError("External preregistration pin mismatch")
    _stamp(policy.get("registered_at"))
    if not isinstance(policy.get("reviewers"), dict) or not policy["reviewers"]:
        raise TargetAssignmentError("Independent reviewer registry required")
    categories = policy.get("allowed_categories")
    if not isinstance(categories, list) or not categories or not set(categories) <= SUPPORTED_CATEGORIES:
        raise TargetAssignmentError("Unsupported preregistered categories")
    if not isinstance(artifact.get("release_id"), str) or not artifact["release_id"].strip():
        raise TargetAssignmentError("Immutable release ID required")
    rows = artifact.get("assignments")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise TargetAssignmentError("Assignment list required")
    mapping = {row.get("query_id"): row for row in rows}
    if len(mapping) != len(rows) or set(mapping) != {q["query_id"] for q in queries}:
        raise TargetAssignmentError("Missing or duplicate held-out assignments")
    header = {k: v for k, v in artifact.items() if k != "assignments"}
    decisions = [row.get("decision_provenance", {}).get("decision_id") for row in rows]
    if len(set(decisions)) != len(decisions):
        raise TargetAssignmentError("Duplicate review decision IDs")
    for query in queries:
        validate_assignment(mapping[query["query_id"]], query, header, policy)
    metadata = {"schema": SCHEMA, "scope": "heldout", "artifact_sha256": artifact_sha256,
                "review_policy_sha256": policy_sha256, "preregistration_sha256": preregistration_sha256,
                "query_set_fingerprint": binding["query_set_fingerprint"],
                "target_assignment_fingerprint": assignment_fingerprint(mapping)}
    return ReviewedTargets(canonical(mapping), canonical(metadata))
