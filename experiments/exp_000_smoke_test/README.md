# exp_000_smoke_test

**Purpose:** verify the Week 1-2 clean-pipeline wiring runs end to end,
before any real data or real generation is introduced.

**Config:** `configs/exp_000_smoke.yaml` (config_hash logged in every
result record — see `results/exp_000_smoke_test.jsonl`)

**Dataset:** `data/raw/toy_smoke_dataset.json` — 10 synthetic docs, 5
synthetic queries. NOT a real benchmark sample. Not scientifically
meaningful; wiring test only.

**Generator:** `MockGenerator` — deterministic stub, not a real model.
Expected result: EM = F1 = 0.000 always. This is correct, not a bug.

**Frozen:** nothing yet — this whole experiment is throwaway scaffolding.
Nothing here should be cited or reused as a real result.

**Superseded by:** exp_001_clean_baselines (Weeks 3-4), once real data,
real retrievers, and a real generator are wired in.
