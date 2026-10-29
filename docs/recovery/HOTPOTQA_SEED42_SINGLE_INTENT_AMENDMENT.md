# Seed-42 single-intent recovery amendment

Implementation and synthetic testing only. No production proposal, model call,
publication, supervisor dry-run, or resume is authorized by this document or was
performed as part of implementation. Execute and publish each require a separate
future human decision; resumption requires another explicit compute decision.

## Incident and forensic baseline

The read-only audit on 2026-10-29 found exactly 375 intents, 374 responses,
one unresolved intent and no orphan responses in:

`/Users/sadiapeerzada/Documents/rag-research-results/hotpotqa-transfer-20261028/transfer/execution/candidates`

The relative unresolved path is:

```text
calls/semantic_fluent_false_evidence.intensity-1.seed-42/1/236491dc1eb4b16c9723a7fc93ff1394577a5455e3e155415bb0c1594539a55a/01.intent.json
```

| Binding | Exact value |
| --- | --- |
| Protocol SHA-256 | `94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa` |
| Intent SHA-256 | `8765ff8b160155529aa75d89385e96357adae7b5663b85768dbb7fcdd8e7769f` |
| Canonical request fingerprint | `6fca4964d2548ff495909c4e47a1233836cd6099d148c9b034099d86735e6c76` |
| Inventory fingerprint | `747657ff5d89a088ce7dcff92910bd3b8230f3343e49e4f6b97acf1fc3b08561` |
| Frozen source commit | `9a937afbd94b5a46394b5724a6be2d571d2e0c19` |
| Frozen code fingerprint | `80844d1935d3524bd20c1929ed2f7627a8ef212730c5c657ea8c7d572f72f704` |
| Query | `5add74b75542992200553b24` |
| Family / intensity / seed / band / attempt | `semantic_fluent_false_evidence / 1 / 42 / 1 / 01` |
| Construction runtime seed | `94494956` |
| Model | `mlx-community/Qwen2.5-7B-Instruct-4bit` |
| Revision | `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed` |
| Maximum tokens | `150` |

The inventory binds all 6,709 candidate-store files, including 5,939 query
checkpoints and 19 ledgers. The affected band-1 query checkpoint is absent in the
actual `query-checkpoints/<cell>/1/<query-sha256>.json` namespace. Checkpoints for
this query in other cells/bands are distinct completed work.

The evidence backup remains at:
`/Users/sadiapeerzada/Documents/rag-research-results/recovery-evidence/unresolved-call-20261029T135409Z`.
Its three files matched their originals byte-for-byte during the audit. No model
inference, crash, power loss or inference completion is established by the missing
response. The original physical call has **indeterminate** completion status.

The seed-44 helper, CLI, tests and authorization remain unchanged. This amendment
never rebinds its global `INCIDENT`; it shares only its hash/inventory/path/JSON
primitives. The new controller has no CLI overrides for incident, protocol,
candidates, source, model, runtime seed or replacement namespace.

## Contract and durable accounting

The frozen scientific checkout and protocol are untouched. This is a disclosed
exception to its physical execution contract, not a claim of uninterrupted-run
identity or numerical equivalence. Logical target selection, prompts, population,
quality-attempt limit and metrics remain frozen.

The separate durable amendment root is:

`/Users/sadiapeerzada/Documents/rag-recovery-amendments/hotpotqa-seed42-v1`

It is outside research results and code checkouts. The proposal is `amendment.json`;
the sole replacement namespace is `replacement/`. Archive this complete bundle
with the experiment; do not remove, relocate, edit or restore an earlier version
of it. Its identity and absolute paths are fixed. Deletion or external rollback of
all claim evidence is outside filesystem-based duplicate-call guarantees.

Before dispatch, execution checks the exact proposal, executor commit/cleanliness
and file hashes, protocol, source, environment, local model files, request, and
full original inventory. It checks worker processes and cooperating stage,
supervisor and model locks. It then takes the stage writer lock, revalidates, and
acquires the shared local-model lease before claiming the replacement namespace.
New directory entries and the exclusive replacement intent are fsynced before
backend construction. The worker uses the frozen generator, formatter, explicit
greedy sampler, seed function and QA capture code.

Even an empty namespace or an intent without a response is terminal: another
`execute` is refused. Backend construction failure, KeyboardInterrupt, partial
atomic files and saved successful responses cannot authorize another dispatch.
No automatic retry or fresh-namespace recovery is available. Successful evidence
can be published later without rerunning execute.

Physical accounting is explicitly:

- Original interrupted physical call: one indeterminate call.
- Replacement allowance: maximum one extra physical dispatch.
- Replacement evidence: a separate intent and response, never the original call.
- Additional quality-repair calls: zero. Attempt `01` is the final logical slot
  under the frozen two-attempt limit; there is no new logical attempt `02` for this intensity-1 document.
  Unrelated intensity-3 construction may legitimately use indices `00`–`05`
  across its three documents, retaining two attempts per document.

Immediately after successful recovery, the current baseline would yield 374 base
recorded completions plus one separate replacement completion and one original
indeterminate call: 375 recorded completions, conservative consumed count 376.
These are future expectations, not results of an executed recovery.

## Receipt compatibility and verification boundary

The frozen reader requires `01.response.json`. A future separately approved
publication exclusively creates that previously absent file as a **labeled logical
resolution receipt**, preserving `01.intent.json` and all original files.
It includes:

- `execution.kind: explicit_replacement_resolution` and
  `backend_call_executed: false` (publication itself performs no inference).
- `recovery.is_original_response: false` and original completion `indeterminate`.
- Original intent hash, exact proposal hash, external replacement response path
  and hash, physical accounting and publication approval fields.
- Generation copied exactly from the separately captured replacement response.

This does not fabricate an original generation. The mirror is required for legacy
reader compatibility and must never be reported as the interrupted call's output.
Publication is independent of whether the replacement is scientifically favorable.
No existing response can be overwritten, and publication never edits checkpoints.

The unchanged frozen `validate_store` checks symlinks, atomic debris, checkpoint
data hashes, orphan/missing response pairs, request fingerprints, absence of error,
QA record integrity, prompt equality, optional generation hashes and clean-cache
integrity. The frozen `JournalGenerator` checks exact request equality and response
integrity before replay. **Neither authenticates recovery metadata or verifies the
external replacement evidence.** A structurally valid forged recovery label can
pass those legacy checks. Synthetic tests demonstrate this boundary explicitly.

The external verifier additionally checks the exact incident and paths, proposal
hash, reviewed clean executor binding, frozen source/environment/model bytes,
full protected inventory, exact replacement intent and response schemas, approval
records, hashes, accounting and exact receipt field values. It then runs the
original store validator without exemptions and checks inventory stability.
Later frozen continuation artifacts can be added only in the candidate stage's
known namespaces. Baseline mutations, unknown top-level artifacts, unrelated
receipts, orphan responses and later unresolved intents still fail closed.
The normal supervisor independently retains its checkpoint/ledger population audit.

The updated supervisor requires `--recovery-plan` and `--recovery-plan-sha256`
unconditionally before preflight or even dry-run. It calls the full read-only
verifier before each batch and after the child exits. A receipt or cached
"verified" marker alone cannot open the gate; verification is recomputed every
time. Failed verification prevents launching the next child.

This gate applies to the updated supervisor. Unchanged frozen runners and older
supervisor checkouts cannot acquire new enforcement without changing their code.
An operator must use the reviewed updated supervisor; directly invoking the frozen
runner after publication would bypass this external gate. Do not use the dirty
`/private/tmp/rag-transfer-supervisor` checkout or copy its uncommitted files.
These operational limits are explicit; no frozen code is patched or monkeypatched.
CLI approval flags record operator intent, not cryptographic human authentication.

## Future human procedure — do not run without separate approvals

Use the reviewed clean implementation worktree, at its committed PR revision. If
its commit or bound helper bytes change after preparation, stop and review again;
do not edit the proposal. Repeat process, lock and inventory checks immediately
before any future physical execution. If any evidence differs, stop.

Set these shell variables in a future operator session:

```bash
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
CODE=/private/tmp/rag-seed42-recovery-implementation
HELPER="$CODE/scripts/recover_hotpotqa_seed42_intent.py"
PLAN=/Users/sadiapeerzada/Documents/rag-recovery-amendments/hotpotqa-seed42-v1/amendment.json
REQUEST=6fca4964d2548ff495909c4e47a1233836cd6099d148c9b034099d86735e6c76
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
```

1. **Preparation only**, after reviewing the implementation and clean commit:

```bash
"$PY" -B "$HELPER" prepare --output "$PLAN"
shasum -a 256 "$PLAN"
```

Preparation hashes evidence, checks concurrency and writes only the external
proposal. It does not load a backend, create the replacement namespace or change
the experiment. It refuses an existing replacement namespace or changed baseline.

2. Review the entire proposal, its inventory and displayed exact hash. Obtain
   explicit human approval of that literal proposal hash, `REQUEST`, and **one**
   extra physical call with original completion indeterminate. Set `PLAN_SHA` to
   that approved literal hash; shell assignment does not itself grant approval.

3. Only after execution approval, perform the sole replacement dispatch:

```bash
"$PY" -B "$HELPER" execute --plan "$PLAN" --plan-sha256 "$PLAN_SHA" \
  --approve-request-fingerprint "$REQUEST" --extra-physical-call-allowance 1 \
  --approve-execution
```

Stop after any exception or interruption. Do not rerun execute, remove files,
change namespace or construct a new proposal to obtain another dispatch.

4. Review the saved replacement journal and obtain **separate publication
   approval**. Publication validates that evidence before creating the receipt:

```bash
"$PY" -B "$HELPER" publish --plan "$PLAN" --plan-sha256 "$PLAN_SHA" \
  --approve-request-fingerprint "$REQUEST" --extra-physical-call-allowance 1 \
  --approve-publication
```

5. Verify the entire resolution and store without inference:

```bash
"$PY" -B "$HELPER" verify --plan "$PLAN" --plan-sha256 "$PLAN_SHA"
```

6. Only after successful verification and review, run the updated supervisor's
   dry-run (this also repeats verification):

```bash
"$PY" -B "$CODE/tools/supervise_source_selection_candidates.py" --dry-run \
  --recovery-plan "$PLAN" --recovery-plan-sha256 "$PLAN_SHA"
```

7. Obtain a separate compute/resume approval before one candidate batch:

```bash
"$PY" -B "$CODE/tools/supervise_source_selection_candidates.py" \
  --approve-full-compute --max-batches 1 \
  --recovery-plan "$PLAN" --recovery-plan-sha256 "$PLAN_SHA"
```

No later selection or evaluation stage is authorized by these instructions.
Resumption may create new scientific checkpoints through the frozen runner;
recovery itself never creates or edits them.

## Validation

Tests use temporary directories, fake model files and mocked backend generation.
They cover production authorization constants, each identity binding, physical
allowances, separate approvals, executor cleanliness, source/model mutation,
process and lock refusal, interrupted/duplicate dispatch, journal preservation,
receipt provenance, unrelated corruption and actual supervisor gate ordering.
They also pin the unchanged seed-44 helper, CLI and test file hashes.
No production prepare, execute, publish, verify, dry-run or resume was run during
implementation. Exact test commands and results are reported in the PR and task
completion report; historical seed-44 test results are not seed-42 validation.

Validation commands used the pinned interpreter
`/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python`:

| Command | Result |
| --- | --- |
| `python -m compileall -q run.py src scripts tests` | Passed |
| `python -m compileall -q run.py src scripts tests tools` | Passed |
| `python -B -m pytest -q tests/test_seed42_intent_recovery.py tests/test_single_intent_recovery.py tests/test_source_selection_supervisor.py tests/test_execution_reliability.py tests/test_source_selection_transfer_workflow.py` | 140 passed in 4.21s |
| `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q --tb=short` | 1,332 passed in 205.16s |
| `git diff --check` and staged whitespace check | Passed |

The first sandboxed full-suite run had 1,310 passes and 18 failures, all permission
errors on the existing Hugging Face dataset cache lock. The successful offline
rerun allowed access to that cache lock; no implementation exemption, test skip,
model inference or protected experiment write was used.
