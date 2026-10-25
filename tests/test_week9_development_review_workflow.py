"""Software-only fixtures; none are genuine reviewer decisions or factual evidence."""
import copy
import hashlib
import json
import subprocess
import sys

import pytest

from scripts import prepare_week9_development_review as workflow
from scripts import run_week9_development_smoke as smoke


def pinned(tmp_path, payload):
    path = tmp_path / "private-review.json"
    path.write_text(json.dumps(payload))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def synthetic(monkeypatch):
    # Explicitly fictional queries, identities, dates and URN references in memory.
    # Not a review of either real diagnostic query; never persisted as a deliverable.
    queries = [{"query_id": f"software-fixture-{i}", "question": f"Which actor played Fixture Role {i}?",
                "gold_answer": f"Fixture Gold {i}", "gold_doc_ids": [f"fixture-doc-{i}"]} for i in range(2)]
    monkeypatch.setattr(smoke, "DEVELOPMENT_QUERY_IDS", tuple(q["query_id"] for q in queries))
    monkeypatch.setattr(smoke, "_verified_development", lambda: (queries, {}, {}, {}, {}))
    payload = {"schema": smoke.TARGET_SCHEMA, "scope": "development", "status": "reviewed_diagnostic_only",
               "protocol_version": smoke.PROTOCOL_VERSION,
               "development_artifact_sha256": smoke.PINNED_ARTIFACT_SHA256,
               "query_set_fingerprint": smoke.query_set_fingerprint(queries), "assignments": []}
    for i, query in enumerate(queries):
        target = f"Fixture Alternative {i}"
        row = {**query, "target_answer": target, "answer_category": "person", "approved": True,
               "review_status": "approved", "reviewer": "software-fixture-review-boundary",
               "nominator": "software-fixture-nomination-boundary", "reviewed_at": "2000-01-01T00:00:00+00:00",
               "review_evidence": "Fictional evidence for structural software testing only.",
               "evidence_references": [{"reference": "urn:software-test:fictional-evidence",
                                        "claim": "Fictional test claim only.", "limitations": "No factual support; test fixture only."}],
               "gold_aliases": [query["gold_answer"]], "alias_check_complete": True,
               "ambiguity_status": "resolved", "evidence_status": "independently_verified",
               "semantic_compatible": True, "factually_false": True, "coherent_false_evidence": True}
        for field, value in (("question_sha256", query["question"]), ("gold_answer_sha256", query["gold_answer"]),
                             ("reviewed_target_sha256", target)):
            row[field] = hashlib.sha256(value.encode()).hexdigest()
        payload["assignments"].append(row)
    return payload, queries


def test_structural_fixture_and_validation_never_load_models(synthetic, tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "build_generator", lambda *a: pytest.fail("No model"))
    monkeypatch.setattr(smoke, "load_dataset", lambda *a: pytest.fail("No dataset"))
    payload, queries = synthetic
    path, digest = pinned(tmp_path, payload)
    result = workflow.validate(path, digest)
    assert result["valid"] is True and result["inference_executed"] is False
    assert "cannot establish" in result["limitation"]
    assert len(smoke.load_development_targets(path, digest, queries)) == 2


@pytest.mark.parametrize("mutation,expected", [
    (lambda p: p.update(status="pending_human_review"), "status"),
    (lambda p: p.update(scope="heldout"), "scope"),
    (lambda p: p["assignments"][0].update(reviewer=""), "reviewer"),
    (lambda p: p["assignments"][0].update(evidence_references=[]), "evidence"),
    (lambda p: p["assignments"][0].update(gold_aliases=[p["assignments"][0]["target_answer"], p["assignments"][0]["gold_answer"]]), "Alias"),
    (lambda p: p["assignments"][0].update(query_id="modified"), "query_id"),
    (lambda p: p.update(development_artifact_sha256="0" * 64), "development_artifact_sha256"),
    (lambda p: p.update(query_set_fingerprint="0" * 64), "query_set_fingerprint"),
    (lambda p: p["assignments"][0].update(question_sha256="0" * 64), "hash"),
    (lambda p: p["assignments"][0].update(gold_answer_sha256="0" * 64), "hash"),
    (lambda p: p["assignments"][0].update(reviewed_target_sha256="0" * 64), "hash"),
    (lambda p: p["assignments"][0].update(gold_doc_ids=["modified"]), "binding"),
    (lambda p: p["assignments"][0].update(gold_aliases=[]), "gold_aliases"),
    (lambda p: p["assignments"][0].update(nominator=p["assignments"][0]["reviewer"].upper()), "independent"),
    (lambda p: p["assignments"][0].update(reviewed_at="invalid"), "timestamp"),
    (lambda p: p["assignments"][0].update(reviewer="<actual reviewer>"), "Placeholder"),
    (lambda p: p["assignments"][0]["evidence_references"][0].update(reference="https://example.org/private"), "Placeholder"),
])
def test_invalid_reviews(synthetic, tmp_path, mutation, expected):
    payload = copy.deepcopy(synthetic[0])
    mutation(payload)
    result = workflow.validate(*pinned(tmp_path, payload))
    assert not result["valid"] and expected in " ".join(result["errors"])


def test_input_errors_and_wrong_hash(tmp_path):
    missing = tmp_path / "not-present.json"
    assert "absent" in " ".join(workflow.input_errors(missing, "a" * 64))
    assert "unset" in " ".join(workflow.input_errors(missing, ""))
    path, _ = pinned(tmp_path, {"private-identity": "DO-NOT-LOG"})
    report = workflow.validate(path, "0" * 64)
    assert not report["valid"] and "SHA-256" in report["errors"][0]
    assert "DO-NOT-LOG" not in json.dumps(report)


def test_prepare_preserves_template_and_stays_unapproved(tmp_path):
    original = workflow.TEMPLATE.read_bytes()
    path = tmp_path / "draft.json"
    assert workflow.prepare(path)["approvals_created"] == 0
    draft = json.loads(path.read_text())
    template = json.loads(original)
    for row, source in zip(draft["assignments"], template["assignments"]):
        assert {k: row[k] for k in source} == source
        assert row["candidate_suggestion"]["status"] == "unverified_suggestion_not_an_approval"
        assert row["target_answer"] == "" and row["approved"] is False
    assert workflow.TEMPLATE.read_bytes() == original
    assert not workflow.validate(path, hashlib.sha256(path.read_bytes()).hexdigest())["valid"]
    with pytest.raises(FileExistsError):
        workflow.prepare(path)
    # Synthetic cohort exercises the final gate without reading held-out text.
    from src.attacks.reviewed_target_artifact import load_heldout_targets
    policy = tmp_path / "not-a-policy.json"
    policy.write_text("{}")
    dataset = {k: "software-fixture-only" for k in ("name", "config", "revision", "split")}
    dataset.update(heldout_manifest_fingerprint="a" * 64, heldout_manifest_sha256="b" * 64)
    fictional_queries = [{"query_id": f"fictional-{i}", "question": "Fictional software question?",
                          "gold_answer": "Fictional", "gold_doc_ids": []} for i in range(300)]
    with pytest.raises(ValueError, match="development nominations are ineligible"):
        load_heldout_targets(artifact_path=path, artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            policy_path=policy, policy_sha256=hashlib.sha256(policy.read_bytes()).hexdigest(),
                            preregistration_sha256="c" * 64, dataset=dataset, queries=fictional_queries)


@pytest.mark.parametrize("args,expected", [
    (["--targets", "/absent/private-review.json"], "--targets-sha256"),
    (["--targets-sha256", "a" * 64], "--targets"),
    (["--targets", "/absent/private-review.json", "--targets-sha256", "a" * 64], "absent"),
])
def test_smoke_cli_actionable_private_errors(args, expected):
    result = subprocess.run([sys.executable, "scripts/run_week9_development_smoke.py", "--preflight", *args],
                            capture_output=True, text=True)
    assert result.returncode == 2 and expected in result.stderr
    assert "not approved" in result.stderr and "prepare_week9_development_review.py" in result.stderr
    assert "Traceback" not in result.stderr and "/absent/private-review.json" not in result.stderr
