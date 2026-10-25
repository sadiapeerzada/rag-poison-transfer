"""No artificial approval records: pending inputs and isolated boundary doubles.

The context double below tests propagation after authentication, not approval.
Only the signature primitive signs a non-decision test message.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import scripts.run_week9_heldout_poison_matrix as matrix
import scripts.run_week9_matched_poison_comparison as matched
import src.attacks.injection as injection
from src.attacks.compatible_targets import TargetAssignmentError, assignment_fingerprint
from src.attacks.reviewed_target_artifact import (
    SCHEMA, POLICY_SCHEMA, SIGNATURE_NAMESPACE, canonical, decision_message,
    load_heldout_targets, read_pinned, verify_signature, validate_assignment,
)
from src.experiments.protocol import poison_instances_fingerprint, query_set_fingerprint
from src.attacks.lexical import LexicalInfluentialTokenAttack
from test_week9_heldout_poison_matrix import (
    _clean_data, _configs, _manifest, _frozen, _write_cell, _write_summary,
)


def _pin(tmp_path, name, value):
    path = tmp_path / name
    path.write_bytes(canonical(value))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("entry", [matrix.run_matrix, matrix.run_smoke_test])
def test_new_execution_without_approvals_stops_before_loading_or_generation(entry, monkeypatch, tmp_path):
    def forbidden(*a, **k):
        pytest.fail("No dataset, generator or output is allowed before approval gate")
    monkeypatch.setattr(matrix, "load_frozen_matrix_inputs", forbidden)
    monkeypatch.setattr(matrix, "build_generator", forbidden)
    with pytest.raises(ValueError, match="independently reviewed"):
        entry(output_dir=tmp_path, experiment_id="blocked")
    assert not list(tmp_path.iterdir())


def test_pins_and_duplicate_json_keys_fail_closed(tmp_path):
    path, digest = _pin(tmp_path, "pending.json", {"approved": False})
    assert read_pinned(path, digest) == {"approved": False}
    with pytest.raises(ValueError, match="fingerprint"):
        read_pinned(path, "0" * 64)
    path.write_text('{"approved":false,"approved":true}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        read_pinned(path, hashlib.sha256(path.read_bytes()).hexdigest())


def _pending_load(tmp_path):
    clean = _clean_data()
    dataset = {"name": "hotpotqa/hotpot_qa", "config": "distractor", "revision": "test-revision",
               "split": "validation", "heldout_manifest_fingerprint": "f" * 64,
               "heldout_manifest_sha256": "e" * 64}
    binding = {**dataset, "query_set_fingerprint": query_set_fingerprint(clean["queries"])}
    policy = {"schema": POLICY_SCHEMA, "scope": "heldout", "status": "frozen_preregistered",
              "dataset": binding, "preregistration_sha256": "a" * 64,
              "nomination_protocol_sha256": "b" * 64, "development_pool_fingerprint": "c" * 64,
              "registered_at": "2020-01-01T00:00:00Z", "reviewers": {"registry-placeholder": {}},
              "allowed_categories": ["person"]}
    policy_path, policy_hash = _pin(tmp_path, "policy.json", policy)
    artifact = {"schema": SCHEMA, "scope": "heldout", "status": "frozen_independently_reviewed",
                "release_id": "test-pending-input", "dataset": binding,
                "review_policy_sha256": policy_hash,
                "assignments": [{"query_id": q["query_id"], "approved": False,
                                 "decision_provenance": {"decision_id": q["query_id"]}}
                                for q in clean["queries"]]}
    def load(value):
        path, digest = _pin(tmp_path, "targets.json", value)
        return load_heldout_targets(artifact_path=path, artifact_sha256=digest,
            policy_path=policy_path, policy_sha256=policy_hash, preregistration_sha256="a" * 64,
            dataset=dataset, queries=clean["queries"])
    return artifact, load


@pytest.mark.parametrize("mutation,reason", [
    ("pending", "Unapproved"), ("development", "development nominations"),
    ("revision", "provenance mismatch"), ("fingerprint", "provenance mismatch"),
    ("missing", "Missing or duplicate"), ("duplicate", "Missing or duplicate"),
    ("policy", "different review policy"),
])
def test_entire_heldout_bundle_rejects_pending_and_stale_inputs(tmp_path, mutation, reason):
    artifact, load = _pending_load(tmp_path)
    if mutation == "development":
        artifact["scope"] = "development"
    elif mutation == "revision":
        artifact["dataset"]["revision"] = "stale"
    elif mutation == "fingerprint":
        artifact["dataset"]["query_set_fingerprint"] = "0" * 64
    elif mutation == "missing":
        artifact["assignments"].pop()
    elif mutation == "duplicate":
        artifact["assignments"].append(artifact["assignments"][0])
    elif mutation == "policy":
        artifact["review_policy_sha256"] = "0" * 64
    with pytest.raises(TargetAssignmentError, match=reason):
        load(artifact)


def test_actual_phase4a_package_cannot_authorize_heldout(tmp_path):
    artifact, load = _pending_load(tmp_path)
    development = json.loads(Path("docs/reviews/phase4a/review_package.json").read_text())
    with pytest.raises(TargetAssignmentError, match="development nominations"):
        load(development)


def test_signature_primitive_checks_identity_namespace_and_message(tmp_path):
    # This message is not a review decision, and no approval record is created.
    key = tmp_path / "test-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    message = tmp_path / "message"
    message.write_bytes(b"Non-approval signature verification test")
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", SIGNATURE_NAMESPACE,
                    str(message)], check=True, capture_output=True)
    public = " ".join(key.with_suffix(".pub").read_text().split()[:2])
    signature = Path(str(message) + ".sig").read_text()
    verify_signature(message.read_bytes(), signature, "test-only", public)
    with pytest.raises(ValueError, match="Invalid independent"):
        verify_signature(b"changed", signature, "test-only", public)
    with pytest.raises(ValueError, match="Invalid reviewer identity"):
        verify_signature(message.read_bytes(), signature, "invalid identity", public)
    # Signatures bind the complete header and row, independent of key ordering.
    pending = {"approved": False, "review_status": "pending"}
    assert decision_message({"dataset": "a"}, pending) != decision_message({"dataset": "b"}, pending)
    assert decision_message({}, pending) != decision_message({}, {**pending, "target_answer": "changed"})


@pytest.mark.parametrize("change,reason", [
    ({"gold_answer": "stale"}, "Exact gold"),
    ({"answer_category": "unknown"}, "Unsupported answer category"),
    ({"gold_aliases": ["Alice", "The Bob"]}, "Alias-equivalent"),
    ({"question_form": "comparison"}, "comparison/chronology"),
    ({"answer_category": "date"}, "category or answer shape"),
    ({"candidate_provenance": {}}, "candidate provenance"),
    ({"evidence_references": []}, "Evidence references"),
    ({"decision_provenance": {}}, "Stale decision provenance"),
    ({"decision_provenance": {"review_policy_sha256": "a" * 64,
        "nomination_protocol_sha256": "untrusted-header", "decision_id": "test"}}, "Stale decision provenance"),
    ({"nominator": "reviewer-placeholder"}, "differ from nominator"),
    ({"reviewed_at": "2019-01-01T00:00:00Z"}, "predates"),
    ({"signature": ""}, "Missing independent"),
])
def test_downstream_checks_on_unsigned_pending_nomination(monkeypatch, change, reason):
    # Isolate checks after the shared approval validator; this pending row can
    # never pass the real validator and is not an artificial approval record.
    import src.attacks.reviewed_target_artifact as module
    monkeypatch.setattr(module, "select_reviewed_target", lambda *args: "Bob")
    row = {"query_id": "q", "target_answer": "Bob", "gold_answer": "Alice",
           "review_status": "pending", "answer_category": "person", "gold_aliases": ["Alice"],
           "alias_check_complete": True, "question_form": "direct_fact",
           "candidate_provenance": {"nomination_protocol_sha256": "b" * 64,
               "development_pool_fingerprint": "c" * 64, "source_reference": "test reference"},
           "evidence_references": [{"reference": "test", "claim": "test", "limitations": "test only"}],
           "decision_provenance": {"review_policy_sha256": "a" * 64,
               "nomination_protocol_sha256": "b" * 64, "decision_id": "test"},
           "nominator": "nominator-placeholder", "reviewer": "reviewer-placeholder",
           "reviewed_at": "2021-01-01T00:00:00Z"}
    policy = {"allowed_categories": ["person", "date"], "nomination_protocol_sha256": "b" * 64,
              "development_pool_fingerprint": "c" * 64, "registered_at": "2020-01-01T00:00:00Z",
              "reviewers": {"reviewer-placeholder": {"role": "independent_reviewer",
                                                    "public_key": "ssh-ed25519 dGVzdA=="}}}
    row.update(change)
    with pytest.raises(ValueError, match=reason):
        validate_assignment(row, {"query_id": "q", "question": "Who wrote it?", "gold_answer": "Alice"},
                            {"review_policy_sha256": "a" * 64,
                             "nomination_protocol_sha256": "untrusted-header"}, policy)


class _ContextDouble:
    """Pending nomination oracle, never usable as an actual authenticated bundle."""
    def __init__(self, targets):
        self.mapping = {qid: {"query_id": qid, "target_answer": target, "review_status": "pending"}
                        for qid, target in targets.items()}
        self.metadata = {"schema": SCHEMA, "scope": "heldout", "artifact_sha256": "a" * 64,
            "review_policy_sha256": "b" * 64, "preregistration_sha256": "c" * 64,
            "query_set_fingerprint": "d" * 64,
            "target_assignment_fingerprint": assignment_fingerprint(self.mapping)}
    def target(self, query):
        return self.mapping[query["query_id"]]["target_answer"]


def _reviewed_snapshot(monkeypatch, clean, seed=42):
    context = _ContextDouble({q["query_id"]: "Test target " + q["query_id"] for q in clean["queries"]})
    monkeypatch.setattr(injection, "select_reviewed_target", lambda query, mapping: context.target(query))
    poisoned = injection.inject_poisons(clean, LexicalInfluentialTokenAttack(), seed=seed,
        attacked_query_ids=list(context.mapping), **matrix._review_injection_kwargs(context))
    dense, rcd = _configs()
    manifest = matrix.build_cell_manifest(cell_id=matrix._cell_id("lexical_influential_token", 1, seed),
        clean_data=clean, poisoned_data=poisoned, attack_family="lexical_influential_token",
        intensity=1, poison_seed=seed, heldout_fingerprint="heldout",
        config_hashes={"heldout": "h", "dense": "d", "rcd": "r"}, dense_config=dense, rcd_config=rcd,
        git_sha="a" * 40, git_dirty=False, source_fingerprint="f" * 64, reviewed_targets=context)
    manifest["attack"]["configuration"] = {"repeat_factor": 4}
    return context, poisoned, manifest


def test_all_three_seeds_use_same_targets_and_manifest_replay(monkeypatch):
    clean = _clean_data()
    target_lists = []
    for seed in matrix.PREDECLARED_POISON_SEEDS:
        context, poisoned, manifest = _reviewed_snapshot(monkeypatch, clean, seed)
        replay = matrix.replay_cell_manifest(clean, manifest, reviewed_targets=context)
        assert replay == poisoned
        assert poison_instances_fingerprint(clean, replay) == poison_instances_fingerprint(clean, poisoned)
        frozen = _frozen(clean)
        from dataclasses import replace
        assert matrix.verify_cell_provenance(manifest, replace(frozen, reviewed_targets=context)) == replay
        target_lists.append([q["poison_target_answer"] for q in replay["queries"]])
    assert target_lists[0] == target_lists[1] == target_lists[2]


@pytest.mark.parametrize("mutation", ["missing-context", "artifact-pin", "target", "downgrade", "association"])
def test_reviewed_replay_rejects_mutations(monkeypatch, mutation):
    clean = _clean_data()
    context, _, manifest = _reviewed_snapshot(monkeypatch, clean)
    if mutation == "missing-context":
        context = None
    elif mutation == "artifact-pin":
        manifest["target_review"]["artifact_sha256"] = "0" * 64
        # double metadata is mutable, so isolate it as a real accessor would.
        context.metadata = {**context.metadata, "artifact_sha256": "a" * 64}
    elif mutation == "target":
        manifest["query_poison_associations"][0]["poison_target_answer"] = "Changed"
    elif mutation == "downgrade":
        manifest["schema"] = matrix.CELL_SCHEMA
    else:
        manifest["query_poison_associations"][0].pop("target_review")
    with pytest.raises(ValueError):
        matrix.replay_cell_manifest(clean, manifest, reviewed_targets=context)


def test_checkpoint_provenance_blocks_before_lookup_or_generation(monkeypatch):
    clean = _clean_data()
    context = _ContextDouble({q["query_id"]: "test" for q in clean["queries"]})
    checkpoint = SimpleNamespace(provenance={"target_review": {**context.metadata, "artifact_sha256": "0" * 64}})
    with pytest.raises(ValueError, match="Checkpoint reviewed artifact"):
        injection.inject_poisons(clean, LexicalInfluentialTokenAttack(), checkpoint=checkpoint,
                                **matrix._review_injection_kwargs(context))


def test_matched_comparison_rejects_mixed_artifact_pins():
    context = _ContextDouble({"q": "test"})
    dense = {"query_id": "q", "target_review": context.metadata}
    rcd = {"query_id": "q", "target_review": {**context.metadata, "artifact_sha256": "0" * 64}}
    with pytest.raises(ValueError, match="provenance mismatch"):
        matched.paired_differences([dense], [rcd])


@pytest.mark.parametrize("mutation", [None, "summary", "raw-row", "external-policy"])
def test_completed_reviewed_cell_and_aggregate_provenance(monkeypatch, tmp_path, mutation):
    from dataclasses import replace
    from test_week9_heldout_poison_matrix import _raw_record
    clean = _clean_data()
    context, poisoned, manifest = _reviewed_snapshot(monkeypatch, clean)
    frozen = replace(_frozen(clean), reviewed_targets=context)
    cell_dir = tmp_path / manifest["cell_id"]
    cell_dir.mkdir()
    (cell_dir / "poison.manifest.json").write_text(json.dumps(manifest))
    rows = [{**_raw_record(manifest, q, p, c), "target_review": copy.deepcopy(context.metadata)}
            for q in poisoned["queries"] for p in ("dense", "rcd") for c in ("clean", "poisoned")]
    if mutation == "raw-row":
        rows[0]["target_review"]["artifact_sha256"] = "0" * 64
    (cell_dir / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    _write_summary(cell_dir, manifest, rows)
    path = cell_dir / "summary.json"
    summary = json.loads(path.read_text())
    summary.update(schema=matrix.REVIEWED_CELL_SCHEMA, target_review=copy.deepcopy(context.metadata))
    if mutation == "summary":
        summary["target_review"]["artifact_sha256"] = "0" * 64
    path.write_text(json.dumps(summary))
    if mutation == "external-policy":
        context.metadata = {**context.metadata, "review_policy_sha256": "0" * 64}
    if mutation:
        with pytest.raises(ValueError, match="provenance|authenticated"):
            matrix.validate_completed_cell(cell_dir, frozen_inputs=frozen)
    else:
        verified = matrix.validate_completed_cell(cell_dir, frozen_inputs=frozen)
        assert verified["manifest"]["target_review"] == context.metadata
        # Exercise whole-matrix consistency without creating experiment artifacts.
        import scripts.aggregate_week9_heldout_poison_matrix as aggregate
        other = {**verified, "manifest": {**manifest, "target_review": {**context.metadata, "artifact_sha256": "0" * 64}}}
        values = iter([verified, other] + [verified] * 10)
        monkeypatch.setattr(aggregate, "validate_completed_cell", lambda *a, **k: next(values))
        with pytest.raises(ValueError, match="mixes reviewed"):
            aggregate.aggregate_matrix(tmp_path, frozen_inputs=frozen)


def test_archived_checkpoint_rejects_changed_assignment_artifact(tmp_path):
    from src.attacks.checkpoint import PoisonCheckpoint, CHECKPOINT_SCHEMA
    context = _ContextDouble({"q": "test"})
    old = tmp_path / "old" / "poison.checkpoints"
    old.mkdir(parents=True)
    # Deliberately incomplete negative checkpoint, with no approval record.
    (old / "q.0.json").write_text(json.dumps({"schema": CHECKPOINT_SCHEMA,
        "provenance": {"target_review": context.metadata}}))
    with pytest.raises(ValueError, match="frozen provenance mismatch"):
        PoisonCheckpoint(tmp_path / "new", [tmp_path / "old"],
            provenance={"target_review": {**context.metadata, "artifact_sha256": "0" * 64}},
            attack_family="semantic_fluent_false_evidence", intensity=1, allowed_query_ids=["q"])


def test_reviewed_semantic_configuration_replays_extended_validation_metadata(monkeypatch):
    from dataclasses import replace
    clean = _clean_data()
    context, _, manifest = _reviewed_snapshot(monkeypatch, clean)
    manifest["attack"]["family"] = "semantic_fluent_false_evidence"
    manifest["cell_id"] = matrix._cell_id("semantic_fluent_false_evidence", 1, 42)
    manifest["attack"]["configuration"] = {
        "max_tokens": 150, "max_attempts": 2, "retry_policy": matrix.SEMANTIC_RETRY_POLICY,
        "prompt_version": matrix.SEMANTIC_PROMPT_VERSION,
        "validation_version": matrix.SEMANTIC_VALIDATION_VERSION,
        "validation_status": "heuristically_supported_unverified",
        "requires_independent_semantic_review": True,
    }
    # This unit test isolates configuration validation, not document authentication.
    monkeypatch.setattr(matrix, "_verify_poison_document_identity", lambda *a: None)
    monkeypatch.setattr(matrix, "replay_cell_manifest", lambda *a, **k: "replayed-test-double")
    frozen = replace(_frozen(clean), reviewed_targets=context)
    assert matrix.verify_cell_provenance(manifest, frozen) == "replayed-test-double"
    manifest["attack"]["configuration"]["max_attempts"] = 99
    with pytest.raises(ValueError, match="attack configuration"):
        matrix.verify_cell_provenance(manifest, frozen)


def test_context_accessors_do_not_mutate_stored_decisions():
    from src.attacks.reviewed_target_artifact import ReviewedTargets
    context = ReviewedTargets(canonical({"q": {"review_status": "pending"}}), canonical({"scope": "heldout"}))
    context.mapping["q"]["review_status"] = "changed"
    context.metadata["scope"] = "changed"
    assert context.mapping["q"]["review_status"] == "pending"
    assert context.metadata["scope"] == "heldout"
