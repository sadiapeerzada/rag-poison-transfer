"""Cross-pipeline poison-retrieval evaluation.

Answers the core research question: an attack (lexical or semantic-
fluent) produces poison content without knowledge of which retriever
will index it -- does it fool ALL FOUR retrievers, or just some? This
measures PRR@k per retriever against the SAME poisoned corpus, so the
comparison is apples-to-apples (same poison, same queries, only the
retriever differs).

Retriever instances are passed in already-constructed (not built), so
tests can use cheap retrievers (BM25Retriever, DenseRetriever with a
HashingEmbedder) without downloading real models -- see
build_standard_retrievers() below for the REAL 4-retriever set matching
Clean Baseline v1, for actual experiments.
"""
from src.evaluation.metrics import poison_retrieval_rate_at_k

_PRR_KS = (1, 3, 5, 10)


def evaluate_poison_across_retrievers(poisoned_data: dict, retrievers: dict, top_k: int = 10) -> dict:
    """
    Args:
        poisoned_data: output of inject_poisons() -- {corpus, queries},
            where attacked queries have non-empty poison_doc_ids.
        retrievers: dict mapping retriever_name -> an UNBUILT retriever
            instance implementing .build(corpus) / .retrieve(query, top_k).
            Each gets its own .build() call on the SAME poisoned corpus.
        top_k: retrieval depth for PRR computation (should be >= max(_PRR_KS)).

    Returns:
        {retriever_name: {"mean_prr": {1: float|None, 3: ..., 5: ..., 10: ...},
                           "per_query": [ {query_id, poison_doc_ids,
                                           retrieved_doc_ids, poison_rank,
                                           poison_retrieved, "prr@1": ..., ...}, ... ]}}
    """
    attacked_queries = [q for q in poisoned_data["queries"] if q["poison_doc_ids"]]
    if not attacked_queries:
        raise ValueError("poisoned_data has no attacked queries (all poison_doc_ids empty) -- nothing to evaluate")

    results = {}
    for name, retriever in retrievers.items():
        retriever.build(poisoned_data["corpus"])
        per_query = []
        prr_accum = {k: [] for k in _PRR_KS}

        for query in attacked_queries:
            retrieved = retriever.retrieve(query["question"], top_k=max(top_k, max(_PRR_KS)))
            retrieved_ids = [r.doc_id for r in retrieved]
            poison_set = set(query["poison_doc_ids"])

            poison_rank = None
            for rank, doc_id in enumerate(retrieved_ids, start=1):
                if doc_id in poison_set:
                    poison_rank = rank
                    break

            record = {
                "query_id": query["query_id"],
                "poison_doc_ids": query["poison_doc_ids"],
                "retrieved_doc_ids": retrieved_ids,
                "poison_rank": poison_rank,
                "poison_retrieved": poison_rank is not None,
            }
            for k in _PRR_KS:
                score = poison_retrieval_rate_at_k(retrieved_ids, query["poison_doc_ids"], k)
                record[f"prr@{k}"] = score
                if score is not None:
                    prr_accum[k].append(score)
            per_query.append(record)

        mean_prr = {k: (sum(v) / len(v) if v else None) for k, v in prr_accum.items()}
        results[name] = {"mean_prr": mean_prr, "per_query": per_query}

    return results


def build_standard_retrievers(embedder_model: str = "BAAI/bge-small-en-v1.5",
                                reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> dict:
    """Build the real 4-retriever set matching Clean Baseline v1's setup,
    for actual experiments (downloads real models -- not for unit tests).
    """
    from run import build_retriever
    configs = {
        "bm25": {"retriever": "bm25"},
        "dense": {"retriever": "dense", "embedder_model": embedder_model},
        "hybrid": {"retriever": "hybrid", "embedder_model": embedder_model},
        "reranker": {"retriever": "reranker", "embedder_model": embedder_model, "reranker_model": reranker_model},
    }
    return {name: build_retriever(cfg) for name, cfg in configs.items()}
