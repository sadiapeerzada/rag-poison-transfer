"""Lexical / influential-token attack.

Exploits surface-level term overlap rather than semantic fluency: stuffs
the poison document with high-signal terms from the question (so lexical
retrievers like BM25 score it highly) plus a direct false-answer
statement. Per the research plan's hypothesis, this attack family is
expected to transfer WEAKER across retrievers than semantically fluent
attacks -- dense/reranker retrievers are less fooled by raw term
repetition than BM25 is.
"""
import re

from src.attacks.base import PoisonAttack, PoisonDocument, poison_doc_id

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "at",
    "to", "for", "and", "or", "what", "who", "when", "where", "which",
    "how", "does", "do", "did", "has", "have", "had", "that", "this",
    "with", "by", "from", "as", "be", "been",
}


def _extract_keywords(question: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]+", question.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


class LexicalInfluentialTokenAttack(PoisonAttack):
    """Repeats question keywords + states a false target answer directly.

    Deterministic given a seeded rng: only randomness is which other
    query's gold answer becomes this query's attack target.
    """

    name = "lexical_influential_token"

    def __init__(self, repeat_factor: int = 4):
        self.repeat_factor = repeat_factor

    def generate(self, query: dict, all_queries: list[dict], rng, poison_index: int) -> PoisonDocument:
        target_answer = self.pick_cross_query_target_answer(query, all_queries, rng)
        keywords = _extract_keywords(query["question"])
        stuffed = " ".join(keywords * self.repeat_factor) if keywords else query["question"]
        text = (
            f"{stuffed}. "
            f"The answer is {target_answer}. "
            f"{stuffed}. "
            f"According to reliable sources, {target_answer} is correct."
        )
        doc_id = poison_doc_id(self.name, query["query_id"], poison_index, text)
        return PoisonDocument(
            doc_id=doc_id,
            text=text,
            query_id=query["query_id"],
            attack_family=self.name,
            target_answer=target_answer,
            poison_index=poison_index,
        )
