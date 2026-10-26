# October 26 final execution handoff

The completed HotpotQA study is archived at `7a24a40` and is never a new output
destination. The final branch continues `research/oct26-execution-reliability`
from reviewed `8c55b3c`; initial reliability implementation is `8ef82c1`.
The release execution manifest records the exact final source commit, hashes,
model snapshot and output locations. Do not infer a runtime commit from a README.

## Readiness and limits

| Study | Preparation decision | Evidence | Not yet established |
|---|---|---|---|
| Full 2Wiki matched replication | READY WITH DOCUMENTED LIMITATIONS | Local pinned 300-query input, fixed train pool, full matrix/schema checks, interruption/resume fixtures, complete-corpus batches, paired aggregation | Full MLX outcomes, runtime/peak RAM, real-model behavior of the new cache/resume path; unknown historical 25-query exposure |
| Full source-crafted transfer | READY WITH DOCUMENTED LIMITATIONS | Fixed 300 IDs; four sources/five targets; three candidates; two attacks/intensities; three seeds; global barriers; old real development smoke; new cache/resume/equivalence fixtures | Full transfer results, real-model cache/resume smoke, sustained multi-day resource stability |

These are workflow-preparation decisions, not completed-experiment or scientific-
effectiveness certificates. No full inference or substantial smoke was run for
this release. A clean code checkout, the pinned local inputs/models, sufficient
storage and explicit compute authorization remain execution prerequisites.

The supervisor-approved all-300 failure policy is unchanged. No eligible-subset,
target-free fallback, additional individual target-signature requirement, intensity
reduction, source reduction or RCD change is introduced. A matching cache input is
not an independent factual validation of a poison target.

## Code, protocol and paths

Execution-policy details are in [the reliability amendment](OCT26_EXECUTION_RELIABILITY.md).
The public 2Wiki selection records are [cohort_manifest.json](protocols/oct26_2wiki/cohort_manifest.json)
and [cohort_policy.json](protocols/oct26_2wiki/cohort_policy.json). They preserve the
already frozen IDs and risk disclosure; they contain no reviewer approvals.
Runtime local data and large model weights are intentionally not committed.

The final local execution namespace is:

```text
/private/tmp/oct26-reliable-release-2026-10-26-v1/
  EXECUTION_MANIFEST.json
  transfer-development/protocol.json
  transfer-heldout/protocol.json
  twowiki-development/protocol.json
  twowiki-heldout/protocol.json
  <study-scope>/execution/{construction|candidates,selection,evaluation,aggregate.json}
```

Protocols declare their exact output paths; never substitute an existing archive.
2Wiki runtime inputs are local SHA-pinned specifications under
`/private/tmp/oct26-reliable-2026-10-26-v1/twowiki-{development,heldout}/local/`.
The original train/dev selection and dataset revision remain unchanged. No new
held-out nomination or optimization was performed during materialization.

Runtime guards require the exact clean commit in `EXECUTION_MANIFEST.json`.
After merging the PR, the existing feature worktree can still execute its pinned
release commit. Do not pull, switch branches or edit tracked files mid-run.
If running from the new merge commit instead, create new execution freezes under
a new external namespace before inference, retaining scientific rules, dataset/
cohort pins and model hashes. Never edit the old frozen protocol or bypass the
clean-Git guard to accommodate a different commit.

## Recommended sequence

1. Archive the small release manifest/protocols and raw datasets/results to durable
   storage. `/private/tmp` is a local working location, not public deposition.
2. Obtain safe disk headroom and ensure no unrelated GPU workload is running.
3. Run a separately approved bounded development smoke for the **new** reliability
   path. The prior 211-call transfer smoke predates these reliability changes.
4. Start 2Wiki construction first. Complete and validate all 12 construction cells
   before any Dense/RCD evaluation. Review construction accounting, not outcomes,
   to estimate the actual remaining cost.
5. Run matched 2Wiki evaluation, assemble every ID, then aggregate/revalidate.
6. Construct all transfer candidates. If `C` candidate records are valid and `U`
   query/cell records have any valid candidate, the uncached remaining calls are
   `4*C` for source screening and `40*U` for final QA.
7. Screen using each source alone, seal every source selection, then evaluate all
   target arms. Zero source successes never permits skipping target evaluation.
8. Validate complete outputs and query-cluster uncertainty before interpretation.
   Do not modify construction based on final Dense/RCD or other target outcomes.

## Exact full-run commands (prepared, not executed)

From the clean pinned worktree, **only after explicit full-compute approval**:

```bash
cd /private/tmp/rag-oct26-execution-reliability
OCT26_FULL_RUN_APPROVAL=twowiki /bin/sh docs/OCT26_FULL_COMMANDS.sh
```

After 2Wiki is validated and transfer compute is separately authorized:

```bash
OCT26_FULL_RUN_APPROVAL=transfer /bin/sh docs/OCT26_FULL_COMMANDS.sh
```

The [command worksheet](OCT26_FULL_COMMANDS.sh) reads the actual protocol hashes
and planned output paths from the manifest and verifies the clean source commit.
Both workflows run offline from local inputs and pinned snapshots. It uses a
12-new-batch allowance per invocation by default. Exit **75** is a deliberate
pause: repeat the **same command**, protocol, directory and source commit until
completion. No generation is repeated for completed checkpoints. To use a smaller
job allowance:

```bash
OCT26_MAX_BATCHES=1 OCT26_FULL_RUN_APPROVAL=twowiki /bin/sh docs/OCT26_FULL_COMMANDS.sh
```

A new evaluation batch is one pipeline and at most 25 population IDs; both QA
conditions are checkpointed together. Full condition corpora are retained for
all batches. Separate arm jobs do not change final pairing or bootstrap units.
Construction and screening also pause at their completed 25-query boundaries.
The script advances stages only when the preceding stage returns complete and
its seal exists. It revalidates an existing aggregate rather than overwriting or
trusting it. Do not change these commands to filter cells/queries or resample.

Any error other than a planned pause stops the worksheet. In particular, a saved
intent without a response is **not** retry permission. Preserve that directory
and investigate; do not delete the intent, change the seed or increment a budget.
Recovery at completed checkpoints is supported; recovery of unknowable model
outputs requires a separately recorded incident decision. Do not relabel such
infrastructure errors as construction failure or defense success.

## Bounded smoke commands

The external release manifest includes a prepared development-only command sheet:

```bash
RUN_RELIABILITY_SMOKE=twowiki /bin/sh /private/tmp/oct26-reliable-release-2026-10-26-v1/SMOKE_COMMANDS.sh
RUN_RELIABILITY_SMOKE=transfer /bin/sh /private/tmp/oct26-reliable-release-2026-10-26-v1/SMOKE_COMMANDS.sh
```

These commands require separate approval and were not executed. Transfer's maximum
is 220 backend calls without cache hits, 150 with all planned identical clean hits;
2Wiki's corresponding limits are 20 and 16. Typed failures can reduce the calls.
Passing fixture tests does not certify new real-model outputs.

## Compute and storage planning

The original full transfer proposal permits 208,800 calls in its all-valid
mechanical bound. The unchanged selector supports 135/300 HotpotQA queries, while
retaining all 300 in the population. With three available candidates everywhere,
its coverage-aware bound is 93,960 calls without cache savings. Exact clean hits
reduce the projection to 62,235 calls, approximately **57.4 model-hours** at prior
development-smoke rates; misses can increase it toward the uncached bound.
The all-valid 2Wiki projection is 21,600 calls without hits, or 15,000 with planned
clean hits, approximately **14.9 model-hours** at those proxy rates. No reliable
2Wiki-specific runtime or held-out coverage estimate has been measured.

These are model-time projections, not wall-time limits. Index rebuilding, model
loads, repeated validation, job restarts, thermal effects and memory pressure add
time. Batch checkpoint/cache records also increase disk use beyond previous
artifact estimates. Persistent embedding/index caching is not implemented.
Small job allowances rebuild indexes more frequently; 12 batches amortize this.

The current 16 GB machine passed software checks and the older diagnostic smoke,
but peak RAM for full reliable execution is unmeasured. The new code streams
model hashes, serializes cooperating MLX processes, and releases unused allocator
buffers between conditions. It does not control other applications. Approximately
30 GiB free disk is a recommended margin, not a validated software minimum; the
observed 8–10 GiB headroom remains a practical risk. No old results were deleted
or moved to obtain space. Atomic publication requires appropriate filesystem
hard-link/fsync support; unsupported filesystems fail rather than overwrite.

## HotpotQA archive note

Release verification found eight extra `.DS_Store` files in the archived result
directories. All 17,214 sealed files still match; none is missing. The original
strict inventory check correctly fails on those unsealed extras. A separate
manifest-exact copy was used for numerical reverification without cleaning the
archive. See [the verification receipt](../reports/OCT26_RESULTS_REVERIFICATION.json)
and [audit addendum](../reports/WEEK9_HOTPOTQA_SCIENTIFIC_AUDIT_2026-10-26.md).
Do not suppress inventory checks or rewrite a historical seal to hide extras.
