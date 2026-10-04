"""RCD consistency features. All features are in [0, 1], HIGHER = MORE SUSPICIOUS.

Everything here is training-free and uses only retrieval outputs and text:
no gold labels, no model internals.

Per candidate document d, over the query variants {q, rewrites...}:
  rank_instability      how much d's rank moves across variants (per
                        retriever, averaged). 0 = same rank every time.
  retriever_disagreement 1 - min(sparse_freq, dense_freq): d is only
                        'agreed on' if BOTH families keep it in their top
                        agree_k for the variants.
  unsupported           fraction of d's content tokens that no other
                        top-ranked candidate corroborates (cheap proxy for
                        redundancy; see caveat in the docs: coordinated
                        multi-doc poison corroborates itself).
  claim_conflict        pluggable (NLI / LLM); 0.0 by default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "at", "to", "for", "and",
    "or", "what", "who", "when", "where", "which", "how", "does", "do", "did", "has", "have",
    "had", "that", "this", "with", "by", "from", "as", "be", "been", "it", "its", "his", "her",
    "their", "he", "she", "they", "also", "not", "but", "than", "then", "into", "after", "before",
}


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP]


@dataclass
class Rankings:
    """Raw rank observations: ranks[doc_id][family][variant_index] -> rank (1-based) or None."""
    ranks: dict
    texts: dict
    n_variants: int
    depth: int
    n_retrieval_calls: int


def collect_rankings(variants: list[str], sparse, dense, depth: int) -> Rankings:
    V = len(variants)
    ranks: dict = {}
    texts: dict = {}
    calls = 0
    for v, q in enumerate(variants):
        for fam, retriever in (("sparse", sparse), ("dense", dense)):
            docs = retriever.retrieve(q, top_k=depth)
            calls += 1
            for r, d in enumerate(docs, 1):
                entry = ranks.setdefault(d.doc_id, {"sparse": [None] * V, "dense": [None] * V})
                entry[fam][v] = r
                texts[d.doc_id] = d.text
    return Rankings(ranks=ranks, texts=texts, n_variants=V, depth=depth, n_retrieval_calls=calls)


def rank_instability(rank_lists: dict, depth: int) -> float:
    """Mean over retrievers that ever saw the doc of std(rank)/(depth/2).

    Missing = depth+1. depth/2 is the maximum possible std, so the value is
    in [0, 1]. A doc no retriever ever returned is maximally unstable (1.0).
    With a single variant (no rewrites) this is 0 by construction.
    """
    vals = []
    for fam_ranks in rank_lists.values():
        if all(r is None for r in fam_ranks):
            continue
        arr = np.array([r if r is not None else depth + 1 for r in fam_ranks], dtype=float)
        vals.append(min(1.0, float(arr.std()) / (depth / 2.0)))
    return float(np.mean(vals)) if vals else 1.0


def retriever_freqs(rank_lists: dict, agree_k: int) -> tuple[float, float]:
    def freq(lst):
        return float(np.mean([(r is not None and r <= agree_k) for r in lst]))
    return freq(rank_lists["sparse"]), freq(rank_lists["dense"])


def unsupported_fraction(doc_id: str, rk: Rankings, exclude_tokens: set[str], pool_ids: list[str]) -> float:
    mine = set(tokens(rk.texts[doc_id])) - exclude_tokens
    if not mine:
        return 0.0
    others: set[str] = set()
    for oid in pool_ids:
        if oid != doc_id:
            others |= set(tokens(rk.texts[oid]))
    return float(1.0 - len(mine & others) / len(mine))


class NullClaimConflict:
    """Default: claim-conflict feature switched off (training-free v0)."""
    def score(self, question: str, doc_text: str, reference_texts: list[str]) -> float:
        return 0.0


class NLIClaimConflict:
    """Optional v1 feature: max P(contradiction) between doc and the
    reference (consensus) docs, via an NLI cross-encoder. Lazy import.
    NOT exercised by the unit tests (needs a model download) -- check
    model.model.config.id2label on first use."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small", max_refs: int = 3):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)
        id2label = {int(k): v.lower() for k, v in self.model.model.config.id2label.items()}
        self.contra_idx = next(i for i, v in id2label.items() if "contra" in v)
        self.max_refs = max_refs

    def score(self, question: str, doc_text: str, reference_texts: list[str]) -> float:
        refs = reference_texts[: self.max_refs]
        if not refs:
            return 0.0
        pairs = [(r, doc_text) for r in refs]
        logits = np.asarray(self.model.predict(pairs, apply_softmax=True))
        return float(logits[:, self.contra_idx].max())


@dataclass
class CandidateFeatures:
    doc_id: str
    rank_instability: float
    retriever_disagreement: float
    unsupported: float
    claim_conflict: float
    sparse_freq: float
    dense_freq: float


def compute_features(
    question: str,
    variants: list[str],
    candidates: list,
    rk: Rankings,
    agree_k: int,
    support_pool_k: int,
    claim_scorer=None,
) -> dict[str, CandidateFeatures]:
    claim_scorer = claim_scorer or NullClaimConflict()
    for c in candidates:  # candidates the base pipeline returned but sparse/dense never did
        rk.texts.setdefault(c.doc_id, c.text)
    exclude = set()
    for q in variants:
        exclude |= set(tokens(q))

    # Support pool = docs ranked <= support_pool_k for the ORIGINAL query by either retriever.
    pool_ids = [
        d for d, r in rk.ranks.items()
        if any(x[0] is not None and x[0] <= support_pool_k for x in (r["sparse"], r["dense"]))
    ]

    feats: dict[str, CandidateFeatures] = {}
    for doc_id in [c.doc_id for c in candidates]:
        if doc_id in rk.ranks:
            r = rk.ranks[doc_id]
            inst = rank_instability(r, rk.depth)
            sf, df = retriever_freqs(r, agree_k)
        else:  # never reproduced by independent retrieval: maximally suspicious on both
            inst, sf, df = 1.0, 0.0, 0.0
        text = rk.texts[doc_id]
        unsup = unsupported_fraction(doc_id, rk, exclude, pool_ids)
        refs = [rk.texts[o] for o in pool_ids if o != doc_id]
        conflict = float(claim_scorer.score(question, text, refs))
        feats[doc_id] = CandidateFeatures(
            doc_id=doc_id, rank_instability=inst,
            retriever_disagreement=1.0 - min(sf, df),
            unsupported=unsup, claim_conflict=conflict, sparse_freq=sf, dense_freq=df,
        )
    return feats
