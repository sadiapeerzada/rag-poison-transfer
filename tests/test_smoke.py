"""Smoke test: does the Week 1-2 pipeline run end to end without error,
and does BM25 actually retrieve topically relevant documents?

This does NOT check generation quality (MockGenerator isn't a real
model) -- it only checks that the wiring (retrieval -> prompt ->
generate -> score -> log) is sound. Real quality checks come once the
MLX backend is wired in on your machine.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.bm25 import BM25Retriever
from src.evaluation.metrics import exact_match, f1_score
from src.pipelines.generator import MockGenerator


def load_toy_data():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "raw", "toy_smoke_dataset.json",
    )
    with open(path) as f:
        return json.load(f)


def test_bm25_retrieves_relevant_doc():
    data = load_toy_data()
    retriever = BM25Retriever()
    retriever.build(data["corpus"])
    results = retriever.retrieve("Where is the Eiffel Tower located?", top_k=1)
    assert len(results) == 1
    assert results[0].doc_id == "d1", "BM25 should retrieve the Eiffel Tower doc for this query"


def test_metrics_exact_match():
    assert exact_match("Paris", "paris") == 1.0
    assert exact_match("The Paris", "Paris") == 1.0  # article stripped by normalization
    assert exact_match("London", "Paris") == 0.0


def test_metrics_f1_partial_credit():
    score = f1_score("Paris France", "Paris")
    assert 0.0 < score < 1.0, "Partial overlap should give partial F1, not 0 or 1"


def test_mock_generator_runs():
    gen = MockGenerator()
    result = gen.generate("some prompt")
    assert isinstance(result.text, str) and len(result.text) > 0
    assert result.latency_seconds >= 0


def test_full_pipeline_runs_without_error(tmp_path):
    """Run run.py end-to-end on the mock smoke config.

    Outputs go to ``tmp_path`` (AUDIT-022): this test must never delete or
    rewrite tracked files under ``results/``, because that dirties the tree
    and trips the final-run Git guards.
    """
    import subprocess
    import yaml
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo_root, "configs", "exp_000_smoke.yaml")) as f:
        config = yaml.safe_load(f)
    config["results_dir"] = str(tmp_path / "results")
    config["dataset_path"] = os.path.join(repo_root, config["dataset_path"])
    tmp_config = tmp_path / "exp_000_smoke_tmp.yaml"
    tmp_config.write_text(yaml.safe_dump(config))
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "run.py"), "--config", str(tmp_config)],
        cwd=repo_root, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"run.py failed:\n{result.stdout}\n{result.stderr}"
    assert "Mean EM" in result.stdout
    assert (tmp_path / "results" / "exp_000_smoke_test.jsonl").exists()
