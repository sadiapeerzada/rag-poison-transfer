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


def poison_retrieval_rate_at_k(
    retrieved_doc_ids: list[str], poison_doc_ids: list[str], k: int
) -> float | None:
    """Poison Retrieval Rate@k: fraction of POISON-DOC-ATTACKED QUERIES
    that retrieve at least one poison document in the top-k results.
    
    Used to measure how effectively injected poison/adversarial documents
    rank high enough to influence the retriever's output.
    
        PRR@k = number of queries retrieving poison in top-k
                /
                number of queries with poison attempted
    
    This is a PER-QUERY metric. To compute the aggregate PRR across an
    experiment, accumulate per-query PRR@k values and average them, or
    count queries retrieving poison / total attacked queries.
    
    Returns 1.0 if at least one poison doc is in top-k, else 0.0.
    Returns None if poison_doc_ids is empty (undefined -- cannot measure
    poison retrieval for a query with no poisoned candidates).
    
    Note: This assumes poison_doc_ids and retrieved_doc_ids use the
    same document-ID scheme (e.g., canonical IDs).
    """
    if not poison_doc_ids:
        return None
    poison = set(poison_doc_ids)
    top_k_ids = set(retrieved_doc_ids[:k])
    return 1.0 if len(top_k_ids & poison) > 0 else 0.0


def attack_success_rate(
    attack_results: list[dict],
) -> float | None:
    """Attack Success Rate (ASR): fraction of poisoned queries where the
    attack succeeded (i.e., the model's answer on poisoned evidence differed
    from the ground truth in the expected way).
    
    Requires `attack_results`, a list of dicts with fields:
        - attack_success: bool (pre-computed boolean indicating if attack worked)
        - (other fields like attacked_answer, gold_answer, poison_doc_ids are
          available for future extensions)
    
    Returns the fraction of queries where attack_success is True.
    
    Returns None if the result list is empty.
    
    Note: attack_success is expected to be pre-computed and attached by the
    attack generation/evaluation pipeline, not computed here from raw answers.
    """
    if not attack_results:
        return None
    successful = sum(
        1 for result in attack_results
        if result.get("attack_success", False)
    )
    return successful / len(attack_results) if attack_results else None


def attack_transfer_rate(
    source_results: list[dict],
    target_results: list[dict],
) -> float | None:
    """Attack Transfer Rate (ATR): fraction of queries where an attack
    successful in the SOURCE pipeline also transfers to the TARGET
    pipeline. Uses query_id alignment regardless of input order.
    
    Requires both source_results and target_results to be lists of dicts,
    each with a 'query_id' field and 'attack_success' boolean.
    
        ATR = count(queries where source_attack_success AND
              target_attack_success)
              /
              count(queries where source_attack_success)
    
    Alignment policy: Queries are matched by query_id, not position.
    - If a query_id appears in one list but not the other, raises ValueError.
    - If a query_id is duplicated within a list, raises ValueError.
    - Reordered inputs (same query_ids in different order) produce the same ATR.
    
    Returns None if no queries were successfully attacked in source, or
    if either result list is empty.
    """
    if not source_results or not target_results:
        return None
    
    # Build dicts indexed by query_id for alignment
    source_by_id = {}
    for result in source_results:
        qid = result.get("query_id")
        if qid is None:
            raise ValueError(
                "source_results contains entry without query_id field"
            )
        if qid in source_by_id:
            raise ValueError(
                f"source_results has duplicate query_id={qid!r}"
            )
        source_by_id[qid] = result
    
    target_by_id = {}
    for result in target_results:
        qid = result.get("query_id")
        if qid is None:
            raise ValueError(
                "target_results contains entry without query_id field"
            )
        if qid in target_by_id:
            raise ValueError(
                f"target_results has duplicate query_id={qid!r}"
            )
        target_by_id[qid] = result
    
    # Check that both lists have the same set of query_ids
    source_ids = set(source_by_id.keys())
    target_ids = set(target_by_id.keys())
    if source_ids != target_ids:
        missing_in_target = source_ids - target_ids
        missing_in_source = target_ids - source_ids
        msg = []
        if missing_in_target:
            msg.append(f"query_ids in source but not target: {missing_in_target}")
        if missing_in_source:
            msg.append(f"query_ids in target but not source: {missing_in_source}")
        raise ValueError(
            "source_results and target_results have mismatched query_ids: "
            + "; ".join(msg)
        )
    
    # Count successful source attacks
    source_attack_count = sum(
        1 for result in source_results
        if result.get("attack_success", False)
    )
    
    if source_attack_count == 0:
        return None  # No attacks to transfer
    
    # Count transferred attacks (source successful AND target successful,
    # matched by query_id)
    transferred = 0
    for qid, source_result in source_by_id.items():
        if source_result.get("attack_success", False):
            target_result = target_by_id[qid]
            if target_result.get("attack_success", False):
                transferred += 1
    
    return transferred / source_attack_count
