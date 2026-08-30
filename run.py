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

from src.utils.config import load_config
from src.utils.seeding import set_seed
from src.utils.logging_utils import ExperimentLogger
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever, SentenceTransformerEmbedder
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.reranker import Reranker, CrossEncoderScorer
from src.pipelines.generator import MockGenerator, MLXGenerator, TransformersGenerator
from src.evaluation.metrics import exact_match, f1_score


def build_retriever(config: dict):
    """Real retrievers only (no mocks) -- this is for real experiment
    runs, not tests. embedder_model/reranker_model are optional config
    overrides; sensible defaults (BGE-small / MiniLM cross-encoder) are
    used otherwise.
    """
    kind = config.get("retriever", "bm25")
    embedder_model = config.get("embedder_model", "BAAI/bge-small-en-v1.5")
    reranker_model = config.get("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")

    if kind == "bm25":
        return BM25Retriever()
    elif kind == "dense":
        return DenseRetriever(SentenceTransformerEmbedder(embedder_model))
    elif kind == "hybrid":
        return HybridRetriever(
            BM25Retriever(),
            DenseRetriever(SentenceTransformerEmbedder(embedder_model)),
        )
    elif kind == "reranker":
        return Reranker(BM25Retriever(), CrossEncoderScorer(reranker_model))
    else:
        raise ValueError(f"Unknown retriever: {kind!r}")


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
    logger = ExperimentLogger(config["results_dir"], config["experiment_id"])

    em_scores, f1_scores = [], []

    for q in data["queries"]:
        retrieved = retriever.retrieve(q["question"], top_k=config["top_k"])
        prompt = build_prompt(q["question"], retrieved)
        gen_result = generator.generate(prompt, max_tokens=config["max_tokens"])
        extracted = gen_result.text.split("\n")[0].split(". ")[0].strip()
        gen_result.text = extracted

        em = exact_match(gen_result.text, q["gold_answer"])
        f1 = f1_score(gen_result.text, q["gold_answer"])
        em_scores.append(em)
        f1_scores.append(f1)

        logger.log({
            "experiment_id": config["experiment_id"],
            "config_hash": config["_config_hash"],
            "query_id": q["query_id"],
            "question": q["question"],
            "gold_answer": q["gold_answer"],
            "retrieved_doc_ids": [d.doc_id for d in retrieved],
            "retrieved_scores": [d.score for d in retrieved],
            "prompt": prompt,
            "generated_text": gen_result.text,
            "latency_seconds": gen_result.latency_seconds,
            "prompt_tokens": gen_result.prompt_tokens,
            "completion_tokens": gen_result.completion_tokens,
            "em": em,
            "f1": f1,
            "generator_backend": config["generator_backend"],
        })

    print(f"Ran {len(data['queries'])} queries.")
    print(f"Mean EM: {sum(em_scores) / len(em_scores):.3f}")
    print(f"Mean F1: {sum(f1_scores) / len(f1_scores):.3f}")
    print(f"Raw results: {logger.path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    main(args.config)
