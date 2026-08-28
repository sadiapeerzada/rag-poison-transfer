"""Week 1-2 smoke test: Dataset -> BM25 retrieval -> Generator -> EM/F1.

Run with:
    python run.py --config configs/exp_000_smoke.yaml

This is intentionally the simplest possible clean pipeline (Section 6
of the plan / Section E-Weeks-1-2 of the foundation doc). No attacks,
no defenses, no dense retrieval yet -- just proving the wiring works
end to end, reproducibly, before we add complexity in Weeks 3-4.
"""
import argparse
import json

from src.utils.config import load_config
from src.utils.seeding import set_seed
from src.utils.logging_utils import ExperimentLogger
from src.retrieval.bm25 import BM25Retriever
from src.pipelines.generator import MockGenerator, MLXGenerator
from src.evaluation.metrics import exact_match, f1_score


def build_generator(config: dict):
    if config["generator_backend"] == "mock":
        return MockGenerator()
    elif config["generator_backend"] == "mlx":
        return MLXGenerator(model_name=config["generator_model"])
    else:
        raise ValueError(f"Unknown generator_backend: {config['generator_backend']}")


def build_prompt(question: str, evidence_docs: list) -> str:
    evidence_text = "\n".join(f"- {d.text}" for d in evidence_docs)
    return (
        "Answer the question using only the evidence below. "
        "Be concise.\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )


def main(config_path: str):
    config = load_config(config_path)
    set_seed(config["seed"])

    with open(config["dataset_path"]) as f:
        data = json.load(f)

    retriever = BM25Retriever()
    retriever.build(data["corpus"])

    generator = build_generator(config)
    logger = ExperimentLogger(config["results_dir"], config["experiment_id"])

    em_scores, f1_scores = [], []

    for q in data["queries"]:
        retrieved = retriever.retrieve(q["question"], top_k=config["top_k"])
        prompt = build_prompt(q["question"], retrieved)
        gen_result = generator.generate(prompt, max_tokens=config["max_tokens"])

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
