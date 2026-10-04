"""Retrieval-Consistency Defense: defense object + drop-in retriever wrapper.

DefendedRetriever exposes the same build(corpus)/retrieve(query, top_k)
interface as every retriever in src/retrieval, so it can be passed to
evaluate_asr_for_retriever() / run_source_target_asr() with NO changes to
the attack code:

    factories = {name: make_defended_factory(base_factory, sparse_factory,
                                             dense_factory, rewrites, cfg)
                 for name, base_factory in plain_factories.items()}
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.defenses.rcd.features import CandidateFeatures, collect_rankings, compute_features
from src.defenses.rcd.scoring import RCDConfig, suspicion
from src.defenses.rcd.selector import select_evidence


@dataclass
class DefenseResult:
    selected: list
    suspicion: dict
    features: dict
    adjusted: dict
    n_retrieval_calls: int
    seconds: float


class RetrievalConsistencyDefense:
    def __init__(self, sparse, dense, rewrites, config: RCDConfig | None = None, claim_scorer=None):
        self.sparse, self.dense = sparse, dense
        self.rewrites = rewrites  # anything with get_rewrites(question, n)
        self.cfg = config or RCDConfig()
        self.claim_scorer = claim_scorer

    def variants(self, question: str) -> list[str]:
        n = self.cfg.n_rewrites
        return [question] + (self.rewrites.get_rewrites(question, n) if n > 0 else [])

    def score_candidates(self, question: str, candidates: list):
        variants = self.variants(question)
        rk = collect_rankings(variants, self.sparse, self.dense, self.cfg.depth)
        feats = compute_features(question, variants, candidates, rk,
                                 self.cfg.agree_k, self.cfg.support_pool_k, self.claim_scorer)
        return {d: suspicion(f, self.cfg) for d, f in feats.items()}, feats, rk.n_retrieval_calls

    def defend(self, question: str, candidates: list, top_k: int) -> DefenseResult:
        t0 = time.perf_counter()
        susp, feats, calls = self.score_candidates(question, candidates)
        selected, adjusted = select_evidence(candidates, susp, top_k, self.cfg)
        return DefenseResult(selected, susp, feats, adjusted, calls, time.perf_counter() - t0)


class DefendedRetriever:
    """base pipeline -> RCD -> robust evidence subset."""

    def __init__(self, base, sparse, dense, rewrites, config: RCDConfig | None = None, claim_scorer=None):
        self.base, self.sparse, self.dense = base, sparse, dense
        self.defense = RetrievalConsistencyDefense(sparse, dense, rewrites, config, claim_scorer)
        self.stats = {"queries": 0, "extra_retrieval_calls": 0, "defense_seconds": 0.0}

    def build(self, corpus: list[dict]) -> None:
        self.base.build(corpus)
        self.sparse.build(corpus)
        self.dense.build(corpus)

    def retrieve(self, query: str, top_k: int = 5):
        pool = max(self.defense.cfg.depth, top_k)
        candidates = self.base.retrieve(query, top_k=pool)
        res = self.defense.defend(query, candidates, top_k)
        self.stats["queries"] += 1
        self.stats["extra_retrieval_calls"] += res.n_retrieval_calls
        self.stats["defense_seconds"] += res.seconds
        return res.selected


def make_defended_factory(base_factory, sparse_factory, dense_factory, rewrites,
                          config: RCDConfig | None = None, claim_scorer=None):
    """Zero-arg factory returning a FRESH unbuilt DefendedRetriever, matching
    the retriever_factories contract of run_source_target_asr()."""
    def factory():
        return DefendedRetriever(base_factory(), sparse_factory(), dense_factory(),
                                 rewrites, config, claim_scorer)
    return factory
