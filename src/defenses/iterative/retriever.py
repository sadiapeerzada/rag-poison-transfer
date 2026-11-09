"""A bounded *actual* multi-round retriever, not a synonym rewrite wrapper.

The second query is built from first-round *retrieved content*. No gold
answer, poison target or adversarial label enters the policy.

The deterministic coverage/anchor heuristics are uncalibrated. This is an
exploratory iterative policy, NOT a validated learned adaptive controller.
Model/results papers must run real poisoned and clean QA before making claims.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

_STOP = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "to", "of", "in", "for",
    "and", "or", "by", "with", "what", "which", "who", "when", "where",
    "how", "did", "do", "does", "on", "from", "that", "it", "as", "at",
    "this", "these", "their", "its", "be", "been", "has", "have", "had",
    "into", "during", "before", "after", "between", "under", "over",
})
_WORD = re.compile(r"\b[a-zA-Z][a-zA-Z0-9-]*\b")
_ENTITY = re.compile(r"\b[A-Z][a-zA-Z-]+(?:\s+[A-Z][a-zA-Z-]+){0,2}\b")


def useful_tokens(text: str) -> set[str]:
    if not isinstance(text, str):
        raise ValueError("Expected plain question/evidence text")
    return {w.lower() for w in _WORD.findall(text)
            if w.lower() not in _STOP and len(w) > 2}


def evidence_coverage(query: str, documents) -> float:
    """Question-term coverage proxy, NOT correctness/answer confidence."""
    q = useful_tokens(query)
    if not q or not documents:
        return 0.0
    merged = set()
    for d in documents:
        merged.update(useful_tokens(d.text[:4000]))
    return len(q & merged) / len(q)


def select_evidence_anchor(query: str, documents) -> str | None:
    """Return a deterministic candidate entity *from evidence*, not model truth."""
    q = useful_tokens(query)
    for document in documents:
        for candidate in _ENTITY.findall(document.text[:2500]):
            tokens = useful_tokens(candidate)
            if (tokens and not tokens.issubset(q)
                    and candidate.lower() not in {"the", "this", "according"}):
                return candidate
    for document in documents:
        for token in _WORD.findall(document.text[:2500]):
            if len(token) >= 6 and token.lower() not in q and token.lower() not in _STOP:
                return token
    return None


class EvidenceDependentIterativeRetriever:
    """build/call/retrieve interface, with JSON-serializable last_diagnostics.

    Reuses ONE base retriever index, bounded to at most two real calls.
    Compared configurations must equalize cost and generator budgets.
    """

    def __init__(self, base_retriever, *, max_rounds=2, candidate_k=10,
                 output_k=3, min_coverage=0.75, round2_weight=1.25):
        if type(max_rounds) is not int or max_rounds not in (1, 2):
            raise ValueError("max_rounds must be 1 or 2")
        if (type(candidate_k) is not int or candidate_k < 1 or
            type(output_k) is not int or not 1 <= output_k <= candidate_k):
            raise ValueError("Invalid retrieval depths")
        if (type(min_coverage) not in (int, float)
            or not math.isfinite(min_coverage)
            or not 0.0 <= min_coverage <= 1.0):
            raise ValueError("Invalid coverage threshold")
        if (type(round2_weight) not in (int, float)
            or not math.isfinite(round2_weight) or round2_weight <= 0):
            raise ValueError("Invalid round-two RRF weight")
        self.base_retriever = base_retriever
        self.max_rounds = max_rounds
        self.candidate_k = candidate_k
        self.output_k = output_k
        self.min_coverage = min_coverage
        self.round2_weight = round2_weight
        self.last_diagnostics = None

    def build(self, corpus):
        self.base_retriever.build(corpus)

    def retrieve(self, query: str, top_k: int | None = None):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Question must be nonempty")
        k = self.output_k if top_k is None else top_k
        if type(k) is not int or not 1 <= k <= self.candidate_k:
            raise ValueError("top_k must be positive and <= candidate_k")
        scores = defaultdict(float)
        docs = {}
        first_seen = {}
        rounds = []
        q = query
        action = "answer"
        for index in range(self.max_rounds):
            results = self.base_retriever.retrieve(q, top_k=self.candidate_k)
            current_ids = set()
            for rank, doc in enumerate(results, start=1):
                if (not isinstance(doc.doc_id, str) or
                    not isinstance(doc.text, str) or not doc.doc_id):
                    raise ValueError("Malformed retrieved document")
                if doc.doc_id in current_ids:
                    raise ValueError("Repeated document in a single retrieval result")
                current_ids.add(doc.doc_id)
                if doc.doc_id in docs and docs[doc.doc_id].text != doc.text:
                    raise ValueError("Document ID has changed text between rounds")
                if doc.doc_id not in docs:
                    docs[doc.doc_id] = doc
                    first_seen[doc.doc_id] = (index, rank)
                weight = self.round2_weight if index > 0 else 1.0
                scores[doc.doc_id] += weight / (60 + rank)
            coverage = evidence_coverage(query, results)
            trace = {
                "round": index + 1, "query": q,
                "retrieved_doc_ids": [doc.doc_id for doc in results],
                "question_term_coverage_proxy": coverage,
                "anchor_from_prior_evidence": None,
            }
            rounds.append(trace)
            if not results:
                action = "abstain"
                trace["action"] = action
                break
            if coverage >= self.min_coverage or index + 1 >= self.max_rounds:
                action = "answer"
                trace["action"] = action
                break
            anchor = select_evidence_anchor(query, results)
            if anchor is None:
                action = "abstain"
                trace["action"] = action
                break
            new_query = f"{query} {anchor}"
            if new_query == q:
                action = "abstain"
                trace["action"] = action
                break
            trace["action"] = "retrieve_again"
            trace["anchor_from_prior_evidence"] = anchor
            q = new_query

        ranked_ids = sorted(scores, key=lambda doc_id: (
            -scores[doc_id], first_seen[doc_id], doc_id
        ))
        self.last_diagnostics = {
            "schema": "rag-poison-transfer.iterative-retrieval-trace/v1",
            "policy": "deterministic-first-evidence-anchor-coverage/v1",
            "threshold_type": "lexical_question_coverage_proxy_not_calibrated",
            "retrieval_call_count": len(rounds),
            "final_decision": action,
            "rounds": rounds,
            "all_ranked_doc_ids": ranked_ids,
            "selected_doc_ids": ranked_ids[:k] if action == "answer" else [],
        }
        return [docs[doc_id] for doc_id in ranked_ids[:k]] if action == "answer" else []
