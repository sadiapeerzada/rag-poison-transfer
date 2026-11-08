# Post-run evidence closeout: exact Qwen–Phi pairing, then RCD ablations

**Research:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Status:** Second-family Phi-4-mini-instruct-4bit fixed-evidence replay completed on the operator's Mac, 160 generator requests / 16 aggregate groups. **A paired Qwen–Phi offline check and actual RCD end-to-end ablations remain separate pending tasks.**  
**Repository privacy:** public. Never commit replay plan, held-out prompts, per-item replies, raw QA or poisons.

## Current facts and boundaries

- The original frozen 2Wiki execution completion manifest digest is `db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519`. The operator restored the complete 2Wiki backup and independently verified 37,534 archive file hashes.
- Original Qwen2.5-7B-Instruct-4bit QA had a **64-token generation cap**. The Phi-4 Mini replay used **128**. The model-family, quantization, model size, tokenizer and chat template also differ. This does **not** isolate a causal effect of model family.
- The reported 160 calls are **4 attack-family/intensity strata × 10 valid selected query positions × Dense/RCD × clean/poisoned**. There are not necessarily 40 distinct query IDs.
- Phi reported 16 output groups; in the 40 poisoned entries per arm, Dense nominated-target match was 31/40 and RCD 32/40. These are selected, mechanically valid cases, **not attempted-population ASR**, nor independently certified factual falsehoods.
- No full human factuality adjudication was performed, by user choice; the public preliminary 131-case audit remains AI-assisted and outcome-stratified. No source-backed certification has been fabricated.

## Step A — audit matched Qwen and Phi (no model calls)

The independent CLI `scripts/compare_qwen_phi_replay_offline.py` binds and checks:

1. Exact 2Wiki frozen `evaluation.complete.json` hash and per-cell row hashes.
2. Exact private selected replay plan SHA-256, immutable question/arm/condition identity and the **same original Qwen prompt string and prompt SHA**.
3. The saved original Qwen generation record, extraction and EM against gold; the stored Phi response, extraction, score and private model-snapshot fingerprint.
4. Exactly 160 paired recorded generator observations and 16 family/intensity/arm/condition group summaries. It reports Qwen/Phi target matches, exact-match clean/poison accuracy, descriptive paired discordances and distinct selected question counts, with **no per-example text or IDs in the report**.

Operator command from the local repo:

```bash
cd "$HOME/Downloads/rag-poison-transfer"
git pull --ff-only origin main
python -m pytest -q tests/test_matched_qwen_phi_replay.py tests/test_nov09_research_gates.py

export TWOWIKI_EVAL_DIR="$HOME/Downloads/2wiki-restored-20261109/execution/evaluation"
export MODEL_PLAN="$HOME/Documents/rag-research-results/nov09-research-gates/2wiki-second-model-plan-20261108T204440Z_PRIVATE.json"
export MODEL_PLAN_SHA="9c47a64053c2d53bb016a2bad10503d906a9026e0b7092d55ddb0505bd3b199a"

bash scripts/nov09_mac_research.sh model-compare
```

The output file is **PRIVATE** under `~/Documents/rag-research-results/nov09-research-gates/`. Publish only aggregates after privacy/licensing review. In particular, do **not** compare the entire 300-query original Qwen study against 10-query selected Phi groups as if they were matched.

## Optional Step A2 — matched output-cap Phi@64 control (NEW inference)

The original Qwen QA budget was **64 tokens** and the completed exploratory Phi-4 replay used **128 tokens**. To remove that **one** generation-cap confound, run Phi-4 again with exactly the **same pinned 160-prompt private plan** and the **same pinned local Phi model** but write responses to a **fresh output directory**. This does not control for tokenizer, architecture, training set, parameter count, context capacity or chat template differences.

The saved Phi@128 results are immutable and MUST NOT be overwritten.

```bash
cd "$HOME/Downloads/rag-poison-transfer"
source .venv/bin/activate
export TWOWIKI_EVAL_DIR="$HOME/Downloads/2wiki-restored-20261109/execution/evaluation"
export MODEL_PLAN="$HOME/Documents/rag-research-results/nov09-research-gates/2wiki-second-model-plan-20261108T204440Z_PRIVATE.json"
export MODEL_PLAN_SHA="9c47a64053c2d53bb016a2bad10503d906a9026e0b7092d55ddb0505bd3b199a"
export MODEL_SNAPSHOT="$HOME/.cache/huggingface/hub/models--mlx-community--Phi-4-mini-instruct-4bit/snapshots/ac1c269cb4222a4e136a3d09edad301056c1f36a"
export MODEL_SHA="d0797f104c502aca586559e7334ee3029b59e342831e2c2e5ae9bc3ceeb33d06"
export MODEL_RUN_DIR="$HOME/Documents/rag-research-results/nov09-research-gates/2wiki-second-model-phi64-results_PRIVATE"
export MODEL_MAX_TOKENS=64

# Real, separately authorized 160-call new inference (not a replay cache hit)
bash scripts/nov09_mac_research.sh model-run

# Only after REPLAY_COMPLETE:
bash scripts/nov09_mac_research.sh model-aggregate
bash scripts/nov09_mac_research.sh model-compare
```

The new `model-compare` output is a same-64-token-budget **Qwen vs Phi@64** comparison, reported as a fresh private aggregate, leaving the existing Phi@128 analysis intact. The runner refuses to resume results under a different max-token manifest. If `MODEL_RUN_DIR` is not set, it defaults to the already-completed Phi@128 output, so **set and inspect it carefully** before running Phi@64. A `PASS` after matched cap establishes measurement alignment for this decoding limit only; it does not establish robustness generalization to an untouched model or validate semantic falsehood.

## Step B — last major experiment: explicitly scoped RCD ablation

RCD is a **single composite Dense-primary defense with auxiliary BM25**, not four different wrappers. Its historical frozen configuration must **not** be retuned or retroactively modified. Treat all ablations as a *new, post-hoc development/method sensitivity study* with their own immutable protocol, source commit, fresh output directory and a clearly identified dataset/query subset.

### Minimum defensible ablation contrasts

| Comparison | Mechanism | Valid evidence | Required measurement |
|---|---|---|---|
| Full RCD vs `rewrite_count=0` | Disable rewrite retrieval entirely | New retrieval and generator calls | Poison evidence exposure, EM/F1, targeted matches, latency, retrieval calls |
| Full RCD vs no agreement contribution | Remove cross-retriever agreement **at scoring time**, while keeping the same candidate pool | Re-ranking from complete authentic signals first; end-to-end new QA needed for ASR | Selection changes and paired QA outcomes |
| Full RCD vs `conflict_weight=0` | Remove year-conflict penalty | Same sealed corpus, independent re-ranking, new QA | Exposure, accuracy, ASR, false positives |
| Full RCD at generator evidence depths `k=1,3,5` | Vary selected evidence amount without changing candidate`_k=10` | New retrieved contexts/new QA | Evidence visibility, clean utility, matched target match |

Each variant must be compared **on the same original questions, sealed poisoned documents, retrieval corpus, deterministic seed, and generation decoding**. Use a fresh, named protocol/version and freeze all options **before** any new outcomes are observed. Reusing held-out outcomes to select favorable ablations or tune a threshold makes the comparisons exploratory; they cannot be reported as untouched confirmatory evidence.

For a bounded design, predeclare the subset using immutable query IDs and sample strata without inspecting the ablation outcomes; report both attempted-population and valid-only denominators, empty/failed constructions, paired query-cluster uncertainty, retrieval/generation cost, and where RCD hurts the clean baseline. The original matched Qwen and Phi models **must not be rerun by the existing frozen scripts**.

### Offline-only limitation

`scripts/rcd_offline_scoring_ablations.py` implements **score-only sensitivity** and *requires* authentic `RCDRetriever.last_diagnostics` containing all candidate-level signals and doc IDs. The prior filename search found no `*rcd*diagnostic*.jsonl` matches in the research-results tree, but this does not establish that the original JSONL records lack embedded diagnostics. Inspect the original `exp_026` development log or stored QA evaluation rows **read-only**, then adapt an evidence-preserving exporter if all necessary fields are actually present. Do not invent `last_diagnostics`.

The score-only tool does **not** disable rewrites or produce alternate generator responses; its output cannot establish ASR changes. A true full/no-rewrite/k-depth ablation requires new, separately approved local retrieval and generation execution.

## Closing checklist

- [x] HotpotQA final transfer raw-vs-published verification passed (240 cells; optional candidate library separately unchecked).
- [x] 2Wiki frozen matched original run and independently restored archive.
- [x] AI-assisted post hoc semantic 131-case analysis (unadjudicated).
- [x] Phi-4 Mini fixed-evidence second-model replay (160 saved calls; 16 grouped aggregates).
- [ ] Offline exact Qwen–Phi same-item result comparison (script added, actual Mac output pending).
- [ ] RCD no-rewrite/score/depth ablation experiment results (not yet run).
- [ ] Final tables, limitations and publication manuscript; plan-specific Natural Questions, genuinely iterative/adaptive RAG and intensity 5 remain **extensions or explicit scope gaps**, not silently completed work.
