"""No MLX inference or artificial approvals: authorization-boundary doubles only."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

import scripts.run_week9_development_smoke as smoke
import src.attacks.injection as injection
from src.attacks.compatible_targets import assignment_fingerprint
from src.attacks.semantic_fluent import SemanticQualityError
from src.pipelines.generator import GenerationResult
from src.experiments.protocol import query_set_fingerprint


def test_preflight_never_loads_dataset_or_model_and_keeps_frozen_configuration(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("Preflight cannot materialize a dataset or construct a model")
    monkeypatch.setattr(smoke, "build_generator", forbidden)
    monkeypatch.setattr(smoke, "load_dataset", forbidden)
    report, queries, mapping, dense, rcd = smoke.preflight()
    assert report["scope"] == "development" and report["is_final_run"] is False
    assert report["query_ids"] == list(smoke.DEVELOPMENT_QUERY_IDS)
    assert len(queries) == 2 and mapping is None and report["review_input_validated"] is False
    assert dense["top_k"] == rcd["top_k"] == 3
    assert [rcd[k] for k in ("rcd_consistency_weight", "rcd_redundancy_weight", "rcd_conflict_weight", "rcd_base_rank_weight")] == [0.45, 0, 0.1, 0.45]


def test_actual_pending_review_package_is_not_approval(tmp_path):
    path = Path("docs/reviews/phase4a/review_package.json")
    _, queries, _, _, _ = smoke.preflight()
    with pytest.raises(ValueError, match="genuinely reviewed development"):
        smoke.load_development_targets(path, hashlib.sha256(path.read_bytes()).hexdigest(), queries)


def test_heldout_id_is_rejected_using_metadata_only(monkeypatch):
    manifest = json.loads(smoke.DEFAULT_MANIFEST.read_bytes())
    monkeypatch.setattr(smoke, "DEVELOPMENT_QUERY_IDS", (smoke.DEVELOPMENT_QUERY_IDS[0], manifest["heldout_query_ids"][0]))
    with pytest.raises(ValueError, match="disjoint"):
        smoke.preflight()


def test_missing_reviews_block_before_dataset_or_generator(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "load_dataset", lambda *a: pytest.fail("Missing reviews must fail before dataset load"))
    with pytest.raises(ValueError, match="reviewed"):
        smoke.execute(targets=None, targets_sha256=None, output_dir=tmp_path, experiment_id="blocked")
    assert not list(tmp_path.iterdir())


class FakeMLX:
    calls = []
    mode = "affirm"

    def generate(self, prompt, max_tokens):
        self.calls.append((prompt, max_tokens))
        if self.mode == "error":
            raise RuntimeError("synthetic model error")
        text = ("Synthetic Alternative is the documented answer to this question. The account gives a direct identifying relationship."
                if self.mode == "affirm" else "A discussion mentions Synthetic Alternative without affirming any answer.")
        return GenerationResult(text, 0.1, 20, 20)


class Retriever:
    def build(self, corpus):
        from types import SimpleNamespace
        self.docs = [SimpleNamespace(**doc) for doc in corpus]
    def retrieve(self, question, top_k):
        return self.docs[:top_k]


def harness(monkeypatch):
    # Actual dev identities, but synthetic corpus/model and pending target oracle.
    # No approved record is constructed; production authorization is tested above.
    report, queries, _, dense, rcd = smoke.preflight()
    pending = {q["query_id"]: {"query_id": q["query_id"], "target_answer": "Synthetic Alternative", "review_status": "pending"}
               for q in queries}
    report.update(review_input_validated=True, target_artifact_sha256="b" * 64,
                  target_assignment_fingerprint=assignment_fingerprint(pending), mlx_available=True, mlx_lm_available=True)
    clean = {"queries": queries, "corpus": [{"doc_id": doc_id, "text": "Synthetic development corpus for software tests only."}
             for doc_id in sorted({doc for q in queries for doc in q["gold_doc_ids"]})]}
    monkeypatch.setattr(smoke, "preflight", lambda *a: (copy.deepcopy(report), copy.deepcopy(queries), copy.deepcopy(pending), dense, rcd))
    monkeypatch.setattr(smoke, "load_dataset", lambda config: copy.deepcopy(clean))
    monkeypatch.setattr(smoke, "_require_clean_relevant_inputs", lambda **k: None)
    monkeypatch.setattr(smoke, "git_commit_sha", lambda **k: "a" * 40)
    monkeypatch.setattr(smoke, "compute_source_fingerprint", lambda: "c" * 64)
    monkeypatch.setattr(smoke, "MLXGenerator", FakeMLX)
    monkeypatch.setattr(smoke, "build_generator", lambda config: FakeMLX())
    monkeypatch.setattr(injection, "select_reviewed_target", lambda query, mapping: mapping[query["query_id"]]["target_answer"])
    snapshots = []
    def retrievers(dense, rcd, clean, poisoned):
        snapshots.append(copy.deepcopy(poisoned))
        result = {}
        for pipeline in ("dense", "rcd"):
            a, b = Retriever(), Retriever()
            a.build(copy.deepcopy(clean["corpus"]))
            b.build(copy.deepcopy(poisoned["corpus"]))
            result[pipeline] = a, b
        return result
    monkeypatch.setattr(smoke, "build_matched_retrievers", retrievers)
    FakeMLX.calls, FakeMLX.mode = [], "affirm"
    return report, snapshots


def run(tmp_path, name, recover=None):
    return smoke.execute(targets=Path("test-double-not-a-review-artifact"), targets_sha256="b" * 64,
        output_dir=tmp_path, experiment_id=name, recover_from=recover)


def test_complete_diagnostic_preserves_gold_raw_outputs_and_identical_poison(monkeypatch, tmp_path):
    report, snapshots = harness(monkeypatch)
    result = run(tmp_path, "first")
    assert result["qa_record_count"] == 16
    assert result["is_final_run"] is False and result["requires_human_semantic_review"] is True
    assert len(snapshots) == 2
    for family, poisoned in zip(smoke.FAMILIES, snapshots):
        directory = tmp_path / "first" / family
        manifest = json.loads((directory / "poison.manifest.json").read_text())
        rows = [json.loads(line) for line in (directory / "results.jsonl").read_text().splitlines()]
        assert len(rows) == 8
        assert {r["poison_instance_fingerprint"] for r in rows} == {manifest["poison_instance_fingerprint"]}
        assert [q["gold_answer"] for q in poisoned["queries"]] == [q["gold_answer"] for q in smoke._verified_development()[0]]
        for row in rows:
            assert row["generation"]["raw_response"]
            assert row["generation"]["prompt_sha256"]
            assert "f1" in row and "em" in row
            assert row["scope"] == "development"
        events = [json.loads(line) for line in (directory / "generation.events.jsonl").read_text().splitlines()]
        assert all(event["context"]["query_id"] in smoke.DEVELOPMENT_QUERY_IDS for event in events)
        assert len(events) == (8 if family == smoke.FAMILIES[0] else 10)
        by_pipeline = {p: {r["query_id"]: r["poison_doc_ids"] for r in rows if r["pipeline"] == p} for p in ("dense", "rcd")}
        assert by_pipeline["dense"] == by_pipeline["rcd"]
        from scripts.run_week9_heldout_poison_matrix import validate_completed_cell
        from test_week9_heldout_poison_matrix import _frozen
        with pytest.raises(ValueError, match="unsupported schema"):
            validate_completed_cell(directory, frozen_inputs=_frozen())


def test_recovery_reuses_semantic_checkpoints_and_refuses_stale_provenance(monkeypatch, tmp_path):
    harness(monkeypatch)
    run(tmp_path, "first")
    FakeMLX.calls = []
    run(tmp_path, "recovered", tmp_path / "first")
    assert len(FakeMLX.calls) == 16  # QA only, no semantic poison regeneration.
    plan = tmp_path / "first" / "development.plan.json"
    value = json.loads(plan.read_text()); value["target_artifact_sha256"] = "0" * 64
    plan.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="provenance mismatch"):
        run(tmp_path, "stale", tmp_path / "first")
    assert not (tmp_path / "stale").exists()


def test_invalid_semantic_prose_is_rejected_with_all_attempt_texts_preserved(monkeypatch, tmp_path):
    harness(monkeypatch)
    FakeMLX.mode = "mention"
    with pytest.raises(SemanticQualityError):
        run(tmp_path, "invalid")
    directory = tmp_path / "invalid" / smoke.FAMILIES[1]
    events = [json.loads(line) for line in (directory / "generation.events.jsonl").read_text().splitlines()]
    assert len(events) == 2
    assert all(e["raw_response"] and e["context"]["stage"] == "poison_generation" for e in events)
    assert (tmp_path / "invalid" / "failure.json").exists()
    assert not (tmp_path / "invalid" / "summary.json").exists()


def test_failed_model_call_retains_actual_prompt_and_no_invented_response(tmp_path):
    FakeMLX.mode = "error"
    recorder = smoke._RecordingGenerator(FakeMLX(), tmp_path / "events.jsonl")
    recorder.set_observation_context({"stage": "qa", "query_id": "synthetic"})
    with pytest.raises(RuntimeError):
        recorder.generate("Actual failed input", 64)
    event = json.loads((tmp_path / "events.jsonl").read_text())
    assert event["prompt"] == "Actual failed input"
    assert event["raw_response"] is None and event["status"] == "generation_error"


def test_pending_template_preserves_predeclared_cases_without_human_judgments():
    path = Path("docs/reviews/week9_development_smoke/pending_targets.json")
    payload = json.loads(path.read_text())
    _, queries, _, _, _ = smoke.preflight()
    assert payload["status"] == "pending_human_review"
    assert payload["query_set_fingerprint"] == query_set_fingerprint(queries)
    assert [r["query_id"] for r in payload["assignments"]] == list(smoke.DEVELOPMENT_QUERY_IDS)
    for row, query in zip(payload["assignments"], queries):
        assert row["question"] == query["question"] and row["gold_answer"] == query["gold_answer"]
        assert row["approved"] is False
        assert row["reviewer"] == row["reviewed_at"] == row["target_answer"] == ""
        assert row["factually_false"] is None and row["evidence_references"] == []
    with pytest.raises(ValueError, match="genuinely reviewed"):
        smoke.preflight(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_corrupt_checkpoint_is_rejected_before_model_construction(monkeypatch, tmp_path):
    harness(monkeypatch)
    run(tmp_path, "first")
    checkpoint = next((tmp_path / "first" / smoke.FAMILIES[1] / "poison.checkpoints").glob("*.json"))
    payload = json.loads(checkpoint.read_text())
    payload["provenance"]["source_fingerprint"] = "0" * 64
    checkpoint.write_text(json.dumps(payload))
    monkeypatch.setattr(smoke, "build_generator", lambda *a: pytest.fail("Corrupt recovery must stop before loading model"))
    with pytest.raises(ValueError, match="provenance mismatch"):
        run(tmp_path, "corrupt", tmp_path / "first")
    assert not (tmp_path / "corrupt").exists()
