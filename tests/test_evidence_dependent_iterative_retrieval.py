"""Synthetic regression checks only; no real retrieval or QA inference."""
from dataclasses import dataclass

import pytest

from src.defenses.iterative.retriever import (
    EvidenceDependentIterativeRetriever, evidence_coverage, select_evidence_anchor,
)


@dataclass
class Doc:
    doc_id: str
    text: str
    score: float = 1.


class FakeRetriever:
    def __init__(self):
        self.queries = []
        self.documents = []

    def build(self, corpus):
        self.documents = corpus

    def retrieve(self, query, top_k=10):
        self.queries.append(query)
        if "Meridian Group" in query:
            return [Doc("answer", "Crystal Harbor Museum was founded by Ada Newton."),
                    Doc("other", "The Meridian Group publishes a city report.")]
        return [Doc("seed", "The Meridian Group financed construction of a public building.")]


class EmptyRetriever(FakeRetriever):
    def retrieve(self, query, top_k=10):
        self.queries.append(query)
        return []


class SufficientRetriever(FakeRetriever):
    def retrieve(self, query, top_k=10):
        self.queries.append(query)
        return [Doc("gold", "Crystal Harbor Museum was founded in 1902.")]


def test_second_query_uses_first_round_document_not_gold_or_target():
    fake = FakeRetriever()
    policy = EvidenceDependentIterativeRetriever(fake, min_coverage=0.75,
                                                 candidate_k=10, output_k=3)
    policy.build([{"doc_id": "seed", "text": "The Meridian Group financed construction."}])
    question = "Who founded Crystal Harbor Museum?"
    result = policy.retrieve(question)
    assert len(fake.queries) == 2
    assert fake.queries[0] == question
    assert fake.queries[1] != question
    assert "Meridian Group" in fake.queries[1]
    assert len(result) >= 1
    trace = policy.last_diagnostics
    assert trace["retrieval_call_count"] == 2
    assert trace["rounds"][0]["action"] == "retrieve_again"
    assert trace["rounds"][1]["action"] == "answer"
    assert trace["rounds"][0]["anchor_from_prior_evidence"] == "The Meridian Group"
    assert "gold_answer" not in str(trace)
    assert "poison_target" not in str(trace)


def test_sufficient_evidence_stops_after_one_real_call():
    fake = SufficientRetriever()
    policy = EvidenceDependentIterativeRetriever(fake, min_coverage=.5)
    results = policy.retrieve("Who founded Crystal Harbor Museum?")
    assert len(fake.queries) == 1
    assert results[0].doc_id == "gold"
    assert policy.last_diagnostics["final_decision"] == "answer"
    assert policy.last_diagnostics["retrieval_call_count"] == 1


def test_missing_evidence_abstains_instead_of_fake_success():
    fake = EmptyRetriever()
    policy = EvidenceDependentIterativeRetriever(fake)
    assert policy.retrieve("Where is Moria?") == []
    assert policy.last_diagnostics["final_decision"] == "abstain"
    assert policy.last_diagnostics["retrieval_call_count"] == 1


def test_one_round_forced_budget_even_with_low_coverage():
    fake = FakeRetriever()
    policy = EvidenceDependentIterativeRetriever(fake, max_rounds=1, min_coverage=1.)
    policy.retrieve("Who founded Crystal Harbor Museum?")
    assert len(fake.queries) == 1
    assert policy.last_diagnostics["retrieval_call_count"] == 1


@pytest.mark.parametrize("kwargs", [
    {"max_rounds": 3}, {"candidate_k": 0}, {"output_k": 11},
    {"min_coverage": -0.1}, {"min_coverage": float("nan")}, {"round2_weight": 0},
])
def test_invalid_or_unbounded_policy_rejected(kwargs):
    with pytest.raises(ValueError):
        EvidenceDependentIterativeRetriever(FakeRetriever(), **kwargs)


def test_anchor_selection_has_no_query_answer_annotation_channel():
    docs = [Doc("one", "According to The Meridian Group the town was established in 1900.")]
    assert "Meridian Group" in select_evidence_anchor("Who founded the Harbor Museum?", docs)
    assert evidence_coverage("Who founded the Harbor Museum?", docs) < 1
