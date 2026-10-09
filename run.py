"""Dataset -> Retrieval -> Generator -> EM/F1.

Run with:
    python run.py --config configs/exp_000_smoke.yaml

Supports two data sources, chosen by config:
- dataset_path: static JSON (toy dataset -- exp_000/001/002)
- dataset_loader: a real dataset via src/data/loaders.py (exp_003+)
  Requires internet access to Hugging Face; run on your Mac.
"""
import argparse
import json
import hashlib

from src.utils.config import load_config
from src.utils.seeding import set_seed
from src.utils.logging_utils import ExperimentLogger
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever, SentenceTransformerEmbedder
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.reranker import Reranker, CrossEncoderScorer
from src.defenses.rcd.retriever import RCDRetriever
from src.pipelines.generator import MockGenerator, MLXGenerator, TransformersGenerator
from src.evaluation.metrics import (
    exact_match,
    f1_score,
    recall_at_k,
    mrr,
    ndcg_at_k,
)
from src.experiments.protocol import build_experiment_metadata



def build_retriever(config: dict):
    """Build the configured retriever."""
    kind = config.get("retriever", "bm25")

    if kind == "bm25":
        return BM25Retriever()

    elif kind == "dense":
        embedder_model = config.get("embedder_model", "BAAI/bge-small-en-v1.5")
        return DenseRetriever(
            SentenceTransformerEmbedder(embedder_model)
        )

    elif kind == "hybrid":
        embedder_model = config.get("embedder_model", "BAAI/bge-small-en-v1.5")
        return HybridRetriever(
            BM25Retriever(),
            DenseRetriever(
                SentenceTransformerEmbedder(embedder_model)
            ),
        )

    elif kind == "rcd":
        embedder_model = config.get("embedder_model", "BAAI/bge-small-en-v1.5")
        top_k = int(config.get("top_k", 3))
        dense = DenseRetriever(
            SentenceTransformerEmbedder(embedder_model)
        )
        return RCDRetriever(
            dense,
            sparse_retriever=BM25Retriever(),
            dense_retriever=dense,
            candidate_k=int(config.get("rcd_candidate_k", 10)),
            output_k=top_k,
            rewrite_count=int(config.get("rcd_rewrite_count", 3)),
            consistency_weight=float(
                config.get("rcd_consistency_weight", 0.55)
            ),
            redundancy_weight=float(
                config.get("rcd_redundancy_weight", 0.05)
            ),
            conflict_weight=float(
                config.get("rcd_conflict_weight", 0.20)
            ),
            base_rank_weight=float(
                config.get("rcd_base_rank_weight", 0.20)
            ),
        )

    elif kind == "reranker":
        embedder_model = config.get("embedder_model", "BAAI/bge-small-en-v1.5")
        reranker_model = config.get("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        # Plan spec (Section 6): "dense + cross-encoder reranking" -- base
        # retriever must be dense, not BM25, so this is genuinely a second
        # reranking stage on top of the dense pipeline, not a BM25 variant.
        return Reranker(
            DenseRetriever(SentenceTransformerEmbedder(embedder_model)),
            CrossEncoderScorer(reranker_model),
        )

    else:
        raise ValueError(f"Unknown retriever: {kind}")


def build_generator(config: dict):
    if config["generator_backend"] == "mock":
        return MockGenerator()
    elif config["generator_backend"] == "mlx":
        return MLXGenerator(model_name=config["generator_model"])
    elif config["generator_backend"] == "transformers":
        return TransformersGenerator(
            model_name=config["generator_model"],
            load_in_4bit=config.get("load_in_4bit", True),
        )
    else:
        raise ValueError(f"Unknown generator_backend: {config['generator_backend']}")


def _heldout_manifest_fingerprint(config: dict) -> str | None:
    """Validate and return the held-out query-ID fingerprint."""
    manifest_path = config.get("dataset_query_ids_manifest")
    if not manifest_path:
        return None

    with open(manifest_path, encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    return manifest.get("heldout_query_ids_fingerprint")


def load_dataset(config: dict) -> dict:
    """Returns {"corpus": [...], "queries": [...]}, from either a static
    JSON file (toy dataset) or a real loader in src/data/loaders.py.
    """
    if "dataset_loader" in config:
        from src.data import loaders as real_loaders
        loader_name = config["dataset_loader"]
        loader_fn = getattr(real_loaders, loader_name, None)
        if loader_fn is None:
            raise ValueError(
                f"Unknown dataset_loader: {loader_name!r}. "
                f"Check src/data/loaders.py for available loader function names."
            )
        kwargs = {}
        if "dataset_split" in config:
            kwargs["split"] = config["dataset_split"]
        if "dataset_n_samples" in config:
            kwargs["n_samples"] = config["dataset_n_samples"]
        if "dataset_seed" in config:
            kwargs["seed"] = config["dataset_seed"]
        if "dataset_revision" in config:
            kwargs["revision"] = config["dataset_revision"]
        if "dataset_query_ids_manifest" in config:
            manifest_path = config["dataset_query_ids_manifest"]
            with open(manifest_path, encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)

            query_ids = manifest.get("heldout_query_ids")
            if not isinstance(query_ids, list):
                raise ValueError("Held-out manifest has no query ID list.")
            if len(query_ids) != manifest.get("heldout_query_count"):
                raise ValueError("Held-out manifest query count mismatch.")
            if len(query_ids) != len(set(query_ids)):
                raise ValueError("Held-out manifest contains duplicate query IDs.")

            fingerprint = hashlib.sha256(
                "\n".join(query_ids).encode("utf-8")
            ).hexdigest()
            if fingerprint != manifest.get("heldout_query_ids_fingerprint"):
                raise ValueError("Held-out manifest fingerprint mismatch.")
            if manifest.get("dataset_revision") != config.get("dataset_revision"):
                raise ValueError("Manifest and config dataset revisions differ.")
            if manifest.get("dataset_split") != config.get("dataset_split"):
                raise ValueError("Manifest and config dataset splits differ.")

            kwargs["query_ids"] = query_ids
        elif "dataset_query_ids" in config:
            kwargs["query_ids"] = config["dataset_query_ids"]
        return loader_fn(**kwargs)
    else:
        with open(config["dataset_path"]) as f:
            return json.load(f)


def build_prompt(question: str, evidence_docs: list) -> str:
    evidence_text = "\n".join(f"- {d.text}" for d in evidence_docs)
    return (
        "Answer the question using only the evidence below.\n"
        "Respond with ONLY the short factual answer (a name, place, date, or number). "
        "No explanation, no extra sentences, no punctuation-terminated reasoning.\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )


def main(config_path: str):
    config = load_config(config_path)
    set_seed(config["seed"])

    data = load_dataset(config)

    retriever = build_retriever(config)
    retriever.build(data["corpus"])

    generator = build_generator(config)
    logger = ExperimentLogger(config["results_dir"], config["experiment_id"], config=config)

    em_scores, f1_scores = [], []
    retrieval_metric_scores = {}

    for q in data["queries"]:
        # Retrieve enough ranked documents to evaluate Recall@1/3/5/10,
        # MRR@1/3/5/10, and nDCG@10. Generation still uses only the
        # configured top_k evidence documents.
        retrieval_metric_k = 10
        retrieved_for_metrics = retriever.retrieve(
            q["question"],
            top_k=max(config["top_k"], retrieval_metric_k),
        )
        retrieved = retrieved_for_metrics[:config["top_k"]]

        # Capture RCD internals from the retrieval call without changing
        # the retrieval API used by the rest of the experiment.
        rcd_diagnostics = (
            retriever.last_diagnostics
            if isinstance(retriever, RCDRetriever)
            else None
        )

        prompt = build_prompt(q["question"], retrieved)
        gen_result = generator.generate(prompt, max_tokens=config["max_tokens"])
        extracted = gen_result.text.split("\n")[0].split(". ")[0].strip()
        gen_result.text = extracted

        em = exact_match(gen_result.text, q["gold_answer"])
        f1 = f1_score(gen_result.text, q["gold_answer"])

        # Retrieval metrics use the actual ranked retrieval output,
        # not the smaller evidence set passed to the generator.
        retrieved_doc_ids = [d.doc_id for d in retrieved_for_metrics]
        gold_doc_ids = q.get("gold_doc_ids", [])

        # RCD ranks documents using its final defense score rather than
        # the underlying base-retriever score stored on each document.
        # Preserve the base score separately for diagnostics/backward
        # compatibility while making retrieved_scores reflect the actual
        # ranking used for evaluation.
        if rcd_diagnostics is not None:
            rcd_scores = rcd_diagnostics.get("scores", {})
            retrieved_scores = [
                rcd_scores[doc_id]["final_score"]
                for doc_id in retrieved_doc_ids
            ]
            base_retriever_scores = [
                d.score
                for d in retrieved_for_metrics
            ]
        else:
            retrieved_scores = [
                d.score
                for d in retrieved_for_metrics
            ]
            base_retriever_scores = None

        recall_1 = recall_at_k(retrieved_doc_ids, gold_doc_ids, 1)
        recall_3 = recall_at_k(retrieved_doc_ids, gold_doc_ids, 3)
        recall_5 = recall_at_k(retrieved_doc_ids, gold_doc_ids, 5)
        recall_10 = recall_at_k(retrieved_doc_ids, gold_doc_ids, 10)
        mrr_1 = mrr(retrieved_doc_ids, gold_doc_ids, 1)
        mrr_3 = mrr(retrieved_doc_ids, gold_doc_ids, 3)
        mrr_5 = mrr(retrieved_doc_ids, gold_doc_ids, 5)
        mrr_10 = mrr(retrieved_doc_ids, gold_doc_ids, 10)
        retrieval_ndcg_10 = ndcg_at_k(
            retrieved_doc_ids, gold_doc_ids, 10
        )

        retrieval_metrics = {
            "recall@1": recall_1,
            "recall@3": recall_3,
            "recall@5": recall_5,
            "recall@10": recall_10,
            "mrr@1": mrr_1,
            "mrr@3": mrr_3,
            "mrr@5": mrr_5,
            "mrr@10": mrr_10,
            "ndcg@10": retrieval_ndcg_10,
        }
        for metric_name, metric_value in retrieval_metrics.items():
            if metric_value is not None:
                retrieval_metric_scores.setdefault(metric_name, []).append(metric_value)

        em_scores.append(em)
        f1_scores.append(f1)

        logger.log({
            "experiment_id": config["experiment_id"],
            "config_hash": config["_config_hash"],
            "query_id": q["query_id"],
            "question": q["question"],
            "gold_answer": q["gold_answer"],
            "retrieved_doc_ids": retrieved_doc_ids,
            "retrieved_scores": [d.score for d in retrieved_for_metrics],
            "gold_doc_ids": gold_doc_ids,
            "gold_supporting_facts": q.get("gold_supporting_facts", []),
            "prompt": prompt,
            "generated_text": gen_result.text,
            "latency_seconds": gen_result.latency_seconds,
            "prompt_tokens": gen_result.prompt_tokens,
            "completion_tokens": gen_result.completion_tokens,
            "em": em,
            "f1": f1,
            "retrieval_metrics": retrieval_metrics,
            # Preserve the existing flat fields for backwards compatibility.
            "recall_at_1": recall_1,
            "recall_at_3": recall_3,
            "recall_at_5": recall_5,
            "recall_at_10": recall_10,
            "mrr_at_1": mrr_1,
            "mrr_at_3": mrr_3,
            "mrr_at_5": mrr_5,
            "mrr_at_10": mrr_10,
            "mrr": mrr_10,
            "ndcg_at_10": retrieval_ndcg_10,
            "generator_backend": config["generator_backend"],
            "retrieval_call_count": (
                rcd_diagnostics.get("retrieval_call_count")
                if rcd_diagnostics is not None
                else 1
            ),
            "retrieval_latency_seconds": (
                rcd_diagnostics.get("retrieval_latency_seconds")
                if rcd_diagnostics is not None
                else None
            ),
            "rcd_diagnostics": rcd_diagnostics,
        })

    retrieval_metric_means = {
        metric_name: sum(scores) / len(scores)
        for metric_name, scores in retrieval_metric_scores.items()
    }
    
    # Corpus metadata for experiment reproducibility
    corpus = data.get("corpus", [])
    num_queries = len(data["queries"])
    corpus_stats = {
        "dataset": config.get("dataset_loader"),
        "dataset_split": config.get("dataset_split", "train"),
        "num_queries": num_queries,
        "num_unique_documents": len(corpus),
        "corpus_type": {
            "load_hotpotqa_distractor": "pooled_hotpotqa",
            "load_2wikimultihopqa": "pooled_2wikimultihopqa",
        }.get(config.get("dataset_loader"), "unknown"),  # supervisor review 3.5: was hardcoded to pooled_hotpotqa for every dataset
        "seed": config.get("seed", 42),
    }
    
    experiment_metadata = build_experiment_metadata(
        experiment_id=config["experiment_id"],
        dataset=config.get(
            "dataset_loader",
            config.get("dataset", "unknown"),
        ),
        dataset_revision=config.get("dataset_revision"),
        dataset_split=config.get("dataset_split"),
        dataset_n_samples=config.get("dataset_n_samples"),
        dataset_seed=config.get("dataset_seed"),
        queries=data["queries"],
        corpus=corpus,
        retriever=config.get("retriever", "unknown"),
        embedder_model=config.get("embedder_model"),
        reranker_model=config.get("reranker_model"),
        generator_model=config.get(
            "generator_model",
            config.get("generator_backend", "unknown"),
        ),
        defense=config.get(
            "defense",
            "rcd" if config.get("retriever") == "rcd" else "none",
        ),
        defense_config={
            "candidate_k": (
                retriever.candidate_k
                if isinstance(retriever, RCDRetriever)
                else int(config.get("rcd_candidate_k", 10))
            ),
            "rewrite_count": (
                retriever.rewrite_count
                if isinstance(retriever, RCDRetriever)
                else int(config.get("rcd_rewrite_count", 3))
            ),
            "consistency_weight": (
                retriever.consistency_weight
                if isinstance(retriever, RCDRetriever)
                else None
            ),
            "redundancy_weight": (
                retriever.redundancy_weight
                if isinstance(retriever, RCDRetriever)
                else None
            ),
            "conflict_weight": (
                retriever.conflict_weight
                if isinstance(retriever, RCDRetriever)
                else None
            ),
            "base_rank_weight": (
                retriever.base_rank_weight
                if isinstance(retriever, RCDRetriever)
                else None
            ),
        },
        source_pipeline=config.get("source_pipeline"),
        target_pipeline=config.get("target_pipeline"),
        attack_family=config.get("attack_family", "none"),
        attack_version=config.get("attack_version", "none"),
        attack_config=config.get("attack_config", {}),
        seed=int(config.get("seed", 42)),
        top_k=int(config.get("top_k", 3)),
        n_poison=int(config.get("n_poison", 0)),
        poison_rate=float(config.get("poison_rate", 0.0)),
        attacked_query_ids=config.get("attacked_query_ids"),
        dataset_query_ids_manifest=config.get("dataset_query_ids_manifest"),
        heldout_query_ids_fingerprint=(
            _heldout_manifest_fingerprint(config)
        ),
    )

    summary = {
        "experiment_id": config["experiment_id"],
        "query_count": num_queries,
        "corpus": corpus_stats,
        "experiment_metadata": experiment_metadata,
        "mean_em": sum(em_scores) / len(em_scores),
        "mean_f1": sum(f1_scores) / len(f1_scores),
        "mean_retrieval_metrics": retrieval_metric_means,
    }
    logger.write_summary(summary)

    print(f"Ran {len(data['queries'])} queries.")
    print(f"Mean EM: {summary['mean_em']:.3f}")
    print(f"Mean F1: {summary['mean_f1']:.3f}")
    if retrieval_metric_means:
        print(f"Mean retrieval metrics: {json.dumps(retrieval_metric_means, sort_keys=True)}")
    print(f"Raw results: {logger.path}")
    print(f"Summary: {logger.summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    main(args.config)
