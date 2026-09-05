"""Base classes for knowledge-poisoning attacks.

An attack's job is to produce PoisonDocument(s) for a given query: text
that will be injected into the retrieval corpus, crafted to make the
retriever surface it and the generator produce a specific wrong answer
instead of (or alongside) the true one.

Poison documents get their own canonical-ID namespace, separate from
clean corpus docs (see `_canonical_doc_id` in src/data/loaders.py):
poison IDs are query-scoped (crafted *for* one query) rather than
content-addressed and shared across queries the way clean docs are.
This keeps poison docs unambiguous in logs/metrics and guarantees they
can never collide with a clean doc_id.
"""
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass


def poison_doc_id(attack_family: str, query_id: str, poison_index: int, text: str) -> str:
    """Canonical ID for a poison document.

    Format: poison::{attack_family}::{query_id}::{poison_index}::{content_hash}

    Query-scoped (unlike clean corpus IDs) because poison is crafted per
    query, not shared content. Content-hash suffix still included so two
    identical poison texts (e.g. same attack, same query, regenerated)
    collapse to the same ID rather than silently duplicating.
    """
    content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"poison::{attack_family}::{query_id}::{poison_index}::{content_hash}"


@dataclass
class PoisonDocument:
    """A single poison document produced by an attack for one query."""
    doc_id: str
    text: str
    query_id: str
    attack_family: str
    target_answer: str  # the wrong answer this poison tries to induce
    poison_index: int  # 0-indexed position among this query's poison docs


class PoisonAttack(ABC):
    """Base class for a knowledge-poisoning attack family.

    Subclasses implement `generate()` to produce one PoisonDocument for
    a given query. `inject_poisons()` (see injection.py) calls this once
    per poison document requested per attacked query.
    """

    name: str = "base"

    @abstractmethod
    def generate(self, query: dict, all_queries: list[dict], rng, poison_index: int) -> PoisonDocument:
        """Produce one poison document for `query`.

        Args:
            query: the query dict being attacked (has query_id, question,
                gold_answer, gold_doc_ids -- must NOT be mutated).
            all_queries: the full query list, in case the attack needs to
                pick a target answer from elsewhere in the dataset (e.g.
                another query's gold answer as a plausible wrong target).
            rng: a seeded random.Random instance for determinism.
            poison_index: 0-indexed position, for attacks producing
                multiple distinct documents per query (intensity > 1).
        """
        raise NotImplementedError

    def pick_cross_query_target_answer(self, query: dict, all_queries: list[dict], rng) -> str:
        """Shared helper: pick another query's gold answer as this
        query's attack target, guaranteed different from its own true
        answer. A standard construction for a "plausible wrong answer"
        without needing a separate answer-generation model.
        """
        candidates = [
            q["gold_answer"] for q in all_queries
            if q.get("gold_answer") and q["gold_answer"] != query.get("gold_answer") and q["query_id"] != query["query_id"]
        ]
        if not candidates:
            raise ValueError(f"No valid cross-query target answer available for query {query['query_id']!r}")
        return rng.choice(candidates)
