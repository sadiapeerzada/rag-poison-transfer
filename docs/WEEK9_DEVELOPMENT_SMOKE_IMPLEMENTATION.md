# Week 9 measurement fixes and development diagnostic

Base: `5548cd7` (latest verified main). The existing in-progress patch was
preserved byte-for-byte while fast-forwarding from `81aeac1`; main added only the
binding reconciliation report. No frozen configuration, RCD behavior/weights,
held-out manifest, original research question, historical result, or final target
approval gate was changed. No real MLX inference or experimental matrix was run.

## Completed

- Abbreviation-safe extraction preserves `A. B. Example`, initials, honorifics,
  dotted abbreviations and decimals. It retains the first answer line and stops
  at ordinary sentence boundaries. The old extractor remains explicitly
  selectable for historical reproduction, without rewriting old results.
- Shared QA observations preserve complete raw response, extracted answer,
  logical prompt/SHA-256, extractor version, elapsed time, reported backend
  latency and actual token counts. Missing backend accounting is `null`, never
  invented. MLX additionally returns its actual formatted chat prompt and hash;
  the chat template is applied only once at the backend.
- Matched and transfer rows retain EM/F1, targeted success, ranks, retrieved IDs
  and evidence, generator-visible exposure and measured retrieval times/calls.
  New summaries include explicit numerators/denominators, F1 means, PRR@k,
  conditional ASR, rank misses and undefined (`null`) conditional means/rates.
  Inner retrieval counts remain unknown when the retriever does not report them.
- Source-to-target evaluation no longer aborts at zero source successes. It
  evaluates all target queries, retains full source/target rows, reports full
  cohort ASRs, and calculates ATR only on the source-success conditioning set.
  At zero source success, source ASR is 0 and ATR/conditional target ASR are null.
  No strengthening, resampling or source-failure omission is performed.
- A separate development-only runner verifies two fixed IDs against the exact
  pinned development artifact and held-out **IDs**, then checks the original
  question/gold/document identities again after development-only loading. The
  existing loader reads the dataset ID column and selects these two rows before
  reading their question/context/gold fields. It never requests held-out text.
- Both lexical and semantic-fluent families run intensity 1/seed 42 under the
  same frozen model, Dense and composite RCD settings. Within a family, identical
  poison documents and target associations feed both pipelines. The diagnostic
  does not implement source-specific attack optimization or the full research
  transfer matrix; that original work remains separate.

New QA records use `rag-poison-transfer.qa-measurement/v2` and extractor
`short-answer-extraction/v2-abbreviation-safe`. Full-cohort transfer outputs use
`rag-poison-transfer.transfer-result/v2-full-cohort`; their ASRs now refer to the
whole evaluated cohort, with separately named conditional target ASR. Historical
cell schemas/summaries without v2 measurement fields retain their old replay
behavior. Consumers must not pool extraction/scoring versions without an explicit
impact analysis. Existing clean publication baselines require that comparison
before reuse; this task does not rescore or overwrite them.

## Fixed development cases and genuine review input

- `5ae2c416554299492dc91c67`: named-person answer diagnostic.
- `5ae143ed55429920d5234360`: year-answer diagnostic.

The input template is
[`pending_targets.json`](reviews/week9_development_smoke/pending_targets.json).
It preserves genuine development questions/gold/document IDs and their hashes;
all reviewer identities, actual timestamps, targets and evidence are blank. All
approval values are false/unset. It **cannot** be executed as an approved input.
Phase 4A recommendations and Phase 4E mechanical nominations are not approvals.

An actual independent reviewer and nominator must supply a **private copy**, with:

1. Exact header schema `rag-poison-transfer.development-smoke-targets/v1`,
   `scope: development`, `protocol_version: answer-compatible-targets/v3-reviewed`,
   the original development artifact SHA-256 and two-query fingerprint. Preserve
   all original case identities/text/hashes; no extra, missing or duplicate IDs.
2. Only after genuine review, header `status: reviewed_diagnostic_only` and each
   real v3 decision: actual reviewer/nominator (distinct), real timezone-aware
   `reviewed_at`, nonempty `review_evidence`, `approved: true`,
   `review_status: approved`, and explicit true decisions for compatibility,
   factual falsehood and coherent false evidence. The tool creates none of these.
3. Exact reviewed `target_answer` and its `reviewed_target_sha256` (SHA-256 of
   exact UTF-8 string), known relevant `gold_aliases` including the stored gold,
   actual `alias_check_complete`, resolved ambiguity, and
   `evidence_status: independently_verified`. Each genuine evidence entry needs
   `reference`, precise supported `claim`, and honest `limitations`.
4. A trusted exact-byte SHA-256 supplied through the review handoff. Keep private
   identities/evidence outside Git. Software checks structure, bindings and
   recorded assertions; it cannot prove human independence, actual evidence
   access or factual truth. The operator must verify that provenance before
   trusting the pin. No signing/approval-conversion command is provided.

The development input has a distinct schema/scope and only two records. It
cannot satisfy the final held-out artifact loader. The 300-query signed review
policy and its gate remain unchanged; there is no skip-review flag.

## Commands — no inference was run here

From repository root, metadata-only preflight (safe without model construction):

```bash
.venv/bin/python scripts/run_week9_development_smoke.py --preflight
```

Validated input preflight, still no model/dataset materialization:

```bash
.venv/bin/python scripts/run_week9_development_smoke.py --preflight \
  --targets /secure/path/reviewed-week9-development-targets.json \
  --targets-sha256 "$WEEK9_DEV_REVIEW_SHA256"
```

Set `WEEK9_DEV_REVIEW_SHA256` only to the actual trusted 64-hex handoff pin.
After genuine review and **separate authorization to run inference**, the exact
execution command is:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
.venv/bin/python scripts/run_week9_development_smoke.py --execute \
  --targets /secure/path/reviewed-week9-development-targets.json \
  --targets-sha256 "$WEEK9_DEV_REVIEW_SHA256" \
  --output-dir /Users/sadiapeerzada/Downloads/rag-rcd-week9-development-smoke \
  --experiment-id development-smoke-01
```

Execution requires a clean committed source tree, available cached model/dataset
weights and the configured real MLX backend. There is no mock/paid-API execution
mode. Output must be outside this repository, under a fresh attempt ID. A valid
complete diagnostic emits 16 QA records (2 queries × 2 pipelines × 2 conditions ×
2 families) plus two accepted semantic documents and all actual generation attempts.
ASR=0 is a valid model outcome; it does not cause stronger attacks or retargeting.

Optional generation-only recovery adds `--recover-from` pointing at an earlier
attempt root and uses a **new** experiment ID. It verifies identical committed
code/source/config/query/review provenance and every checkpoint before loading a
model. Valid semantic documents are reused unchanged; QA is repeated as a new
attempt rather than appended to or pooled with old results. Corrupt/stale
checkpoints fail closed. Existing directories and files are never overwritten.

## Outputs and remaining scientific review

Each diagnostic root has `development.plan.json`, per-family immutable poison
snapshots, complete QA `results.jsonl`, `generation.events.jsonl`, attempt histories,
semantic checkpoints and summaries or an explicit failure record. Every actual
model call is traced before content validation, including rejected prose and
backend errors. Backend errors have no invented response. Partial attempts remain
failed/incomplete and cannot masquerade as a successful full diagnostic.

All manifests, rows and summaries are development-scoped and non-final with the
separate `rag-poison-transfer.week9-development-smoke/v1` schema. Final held-out
cell validation/aggregation rejects them. Review metadata is bound by artifact
and assignment hashes; no diagnostic output is converted into an approval.

The existing semantic validator is reused, plus a development-only direct-relation
screen `development-direct-affirmation/v1`. The extra screen rejects a target
merely mentioned near the word “answer”, a false acceptance found during new
testing. It does not alter frozen shared prompts/validators and does not prove
entailment. Accepted text remains `heuristically_supported_unverified` and requires
human inspection for actual affirmative support, falsehood, aliases, question
constraints and coherent prose. Two successful cases would demonstrate plumbing,
not effectiveness or semantic correctness of the attack distribution.

**Execution is presently blocked:** no genuine reviewed two-case input was supplied,
and this task explicitly forbids running inference. Metadata-only preflight found
MLX packages available but did not load weights or test real-model behavior.
A completed software test suite is not human approval. Post-run human semantic
review and the original full-cohort approvals remain separate later requirements.

## Software validation

Final checks for this implementation:

- Full offline suite: `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q` — **915 passed, 0 failed** (94.72 seconds).
- New measurement and development diagnostic regression tests: **26 passed**.
- `.venv/bin/python -m compileall -q src scripts tests` — passed.
- `git diff --check` — passed.

The diagnostic execution tests use synthetic corpora and mocked model boundaries;
they create no human approvals. No real MLX inference or experimental matrix was
executed. Cached weights, actual runtime behavior and scientific semantic validity
remain untested by these software checks.
