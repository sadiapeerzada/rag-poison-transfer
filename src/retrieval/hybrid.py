"""Hybrid retriever: reciprocal rank fusion (RRF) of two retrievers.

RRF combines rankings (not raw scores, which are on incomparable
scales between BM25 and dense cosine similarity) using:
    RRF_score(doc) = sum over retrievers of 1 / (k_rrf + rank(doc))
This is the standard, parameter-light way to fuse sparse + dense
retrieval (Section K of the foundation doc).

Works with ANY two retrievers that share the build/retrieve interface
-- doesn't care if they're BM25+Dense or something else entirely.
"""
from dataclasses import dataclass


@dataclass
class RetrievedDoc:
    doc_id: str
    text: str
    score: float


class HybridRetriever:
    def __init__(self, retriever_a, retriever_b, k_rrf: int = 60):
        self.retriever_a = retriever_a
        self.retriever_b = retriever_b
        self.k_rrf = k_rrf
        self._doc_lookup = {}  # doc_id -> text, populated on build

    def build(self, corpus: list[dict]) -> None:
        self.retriever_a.build(corpus)
        self.retriever_b.build(corpus)
        self._doc_lookup = {d["doc_id"]: d["text"] for d in corpus}

    def retrieve(self, query: str, top_k: int = 5, candidate_pool: int = 50) -> list[RetrievedDoc]:
        # Pull a larger candidate pool from each retriever before fusing,
        # so the fused top_k isn't artificially limited by either
        # retriever's own top_k cutoff.
        results_a = self.retriever_a.retrieve(query, top_k=candidate_pool)
        results_b = self.retriever_b.retrieve(query, top_k=candidate_pool)

        rrf_scores: dict[str, float] = {}
        for rank, doc in enumerate(results_a):
            rrf_scores[doc.doc_id] = rrf_scores.get(doc.doc_id, 0.0) + 1.0 / (self.k_rrf + rank + 1)
        for rank, doc in enumerate(results_b):
            rrf_scores[doc.doc_id] = rrf_scores.get(doc.doc_id, 0.0) + 1.0 / (self.k_rrf + rank + 1)

        ranked_ids = sorted(rrf_scores, key=lambda d: rrf_scores[d], reverse=True)[:top_k]
        return [
            RetrievedDoc(doc_id=doc_id, text=self._doc_lookup[doc_id], score=rrf_scores[doc_id])
            for doc_id in ranked_ids
        ]
