"""Synthetic no-agreement RCD variant tests; no embedding downloads or model calls."""
from dataclasses import dataclass

import pytest

from src.defenses.rcd.retriever import RCDRetriever
from src.experiments.rcd_component_variants import (
    NoAgreementRCDRetriever, retriever_config
)
from scripts.prepare_2wiki_rcd_ablation_plan import VARIANTS


@dataclass
class Doc:
    doc_id: str
    text: str
    score: float = 0.0


class FixedRetriever:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []
    def build(self, corpus):
        self.corpus = corpus
    def retrieve(self, question, *, top_k):
        self.calls.append((question, top_k))
        return self.docs[:top_k]


def build_pair(rewrites=3):
    base = FixedRetriever([
        Doc("one", "His father lived in Paris in 1990."),
        Doc("two", "His father lived in Rome in 2001."),
        Doc("three", "Paris France 1990."),
    ])
    sparse = FixedRetriever([
        Doc("two", "His father lived in Rome in 2001."),
        Doc("three", "Paris France 1990."),
        Doc("one", "His father lived in Paris in 1990."),
    ])
    args = dict(sparse_retriever=sparse, dense_retriever=base,
                candidate_k=3, output_k=3, rewrite_count=rewrites,
                consistency_weight=.45, redundancy_weight=0.,
                conflict_weight=.10, base_rank_weight=.45)
    return base, args


def test_no_agreement_keeps_same_retrieval_calls_candidates_but_changes_score_signal():
    baseline_base, baseline_args = build_pair()
    baseline = RCDRetriever(baseline_base, **baseline_args)
    projected_base, projected_args = build_pair()
    no_agreement = NoAgreementRCDRetriever(projected_base, **projected_args)
    query = "Where did his father live?"
    observed_base = baseline.retrieve(query)
    observed_projected = no_agreement.retrieve(query)
    a, b = baseline.last_diagnostics, no_agreement.last_diagnostics
    assert a["retrieval_call_count"] == b["retrieval_call_count"]
    assert a["rewrite_queries"] == b["rewrite_queries"]
    assert set(a["scores"]) == set(b["scores"])
    assert len(observed_base) == len(observed_projected) == 3
    assert b["ablation"] == "agreement_signal_dropped_from_consistency_mean"
    for id_, data in b["consistency_signals"].items():
        expected = (data["rank_stability"] + data["rewrite_stability"]) / 2
        assert data["consistency"] == expected
        original = a["consistency_signals"][id_]
        assert original["consistency"] == (
            original["agreement"] + original["rank_stability"]
            + original["rewrite_stability"]
        ) / 3
    assert any(a["scores"][id_]["consistency"] != b["scores"][id_]["consistency"]
               for id_ in a["scores"])


def test_no_rewrites_is_an_actual_zero_rewrite_retrieval():
    base, opts = build_pair(rewrites=0)
    retriever = RCDRetriever(base, **opts)
    retriever.retrieve("Who lived in Paris?", top_k=3)
    d = retriever.last_diagnostics
    assert d["rewrite_queries"] == []
    assert d["rewrite_rankings"] == []
    assert d["retrieval_call_count"] == 2


def test_variant_config_weight_validation_and_depth():
    assert retriever_config(VARIANTS["full_k1"], "synthetic-local-snapshot")["top_k"] == 1
    assert retriever_config(VARIANTS["full_k5"], "synthetic-local-snapshot")["top_k"] == 5
    assert retriever_config(VARIANTS["no_rewrites_k3"], "s")["rcd_rewrite_count"] == 0
    assert retriever_config(VARIANTS["no_conflict_k3"], "s")["rcd_conflict_weight"] == 0.
    wrong = dict(VARIANTS["full_k3"], consistency_weight=.99)
    with pytest.raises(ValueError, match="Variant weights must sum to 1"):
        retriever_config(wrong, "s")
