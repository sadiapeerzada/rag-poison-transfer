# Semantic profile integration and pre-execution readiness

Review base: `286161e5b7c7dffc0ed1bbb9063074e220135c2e`, on
`fix/2wiki-development-semantic-quality`, descended from `9811668`.
This follow-up supersedes the earlier audit's statement that runner wiring was absent.
No real-model inference, freeze, commit, push or merge was performed here.

## Profile review and integration

The original V3 prompt, v4 validator and v1 retry defaults remain unchanged. The
previous audit's place-of-death coverage gap and missing literal `yes` remain its
findings; no additional regression or corrupted scientific outcome was demonstrated.
The development recognizer requires a matching question subject, predicate and exact
target. `died in PLACE` is not accepted for unrelated questions/subjects. Binary
support requires the complete corresponding assertion with `Yes,` and both named
subjects. Negations, uncertainty, gold/aliases, disclaimers and unsupported relations
remain fail-closed. Passing means heuristic support, not factual verification.

The new selector is `--semantic-profile`, supported only at `preflight` and
`freeze-protocol`. Choices:

- `legacy-v3-v4/v1`: unchanged V3/v4/v1 behavior; development or held-out scope.
- `question-anchored-development/v1`: V4-development prompt, v5-development
  validator, v2-development feedback; **development scope only**.

Explicit profile freezes use
`rag-poison-transfer.week9-profiled-construction-protocol/v1`, with a
`rag-poison-transfer.semantic-profile/v1` descriptor. It binds the identifier,
prompt/validator/retry versions, sentence format, permitted scopes, 150-token/two-attempt
limits, and SHA-256 hashes of relevant implementation files. Existing unprofiled
protocol schemas and no-selector freeze behavior are retained for compatibility;
their legacy identity remains unambiguous in their frozen rule/version tuple.

The full descriptor is in the protocol, construction plan and each cell manifest.
Each query record and semantic generation intent binds its fingerprint. Global seals
bind all files and the protocol SHA; evaluation rows bind cell fingerprints and the
construction seal; aggregation reports the explicit profile. The protocol also pins
Git commit/code fingerprint, configurations, dataset/cohort, runtime dependencies,
model/tokenizer files and retrieval snapshots through existing checks.

Unknown identifiers, stale descriptor/config/code hashes, rule/version mismatches,
held-out development-profile selection, changed construction plans and cross-profile
journal replay are refused. Later stages cannot override the profile from the CLI.
Replay reconstructs failure-specific prompts and validates actual rejection reasons.
Two attempts remain the limit; infrastructure errors never become quality retries.

The single-sentence format is a substantive protocol change. It may alter retrieval
and attack strength, so it is not scientifically equivalent to the old construction
policy. It is not eligible for the main held-out protocol. Promotion would require
supervisor review, a separately preregistered held-out profile/configuration/version,
and a new freeze before inspecting final outcomes; not simply removing the scope guard.
Negative Boolean answers, broad paraphrases and arbitrary multi-sentence support remain
unsupported by this conservative development grammar.

## Actual runner and overnight readiness audit

Read-only inspection of the existing full **2Wiki** protocol verified:

| Item | Observed implementation/evidence |
| --- | --- |
| Population | 300 unique, fixed held-out IDs; no question/gold text inspected for this readiness audit |
| Dataset | Published 2Wiki `dev`, revision `9823f70484dea525100394220b0ea5184d0eeb7b` |
| Matrix | Two families × intensities 1/3 × poison seeds 42/43/44 = 12 cells |
| Comparison | Dense and composite RCD receive the same sealed poison instance; source-to-target transfer is a different runner |
| MLX | Qwen2.5-7B-Instruct-4bit revision `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`; local weight/config/tokenizer hashes match existing protocol; explicit greedy sampling; semantic cap 150, QA cap 64 |
| RCD | Existing frozen configurations unchanged; query rewrites are deterministic text operations, not additional MLX generation |
| Construction barrier | All 12 cell records and generation journals must validate before global seal; no final retrieval/QA before seal |
| Construction recovery | Atomic query checkpoints plus per-call intent/response journals; completed calls replay; incomplete/error/orphan/corrupt calls halt |
| Evaluation recovery | Local 2Wiki v2 input path selects atomic batches/query checkpoints and exact-input clean cache; every batch retains the complete condition corpus |
| Pairing/failures | All query IDs retained for both arms; failed constructions have no fabricated measurements; zero end-to-end successes, not defense successes |
| Statistics | All-300 end-to-end and valid-construction conditional rates; paired query-cluster bootstrap across repeated poison seeds; 2,000 replicates, seed 20261025, percentile 95% |
| Aggregation | Requires pinned protocol, complete construction seal and evaluation completion hashes; rereads rows, journals, summaries and paired observations |
| Concurrency | One stage writer and one cooperating MLX-process lease; no protection against unrelated applications/processes consuming RAM |

The existing release protocol is
`/private/tmp/oct26-reliable-release-2026-10-26-v1/twowiki-heldout/protocol.json`.
Its file pin and current dependency versions match its release manifest, but it binds
source **`8f49224a79aad762355c809a2a4aee4d448e012f`**, not this checkout.
The completed recovery diagnostic instead binds `9811668`. Neither source binding may
be edited to run newer code. Current uncommitted integration correctly fails the clean
Git guard. A run using integrated code needs approval to commit and a new freeze in
new output paths. Old protocols remain usable only with their exact clean code/env.
No historical protocol, result or execution manifest was changed.

For the generic **HotpotQA** entrypoint, an unprofiled protocol without the local
2Wiki `execution` configuration still uses the older fresh-directory evaluation path;
it does not acquire the new resumable QA-batch implementation merely by selecting a
semantic profile. Do not describe that legacy path as resumable across interrupted QA.
The completed original HotpotQA matrix is preserved and is not an instruction to rerun it.

**Unattended execution is not approved or demonstrated feasible.** Stages are sequential;
no stage starts another implicitly. `--max-batches` pauses normally with exit 75.
The existing `docs/OCT26_FULL_COMMANDS.sh` uses `set -e`, so it stops at such a pause,
rather than autonomously completing every batch. Never use an unconditional retry loop,
relaunch on arbitrary errors, delete intents or increase retries. Resume the exact
stage/pin/path only after a recognized normal pause, with complete journals; unresolved
intent or error response requires incident review. The new code does not add a resource
watchdog, scheduler, wall-clock deadline or new compute authorization.

## Generation workload: implementation-derived bounds, not runtime promises

Let `V` be the total valid query/cell constructions across all 12 cells (`0..3600`).
Let `C` be actual semantic calls (one or two per attempted document; zero if no target).
Let `H` be validated clean-cache hits. Logical QA observations = `4V` (two arms × clean/
poisoned). Total new backend calls = **`C + 4V - H`**, excluding journal replay.

| Stage | 300-query held-out upper count | Two-query development upper count |
| --- | ---: | ---: |
| Lexical construction / target selection | 0 generation calls | 0 |
| Semantic document slots | `300 × 3 seeds × (1+3) = 3600` | `2 × 1 × 1 = 2` |
| Semantic generation, at most two attempts/slot | 7200 | 4 |
| Source screening | 0 in this Dense/RCD runner | 0 |
| QA without clean hits | `300 × 12 × 2 arms × 2 conditions = 14400` | 16 |
| QA with all planned identical clean hits | `7200 poisoned + 600 distinct clean = 7800` | `8 poisoned + 4 clean = 12` |
| Total maximum without cache savings | **21600** | **20** |
| All-valid/two-attempt projection with planned clean hits | **15000** | **16** |

If every semantic slot succeeds on attempt 1, the all-valid projection is 18000 calls
without hits or 11400 with all planned clean hits. These are scenarios, not expected
coverage forecasts. No expected call point estimate is justified without new evidence
on target availability, rejection rate and exact-cache hit rate. Failed constructions
reduce evaluation calls while keeping every query in end-to-end denominators.
The runner does not treat a construction failure as an evaluated defense success.

At batch size 25, the complete construction plan has 144 cell batches; evaluation has
up to 288 arm batches. A semantic construction batch needs at most 50 calls at intensity 1
or 150 at intensity 3; a fully valid QA arm batch needs at most 50 without hits.
These bounds follow the frozen two-attempt budget and do not permit extra retries.

Read-only recovery-journal timing inspection found **12 recorded backend calls**:
4 construction and 8 evaluation, totaling **29.43 seconds** of reported backend latency,
median 2.57 seconds (range 1.69–2.96). This tiny sample had zero valid semantic constructions.
It does not establish throughput for 300 queries, longer contexts, intensity 3, cache hits,
thermal throttling, indexing, memory pressure or repeated batch restarts. Do not extrapolate
it into an overnight completion promise. Model-time excludes embedding/RCD retrieval,
diagnostic retrieval at k=10, snapshot hashing and checkpoint I/O.

The user-described machine has 16 GB unified RAM; no peak-RAM validation was performed
here. The sandbox did not permit a kernel memory-size query. Current disk observation
was approximately **28 GiB free**, below the prior 30 GiB engineering margin. This is a
resource risk, not a scientifically established minimum. Preserve historical artifacts;
do not delete them to gain space. Resolve storage/runtime supervision before full compute.
The known historical 25-query 2Wiki exposure uncertainty remains disclosed and unchanged.

## Exact supported next commands (prepared only)

First review changes/tests and authorize a commit. Freeze requires the resulting clean
reviewed checkout; it is intentionally blocked now. Run no model stage without separate
explicit approval for this namespace and its maximum 20-call budget.

```sh
cd /private/tmp/rag-oct26-execution-reliability
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
SPEC=/private/tmp/oct26-reliable-2026-10-26-v1/twowiki-development/local/replication_inputs.json
SPEC_SHA=8e9467072d97419df69aea0786e28b32c20eaa6fc6342e68ff70b05afe64bba0
PROFILE=question-anchored-development/v1
NEW=/private/tmp/oct26-2wiki-semantic-profile-development-v1

# Metadata only; supported while reviewing dirty code.
"$PY" scripts/run_week9_protocol_poison_matrix.py preflight --scope development \
  --semantic-profile "$PROFILE" --replication-spec "$SPEC" --replication-spec-sha256 "$SPEC_SHA"

# Metadata freeze only, AFTER authorized commit and review; never overwrite a namespace.
test ! -e "$NEW"
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope development \
  --semantic-profile "$PROFILE" --replication-spec "$SPEC" --replication-spec-sha256 "$SPEC_SHA" \
  --model-snapshot "$MODEL" --output "$NEW/protocol.json"
```

Inspect/pin the printed protocol hash and scope/IDs/profile before compute. The next
commands are **only after explicit model-call approval**, not authorized by this report:

```sh
P="$NEW/protocol.json"
P_SHA=$(shasum -a 256 "$P" | cut -d ' ' -f 1)
C="$NEW/execution/construction"
E="$NEW/execution/evaluation"
"$PY" scripts/run_week9_protocol_poison_matrix.py construct \
  --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --construction-dir "$C"
# Stop on any error. Do not compute a seal hash until construction reports complete.
C_SHA=$(shasum -a 256 "$C/construction.seal.json" | cut -d ' ' -f 1)
"$PY" scripts/run_week9_protocol_poison_matrix.py evaluate \
  --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E"
E_SHA=$(shasum -a 256 "$E/evaluation.complete.json" | cut -d ' ' -f 1)
"$PY" scripts/run_week9_protocol_poison_matrix.py aggregate \
  --protocol "$P" --protocol-sha256 "$P_SHA" --construction-dir "$C" \
  --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E" \
  --evaluation-completion-sha256 "$E_SHA" --output "$NEW/execution/aggregate.json"
```

Execute stages individually, checking their status; this worksheet is not a shell retry
or approval mechanism. Later-stage scope comes from the pinned protocol and the profile
cannot be overridden. The unchanged recovery helper preserves identical old scientific
fields and is not the tool for selecting this changed profile.

If retaining the **legacy** 2Wiki held-out design, a new metadata freeze on reviewed
code can use the following, only after authorizing that execution lineage/output path.
This does not launch construction/evaluation:

```sh
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope heldout \
  --semantic-profile legacy-v3-v4/v1 --model-snapshot "$MODEL" \
  --replication-spec /private/tmp/oct26-reliable-2026-10-26-v1/twowiki-heldout/local/replication_inputs.json \
  --replication-spec-sha256 b90fa279b8b31c0426ecd38917eab5058d50f0492b31e291d162b337fac1ee19 \
  --output /private/tmp/oct26-2wiki-legacy-heldout-reviewed-v2/protocol.json
```

Full execution remains blocked pending approvals, resource planning and an appropriate
runtime smoke. Selecting the development profile with `--scope heldout` is deliberately
unsupported. No result tables, README, frozen configuration, selected IDs or RCD behavior
were changed.

## Executed verification and delivery state

- Focused offline suite: **163 passed in 10.64 seconds**. This includes the new
  21-case profile integration suite and existing semantic, recovery, frozen-construction
  and reliable 2Wiki tests. Log: `/private/tmp/oct26-semantic-profile-focused.log`.
- Full offline pytest: **1116 passed in 112.71 seconds**, no failures.
  Log: `/private/tmp/oct26-semantic-profile-full.log`.
- Python compilation (`src scripts tests`): passed, with external bytecode cache
  `/private/tmp/oct26-semantic-profile-pycache`.
- `git diff --check`: passed; runner `--help` lists supported choices and stage flags.
- Actual metadata-only development preflight: exact two train IDs, local input hashes
  and retrieval snapshot bindings verified. No model inference. Clean-source freeze
  precondition was separately checked and correctly refuses the uncommitted checkout.
- Both completed legacy construction cells revalidate against unchanged rules.
  All **64** files in the completed recovery namespace retain their original SHA-256
  hashes. Ordered held-out IDs match the pinned 300-ID cohort manifest; no held-out
  question/gold text was inspected for selection or optimization.
- Model snapshot bytes and current dependency versions match the existing release
  protocol. This does not waive its different source-commit binding.

Files changed in this follow-up:

1. `src/attacks/semantic_profiles.py` — new versioned registry, hashes, scope guard and factory.
2. `src/attacks/semantic_fluent_development.py` — docstrings reflect explicit runner integration;
   no additional validation/prompt semantics changed here.
3. `src/experiments/week9_construction.py` — profile-aware construction, attempt replay and validation.
4. `scripts/run_week9_protocol_poison_matrix.py` — selector, schema, provenance and manifest wiring.
5. `tests/test_semantic_profile_integration.py` — profile selection, version/hash/scope rejection,
   interruption/replay, journal identity, resume refusal, paired evaluation and aggregation tests.
6. `docs/SEMANTIC_PROFILE_INTEGRATION_AND_READINESS.md` — this audit and command worksheet.

No new regressions were confirmed in the reviewed four-file baseline. The missing
explicit runner/profile integration is now implemented and software-tested. Scientific
and runtime limits remain as above. No commit, push, merge, new protocol freeze, MLX
inference or full experimental run was performed. Changes await review and approval.
