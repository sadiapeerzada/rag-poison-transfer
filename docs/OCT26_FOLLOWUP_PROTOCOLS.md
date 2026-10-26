# October 26 follow-up protocols and execution gates

Historical proposal recorded at reviewed `8c55b3c`. The subsequent bounded
transfer smoke completed 211 model calls; new reliability/cache/resume execution
uses separately frozen v2 protocols. Current status and commands are in the
[release handoff](OCT26_FINAL_EXECUTION_HANDOFF.md); preserve the proposal below
as history rather than using its old paths with a newer source commit.

These are new experiments, not revisions to the completed HotpotQA matrix.
The original `7a24a40c0a25399e1defc02844eb3a1de44b4a19` worktree and artifacts
are read-only. No README changes are authorized until all experimental milestones
are complete. No full follow-up run, push, or merge is authorized by this document.

## Source-only bounded transfer selection

Implementation: `scripts/run_source_selection_transfer.py`.
Schema: `rag-poison-transfer.bounded-source-selection/v1`.

The user authorized source-only selection with the budget frozen before compute.
For each query and poison seed, nominate at most three distinct targets using the
existing development-only pool, canonical ordering, and frozen seed rotation.
Construct all candidate bands before source screening. Each semantic document has
two predefined attempts and a 150-token budget. Preserve every attempt and partial
construction; inject exactly the declared one or three documents or none.

Evaluate all available candidates on each source: BM25, Dense, Hybrid, Reranker.
Select the first candidate with source targeted success, otherwise the first valid
candidate. Never consult another target or RCD while selecting. Missing candidates
and failed construction remain typed failures; there is no replacement or adaptive
increase to the candidate budget. RCD is one composite defended target, not four
wrapper variants. The selected candidate can differ by source, family, intensity and seed; the
selected instance is identical across final targets for that condition. All
source selections must be sealed before final target QA.

Screening uses candidate-band pooled corpora. Final evaluation uses the selected
poison union for that source and condition. Consequently, reevaluate the source
under the final corpus; screening success is not the ATR denominator. Evaluate
BM25, Dense, Hybrid, Reranker and RCD on identical selected instances within each
source condition, retaining all query IDs and explicit construction failures.
ATR is final source-and-target co-success divided by final source success;
zero source successes gives null ATR. End-to-end targeted ASR uses the entire
cohort; conditional ASR uses valid constructions. Bootstrap query clusters across
all three seeds, not individual query/seed rows; 2,000 replicates, seed 20261026,
percentile 95% intervals, unadjusted. Do not infer transfer from source labels alone.

Freeze source Git/source/environment fingerprints, base protocol hash, exact
configs, query IDs, MLX model weights, embedder and reranker snapshots. Verify stage
file inventories and externally pinned seals before progressing. Fresh output
paths are mandatory; incomplete attempts remain archived. This new transfer runner
does not implement automatic recovery/resume, so interruption requires diagnosing
and documenting the preserved partial run, not silently spending a fresh budget.

Development smoke: two existing predeclared development queries, both attacks,
intensity 1, seed 42, four sources/five targets, at most **220 local model calls**.
Full proposal: 300 queries, two attacks, intensities 1/3, seeds 42/43/44;
48 source conditions and 240 source/target arm conditions. Maximum **208,800 model
calls**: 21,600 semantic construction, 43,200 screening, 144,000 final QA.
Clean-QA reuse is not implemented. At the observed HotpotQA backend means, this
upper bound is approximately **279.5 model-hours**, excluding retrieval, indexing,
loading and hardware differences. Actual coverage can reduce this substantially.
A real-model smoke has not yet passed; approval and smoke validation precede full
execution. A workload cap is not a prediction of useful attacks or wall time.

## Risk-disclosed 2Wiki replication

Implementation: `scripts/prepare_oct26_followups.py`,
`scripts/prepare_2wiki_development.py`, `src/experiments/twowiki_replication.py`, and
an explicitly separate `rag-poison-transfer.2wiki-frozen-construction-protocol/v1`
branch of `scripts/run_week9_protocol_poison_matrix.py`. Existing HotpotQA defaults
and protocol schema are retained; RCD weights/retrieval code are unchanged.

Pinned dataset: Salesforce/ContextualBench, 2WikiMultihopQA,
revision `9823f70484dea525100394220b0ea5184d0eeb7b`.
Freeze 300 development IDs from train and 300 held-out IDs from dev. Rank IDs by
SHA-256 of canonical `["2wiki-cohort-hygiene/v1", revision, 42, split, id]`.
Exclude all 300 known historical baseline IDs. Reject duplicate IDs, normalized
exact question duplicates and question 3-token-shingle Jaccard similarity >=0.85
against known history and previously selected cohorts. These are bounded text
hygiene checks, not proof of semantic disjointness. Selection never uses answers,
target eligibility, model outputs, or defense outcomes. Policy was recorded before
new question access. Only selected train answers/context have been materialized;
no new held-out answers have been accessed for this preparation.

### Bounded historical provenance search (completed)

One read-only search covered repository history, introducing commits, scripts,
configs, reports, raw tracked baselines and matching available local artifacts.
The 25-query sweep was introduced in commit
`d232fdf3b38aca9134c9728e85dad00605c6f069`; its CSV and Week 5–6 report do not
contain query IDs or a recoverable selection ledger. No exact selection was
recovered. Do not claim an exhaustive search of unavailable records.
The four exp_017–020 baselines expose the same 300 IDs; those IDs are excluded.
Their raw provenance records revision `e37a4050605363be62f1d02e6eb888fe5f56530e`,
whereas later configs pin `9823f70484dea525100394220b0ea5184d0eeb7b`.
These revisions are not silently treated as equivalent.

**Complete historical non-overlap cannot be certified.** The unknown 25-query
sweep is an unresolved potential exposure. This limits a claim of untouched,
confirmatory replication; it does not preclude an explicitly disclosed secondary
replication with fixed weights and no new tuning. Up to 25/300 overlap is possible
from that particular sweep alone; that is not a bound on all historical exposure.
If an entirely unexposed confirmatory cohort is required, use an independently
sourced evaluation cohort under a newly approved protocol instead.

### Frozen preparation artifacts and observed checks

External root: `/private/tmp/week9-2wiki-protocol-2026-10-26-v1/`.

- `cohorts/cohort_policy.json` SHA-256:
  `827165092a07f2f4efb55626db842670db02dfcef164856f9eb2d1b9e74d442a`.
- `cohorts/cohort_manifest.json` SHA-256:
  `3f51077946601cc0f58c0866716bf6c4650306dfd497cb98ed2973a466ca2cd4`.
- `development/replication_inputs.json` SHA-256:
  `a589c54d0153b20d76e63fbd58bd5328957efe413e5c28b6272f96139172d59e`.

Observed: 300 train and 300 dev IDs; zero selected ID overlap; no selected exact
or near-duplicate questions under the declared rule; known historical IDs excluded.
300 train answer/context records prepared; **zero held-out answer records read,
zero model calls**. Development metadata preflight passed. A two-query diagnostic
uses the first two frozen train IDs and the 300-query train corpus. It is not the
full replication. Full protocol retains frozen attack rules, RCD, exact counts,
construction/evaluation barrier, paired Dense/RCD and failure-aware aggregation.
Worst-case full run: 7,200 semantic construction plus 14,400 QA = **21,600 model
calls**, approximately **29.5 model-hours** at observed HotpotQA means, before
retrieval and data costs. Full replication has not run and requires approval.

## Commands and approval gates

Run from a clean checkout of the implementation commit; retain that checkout and
its environment for every stage. `PY` is the existing project `.venv/bin/python`.
Set `MODEL`, `EMBEDDER`, `RERANKER` to the exact verified cached snapshot paths;
freeze records their file hashes. No model inference occurs in freeze/preflight.

```bash
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
EMBEDDER=/Users/sadiapeerzada/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5/snapshots/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
RERANKER=/Users/sadiapeerzada/.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L-6-v2/snapshots/233902d25c440f23af6f7d6e94d2946bac0bee0a
BASE=/private/tmp/week9-protocol-heldout/protocol.json
BASE_SHA=5eb83f381745addbd102547540362dac6fc099ab7fd1594dcd6e2975ba376025
REPLICATION=/private/tmp/week9-2wiki-protocol-2026-10-26-v1/development/replication_inputs.json
REPLICATION_SHA=a589c54d0153b20d76e63fbd58bd5328957efe413e5c28b6272f96139172d59e

# Metadata-only smoke preflight; no model call:
"$PY" scripts/run_week9_protocol_poison_matrix.py preflight --scope development \
  --replication-spec "$REPLICATION" --replication-spec-sha256 "$REPLICATION_SHA"

# New, non-existing external paths; scope development for the bounded transfer smoke:
"$PY" scripts/run_source_selection_transfer.py freeze --scope development \
  --base-protocol "$BASE" --base-protocol-sha256 "$BASE_SHA" \
  --model-snapshot "$MODEL" --embedder-snapshot "$EMBEDDER" \
  --reranker-snapshot "$RERANKER" --output /private/tmp/oct26-transfer-smoke-protocol.json
```

For transfer execution, pin the returned protocol hash, run `candidates`, pin
`candidates.complete.json`, run `source-select`, pin `selection.seal.json`, then
`evaluate` and `aggregate`. The CLI requires the previous-stage pin at each step.
Do not substitute an unverified hash inferred from filenames. For a full-run
proposal freeze with `--scope heldout` into another fresh path; each model stage
requires `--allow-full-compute` **only after explicit user approval**.

For 2Wiki freeze use `freeze-protocol --scope heldout --model-snapshot "$MODEL"
--replication-spec "$REPLICATION" --replication-spec-sha256 "$REPLICATION_SHA"
--output NEW_PROTOCOL_PATH`. Pin that artifact, then use `construct`, externally
pin `construction.seal.json`, `evaluate`, pin `evaluation.complete.json`, and
`aggregate`. No full-run command is authorized until the smoke/preflight and
scientific/compute approval gates are satisfied. Historical artifacts must never
be destinations. A metadata preflight does not establish semantic correctness,
backend readiness or statistical power.

## Validation performed

Full offline pytest: **999 passed in 106.33 seconds**. New tests cover source-only
selection/budget, zero-source-success ATR, paired final rows, stage seals,
cohort/near-duplicate selection, explicit 2Wiki scope and schema, exposure
provenance, and publication export recomputation. Passing software tests does not
verify generated semantic evidence or establish defense effectiveness.

A sandbox-only full-suite retry produced 18 cache-lock permission failures
(981 tests passed). The subsequent offline run with existing cache access passed
all 999 tests; the failure log is retained, not relabeled as a successful run.
