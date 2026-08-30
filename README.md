# Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG

Research repo for Sadia Peerzada's undergraduate thesis project. See
`experiments/exp_000_smoke_test/README.md` for what this specific
experiment proves, and the project foundation doc (shared separately)
for the full 12-week roadmap and repository design rationale.

## Status: Week 3-4 pilot results in (real data, real GPU, pending supervisor sign-off on final scope)

All four retrievers have now been tested end-to-end on real HotpotQA data
(distractor setting, N=50 sampled from validation, same seed across all
four runs for a fair comparison), using the real generator
(`Qwen/Qwen2.5-7B-Instruct`, 4-bit) on a Kaggle GPU (T4):

| Retriever |        EM |        F1 | Config                           |
| --------- | --------: | --------: | -------------------------------- |
| BM25      |     0.360 |     0.485 | `exp_004_hotpotqa_kaggle.yaml`   |
| Dense     |     0.380 |     0.574 | `exp_005_hotpotqa_dense.yaml`    |
| Hybrid    |     0.400 |     0.524 | `exp_006_hotpotqa_hybrid.yaml`   |
| Reranker  | **0.460** | **0.574** | `exp_007_hotpotqa_reranker.yaml` |

**Reranking currently wins on exact match and ties dense retrieval on
F1.** Cross-encoder reranking of BM25's candidates achieves the highest
pilot EM (0.460) while matching dense retrieval's F1 (0.574).

This is a real, reproducible pilot finding and is directionally useful
for the next phase of the thesis. It is **not yet a frozen benchmark
result**.

**IMPORTANT — supervisor sign-off is still pending before this counts
as a final result:** `src/data/loaders.py` currently contains
corpus-scope shortcuts, including test-set subsampling at N=50,
well below the eventual N~=150-300 target, and use of HotpotQA's
provided candidate pool rather than full open-domain retrieval.

These `[REC]` items are recommendations for compute feasibility and
have not yet been confirmed by the supervisor. See the module
docstring for the exact items requiring confirmation.

## Built and verified

* `src/retrieval/bm25.py` — BM25 retrieval
* `src/retrieval/dense.py` — dense retrieval using BGE-small
* `src/retrieval/hybrid.py` — reciprocal rank fusion of BM25 + dense
* `src/retrieval/reranker.py` — cross-encoder rescoring using MiniLM
* `src/data/loaders.py` — HotpotQA / 2WikiMultiHopQA / NQ-open loaders
* `src/pipelines/generator.py` — Mock, MLX, and Transformers+bitsandbytes
  generator backends
* `run.py` — unified experiment runner supporting all four retrievers
* `src/evaluation/metrics.py` — EM/F1 evaluation

## Two working environments

* **Local (MacBook Air M4):** development/debug loop, using
  `generator_backend: mlx`
* **Kaggle (T4/P100 GPU):** real generation runs, using
  `generator_backend: transformers` with 4-bit quantization

Both environments point to the same GitHub repository. After working
in either environment, run `git pull` in the other environment to stay
in sync. See commit history for the canonical current state.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the smoke test

```bash
python run.py --config configs/exp_000_smoke.yaml
pytest tests/ -v
```

Expect `Mean EM: 0.000` and `Mean F1: 0.000` — this is correct. The
config's `generator_backend: mock` uses a stub that always returns the
literal string `"mock-answer"`, so it will never match a real gold
answer.

That's intentional: it isolates "does the pipeline plumbing work?"
from "does the model generate good answers?", which is a separate
question once the real generator is wired in.

## Real generator, on your Mac (MLX)

```bash
pip install mlx-lm
python run.py --config configs/exp_001_real_generator.yaml
```

First run downloads `mlx-community/Qwen2.5-7B-Instruct-4bit` (a few GB).

The real generator can produce genuine EM/F1 results on real questions,
but those results should not be treated as frozen benchmark results
unless they use the finalized experimental protocol.

## Real generator, on Kaggle GPU (Transformers + bitsandbytes)

```bash
pip install transformers accelerate bitsandbytes datasets sentence-transformers
python run.py --config configs/exp_007_hotpotqa_reranker.yaml
```

Requires a CUDA GPU. Enable the GPU in Kaggle notebook Settings →
Accelerator.

`generator_backend: transformers` in the config selects this backend.

## Real datasets (pending supervisor confirmation)

```bash
pip install datasets sentence-transformers
```

Then use `src/data/loaders.py` — but read its docstring warnings first.

The current HotpotQA pilot uses N=50 and the dataset's provided
candidate pool. These choices are currently provisional and should not
be treated as the final thesis benchmark protocol until supervisor
confirmation.

## What's real vs placeholder right now

| Component                                        | Status                                                 |
| ------------------------------------------------ | ------------------------------------------------------ |
| Repo structure, config loading, seeding, logging | Real, final                                            |
| BM25 / Dense / Hybrid / Reranker retrievers      | Real, tested on real data                              |
| `MockGenerator`                                  | **Placeholder/test-only** — never use for real results |
| `MLXGenerator` / `TransformersGenerator`         | Real, verified working                                 |
| EM/F1 metrics                                    | Real, final                                            |
| HotpotQA pilot (N=50)                            | Real results, pending supervisor sign-off              |
| 2WikiMultiHopQA / NQ-open loaders                | Built, not yet run on real data                        |
| Knowledge-poisoning attacks                      | Not yet built — planned for Weeks 5-10                 |
| RCD and full metric suite                        | Not yet built — planned for Weeks 5-10                 |

## Repository layout

See the foundation doc, Section F, for the full rationale on what
goes where and what's git-ignored vs. committed.

Quick summary:

* `src/` — source code; committed
* `configs/` — experiment configurations; committed
* `experiments/*/config.yaml` + `README.md` — committed; these are the
  record of what happened
* `data/raw/` — gitignored; large/regeneratable
* `data/processed/` — gitignored; large/regeneratable
* `results/` — raw experiment logs; gitignored or Git-LFS'd depending
  on size

## Current pilot finding

The current Week 3–4 HotpotQA pilot gives the following ordering by
exact match:

1. **Reranker — EM 0.460, F1 0.574**
2. **Hybrid — EM 0.400, F1 0.524**
3. **Dense — EM 0.380, F1 0.574**
4. **BM25 — EM 0.360, F1 0.485**

The reranker therefore has the strongest pilot EM, while dense retrieval
and reranking are tied on F1.

These results are useful for guiding the next stage of the research,
but they remain **preliminary** until the supervisor confirms the final
dataset/corpus scope, sample size, and retrieval protocol.

## Next phase

After supervisor confirmation of the experimental scope, the project
will proceed toward the knowledge-poisoning experiments.

Planned components include:

* poisoning attack construction
* retrieval manipulation and attack evaluation
* RCD and the full metric suite
* experiments across additional datasets
* cross-pipeline transferability analysis
* final benchmark runs
* thesis-ready evaluation and reporting

Until the protocol is frozen, the HotpotQA N=50 results are treated as
a reproducible pilot baseline rather than a final thesis benchmark.
