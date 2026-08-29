"""Dense (embedding-based) retriever.

Same interface as BM25Retriever (build/retrieve) so pipelines can swap
retrievers freely (Section F of the foundation doc).

Embedding is pluggable via the `embedder` argument:
- SentenceTransformerEmbedder: the REAL embedder (BGE/E5-family).
  Requires `pip install sentence-transformers` and downloads a model
  the first time -- run this on your Mac, not in a sandbox with no
  internet access to Hugging Face.
- HashingEmbedder: a deterministic bag-of-words embedder with NO model
  download. Used only to test the retrieval/ranking/fusion LOGIC here
  without needing real embeddings. Never use it for real results --
  it has no semantic understanding, just word-hash buckets.
"""
import numpy as np
from dataclasses import dataclass


@dataclass
class RetrievedDoc:
    doc_id: str
    text: str
    score: float


class HashingEmbedder:
    """Deterministic bag-of-words hashing embedder. Testing only."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                vectors[i, hash(word) % self.dim] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


class SentenceTransformerEmbedder:
    """Real embedder. Run on your Mac, not in a sandbox."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required. Install with:\n"
                "  pip install sentence-transformers\n"
            ) from e
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


class DenseRetriever:
    def __init__(self, embedder=None):
        self.embedder = embedder or HashingEmbedder()
        self._doc_ids = None
        self._texts = None
        self._doc_vectors = None

    def build(self, corpus: list[dict]) -> None:
        self._doc_ids = [d["doc_id"] for d in corpus]
        self._texts = [d["text"] for d in corpus]
        self._doc_vectors = self.embedder.encode(self._texts)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedDoc]:
        if self._doc_vectors is None:
            raise RuntimeError("Call .build(corpus) before .retrieve().")
        query_vec = self.embedder.encode([query])[0]
        scores = self._doc_vectors @ query_vec  # cosine sim, since vectors are normalized
        ranked = np.argsort(-scores)[:top_k]
        return [
            RetrievedDoc(doc_id=self._doc_ids[i], text=self._texts[i], score=float(scores[i]))
            for i in ranked
        ]
