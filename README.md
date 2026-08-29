# Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG

Research repo for Sadia Peerzada's undergraduate thesis project. See
`experiments/exp_000_smoke_test/README.md` for what this specific
experiment proves, and the project foundation doc (shared separately)
for the full 12-week roadmap and repository design rationale.

## Status: Week 3-4, retrieval components built + tested (dataset scope pending supervisor sign-off)

Built and verified (with mock embedders/scorers, no model downloads needed):
- `src/retrieval/dense.py` — dense retriever, pluggable embedder
- `src/retrieval/hybrid.py` — reciprocal rank fusion of any two retrievers
- `src/retrieval/reranker.py` — cross-encoder rescoring stage
- `src/data/loaders.py` — HotpotQA / 2WikiMultiHopQA / NQ-open loaders

**IMPORTANT:** `src/data/loaders.py` bakes in corpus-scope shortcuts
(test-set subsampling, using each dataset's provided candidate pool
instead of full open-domain retrieval, an NQ pilot-only loader with no
real corpus yet) that are `[REC]` — my recommendations for MacBook
feasibility, NOT yet confirmed by your supervisor. Do not report any
numbers from these loaders as final results until he's signed off —
see the module docstring for the exact three items to confirm.

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
answer. That's intentional: it isolates "does the pipeline plumbing
work" from "does the model generate good answers," which is a separate
question for once the real generator is wired in.

## Real generator (exp_001, on your Mac)

```bash
pip install mlx-lm
python run.py --config configs/exp_001_real_generator.yaml
```

First run downloads `mlx-community/Qwen2.5-7B-Instruct-4bit` (a few
GB). This still uses the toy dataset — real EM/F1 on real questions,
but not yet a frozen benchmark result.

## Real datasets (pending supervisor confirmation)

```bash
pip install datasets sentence-transformers
```

Then use `src/data/loaders.py` — but read its docstring warnings
first. Don't treat output from this as a citable result until the
corpus-scope questions are confirmed.

## What's real vs placeholder right now

| Component | Status |
|---|---|
| Repo structure, config loading, seeding, logging | Real, final |
| BM25 retriever | Real, final for this stage |
| `data/raw/toy_smoke_dataset.json` | **Placeholder** — 10 synthetic docs, not NQ. Swap in Weeks 3-4. |
| `MockGenerator` | **Placeholder/test-only** — never use for real results |
| `MLXGenerator` | Real interface, needs your Mac + internet to actually run |
| EM/F1 metrics | Real, final |
| Dense/hybrid/reranking retrieval, attacks, RCD, full metric suite | Not yet built — Weeks 3-10 |

## Repository layout

See the foundation doc, Section F, for the full rationale on what
goes where and what's git-ignored vs. committed. Quick summary:
`src/` is source code (commit), `data/raw` and `data/processed` are
gitignored (large/regeneratable), `experiments/*/config.yaml` +
`README.md` are committed (they ARE the record of what happened),
`results/` raw logs are gitignored or Git-LFS'd.
