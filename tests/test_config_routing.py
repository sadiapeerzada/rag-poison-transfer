"""Integration test: does config['retriever'] actually route to the
right retriever CLASS, all the way through main()'s real execution
path -- not just in build_retriever() tested in isolation?

This is deliberately separate from test_retrieval_variants.py, which
tests each retriever's LOGIC in isolation but never checks that the
config-driven dispatch in run.py actually wires them up correctly.
That gap is exactly how a previous regression (main() hardcoding
BM25Retriever() directly, bypassing build_retriever() entirely) went
undetected -- flagged by supervisor review, not caught by tests.

IMPORTANT: an earlier version of this file only tested build_retriever()
in isolation, calling it directly rather than exercising main()'s real
code path. That version would NOT have caught the actual regression
(main() calling BM25Retriever() directly instead of build_retriever()),
since it never touched main() at all -- the same category of blind spot
being fixed here. These tests call main() end-to-end instead.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.reranker import Reranker


def _toy_config(tmp_path, retriever_kind, experiment_id, extra=None):
    """A minimal config pointing at the toy dataset with a mock
    generator, so this test runs in milliseconds with no network
    access -- we're testing ROUTING here, not retrieval quality or
    generation quality (those are covered elsewhere)."""
    config = {
        "experiment_id": experiment_id,
        "seed": 42,
        "dataset_path": os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "raw", "toy_smoke_dataset.json",
        ),
        "retriever": retriever_kind,
        "top_k": 2,
        "generator_backend": "mock",
        "max_tokens": 32,
        "results_dir": str(tmp_path),
    }
    if extra:
        config.update(extra)
    config_path = tmp_path / f"{experiment_id}.yaml"
    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return str(config_path)


def _run_main_and_capture_retriever_class(monkeypatch, config_path):
    """Patches build_retriever to record which class it returns, then
    runs the REAL main() end-to-end. This catches both failure modes:
    (a) build_retriever() itself routing wrong, and (b) main() not
    calling build_retriever() at all (the actual regression found)."""
    captured = {}
    real_build_retriever = run.build_retriever

    def spy_build_retriever(config):
        retriever = real_build_retriever(config)
        captured["class"] = type(retriever)
        return retriever

    monkeypatch.setattr(run, "build_retriever", spy_build_retriever)
    run.main(config_path)

    if "class" not in captured:
        raise AssertionError(
            "main() completed WITHOUT ever calling build_retriever() -- "
            "this is exactly the regression this test exists to catch. "
            "main() is instantiating a retriever some other way, "
            "ignoring the config's 'retriever' field."
        )
    return captured["class"]


def test_bm25_config_routes_through_main(tmp_path, monkeypatch):
    config_path = _toy_config(tmp_path, "bm25", "test_bm25_routing")
    cls = _run_main_and_capture_retriever_class(monkeypatch, config_path)
    assert cls is BM25Retriever


def test_dense_config_routes_through_main(tmp_path, monkeypatch):
    from src.retrieval.dense import HashingEmbedder

    class _FakeEmbedder(HashingEmbedder):
        """Same deterministic test double used in test_retrieval_variants.py,
        adapted to accept a model_name argument (real SentenceTransformerEmbedder
        takes one; this stub just ignores it)."""
        def __init__(self, model_name):
            super().__init__()

    monkeypatch.setattr(run, "SentenceTransformerEmbedder", _FakeEmbedder)
    config_path = _toy_config(tmp_path, "dense", "test_dense_routing")
    cls = _run_main_and_capture_retriever_class(monkeypatch, config_path)
    assert cls is DenseRetriever, (
        f"config specified retriever: dense but main() used {cls.__name__} -- "
        f"this is the exact class of regression flagged by supervisor review."
    )


def test_hybrid_config_routes_through_main(tmp_path, monkeypatch):
    from src.retrieval.dense import HashingEmbedder

    class _FakeEmbedder(HashingEmbedder):
        def __init__(self, model_name):
            super().__init__()

    monkeypatch.setattr(run, "SentenceTransformerEmbedder", _FakeEmbedder)
    config_path = _toy_config(tmp_path, "hybrid", "test_hybrid_routing")
    cls = _run_main_and_capture_retriever_class(monkeypatch, config_path)
    assert cls is HybridRetriever


def test_reranker_config_routes_through_main(tmp_path, monkeypatch):
    from src.retrieval.dense import HashingEmbedder
    from src.retrieval.reranker import MockCrossEncoderScorer

    class _FakeEmbedder(HashingEmbedder):
        """Same deterministic test double used in dense/hybrid routing tests."""
        def __init__(self, model_name):
            super().__init__()

    class _FakeScorer(MockCrossEncoderScorer):
        def __init__(self, model_name):
            super().__init__()

    monkeypatch.setattr(run, "SentenceTransformerEmbedder", _FakeEmbedder)
    monkeypatch.setattr(run, "CrossEncoderScorer", _FakeScorer)
    config_path = _toy_config(tmp_path, "reranker", "test_reranker_routing")
    cls = _run_main_and_capture_retriever_class(monkeypatch, config_path)
    assert cls is Reranker


def test_unknown_retriever_raises_clear_error():
    """A typo'd retriever name should fail loudly, not silently fall
    back to BM25 -- that silent-fallback failure mode is exactly what
    caused the regression this test file exists to prevent."""
    try:
        run.build_retriever({"retriever": "not_a_real_retriever"})
        assert False, "Expected ValueError for unknown retriever name"
    except ValueError as e:
        assert "not_a_real_retriever" in str(e)
