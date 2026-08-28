# Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG

Research repo for Sadia Peerzada's undergraduate thesis project. See
`experiments/exp_000_smoke_test/README.md` for what this specific
experiment proves, and the project foundation doc (shared separately)
for the full 12-week roadmap and repository design rationale.

## Status: Week 1-2, smoke test complete

This currently proves the *pipeline wiring* works end to end:
`toy dataset -> BM25 retrieval -> generator -> EM/F1 scoring -> logged results`.
It does **not** yet use real data, a real model, or any of the attacks/
defenses -- those come in Weeks 3-8 per the roadmap.

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

## Switching to the real generator (on your Mac only)

This sandbox has no internet access to Hugging Face, so the real
model must be set up on your machine:

```bash
pip install mlx-lm
```

Then in `configs/exp_000_smoke.yaml`, change:
```yaml
generator_backend: mlx
```

The first run will download `mlx-community/Qwen2.5-7B-Instruct-4bit`
(a few GB) — expect this to take a while depending on your connection.
Delete `results/exp_000_smoke_test.jsonl` first if you already have a
mock-generator run logged (raw results are never overwritten — see
`src/utils/logging_utils.py`).

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
