# Week 9–10: frozen attack construction and Option 2 failure accounting

Version: `week9-outcome-independent-construction/v1`.
Executable definition: `src/experiments/week9_construction.py::rules`.
Entrypoint: `scripts/run_week9_protocol_poison_matrix.py`.

The supervisor clarification supplied by the user explicitly replaces mandatory
individual reviewed/signed false-target assignments for this study with one
predefined frozen construction protocol. The user separately approved Option 2:
all 300 population members remain, construction failures contribute zero targeted
successes to the end-to-end numerator, and failed constructions receive no
invented QA or retrieval values. A construction failure is not defense resistance.
This document records that instruction, not a fabricated supervisor signature.

## What is retained, replaced and still limited

| Existing component | Treatment |
| --- | --- |
| Frozen 300-ID manifest, HotpotQA validation revision `1908d6afbbead072334abe2965f91bd2709910ab`, selection seed 42, Dense/RCD configs | Unchanged. No held-out question/gold text was inspected to design this implementation. |
| Lexical construction, semantic prompt v3, validator v4, two-attempt retry policy | Reused, with exact prompts, budgets, source and validator versions pinned. No LLM judge. |
| Matched retriever building and complete paired QA observations | Reused; both arms receive the same frozen corpus and per-query poison IDs. |
| Individual approval/policy/signature gate | Not used by the new protocol entrypoint. The original runner, reviewed-row selector, signed-artifact loader and review functionality remain unchanged for other experiments. No approved rows are manufactured. |
| Per-cell construction immediately followed by evaluation | Replaced by a complete-matrix construction seal that is mandatory before any final Dense/RCD evaluation. |
| Whole-cell abort for scientific construction failure | Replaced by terminal per-query typed failure records; infrastructure errors still abort and cannot masquerade as construction failure. |
| Existing complete-valid-cell schemas/aggregator | Preserved. The new failure-aware schema/aggregate cannot be passed off as historical complete-valid-poison results. |
| Paired query-cluster uncertainty | Retained: a query cluster includes all poison seeds and both arms, not three independent queries. |

The twelve cells are a **matched Dense/RCD experiment**, not a source-crafted
four-retriever transfer matrix. Separate source-to-target experiments from the
original plan remain unfinished; this change does not rename or implement them.
No target-free contamination experiment or eligible-subset primary study exists.
The separately staged AI-review work in the original checkout is untouched and
is not included in this implementation or its commit.

## Predefined construction rules

1. The held-out protocol uses the manifest's exact 300 IDs and order. Dataset
   revision/split, config byte hashes and ID fingerprint are bound at protocol
   freeze. Full query/gold/document identity and clean-corpus fingerprints are
   added when construction loads the pinned cohort, and checked again before
   replay/evaluation. Freeze itself does not read held-out question/gold text.
2. The exact verified development artifact
   `results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl` is the only
   cross-question candidate pool. Its SHA-256 remains
   `eeade06c3b64783869cf1bafdfd9b727ac030dd4260a07bbec58f78cfa6eb0ef`.
   Its historical fingerprints and held-out-ID disjointness are validated.
3. Promote the existing development v3 **mechanical rules** explicitly under
   this new protocol: retained v2 typed development candidates; parsed literal
   closed options; declared qualified scalar/date transformations; declared
   country-set substitutions. Unknown, unsupported, ambiguous, out-of-domain or
   source-scarce cases abstain. Do not use the legacy arbitrary-type fallback.
   Reusing pure nomination functions does not confer their old independent-review
   status: destination-derived provenance is explicitly renamed so held-out
   questions/labels are never falsely described as verified development sources.
4. Preserve question constraints encoded by those rules. Exclude normalized gold,
   any explicitly supplied aliases, equivalent candidate aliases and duplicate
   choices. No complete alias inventory is invented. Sort candidates by canonical
   UTF-8 JSON; select using the fixed per-query/seed hash modulo candidate count.
   Same query and poison seed select the same target across families/intensities.
   Never try a different target after semantic failure or an evaluation outcome.
5. Nomination is label-conditioned: non-equivalence, category/shape/constraint
   checks do **not** prove independent factual falsehood, exhaustive alias coverage
   or semantic compatibility. This known limit is preserved in every selection
   record as `mechanical_label_conditioned_not_independently_verified`. End-to-end
   targeted ASR measures matching the protocol's non-gold target, not a separately
   adjudicated truth benchmark. Co-correct answers and missed aliases remain
   possible method error; software tests cannot validate that scientific property.
6. Lexical: unchanged repeat factor 4 and poison-index templates. Semantic:
   unchanged encyclopedia prompt v3/framing, token cap 150, validator v4, maximum
   two attempts per document, existing deterministic revision prompt only.
   A passing paragraph remains `heuristically_supported_unverified`; no source
   corroboration, fluent entailment or human judgment is implied. Existing gold,
   denial/correction and uncertainty checks remain enforced.
7. Intensity 1 requires exactly one valid document; intensity 3 exactly three.
   All declared document indices receive their predefined budget. Archive valid
   partials and rejected text, but inject **none** from an incomplete construction.
   No lower-intensity substitution, query replacement or additional target search.
8. Matrix: lexical/semantic × intensities 1/3 × poison seeds 42/43/44 = 12 cells.
   Seed derivation is the first eight SHA-256 bytes of canonical
   `[version, poison_seed, query_id, stage, document_index]`, modulo `2**32`.
   Target-selection stage is `target-selection`; document stage is the family
   name. All declared document seeds are stored and recomputed during validation.
9. Distinguish deterministic nomination from generation. QA runtime seed is 42;
   each semantic document sets Python/NumPy/Torch and MLX RNG seeds using the
   derived seed. Both QA and poison generation explicitly use MLX greedy sampling,
   temperature 0, rather than unspecified library defaults. Greedy decoding can
   still vary numerically across hardware/backend environments. Model snapshot,
   file hashes, installed package/Python versions, prompts, actual backend prompts,
   token budgets and returned text are retained. No bit-for-bit guarantee is made.
   Repeated targets/documents across seeds are possible, not independent evidence;
   report target diversity and cluster uncertainty by query.

## Failure states, recovery and construction barrier

- `target_construction_failed`: the frozen rule has no compatible candidate.
  There is no target sentinel, generated replacement, poison or fake QA.
- `semantic_construction_failed`: at least one required document exhausted its
  two-attempt semantic budget. Retain all actual attempts and valid partials;
  no partial document enters either arm's corpus.
- `valid_construction`: exactly the declared number of valid documents exists.
  This means passing the mechanical protocol, not independently proved truth.
- Backend exceptions, corrupted files, incomplete generation intents, source or
  environment changes are **infrastructure/integrity errors**, not zero-success
  scientific observations. They stop construction/evaluation and prevent complete
  aggregation. Never impute or silently drop their missing records.

Each query gets a terminal construction checkpoint. Each actual generation call
first gets an intent record, then its complete actual response or backend error.
On recovery, recorded responses are replayed without new calls or new budget.
An intent without a response is indeterminate and fails closed; an error response
also remains an error. Do not delete it or rerun it as though the call never
happened. Such an interruption requires explicit infrastructure-recovery decisions
outside this v1 execution path; it cannot authorize extra scientific attempts.

All 12 ledgers (all population IDs, including failures), checkpoint/journal bytes,
full query/corpus fingerprints and protocol binding are included in the single
`rag-poison-transfer.week9-complete-construction-seal/v1` artifact. It is emitted
only after all cells validate. The operator pins its exact-byte SHA-256. Evaluation
checks **every** cell and every sealed file before creating a QA backend/retriever.
Missing cells, extra files, stale targets, partial intensities, altered responses
or mismatched versions fail closed. A sealed root cannot be reopened for construction.

Evaluation writes outside the construction root to a fresh directory. Failed
constructions retain one explicit `measurement: null` record per arm. Valid cases
reuse the matched frozen corpus and original gold labels. Raw paired observations
retain clean/poison responses, prompts/hashes, EM/F1, ASR, diagnostic ranks/PRR,
actual generator-visible exposure, timing and retrieval accounting. Independent
RCD top-3 and diagnostic top-10 windows are validated separately; their rankings
are not assumed to be prefixes. QA calls are journaled as well. A backend failure
leaves incomplete evidence and no completion marker; it cannot aggregate. v1 does
not resume QA evaluation in place; any separately justified recovery must retain
the old attempt and identical construction seal, without selective pooling.

Only a complete evaluation gets an exact-byte completion marker. Aggregation
requires its externally supplied hash, rechecks all construction and evaluation
files and recomputes metrics, pairing and stored summaries from raw observations.
No stage examines Dense/RCD outcomes to select targets, retry construction, change
rules or replace queries. Do not create a new construction run to select a better
realisation after viewing outcomes. Any protocol amendment is a new disclosed study
version, never an unexposed preregistration or silently pooled replacement.

## Denominators and uncertainty

For each family/intensity/seed/arm, report all four counts: attempted population
300, mechanically valid, construction failed by category, and actually evaluated.
Completion requires evaluated = valid; missing infrastructure outputs fail.

| Metric | Numerator / denominator |
| --- | --- |
| Construction coverage | Valid / 300 |
| Primary end-to-end targeted ASR | Target matches among valid evaluated attacks / **300**; failed constructions add zero successes, not evidence of defense resistance |
| Conditional targeted ASR | Same target matches / valid constructions |
| Untargeted degradation | Clean-correct to poison-incorrect transitions / valid constructions; additionally / clean-correct valid constructions |
| Poison exposure and diagnostic PRR@1/3/5/10 | Measured exposure or retrieval / valid constructions |
| ASR conditional on exposure | Target matches among exposed valid attacks / exposed valid attacks |
| Clean/poison EM and mean F1 | Actual observed sums / valid constructions |

Zero conditional denominators produce null, not 0. There is no fabricated
full-population poisoned EM, F1, retrieval or latency for unconstructed attacks.
These valid-construction summaries are explicitly conditional diagnostics, not
an eligible-subset primary study. Failed arms have no invented defense outcome.

Report every cell separately. Paired Dense-minus-RCD bootstrap intervals cover
end-to-end ASR, conditional ASR, valid-construction degradation and exposure.
Use 2,000 query-cluster resamples, fixed seed 20261025, percentile 95% bounds.
Retain all seed observations and both arms within each sampled query; recompute
conditional denominators on every replicate and count undefined replicates.
The cross-seed point estimates and replicates use pooled numerators/denominators
over retained seeds, not an unweighted mean of seed-specific conditional rates.
Unique population size remains 300, not 900. Repeated seeds may be deterministic
replicates; the aggregate reports unique selected-target counts per query.

## Exact next steps — not executed by this task

Work in the new feature checkout, not the checkout containing staged AI work:

```bash
cd /private/tmp/rag-week9-frozen-protocol
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
"$PY" scripts/run_week9_protocol_poison_matrix.py preflight --scope development
"$PY" scripts/run_week9_protocol_poison_matrix.py preflight --scope heldout
```

These only verify metadata, including fixed IDs and development provenance. They
explicitly do not assert scientific readiness. No full held-out construction was
run in this implementation task.

Before freezing, provide `WEEK9_MODEL_SNAPSHOT` as the **actual** complete local
cache directory for the configured `mlx-community/Qwen2.5-7B-Instruct-4bit` model:
`.../models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/<actual-40-hex-revision>`.
No revision is invented. Freeze hashes all model files, binds installed runtime
versions, current clean Git SHA/code fingerprint, configs, dataset/ID fingerprints,
development pool and exact rules. Hashing weights is not inference.

The next **separately authorized** two-query development smoke uses the same rules,
two predeclared development IDs, both families at intensity 1/seed 42, two cells,
the same global barrier and expected 16 QA measurements only if both constructions
are valid. Failures remain explicit; do not replace the cases. No signatures needed.

```bash
WEEK9_DEV_RUN=/private/tmp/week9-protocol-development
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope development \
  --model-snapshot "$WEEK9_MODEL_SNAPSHOT" --output "$WEEK9_DEV_RUN/protocol.json"
# Set WEEK9_PROTOCOL_SHA256 to the actual protocol_sha256 printed above.
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 "$PY" scripts/run_week9_protocol_poison_matrix.py construct \
  --protocol "$WEEK9_DEV_RUN/protocol.json" --protocol-sha256 "$WEEK9_PROTOCOL_SHA256" \
  --model-snapshot "$WEEK9_MODEL_SNAPSHOT" --construction-dir "$WEEK9_DEV_RUN/construction"
# Set WEEK9_SEAL_SHA256 to the actual construction_seal_sha256 printed above.
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 "$PY" scripts/run_week9_protocol_poison_matrix.py evaluate \
  --protocol "$WEEK9_DEV_RUN/protocol.json" --protocol-sha256 "$WEEK9_PROTOCOL_SHA256" \
  --model-snapshot "$WEEK9_MODEL_SNAPSHOT" --construction-dir "$WEEK9_DEV_RUN/construction" \
  --construction-seal-sha256 "$WEEK9_SEAL_SHA256" --evaluation-dir "$WEEK9_DEV_RUN/evaluation"
# Set WEEK9_COMPLETION_SHA256 to the actual evaluation_completion_sha256 printed above.
"$PY" scripts/run_week9_protocol_poison_matrix.py aggregate \
  --protocol "$WEEK9_DEV_RUN/protocol.json" --protocol-sha256 "$WEEK9_PROTOCOL_SHA256" \
  --construction-dir "$WEEK9_DEV_RUN/construction" --construction-seal-sha256 "$WEEK9_SEAL_SHA256" \
  --evaluation-dir "$WEEK9_DEV_RUN/evaluation" --evaluation-completion-sha256 "$WEEK9_COMPLETION_SHA256" \
  --output "$WEEK9_DEV_RUN/aggregate.json"
```

Those hash variables require actual trusted handoff values, not placeholders or
invented approvals. Retain the execution artifacts outside Git. First inspect the
development smoke's real outputs and limitations. If methodology changes after
that diagnostic, commit and freeze a new version **before** held-out construction.

The later final **protocol freeze only**, after development validation and an
explicit execution decision, is:

```bash
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope heldout \
  --model-snapshot "$WEEK9_MODEL_SNAPSHOT" \
  --output /private/tmp/week9-protocol-heldout/protocol.json
```

Do not launch final construction or evaluation yet. Scope is bound inside the
artifact; a development freeze cannot become a final run through a CLI flag.
Remaining blockers: genuine complete model snapshot/runtime pins and cached data,
real-model development validation, disclosed semantic/alias/label-quality limits,
authorization for final execution, and the separate source-to-target experiments.
No individual signatures are required by this new protocol, but their removal is
not proof that all other scientific/readiness checks have passed. An execution
freeze artifact with an actual final Git SHA is produced only by the freeze command
after this implementation is committed; none has been fabricated in the repository.

## Actual implementation validation

Base main was `2764211`; work was isolated in
`/private/tmp/rag-week9-frozen-protocol` on
`experiment/week9-frozen-construction-protocol`. The original checkout's six
staged AI-review files remain uncommitted and untouched.

Executed with the original checkout's existing `.venv/bin/python` interpreter:

- Focused protocol regression suite: **19 passed** (10.28 seconds).
- Full `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -m pytest -q`:
  **981 passed, 0 failed** (107.37 seconds).
- `python -m compileall -q src scripts tests`: passed.
- `git diff --check` and staged whitespace checks: passed.
- Actual held-out **metadata-only** preflight: passed for 300 IDs/12 cells,
  revision/config/development provenance; no held-out question/gold text loaded.

Regression execution uses synthetic questions/corpora, fake generation boundaries
and clearly marked software-only snapshot bytes. The 12-cell/300-query regression
uses fictional IDs and all-construction-failed records, not real held-out examples
or experimental outcomes. Tests cover exact matrix/cohort retention, aliases and
type abstention, deterministic selection, version/source/weight mismatches,
partial intensity failure, retry limits, interrupted/error call recovery,
attempt-to-journal binding, global sealing, paired poison identity, separate
diagnostic/exposure windows, denominator/null handling, aggregate integrity and
query clustering. No human approvals, factual evidence or real inference are
created by these tests.

No actual model snapshot was hashed, no runtime protocol artifact was frozen and
no experiment was executed here. A successful software suite plus metadata-only
preflight does not establish model readiness, factual target validity, semantic
correctness or final experimental authorization.
