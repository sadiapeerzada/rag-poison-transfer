"""Cross-encoder reranker: rescore an initial retriever's candidates.

Takes any retriever's output as input candidates, rescores each
(query, doc) pair with a more expensive cross-encoder, and returns a
re-sorted top_k. This is a rescoring STAGE, not a standalone retriever
-- it always wraps another retriever's output.
"""
from dataclasses import dataclass


@dataclass
class RetrievedDoc:
    doc_id: str
    text: str
    score: float


class MockCrossEncoderScorer:
    """Deterministic overlap-based scorer. Testing only, not semantic."""

    def score(self, query: str, doc_text: str) -> float:
        q_words = set(query.lower().split())
        d_words = set(doc_text.lower().split())
        if not q_words:
            return 0.0
        return len(q_words & d_words) / len(q_words)


class CrossEncoderScorer:
    """Real cross-encoder scorer. Run on your Mac, not in a sandbox."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for CrossEncoderScorer. "
                "Install with:\n  pip install sentence-transformers\n"
            ) from e
        self.model = CrossEncoder(model_name)

    def score(self, query: str, doc_text: str) -> float:
        return float(self.model.predict([(query, doc_text)])[0])


class Reranker:
    def __init__(self, base_retriever, scorer=None):
        self.base_retriever = base_retriever
        self.scorer = scorer or MockCrossEncoderScorer()

    def build(self, corpus: list[dict]) -> None:
        self.base_retriever.build(corpus)

    def retrieve(self, query: str, top_k: int = 5, candidate_pool: int = 20) -> list[RetrievedDoc]:
        candidates = self.base_retriever.retrieve(query, top_k=candidate_pool)
        rescored = [
            RetrievedDoc(doc_id=c.doc_id, text=c.text, score=self.scorer.score(query, c.text))
            for c in candidates
        ]
        rescored.sort(key=lambda d: d.score, reverse=True)
        return rescored[:top_k]
