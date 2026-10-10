from src.defenses.rcd.core import build_consistency_signals
from src.defenses.rcd.redundancy import evidence_redundancy
from src.defenses.rcd.conflict import evidence_conflict_scores
from src.defenses.rcd.scoring import score_documents, select_evidence
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

@dataclass
class RetrievedDocument:
    doc_id: str
    text: str


def test_rcd_components_smoke():
    retriever_rankings = [
        ["d1", "d2", "d3"],
        ["d1", "d3", "d2"],
    ]

    rewrite_rankings = [
        ["d1", "d2", "d3"],
        ["d1", "d3", "d2"],
    ]

    signals = build_consistency_signals(
        retriever_rankings,
        rewrite_rankings,
        top_k=3,
    )

    documents = [
        RetrievedDocument("d1", "Paris is the capital of France."),
        RetrievedDocument("d2", "Berlin is the capital of Germany."),
        RetrievedDocument("d3", "Madrid is the capital of Spain."),
    ]

    redundancy = evidence_redundancy(documents)
    conflict = evidence_conflict_scores(documents)

    scores = score_documents(
        signals,
        redundancy,
        conflict,
        base_rankings=["d1", "d2", "d3"],
    )

    assert scores
    assert "d1" in scores
    assert scores["d1"].final_score >= scores["d3"].final_score

def test_claim_conflict_distinguishes_related_and_unrelated_years():
    from src.defenses.rcd.conflict import claim_conflict

    assert claim_conflict(
        "The company was founded in 1990.",
        "The company was founded in 2000.",
    ) == 1.0

    assert claim_conflict(
        "The company was founded in 1990.",
        "The capital city was Paris in 2000.",
    ) == 0.0

    assert claim_conflict(
        "The company was founded in 1990.",
        "The company was founded in 1990.",
    ) == 0.0


def test_agreement_is_document_specific():
    retriever_rankings = [
        ["d1", "d2"],
        ["d1", "d3"],
    ]

    rewrite_rankings = [
        ["d1"],
        ["d2"],
    ]

    signals = build_consistency_signals(
        retriever_rankings,
        rewrite_rankings,
        top_k=3,
    )

    assert signals["d1"].agreement == 1.0
    assert signals["d2"].agreement == 0.5
    assert signals["d3"].agreement == 0.5


def test_rcd_retrieval_accounting():
    from src.defenses.rcd.retriever import RCDRetriever

    class FakeRetriever:
        def build(self, corpus):
            self.corpus = corpus

        def retrieve(self, query, top_k=10):
            return [
                RetrievedDocument("d1", "Paris is the capital of France."),
                RetrievedDocument("d2", "Berlin is the capital of Germany."),
            ][:top_k]

    base = FakeRetriever()
    sparse = FakeRetriever()
    dense = FakeRetriever()

    retriever = RCDRetriever(
        base,
        sparse_retriever=sparse,
        dense_retriever=dense,
        rewrite_count=3,
        candidate_k=2,
        output_k=2,
    )

    retriever.build([
        {"doc_id": "d1", "text": "Paris is the capital of France."},
        {"doc_id": "d2", "text": "Berlin is the capital of Germany."},
    ])

    retriever.retrieve("What is the capital of France?", top_k=2)

    diagnostics = retriever.last_diagnostics
    assert diagnostics is not None
    assert diagnostics["retrieval_call_count"] == 5
    assert diagnostics["retrieval_latency_seconds"] >= 0.0


def test_rcd_signal_order_is_deterministic():
    retriever_rankings = [
        ["d1", "d2"],
        ["d2", "d3"],
    ]
    rewrite_rankings = [
        ["d1", "d3"],
        ["d2", "d3"],
    ]

    signals = build_consistency_signals(
        retriever_rankings,
        rewrite_rankings,
        top_k=2,
    )

    assert list(signals) == ["d1", "d2", "d3"]


def test_frozen_score_calculation_and_evidence_ordering():
    scores = score_documents(
        {
            "d1": SimpleNamespace(consistency=0.8),
            "d2": SimpleNamespace(consistency=0.6),
        },
        {"d1": 0.9, "d2": 0.1},
        {"d1": 0.2, "d2": 0.0},
        base_rankings=["d1", "d2"],
        consistency_weight=0.45,
        redundancy_weight=0.00,
        conflict_weight=0.10,
        base_rank_weight=0.45,
    )

    assert scores["d1"].final_score == pytest.approx(0.79)
    assert scores["d2"].final_score == pytest.approx(0.495)
    assert [score.doc_id for score in select_evidence(scores, top_k=2)] == [
        "d1",
        "d2",
    ]


def test_rewrite_count_means_additional_rewrites_excluding_original(monkeypatch):
    from src.defenses.rcd import rewrites

    query = "Who founded the company in 1990?"

    monkeypatch.setattr(
        rewrites,
        "_generic_rewrites",
        lambda q: [
            q,
            "Who established the company in 1990?",
            "Who was the founder of the company in 1990?",
            "Which person founded the company in 1990?",
            "Who established the company in 1990?",
        ],
    )

    generated = rewrites.generate_query_rewrites(
        query,
        n_rewrites=3,
    )

    assert len(generated) == 3
    assert query not in generated
    assert len(generated) == len(set(generated))


def test_rewrite_count_can_return_fewer_than_requested_unique_rewrites(
    monkeypatch,
):
    from src.defenses.rcd import rewrites

    query = "Who founded the company?"
    monkeypatch.setattr(
        rewrites,
        "_generic_rewrites",
        lambda q: [q, "Who founded the company?", "A unique variant", "A unique variant"],
    )

    generated = rewrites.generate_query_rewrites(query, n_rewrites=3)

    assert generated == ["A unique variant"]


def test_frozen_rcd_configuration_weights_and_depths():
    from pathlib import Path
    import yaml

    config_path = (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "exp_026_hotpotqa_rcd_v1_mlx_frozen_current.yaml"
    )
    config = yaml.safe_load(config_path.read_text())

    assert config["final_run"] is True
    assert config["rcd_consistency_weight"] == 0.45
    assert config["rcd_redundancy_weight"] == 0.00
    assert config["rcd_conflict_weight"] == 0.10
    assert config["rcd_base_rank_weight"] == 0.45
    assert sum(
        config[key]
        for key in (
            "rcd_consistency_weight",
            "rcd_redundancy_weight",
            "rcd_conflict_weight",
            "rcd_base_rank_weight",
        )
    ) == 1.0
    assert config["rcd_candidate_k"] == 10
    assert config["top_k"] == 3
