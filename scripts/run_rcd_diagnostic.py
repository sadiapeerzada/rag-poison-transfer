"""RCD step 1: rewrites + feature diagnostic (go/no-go before any ASR run).

Kaggle (GPU on, needed for rewrites and for the semantic attack):
    python scripts/run_rcd_diagnostic.py --dataset hotpotqa --attack lexical  --n_poison 1
    python scripts/run_rcd_diagnostic.py --dataset hotpotqa --attack semantic --n_poison 1
No-GPU wiring check (toy data, stub generator):
    python scripts/run_rcd_diagnostic.py --smoke

Outputs (results/):
    rcd_rewrites_<dataset>.jsonl                      resumable rewrite cache
    rcd_diag_rows_<dataset>_<attack>_n<k>.csv         per (query, candidate) features
    rcd_diag_auroc_<dataset>_<attack>_n<k>.csv        AUROC + 95% query-bootstrap CI

DEV/TEST DISCIPLINE: attacked queries are drawn ONLY from the dev partition
(--n_dev questions, seeded). The remaining questions are the held-out test
partition; do not run RCD tuning on them.
"""
import argparse
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.attacks.injection import inject_poisons
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.defenses.rcd import RCDConfig, RewriteCache
from src.defenses.rcd.diagnostic import feature_rows, summarize_auroc
from src.experiments.protocol import select_fixed_query_ids


def dev_partition(queries, n_dev, seed=2024):
    return select_fixed_query_ids(queries, n_dev, seed=seed)


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def smoke_inputs():
    topics = [
        ("Who founded the Aldrin Observatory", "Marta Quill", "The Aldrin Observatory was founded by Marta Quill in the northern hills."),
        ("Where is the Brevik Museum located", "Tromso", "The Brevik Museum is located in Tromso beside the harbour."),
        ("When did the Calder Railway open", "1894", "The Calder Railway opened in 1894 connecting the two valleys."),
        ("Who designed the Dunmore Bridge", "Ines Faro", "The Dunmore Bridge was designed by Ines Faro using steel arches."),
        ("What is the capital of Eskerland", "Valdor", "The capital of Eskerland is Valdor, a river city."),
        ("Who wrote the Fenwick Chronicle", "Olaf Strand", "The Fenwick Chronicle was written by Olaf Strand in the winter."),
    ]
    corpus, queries = [], []
    for i, (q, a, doc) in enumerate(topics):
        corpus += [{"doc_id": f"d{i}", "text": doc},
                   {"doc_id": f"x{i}", "text": f"Unrelated filler paragraph {i} about gardening soil and weather."}]
        queries.append({"query_id": f"q{i}", "question": q, "gold_answer": a, "gold_doc_ids": [f"d{i}"]})

    class Stub:
        def generate(self, prompt, max_tokens=64):
            q = prompt.split("Question:")[1].split("\n")[0].strip()
            return type("R", (), {"text": f"1. Please tell me: {q}\n2. {q} exactly\n3. Could you say: {q}\n4. Regarding this: {q}"})()

    return {"corpus": corpus, "queries": queries}, Stub()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="hotpotqa", choices=["hotpotqa", "2wiki", "nq"])
    ap.add_argument("--attack", default="lexical", choices=["lexical", "semantic"])
    ap.add_argument("--n_poison", type=int, default=1)
    ap.add_argument("--n_samples", type=int, default=300)
    ap.add_argument("--n_dev", type=int, default=100)
    ap.add_argument("--n_attacked", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n_rewrites", type=int, default=3)
    ap.add_argument("--depth", type=int, default=20)
    ap.add_argument("--n_boot", type=int, default=500)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    if a.smoke:
        data, generator = smoke_inputs()
        a.dataset, a.n_dev, a.n_attacked, a.n_boot, a.depth = "smoke", 4, 4, 20, 8
        from src.retrieval.bm25 import BM25Retriever
        from src.retrieval.dense import DenseRetriever
        make_sparse, make_dense = BM25Retriever, DenseRetriever
    else:
        from run import build_retriever
        from src.data import loaders
        from src.pipelines.generator import TransformersGenerator
        loader = {"hotpotqa": loaders.load_hotpotqa_distractor,
                  "2wiki": loaders.load_2wikimultihopqa,
                  "nq": loaders.load_natural_questions}[a.dataset]
        data = loader(split="validation", n_samples=a.n_samples, seed=a.seed)
        generator = TransformersGenerator()
        make_sparse = lambda: build_retriever({"retriever": "bm25"})
        make_dense = lambda: build_retriever({"retriever": "dense", "embedder_model": "BAAI/bge-small-en-v1.5"})

    queries = data["queries"]
    dev_ids = dev_partition(queries, min(a.n_dev, len(queries)))
    print(f"dev partition: {len(dev_ids)} of {len(queries)} questions (rest = held-out test)")

    # 1) rewrites for ALL questions, once (resumable)
    cache = RewriteCache(os.path.join(a.out, f"rcd_rewrites_{a.dataset}.jsonl"), generator=generator)
    cache.prefill([q["question"] for q in queries], n=4)

    # 2) poison the dev queries only
    n_att = min(a.n_attacked, len(dev_ids))
    attacked = sorted(random.Random(a.seed).sample(dev_ids, n_att))
    if a.attack == "lexical":
        attack = LexicalInfluentialTokenAttack()
    else:
        from src.attacks.semantic_fluent import SemanticFluentFalseEvidenceAttack
        attack = SemanticFluentFalseEvidenceAttack(generator)
    pdata = inject_poisons(data, attack, n_poison=a.n_poison, poison_rate=n_att / len(queries),
                           seed=a.seed, attacked_query_ids=attacked)

    # 3) features + AUROC (CPU)
    sparse, dense = make_sparse(), make_dense()
    sparse.build(pdata["corpus"]); dense.build(pdata["corpus"])
    cfg = RCDConfig(depth=a.depth, n_rewrites=a.n_rewrites)
    rows = feature_rows(pdata, cache, sparse, dense, cfg, pool_k=10)
    summ = summarize_auroc(rows, n_boot=a.n_boot)
    tag = f"{a.dataset}_{a.attack}_n{a.n_poison}"
    write_csv(os.path.join(a.out, f"rcd_diag_rows_{tag}.csv"), rows)
    write_csv(os.path.join(a.out, f"rcd_diag_auroc_{tag}.csv"), summ)

    print(f"\nAUROC, poison vs clean-gold candidates, slice=all  ({tag})")
    for r in summ:
        if r["slice"] == "all" and r["negatives"] == "vs_clean_gold":
            print(f"  {r['feature']:<24} {r['auroc']:.3f}  [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]  (n_queries={r['n_queries']})")


if __name__ == "__main__":
    main()
