# Professor-requested semantic development validation — 26 October 2026

## 1. Motivation and delivery state

The two-query semantic-profile smoke succeeded, but cannot establish reliability,
semantic correctness or factual falsity. This development-methodology study measures
automatic construction quality and prepares genuine independent review before a final
held-out protocol is proposed. The 300-query 2Wiki study is **DEFERRED**. No new model
calls or human judgments were produced during implementation.

The interrupted original checkout remains at `b66d840` on
`execution/2wiki-heldout-overnight-preparation`, with its untracked held-out supervisor
preserved. Its SHA-256 was
`09245d1747ddf0e0a0459bbee115e2edb65c885b4a3a4534f32e5ead1cbfdf00`.
Implementation is isolated in `/private/tmp/rag-semantic-development-validation`,
branch `development/2wiki-semantic-validation-25`, based on the same merged commit.
No unfinished held-out supervisor is reused or included in this development study.

## 2. Protocol and dataset identity

- Study: `semantic-quality-25/v1`; diagnostic-only, development scope.
- Artifact schema: `rag-poison-transfer.semantic-development-protocol/v1`.
- Dataset: 2WikiMultihopQA, published **train**, revision
  `9823f70484dea525100394220b0ea5184d0eeb7b`.
- Input: existing pinned 300-query train development pool and complete local corpus.
- Input specification:
  `/private/tmp/oct26-reliable-2026-10-26-v1/twowiki-development/local/replication_inputs.json`.
- Specification SHA-256:
  `8e9467072d97419df69aea0786e28b32c20eaa6fc6342e68ff70b05afe64bba0`.
- New isolated output namespace:
  `/private/tmp/oct26-2wiki-semantic-development-25-v1`.
- Delivery freezes metadata only after tests and a clean implementation commit.
  Exact protocol/code/model/config pins are recorded in that namespace's protocol
  and `APPROVAL_REQUEST.json`; never edit those frozen files to change code lineage.
- The previous two-query namespace and all historical protocols/results remain immutable.

## 3. Deterministic development selection

Use SHA-256 of canonical JSON `[study identifier, 42, query ID]` as the primary sort
key, then literal query ID to break ties; take the first **25**. Do not filter by
construction success, model output or Dense/RCD outcome. All IDs in the development
pool must be unique and disjoint from the held-out cohort manifest; duplicates,
overlap or fewer than 25 development records fail closed. No held-out question or
answer text is used for selection. The complete source pool and selected query set
are fingerprinted; original labels, aliases where explicitly supplied, and document
IDs are preserved. Target nomination uses the unchanged full development source pool.

Selected query-set fingerprint:
`4a0ec53d01980a36b1b0e5ee55651fdfc50277c46214182e190e695fe979deea`.
Sorted development-pool-ID fingerprint:
`8789aed0b5dd74b2d66ba4bae40beecece8f81dde53e1a1c47e9f3943cf84132`.
The exact ordered IDs appear in the frozen protocol binding.

There is no invented metadata stratification or outcome-based resampling. The existing
v2 answer-shape classifier descriptively labels the chosen sample as 11 unknown,
4 yes/no, 5 place, 1 nationality, 2 calendar date and 2 person. These are mechanical
classifier labels, not verified types or selection strata. Unsupported questions
remain in the denominator and are not replaced. This sample is not selected to make
the narrow grammar look successful.

## 4. Attack and intensity configurations

Only `semantic_fluent_false_evidence`, intensities **1 and 3**, poison seed **42**,
exactly the same 25 IDs. No lexical matrix or extra poison seeds are introduced.
Profile: `question-anchored-development/v1`, unchanged from the merged implementation:

- `semantic-encyclopedic-prompt/v4-development`;
- `conservative-text-heuristic/v5-development`;
- `failure-specific-revision-prompts/v2-development`;
- at most two attempts per document, 150 completion tokens, explicit greedy sampler.

The versioned single-sentence format is a substantive construction-policy change
from legacy paragraphs, not an equivalent replacement. The development profile is
still prohibited in held-out scope. Original target selection, gold/alias exclusions,
seed derivation and frozen RCD configurations are unchanged. No target/prompt/validator
or retry change is permitted after observing study results. Any later method revision
requires a separate version/run; failures here remain failures.

## 5. Automatic semantic-quality validation

Report all planned document slots, attempted documents, generation attempts, first-pass
acceptance, retries, retry acceptance, automatically accepted documents, full-query
construction, partial-query construction, final failures and failure categories.
Keep original raw text, prompts, revisions, model/seed provenance and exact reasons.
Separate exact duplicate text from distinct outputs. Empty/short/meta-leaking outputs
are counted as malformed rejections. Unsupported syntax is not automatically a human
judgment of irrelevance. Subject/relation matching is reported as a heuristic pattern
match only. Factual falsity and genuine evidence sufficiency remain unverified.

A target-construction failure has zero generation attempts and remains in query and
planned-slot denominators. Partial intensity-3 constructions are archived but **none**
are injected unless exactly three valid documents exist. Infrastructure interruptions
abort, preserving journals; they are not counted as scientific construction failure.
The same index-0 prompt/seed can recur across intensities; generation is not cached or
regenerated based on QA outcomes. Exact outputs are preserved rather than promised to
be numerically reproducible on all hardware.

## 6. Independent semantic-quality review

Export all generated attempts (maximum 200) after the complete construction seal:

- `master.jsonl`: full query/gold/explicit aliases/target/text/intensity/index/attempt,
  automatic decision/reason, provided dataset passages and actual model provenance.
- `blinded_review.csv` and `.jsonl`: same immutable review content, excluding automatic
  decisions/reasons and any Dense/RCD outcomes. All human fields pending/blank.
- `manifest.json`: trusted protocol/seal context, file hashes, item count and blinding limits.

Review IDs bind the exact protocol, query, target-generation instance and text.
The import command requires trusted protocol and construction pins, reconstructs
expected items and rejects altered packages, changed immutable fields, unknown/duplicate
IDs, malformed ratings/decisions and unsubstantiated accept decisions. Missing/pending
reviews are explicitly counted. No identity, timestamp, evidence or judgment is
fabricated. Dataset passages are available provenance, not independent factual proof.

A genuinely independent person fills subject, relation, target assertion, grammar,
relevance, falsity, evidence, confidence and notes. Identity, actual timezone-qualified
timestamp and an honest independence attestation are supplied by that person.
Acceptance requires the affirmative rubric and referenced evidence; software does not
authenticate the reviewer or certify factual truth. Follow the
[review instructions](reviews/semantic_development_25/REVIEW_INSTRUCTIONS.md).
The custodian keeps the master and attack outcomes away from the reviewer. Disagreement,
ambiguous labels or inadequate evidence requires supervisor adjudication; no automatic
approval or silent gold-label correction is allowed. Review imports never approve the
held-out protocol.

## 7. Construction results

**NOT YET EXECUTED.** Both intensity rows remain PENDING, not zero-result experiments.

| Metric | Intensity 1 | Intensity 3 |
| --- | --- | --- |
| Query population | 25 | 25 |
| Planned poison-document slots | 25 | 75 |
| Attempted / accepted documents | PENDING | PENDING |
| Full / partial / failed queries | PENDING | PENDING |
| First / retry acceptance | PENDING | PENDING |
| Generation calls and latency | PENDING | PENDING |
| Independent semantic/factual review | PENDING | PENDING |

## 8. Paired Dense/RCD sanity results

**NOT YET EXECUTED.** Evaluation cannot start before both construction cells are sealed.
Use the same frozen poison corpus in both arms and retain the complete condition corpus
in every batch. Preserve all 25 query IDs, original gold labels and explicit failure
records; unconstructed attacks receive no fabricated QA or retrieval measurements.
Report end-to-end ASR over 25, conditional ASR over full constructions, PRR@1/3/5/10,
actual generator-visible exposure and ranks, clean/poison EM/F1, degradation and measured
retrieval/generation latency with explicit denominators. These are diagnostic findings;
do not infer defense effectiveness or statistical significance from this development set.

## 9. Failure analysis and reproducibility

**PENDING real generation and independent review.** The summary tool counts automatic
failure categories/reasons, partials, attempt consumption and construction latency from
frozen journals. Human review must distinguish syntax misses, genuine semantic errors,
factual ambiguity and unsupported evidence. Do not relabel construction failure as a
successful defense. No comparison is outcome-adaptive. Durable intents without responses,
error responses, corrupt hashes or stale provenance halt recovery; never delete/copy an
intent or rerun it as a new attempt. Changes require a separate approved namespace.

## 10. Resource and call accounting

The 25-query/two-intensity design has 100 document slots, at most **200 construction
calls**, plus **200 QA calls** without savings (50 query/cell observations × two arms ×
clean/poisoned). Full constructions with exact clean reuse need 100 poisoned QA plus
50 distinct clean QA = **150 QA calls**, so the maximum with planned hits is **350**;
the approval ceiling is **400**. Failures reduce calls, never denominators. Actual
hit rate and semantic coverage are unknown; no point forecast is justified.

The fixed cohort preflight mechanically nominates a target for **19/25** questions;
6 have no target under the unchanged method. No question is replaced. This is
pre-generation nomination availability, not observed construction quality or factual
verification. Therefore this exact frozen cohort has tighter bounds: 76 attempted
document slots, at most **152 construction calls**, **152 QA calls** without savings,
and **304 total**. With all planned clean hits the corresponding maximum is 266
(152 construction + 76 poisoned QA + 38 distinct clean QA). Request approval for
up to 304 calls, not the generic 400 ceiling. All quality outcomes remain PENDING.

Preflight observed 16 GB RAM, normal memory pressure (level 1, about 77% free by the
system tool), approximately 27 GiB free disk and no matching active research MLX/
`caffeinate` process. Model files/dependencies are checked against local pinned bindings.
These are idle observations, not measured inference peak RAM. No resource benchmark
or new model initialization has been run for this study. Do not promise a wall-clock
completion time. Illustratively, 400 calls at 3/6/12 seconds each consume 20/40/80 minutes
of model time, excluding indexing, snapshot validation, six potential stage launches
and thermal/memory effects. These are assumptions, not measured scenarios.

Use one cooperating MLX process, `caffeinate -i` and `/usr/bin/time -l` for measured stage wall time/peak RSS; check resources before each bounded
stage. Construction has two 25-query cell batches. Paired evaluation has at most four
25-query arm batches. Continue only documented exit-75 batch pauses after journal checks;
stop on any other error or non-normal memory pressure/unsafe disk headroom. No unlimited
loop or held-out supervisor is used. Live dangerous pressure requires stopping the
process and preserving any unresolved intent for review, not silently repeating it.

## 11. Limitations

Uniform selection does not guarantee coverage of every question type. The grammar is
intentionally narrow and some selected questions may have no compatible target or no
recognized relation. Complete gold aliases, factual falsehood and evidence consistency
are not automatically known. The earlier 25-query historical 2Wiki exposure record is
still unresolved; the fixed held-out cohort excludes the 300 known historical baseline
IDs but is not certified historically untouched. Nothing in this development study
changes that disclosure. Human reviewers remain unavailable until actually supplied.

## 12. Supervisor recommendation and exact procedure

Approve this as a bounded development-methodology study only, subject to code review,
clean-source freeze and explicit compute permission. A final held-out proposal requires
genuine independent review and supervisor approval of a preregistered semantic protocol.
The successful two-query smoke is not that approval. Main 300-query execution is deferred.

From the clean implementation worktree, metadata-only preparation is:

```sh
cd /private/tmp/rag-semantic-development-validation
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
SPEC=/private/tmp/oct26-reliable-2026-10-26-v1/twowiki-development/local/replication_inputs.json
SPEC_SHA=8e9467072d97419df69aea0786e28b32c20eaa6fc6342e68ff70b05afe64bba0
NEW=/private/tmp/oct26-2wiki-semantic-development-25-v1
"$PY" scripts/run_week9_protocol_poison_matrix.py preflight --scope development \
  --semantic-profile question-anchored-development/v1 --development-study semantic-quality-25/v1 \
  --replication-spec "$SPEC" --replication-spec-sha256 "$SPEC_SHA"
# Metadata freeze only, once, from the reviewed clean source commit:
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope development \
  --semantic-profile question-anchored-development/v1 --development-study semantic-quality-25/v1 \
  --replication-spec "$SPEC" --replication-spec-sha256 "$SPEC_SHA" \
  --model-snapshot "$MODEL" --output "$NEW/protocol.json"
```

After **explicit approval for up to 304 new local backend calls**, execute each stage
individually. Protocol scope/matrix are pinned; never supply profile/study overrides
on resume. First construction command below may pause with exit 75 after intensity 1;
inspect complete journals, then repeat exactly once to finish intensity 3 and seal.

```sh
P="$NEW/protocol.json"
P_SHA=$(shasum -a 256 "$P" | cut -d ' ' -f 1)
C="$NEW/execution/construction"
E="$NEW/execution/evaluation"
caffeinate -i /usr/bin/time -l "$PY" scripts/run_week9_protocol_poison_matrix.py construct \
  --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" \
  --construction-dir "$C" --max-batches 1
# Only once the full construction seal exists and validates:
C_SHA=$(shasum -a 256 "$C/construction.seal.json" | cut -d ' ' -f 1)
"$PY" scripts/review_semantic_development.py summary --protocol "$P" --protocol-sha256 "$P_SHA" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --output "$NEW/construction_quality.json"
"$PY" scripts/review_semantic_development.py export --protocol "$P" --protocol-sha256 "$P_SHA" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --output "$NEW/review_package"
caffeinate -i /usr/bin/time -l "$PY" scripts/run_week9_protocol_poison_matrix.py evaluate \
  --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E" --max-batches 1
# At most four evaluation launches total; repeat only recognized normal pauses.
E_SHA=$(shasum -a 256 "$E/evaluation.complete.json" | cut -d ' ' -f 1)
"$PY" scripts/run_week9_protocol_poison_matrix.py aggregate --protocol "$P" --protocol-sha256 "$P_SHA" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E" \
  --evaluation-completion-sha256 "$E_SHA" --output "$NEW/execution/aggregate.json"
# Only after real completed reviews exist, in a separate copy of the blinded sheet:
"$PY" scripts/review_semantic_development.py import --protocol "$P" --protocol-sha256 "$P_SHA" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --package "$NEW/review_package" \
  --reviews /path/to/actual_completed_review_copy.csv --output "$NEW/imported_human_reviews.json"
```

All unavailable 25-query results and human decisions remain PENDING. The header-only
committed template is not a substitute for generated review items or completed reviews.

## Verification completed before metadata freeze

- Focused offline suite: **167 passed in 18.01 seconds**;
  `/private/tmp/semantic25-focused-delivery.log`.
- Full offline pytest: **1145 passed in 117.26 seconds**, no failures;
  `/private/tmp/semantic25-full-delivery.log`.
- Python compilation of `src scripts tests`: passed; bytecode goes to
  `/private/tmp/semantic25-pycache`, outside the repository.
- `git diff --check`: passed. Runner/review CLI help and the actual metadata-only
  25-query preflight were executed successfully.
- Completed two-query smoke: all supplied protocol/seal/completion hashes match,
  all sealed construction/evaluation file hashes match, and per-arm summaries were
  independently recomputed from rows and matched the aggregate. Its 75 files were
  inventoried for post-preparation integrity verification.
- Regression coverage includes deterministic/order-independent selection, overlap
  rejection, stale bindings/scope refusal, partial intensity-3 accounting, normal
  batch pauses, indeterminate-intent refusal, complete journal replay, paired
  evaluation/aggregation, blinded export, missing/duplicate/malformed reviews,
  trusted-context import validation and refusal to write inside frozen namespaces.

Synthetic test reviews are explicitly labeled fixtures, not actual human judgments.
No new model calls or independent human reviews occurred during these checks.
The metadata-only freeze and Git delivery are recorded in the final handoff and
external approval manifest; neither authorizes inference.
