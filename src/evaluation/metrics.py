"""Exact Match and F1 for QA, using the standard SQuAD-style normalization.
Plus retrieval-quality metrics (Recall@k, MRR, nDCG@k), which measure
whether the RETRIEVER found the right evidence -- independent of whether
the generator then used it correctly. These require `gold_doc_ids` on a
query (see src/data/loaders.py); older toy-dataset queries don't have
them, so callers should skip retrieval metrics when the field is absent
rather than treating a missing gold set as "zero relevant docs."

The full metric suite (ASR, ATR, Poison Retrieval Rate@k, faithfulness,
AUROC, etc. from Section 7/11) gets added incrementally in later weeks,
each with its own test, per Section 16's "explain before large code" rule.
"""
import math
import re
import string
from collections import Counter


def normalize_answer(s: str) -> str:
    s = s.lower()
    s = "".join(ch for ch in s if ch not in string.punctuation)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = " ".join(s.split())
    return s


def exact_match(prediction: str, gold: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(gold))


def f1_score(prediction: str, gold: str) -> float:
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(gold).split()
    if len(pred_tokens) == 0 or len(gold_tokens) == 0:
        return float(pred_tokens == gold_tokens)
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def recall_at_k(retrieved_doc_ids: list[str], gold_doc_ids: list[str], k: int) -> float | None:
    """Standard IR Recall@k: fraction of this query's gold/relevant docs
    that appear anywhere in the top-k retrieved results.

        Recall@k = |top_k(retrieved) ∩ gold| / |gold|

    Returns None (not 0.0) if `gold_doc_ids` is empty -- a query with no
    gold docs has UNDEFINED recall, not zero recall. Callers should
    exclude None results from an average rather than counting them as
    failures, or they'll silently understate the real score.

    IMPORTANT: `retrieved_doc_ids[:k]` only reflects docs actually
    retrieved by the pipeline. If the pipeline only ever retrieves 3
    docs (top_k=3 in the config), calling this with k=10 silently
    computes Recall@3, not Recall@10 -- there's no way to distinguish
    "nothing relevant beyond rank 3" from "we never looked beyond rank
    3." Only call this with a k <= the number of docs actually
    retrieved for that query.
    """
    if not gold_doc_ids:
        return None
    top_k_ids = set(retrieved_doc_ids[:k])
    gold = set(gold_doc_ids)
    return len(top_k_ids & gold) / len(gold)


def mrr(retrieved_doc_ids: list[str], gold_doc_ids: list[str], k: int | None = None) -> float | None:
    """Mean Reciprocal Rank (for a single query -- average across queries
    yourself to get the usual "MRR@k" reported in papers).

    Reciprocal rank of the FIRST retrieved doc that's in gold_doc_ids,
    1-indexed (rank 1 -> 1.0, rank 2 -> 0.5, ...). 0.0 if no gold doc
    appears in the considered results at all.

    `k=None` (default) considers the full retrieved list; pass an
    explicit k to cap it -- same "only retrieved, not hypothetical"
    caveat as recall_at_k applies.

    Returns None if `gold_doc_ids` is empty (undefined, not 0.0).
    """
    if not gold_doc_ids:
        return None
    gold = set(gold_doc_ids)
    candidates = retrieved_doc_ids[:k] if k is not None else retrieved_doc_ids
    for rank, doc_id in enumerate(candidates, start=1):
        if doc_id in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_doc_ids: list[str], gold_doc_ids: list[str], k: int) -> float | None:
    """Normalized Discounted Cumulative Gain @ k, with BINARY relevance
    (a doc is either in gold_doc_ids, relevance=1, or it isn't,
    relevance=0). We use binary rather than graded relevance because
    HotpotQA's supporting-fact docs aren't ranked by importance --
    graded nDCG would need a relevance judgment we don't have.

        DCG@k  = sum_{i=1}^{k} rel_i / log2(i + 1)
        IDCG@k = DCG@k of the best possible ranking (all relevant docs
                 first, up to k)
        nDCG@k = DCG@k / IDCG@k   (1.0 = perfect ranking, 0.0 = no
                 relevant docs retrieved in the top k)

    Returns None if `gold_doc_ids` is empty (undefined -- IDCG would be
    0, so this would otherwise silently become a 0/0 -> treated-as-1.0
    trap if not handled explicitly).

    Same "only retrieved, not hypothetical" caveat as recall_at_k: k
    must not exceed the number of docs actually retrieved, or this
    silently computes nDCG@(len(retrieved)) under a different label.
    """
    if not gold_doc_ids:
        return None
    gold = set(gold_doc_ids)
    top_k_ids = retrieved_doc_ids[:k]

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(top_k_ids, start=1)
        if doc_id in gold
    )
    ideal_relevant_count = min(len(gold), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_relevant_count + 1))
    return dcg / idcg if idcg > 0 else 0.0
