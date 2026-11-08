# November 9 research closure: four distinct evidence gates

**Scope:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Status:** Three reproducible utilities and offline tests prepared; **private raw-data and fresh model runs are not claimed completed**. Earlier frozen datasets/protocols/reports remain unchanged.  
**Repository visibility:** public. Do **not** commit raw held-out examples, model prompts/responses, generated poisoned evidence or private 2Wiki reviewer packets.

This note supersedes any instruction to rerun already completed original HotpotQA or 2Wiki inference. It does not supersede their actual completion seals or frozen scientific protocols.

## Gate 1 — Independently check original HotpotQA source-crafted transfer raw artifacts

The [240-cell public transfer aggregate](../paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json) and 80 query-cluster transfer intervals have already passed internal arithmetic checks, but **the private original raw transfer run has not been checked in this PR**.

The new [raw audit CLI](../scripts/audit_hotpotqa_transfer_raw_offline.py) verifies against these previously recorded immutable SHA-256 pins:

| Artifact | Expected SHA-256 |
|---|---|
| Frozen transfer protocol | \`94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa\` |
| Source-selected poison seal | \`3f9217c83a7c1309763468be1cf2e57ebcd0ecd726a44c57b4eaa4d61ab3b750\` |
| Transfer evaluation completion | \`72343b04134f8d6f24815d731af52c644d517dba042754236f9e7f089316c191\` |
| Original, non-public aggregate | \`43f3f652460ac365fefdf2e516d227c66aae9fb124df8ca028874327e9335adc\` |

The CLI re-hashes all selected and evaluated stage files, checks optional candidate library against its manifest, validates each stored answer's generation record/answer extraction/EM/targeted ASR, rechecks **240 source×target×attack×intensity×seed cells** and verifies they match the original aggregate and published aggregate. The CI fixture tests check failure handling, **not real private-file custody**.

First locate your private files on the Mac. Do not invent paths or copy over the original:

\`\`\`bash
ROOT="$HOME/Documents/rag-research-results/hotpotqa-transfer-20261028/transfer"
find "$ROOT" -name 'protocol.json' -o -name 'selection.seal.json' -o \
  -name 'transfer.complete.json' -o -name 'candidates.complete.json' -o -name 'aggregate.json'
\`\`\`

Once the actual five paths are confirmed, set them, e.g.:

\`\`\`bash
REPO="$HOME/Downloads/rag-poison-transfer"
cd "$REPO"
PY="$REPO/.venv/bin/python"

# THESE PATHS ARE EXAMPLES ONLY. Confirm the discovery results above.
PROTOCOL="$ROOT/protocol.json"
SELECTED="$ROOT/execution/selection"
EVALUATION="$ROOT/execution/evaluation"
ORIGINAL_AGGREGATE="$ROOT/execution/aggregate.json"

mkdir -p "$HOME/Documents/rag-research-results/nov09-audits"
"$PY" scripts/audit_hotpotqa_transfer_raw_offline.py \
  --protocol "$PROTOCOL" \
  --selected-dir "$SELECTED" \
  --evaluation-dir "$EVALUATION" \
  --original-aggregate "$ORIGINAL_AGGREGATE" \
  --public-aggregate paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json \
  --report-out "$HOME/Documents/rag-research-results/nov09-audits/hotpotqa-transfer-raw-pass.json"
\`\`\`

Optionally add \`--candidate-dir PATH\` if the original candidate library is available. A **PASS** report can be added to the public repository only after redaction and after verifying the run was performed on the actual original files. A missing file or wrong SHA is a real unresolved gate, not a reason to silently fall back to a re-export.

## Gate 2 — AI-assisted semantic audit: no human reviewers

The user elected **not** to use external human reviewers. The public [preliminary qualitative audit](../reports/2WIKI_QUALITATIVE_ERROR_AUDIT_PUBLIC_2026-11-09.md) and [aggregate triage](../reports/2wiki_qualitative_triage_aggregate_public_2026-11-09.json) therefore remain the completed **AI-assisted and deterministic** review. Their observed scope is 131 selected case rows / 102 distinct queries, with 107 valid cases and 24 construction failures needing original context.

This is **not** an "independent human review," inter-rater reliability study, adjudicated ground-truth set, or complete factual verification of the 107 accepted statements. The [optional human workflow](2WIKI_INDEPENDENT_SEMANTIC_ADJUDICATION_2026-11-09.md) remains available but should not be represented as performed.

Recommended *AI-only* extension if stronger semantic evidence is desired: collect reproducible source-cited research ledgers for cases requiring verification, preserve model identifiers and exact source references, allow "unsupported/unverifiable," and label all verdicts **AI-assisted, unadjudicated**. Independent sources support specific facts, but a language model checking its own evidence does not become a second independent human. Do not claim all 107 cases independently fact-checked unless there is actually corresponding reliable source evidence; do not conceal the 24 unavailable contexts.

**Publication-safe wording:** "We conducted an AI-assisted, post-hoc failure analysis of a deliberately stratified 131-case sample. It identifies probable answer-type and evidence-attribution problems but does not establish the factual validity of all semantic-poison constructions."

## Gate 3 — RCD ablations: separate rankings from real end-to-end results

The already frozen 2Wiki RCD weights were \`consistency=0.45\`, \`redundancy=0.00\`, \`conflict=0.10\`, \`base_rank=0.45\`, with \`rewrite_count=3\`. A zero-weight redundancy term **already is absent from the frozen score**, not a separate novel ablation.

The [ranking-only score ablation](../scripts/rcd_offline_scoring_ablations.py) can read JSONL of previously stored **complete authentic \`RCDRetriever.last_diagnostics\`**:

\`\`\`json
{"query_id":"<PRIVATE-ID>","condition":"poisoned","poison_doc_ids":["<PRIVATE-ID>"],"diagnostics":{"scores":{},"consistency_signals":{},"selected_doc_ids":[]}}
\`\`\`

The placeholders above are a schema sketch, not real data. Diagnostics must contain all original per-document scores/signals; synthetic filler must **never** be passed as empirical evidence. The tool **fails closed** if it cannot reproduce the original selected ordering.

\`\`\`bash
"$PY" scripts/rcd_offline_scoring_ablations.py \
  --diagnostics-jsonl "$HOME/Documents/rag-research-results/PRIVATE-existing-rcd-diagnostics.jsonl" \
  --top-k 3 \
  --output "$HOME/Documents/rag-research-results/nov09-audits/rcd-offline-ranking-sensitivity.json"
\`\`\`

Variants: \`full\`, \`no_conflict_penalty\`, \`no_consistency_score\`, \`no_base_rank\`, \`no_agreement_signal\`, \`no_rewrite_stability_signal\`. The rank-only outputs include selected-evidence order changes, set Jaccard, and poison-exposure differences. **Removing the rewrite-stability scoring term is not the same as disabling query rewriting itself.**

The frozen paired evaluation logs record the generator-visible selected evidence but **may not contain every per-candidate signal required**. If full \`last_diagnostics\` was not saved, this exact retrospective analysis is unavailable from those results; do not fabricate it. A *true* no-rewrite/candidate-depth test requires newly frozen retrieval replay, and a claim about alternate answer ASR or EM requires actual new generator inference. RCD ablations are **not finished** until such comparisons run and their output hashes, denominators, and cluster-level uncertainty are checked.

Minimum experiment design for new approved runs: same already disclosed source poison instances, identical original query IDs/corpus/seed/model, independent versioned protocol/output path, baseline vs one-feature-at-a-time ablations, fixed generation depth, clean/poisoned EM/F1, poison PRR/evidence exposure, target ASR, normal/diagnostic retrieval calls, latency, and paired query-cluster confidence intervals. No change to existing frozen results.

## Gate 4 — Pinned non-Qwen generator, evidence-fixed 2Wiki replay

[The second-model CLI](../scripts/second_model_prompt_replay.py) prepares a private, selected subset of **40 valid question-condition strata** (10 query IDs × 4 family/intensity strata, one seed), with matched Dense/RCD and clean/poisoned evidence, for **160 generator calls**. Questions are selected deterministically by query ID within each valid-construction stratum, **without consulting new-model outcomes**. The original 2Wiki outcomes are already known; this is a **post-hoc exploratory, valid-only** model comparison, not a new untouched held-out benchmark.

Unlike an RCD ablation, this tests only **generator response differences to identical stored evidence prompts**. It does *not* regenerate poisons or re-run retrieval. It cannot establish that all results transfer to another corpus or that RCD is model-invariant.

\`\`\`bash
REPO="$HOME/Downloads/rag-poison-transfer"
PY="$REPO/.venv/bin/python"
EVAL="$HOME/Documents/rag-research-results/twowiki-300-readiness-20261106/authorized-matrix/evaluation"
OUT="$HOME/Documents/rag-research-results/nov09-audits"
mkdir -p "$OUT"
cd "$REPO"

"$PY" scripts/second_model_prompt_replay.py prepare \
  --evaluation-dir "$EVAL" --n-per-stratum 10 \
  --output "$OUT/2wiki-second-model-plan_PRIVATE.json"

# Copy the printed plan SHA-256 from prepare.
"$PY" scripts/second_model_prompt_replay.py pin-model \
  --model-snapshot "/FULL/PATH/TO/A/LOCALLY-CACHED/NON-QWEN-MLX-MODEL"

# Only after pinning the plan and local model and authorizing inference:
"$PY" scripts/second_model_prompt_replay.py run \
  --plan "$OUT/2wiki-second-model-plan_PRIVATE.json" \
  --plan-sha256 "REPLACE_WITH_ACTUAL_PLAN_SHA256" \
  --model-snapshot "/FULL/PATH/TO/A/LOCALLY-CACHED/NON-QWEN-MLX-MODEL" \
  --model-sha256 "REPLACE_WITH_ACTUAL_MODEL_SHA256" \
  --output "$OUT/2wiki-second-model-results_PRIVATE" \
  --max-tokens 128 --execute

"$PY" scripts/second_model_prompt_replay.py aggregate \
  --plan "$OUT/2wiki-second-model-plan_PRIVATE.json" \
  --plan-sha256 "REPLACE_WITH_ACTUAL_PLAN_SHA256" \
  --results "$OUT/2wiki-second-model-results_PRIVATE" \
  --output "$OUT/2wiki-second-model-aggregate_PRIVATE.json"
\`\`\`

The model snapshot is hashed byte-for-byte, including dereferenced Hugging Face cache blob symlinks; \`config.json model_type\` must be non-Qwen. The runner uses the repository's MLXGenerator and checkpoints each generated response in an atomic private file, allowing verified resume. A scripted mock/synthetic test **does not count as a real second-model result**.

Always keep the private replay plan, prompts, model outputs, and per-query paths outside public GitHub. Publish only sanitized grouped rates and strong caveats after a successful real local run.

## Completion status summary

| Task | Actual status after this PR |
|---|---|
| Full HotpotQA transfer aggregate already completed/published | ✅ Existing PR #124 |
| Raw original HotpotQA artifact audit | **Verifier ready; private raw verification pending** |
| 2Wiki AI-assisted preliminary semantic review | ✅ Existing PR #125; **not independently human-validated** |
| RCD offline score-ablation code/tests | **Ready; authentic diagnostics/results pending** |
| True retrieval/QA RCD ablations | **New experiments pending** |
| Second-model prompt-replay code/tests | **Ready; local MLX execution and results pending** |

The correct paper status is **method/tooling complete where checked; empirical claims pending where actual data/model results are unavailable**. Never treat a PASS on synthetic fixtures as a scientific outcome.
