"""BM25 sparse retriever.

This defines the retriever interface every other retriever (dense,
hybrid, reranked) will match: build(corpus) once, then retrieve(query,
top_k) many times. Keeping this interface identical across retrievers
is what lets `pipelines/` swap retrievers without touching anything
else (Section F of the foundation doc).
"""
from dataclasses import dataclass
from rank_bm25 import BM25Okapi


@dataclass
class RetrievedDoc:
    doc_id: str
    text: str
    score: float


class BM25Retriever:
    def __init__(self):
        self._bm25 = None
        self._doc_ids = None
        self._texts = None

    def build(self, corpus: list[dict]) -> None:
        """corpus: list of {"doc_id": str, "text": str}"""
        self._doc_ids = [d["doc_id"] for d in corpus]
        self._texts = [d["text"] for d in corpus]
        tokenized = [t.lower().split() for t in self._texts]
        self._bm25 = BM25Okapi(tokenized)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedDoc]:
        if self._bm25 is None:
            raise RuntimeError("Call .build(corpus) before .retrieve().")
        scores = self._bm25.get_scores(query.lower().split())
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            RetrievedDoc(doc_id=self._doc_ids[i], text=self._texts[i], score=float(scores[i]))
            for i in ranked
        ]
