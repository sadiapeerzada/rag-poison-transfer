"""Private CLI orchestration with synthetic fixtures; no network/model downloads."""
import json
from dataclasses import dataclass

import pytest

from scripts import evaluate_poison_detection_v1 as detect
from scripts import nq_iterative_retrieval_v1 as iterative


@dataclass
class FakeDoc:
    doc_id: str
    text: str
    score: float = 1.


class FakeRetriever:
    def build(self, corpus):
        self.corpus = corpus

    def retrieve(self, query, top_k=10):
        if "Meridian Group" in query:
            return [FakeDoc("answer", "Crystal Harbor Museum was founded by Ada Newton")]
        return [FakeDoc("seed", "The Meridian Group financed a public building")]


def test_nq_development_runner_does_real_fake_backend_calls_only(tmp_path, monkeypatch):
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    (frozen / "dev_train.json").write_text(json.dumps({
        "queries": [{"query_id": "q1", "question": "Who founded Crystal Harbor Museum?",
                     "gold_doc_ids": ["answer"]}],
        "corpus": [{"doc_id": "seed", "text": "The Meridian Group financed a public building"},
                   {"doc_id": "answer", "text": "Crystal Harbor Museum was founded by Ada Newton"}],
    }))
    monkeypatch.setattr(iterative, "verify", lambda *a: {
        "status": "PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY"})
    out = tmp_path / "traces_PRIVATE.json"
    result = iterative.diagnostic(frozen, "a" * 64, out,
                                  max_queries=1, retriever_factory=FakeRetriever)
    assert result["status"] == "NQ_REAL_CLEAN_ITERATIVE_RETRIEVAL_DIAGNOSTIC_ONLY"
    assert result["n_second_round_calls"] == 1
    payload = json.loads(out.read_text())
    assert payload["records_private"][0]["iterative_retrieved_doc_ids"]
    assert payload["embedding_model_file_hashes_verified"] is False
    assert "no poisoning" in payload["scope"].lower() or "NO poisoning" in payload["scope"]
    with pytest.raises(ValueError, match="new private output"):
        iterative.diagnostic(frozen, "a" * 64, out,
                             max_queries=1, retriever_factory=FakeRetriever)


def test_evaluation_cohort_cannot_be_used_implicitly(tmp_path):
    with pytest.raises(ValueError, match="explicit"):
        iterative.diagnostic(tmp_path, "hash", tmp_path / "out",
                             cohort="eval", max_queries=1, retriever_factory=FakeRetriever)


def _case(qid):
    return {
        "query_id": qid, "condition": "poisoned",
        "known_global_poison_doc_ids": [f"poison::{qid}"],
        "diagnostics": {
            "consistency_signals": {
                f"poison::{qid}": {"agreement": 0.1, "rank_stability": 0.1, "rewrite_stability": 0.1},
                f"clean::{qid}": {"agreement": 0.9, "rank_stability": 0.9, "rewrite_stability": 0.9},
            },
            "conflict_scores": {f"poison::{qid}": 1., f"clean::{qid}": 0.},
            "scores": {f"poison::{qid}": {"final_score": 0.3},
                       f"clean::{qid}": {"final_score": 0.9}},
        }
    }


def test_private_real_diagnostic_cli_never_exports_per_case_records(tmp_path):
    d, t = tmp_path / "dev.json", tmp_path / "test.json"
    for filename, name in ((d, "dev1"), (t, "test1")):
        filename.write_text(json.dumps({"schema": detect.INPUT_SCHEMA, "records": [_case(name)]}))
    out = tmp_path / "aggregate_private.json"
    receipt = detect.run(d, t, out)
    assert receipt["status"] == "POISON_IDENTITY_DETECTION_EVALUATED_EXPLORATORY"
    assert receipt["test_auroc"] == 1.
    payload = json.loads(out.read_text())
    assert payload["test"]["n_candidate_observations"] == 2
    assert "query_id" not in out.read_text()
    assert "raw_response" not in out.read_text()
    assert payload["shared_document_ids_explicitly_allowed"] is False


def test_private_diagnostic_cli_rejects_missing_provenance(tmp_path):
    dev = tmp_path / "dev.json"
    test = tmp_path / "test.json"
    dev.write_text(json.dumps({"schema": "fake", "records": [_case("dev")]}))
    test.write_text(json.dumps({"schema": detect.INPUT_SCHEMA, "records": [_case("test")]}))
    with pytest.raises(ValueError, match="Unrecognized"):
        detect.run(dev, test, tmp_path / "output.json")
