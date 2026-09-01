"""Integration test for retrieval-metric wiring through run.main()."""

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run


class FakeGenerator:
    """Lightweight generator so main() runs without loading a model."""

    def generate(self, prompt, max_tokens=64):
        return type(
            "GenerationResult",
            (),
            {
                "text": "1755",
                "latency_seconds": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 1,
            },
        )()


class RecordingRetriever:
    def __init__(self):
        self.requested_depths = []

    def build(self, corpus):
        pass

    def retrieve(self, query, top_k=5):
        self.requested_depths.append(top_k)
        return [
            SimpleNamespace(
                doc_id=f"doc-{rank}",
                text=f"Evidence document {rank}.",
                score=float(11 - rank),
            )
            for rank in range(1, 11)
        ][:top_k]


def test_main_logs_retrieval_metrics(tmp_path, monkeypatch):
    """The real main() path must log retrieval metrics per query."""

    dataset = {
        "corpus": [
            {"doc_id": "doc-a", "text": "University founded in 1755."},
            {"doc_id": "doc-b", "text": "A professor worked there."},
            {"doc_id": "doc-c", "text": "Unrelated document."},
        ],
        "queries": [
            {
                "query_id": "q1",
                "question": "When was the university founded?",
                "gold_answer": "1755",
                "gold_doc_ids": ["doc-a", "doc-b"],
                "gold_supporting_facts": [],
            }
        ],
    }

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
experiment_id: test_metric_wiring
seed: 42
dataset_path: {dataset_path}
retriever: bm25
top_k: 3
generator_backend: mock
max_tokens: 64
results_dir: {tmp_path / "results"}
"""
    )

    monkeypatch.setattr(
        run,
        "build_generator",
        lambda config: FakeGenerator(),
    )

    run.main(str(config_path))

    result_path = tmp_path / "results" / "test_metric_wiring.jsonl"
    assert result_path.exists()

    records = [
        json.loads(line)
        for line in result_path.read_text().splitlines()
        if line.strip()
    ]

    assert len(records) == 1

    record = records[0]
    metrics = record["retrieval_metrics"]

    expected_keys = {
        "recall@1",
        "recall@3",
        "recall@5",
        "recall@10",
        "mrr@1",
        "mrr@3",
        "mrr@5",
        "mrr@10",
        "ndcg@10",
    }

    assert set(metrics) == expected_keys

    for value in metrics.values():
        assert isinstance(value, (int, float))

    # These must be based on the actual retrieved ranking, not the
    # gold labels themselves.
    assert record["retrieved_doc_ids"]
    assert len(record["retrieved_doc_ids"]) == len(record["retrieved_scores"])
    assert record["gold_doc_ids"] == ["doc-a", "doc-b"]

    assert metrics["recall@1"] > 0
    assert metrics["mrr@1"] > 0
    assert metrics["mrr@3"] > 0
    assert metrics["mrr@5"] > 0
    assert metrics["mrr@10"] > 0
    assert metrics["ndcg@10"] > 0

    summary_path = tmp_path / "results" / "test_metric_wiring.summary.json"
    summary = json.loads(summary_path.read_text())
    assert summary["query_count"] == 1
    assert set(summary["mean_retrieval_metrics"]) == expected_keys


def test_retrieval_depth_for_metrics_is_decoupled_from_generator_top_k(
    tmp_path, monkeypatch
):
    """run.main() must retrieve enough documents to score Recall@10/MRR@10/
    nDCG@10 even when the generator only sees `top_k` evidence documents.

    Review #1 flagged that retrieval depth and the generator's evidence
    window need to be independent: a config with a small `top_k` (e.g. 1,
    to keep the prompt short) should not silently starve the retrieval
    metrics down to that same depth. This pins the fix by using a gold
    document that only appears at rank 4 of 5 -- outside `top_k=1` -- and
    asserting it still shows up in `retrieved_doc_ids` and is credited by
    the retrieval metrics, while the generation prompt only cites the
    single top-ranked document.
    """

    dataset = {
        "corpus": [
            {"doc_id": "doc-top", "text": "castle river mountain lake forest"},
            {"doc_id": "doc-2", "text": "castle river mountain"},
            {"doc_id": "doc-3", "text": "castle river"},
            {"doc_id": "doc-gold-deep", "text": "castle founded in 1755"},
            {"doc_id": "doc-5", "text": "castle"},
        ],
        "queries": [
            {
                "query_id": "q1",
                "question": "castle",
                "gold_answer": "1755",
                "gold_doc_ids": ["doc-gold-deep"],
                "gold_supporting_facts": [],
            }
        ],
    }

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
experiment_id: test_retrieval_depth
seed: 42
dataset_path: {dataset_path}
retriever: bm25
top_k: 1
generator_backend: mock
max_tokens: 64
results_dir: {tmp_path / "results"}
"""
    )

    monkeypatch.setattr(
        run,
        "build_generator",
        lambda config: FakeGenerator(),
    )

    run.main(str(config_path))

    result_path = tmp_path / "results" / "test_retrieval_depth.jsonl"
    record = json.loads(result_path.read_text().splitlines()[0])

    # Generation must only ever see `top_k` (1) evidence documents.
    assert record["prompt"].count("\n- ") == 1

    # But retrieval-metric scoring must have looked deeper than top_k,
    # otherwise a gold doc ranked below top_k could never be credited.
    assert len(record["retrieved_doc_ids"]) > 1
    assert len(record["retrieved_doc_ids"]) == len(record["retrieved_scores"])
    assert "doc-gold-deep" in record["retrieved_doc_ids"]

    metrics = record["retrieval_metrics"]
    assert metrics["recall@1"] == 0  # gold doc is not the top-1 hit
    assert metrics["recall@10"] == 1  # but is found within depth 10
    assert metrics["mrr@1"] == 0
    assert metrics["mrr@3"] == 0
    assert metrics["mrr@5"] > 0
    assert metrics["mrr@10"] > 0


def test_generator_top_k_does_not_change_retrieval_metric_depth_or_scores(
    tmp_path, monkeypatch
):
    """A fixed 10-document ranking is evaluated unchanged for 3- and 5-doc prompts."""
    dataset = {
        "corpus": [],
        "queries": [{
            "query_id": "q1",
            "question": "Which document is relevant?",
            "gold_answer": "unused",
            "gold_doc_ids": ["doc-10"],
            "gold_supporting_facts": [],
        }],
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset))

    retriever = RecordingRetriever()
    monkeypatch.setattr(run, "build_retriever", lambda config: retriever)
    monkeypatch.setattr(run, "build_generator", lambda config: FakeGenerator())

    records = []
    for generator_top_k in (3, 5):
        config_path = tmp_path / f"config_{generator_top_k}.yaml"
        config_path.write_text(
            f"""
experiment_id: test_generator_top_k_{generator_top_k}
seed: 42
dataset_path: {dataset_path}
retriever: bm25
top_k: {generator_top_k}
generator_backend: mock
max_tokens: 64
results_dir: {tmp_path / "results"}
"""
        )
        run.main(str(config_path))
        result_path = tmp_path / "results" / f"test_generator_top_k_{generator_top_k}.jsonl"
        records.append(json.loads(result_path.read_text().splitlines()[0]))

    assert retriever.requested_depths == [10, 10]
    assert [record["prompt"].count("\n- ") for record in records] == [3, 5]
    assert all(len(record["retrieved_doc_ids"]) == 10 for record in records)
    assert all(len(record["retrieved_doc_ids"]) == len(record["retrieved_scores"]) for record in records)
    assert records[0]["retrieval_metrics"] == records[1]["retrieval_metrics"]
    assert records[0]["retrieval_metrics"]["recall@10"] == 1
    assert records[0]["retrieval_metrics"]["mrr@10"] == 0.1
