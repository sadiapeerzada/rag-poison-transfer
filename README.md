# Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG

Undergraduate thesis project by Sadia Peerzada, studying how knowledge-poisoning
attacks on Retrieval-Augmented Generation (RAG) systems transfer across
different retrieval pipelines, and evaluating a retrieval-consistency defense
against them. See the project foundation doc (shared separately) for the full
12-week roadmap and research plan.

## What this repo demonstrates so far

This isn't a single script that "ran once" -- it's a working, tested,
version-controlled research pipeline built incrementally, with real bugs
found and fixed along the way rather than hidden:

- **Built four retrieval strategies from scratch** (BM25, dense embedding
  retrieval, hybrid fusion, cross-encoder reranking) behind a shared
  interface, so any of them can be swapped into an experiment via config
  alone -- no code changes needed per retriever.
- **Built a generator abstraction supporting two real hardware backends**:
  MLX for local inference on Apple Silicon, and `transformers` +
  `bitsandbytes` 4-bit quantization for CUDA GPUs (Kaggle). Same interface,
  same experiment code, either backend.
- **Ran a real, reproducible pilot experiment**: all four retrievers,
  evaluated on the same 50 real HotpotQA questions (same seed, so it's a
  fair comparison), with a real 7B instruction model doing the generation
  -- not a toy dataset, not a mock model.
- **Found and fixed three real bugs** during development (details below),
  rather than shipping results that happened to work by accident.
- **Set up a dual-environment workflow**: local Mac for fast dev/debug
  iteration, Kaggle GPU for real generation runs, both syncing through this
  repo so neither environment silently drifts out of date with the other.

## Pilot result: retriever comparison on real data

All four retrievers tested end-to-end on real HotpotQA data (distractor
setting, N=50 sampled from validation, same seed across all four runs),
using `Qwen/Qwen2.5-7B-Instruct` (4-bit) on a Kaggle T4 GPU:

| Retriever |        EM |        F1 | Config                           |
| --------- | --------: | --------: | -------------------------------- |
| BM25      |     0.360 |     0.485 | `exp_004_hotpotqa_kaggle.yaml`   |
| Dense     |     0.380 |     0.574 | `exp_005_hotpotqa_dense.yaml`    |
| Hybrid    |     0.400 |     0.524 | `exp_006_hotpotqa_hybrid.yaml`   |
| Reranker  | **0.460** | **0.574** | `exp_007_hotpotqa_reranker.yaml` |

**Reranking wins on exact match and ties dense retrieval on F1.**
Cross-encoder reranking of BM25's candidates gives the model the best
evidence of the four strategies tested. This is a real, reproducible
pilot finding, directionally useful for the next phase of the thesis --
**not yet a frozen benchmark result** (see caveat below).

**Pending supervisor sign-off before this counts as final:**
`src/data/loaders.py` bakes in corpus-scope shortcuts -- test-set
subsampling at N=50 (below the eventual N~=150-300 target) and using
HotpotQA's provided candidate pool rather than full open-domain
retrieval -- that are `[REC]`, my compute-feasibility recommendations,
not yet confirmed. See the module docstring for exact items to confirm.

## Bugs found and fixed along the way

Documenting these because catching and fixing them *is* part of the
engineering work, not something to hide:

1. **Verbose-generation metric mismatch (`exp_001`).** First real-model
   run scored EM=0.000 despite the model answering every question
   correctly -- it was adding unrequested "Explanation:" text after each
   answer, which exact-match scoring penalizes. Fixed by tightening the
   prompt and extracting just the first line/sentence before scoring
   (`exp_002`: EM jumped to 0.600).
2. **Non-deterministic "deterministic" test embedder.** `HashingEmbedder`
   (a mock embedder used only for testing retrieval logic) used Python's
   built-in `hash()`, which is randomly salted per process -- so a
   component built to be deterministic wasn't actually reproducible
   across runs. Fixed by switching to `hashlib.md5`, which is stable
   across processes and machines.
3. **`datasets` v5.x breaking change.** HotpotQA's original Hugging Face
   repo is a legacy "loading script" dataset; `datasets` v5.x removed
   script support entirely, and its automatic parquet-fallback has a bug
   parsing bare-name (no-namespace) legacy repos. Fixed by switching to
   the namespaced mirror (`hotpotqa/hotpot_qa`) and dropping the now-
   invalid `trust_remote_code` argument.

## Two working environments

- **Local (MacBook Air M4):** dev/debug loop, `generator_backend: mlx`
- **Kaggle (T4/P100 GPU):** real generation runs,
  `generator_backend: transformers` with 4-bit quantization

Both point at the same GitHub repo. After working in either environment,
`git pull` in the other to stay in sync -- commit history is the
canonical current state.

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

Expect `Mean EM: 0.000` and `Mean F1: 0.000` -- this is correct. The
config's `generator_backend: mock` uses a stub that always returns the
literal string `"mock-answer"`, so it will never match a real gold
answer. That's intentional: it isolates "does the pipeline plumbing
work" from "does the model generate good answers," which is a separate
question for once the real generator is wired in.

## Real generator, on your Mac (MLX)

```bash
pip install mlx-lm
python run.py --config configs/exp_002_real_generator_fixed_prompt.yaml
```

First run downloads `mlx-community/Qwen2.5-7B-Instruct-4bit` (a few GB).

## Real generator, on Kaggle GPU (transformers + bitsandbytes)

```bash
pip install transformers accelerate bitsandbytes datasets sentence-transformers
python run.py --config configs/exp_007_hotpotqa_reranker.yaml
```

Requires a CUDA GPU (enable in notebook Settings -> Accelerator).
`generator_backend: transformers` in the config selects this backend.

## Real datasets (pending supervisor confirmation on final scope)

```bash
pip install datasets sentence-transformers
```

Then use `src/data/loaders.py` -- but read its docstring warnings first.
Current pilot numbers (N=50) are illustrative, not yet the frozen
benchmark result the plan calls for.

## What's real vs placeholder right now

| Component | Status |
|---|---|
| Repo structure, config loading, seeding, logging | Real, final |
| BM25 / Dense / Hybrid / Reranker retrievers | Real, tested on real data |
| `MockGenerator` | **Placeholder/test-only** -- never use for real results |
| `MLXGenerator` / `TransformersGenerator` | Real, both verified working |
| EM/F1 metrics | Real, final |
| HotpotQA pilot (N=50) | Real results, pending sign-off to become final |
| 2WikiMultiHopQA, NQ-open real runs | Loader built, not yet run on real data |
| Attacks, RCD, full metric suite | Not yet built -- Weeks 5-10 |

## Repository layout

See the foundation doc, Section F, for the full rationale on what goes
where and what's git-ignored vs. committed. Quick summary: `src/` is
source code (commit), `data/raw` and `data/processed` are gitignored
(large/regeneratable), `experiments/*/config.yaml` + `README.md` are
committed (they ARE the record of what happened), `results/` raw logs
are gitignored or Git-LFS'd.

## Next phase

After supervisor confirmation of the experimental scope, the project
moves toward the knowledge-poisoning experiments: attack construction,
attack transfer evaluation across retrievers, RCD (Retrieval-Consistency
Defense) implementation, and the full metric suite -- see the foundation
doc for the complete roadmap.
