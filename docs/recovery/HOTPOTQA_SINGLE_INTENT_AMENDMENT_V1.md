# Proposed one-intent HotpotQA transfer recovery amendment

Status: reviewed recovery implementation and offline tests. Final pre-execution
preparation authorizes a local commit and clean-executor amendment only. **No
replacement inference, receipt publication, experiment resume, push or merge is authorized.**
The helper is on `recovery/hotpotqa-single-intent-amendment` in
`/private/tmp/rag-hotpotqa-single-intent-recovery`, based on `ade475d`.
The frozen execution checkout is unchanged and clean at that original commit.

## Exact scope and parent evidence

Only request fingerprint
`dec08535d5e02ffaa9838f4f35ca3061c3c7b530d550a3c90c4ddda31e22f9ec`
is eligible. There is no CLI override to select another incident. The recovery namespace is
also fixed in the incident allowlist; a new namespace cannot be used to obtain
another automatic attempt after interruption.

- Parent protocol SHA-256:
  `510155bcb15dab07f63d217b66575d8dfd403a7d05b21d0e7cd65b93badd13c8`.
- Original intent SHA-256:
  `0515674a780eee590a8b7a28fa4c33a8cb5cb882ebf3e9ca0874697c3294b64e`.
- Prompt SHA-256:
  `14b32c98142216948f55cfc73a18d8552d83770b83da0615842fc693348e5641`.
- Candidate-stage forensic inventory fingerprint:
  `0ab4403df576b858395c0638f07ad91e8cad123e8e180e33ebd05703e04a863d`.
  This binds all 9,963 existing files, including 7,386 query/candidate checkpoints
  and 1,275 completed response pairs. The plan embeds the complete hash inventory.
- Query `5abc17555542993a06baf858`, semantic intensity 1, poison seed 44,
  candidate band 0, document index 0, journal index 00.
- Exact derived runtime seed: **3215750484**.
- Generator: local `mlx-community/Qwen2.5-7B-Instruct-4bit`, snapshot
  `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`; greedy temperature zero,
  maximum 150 tokens, original chat formatter and frozen dependencies.

The original intent remains unchanged and its physical execution is **indeterminate**.
It is not marked as a confirmed failed generation. Terminal closure is consistent
with the missing response, but does not establish whether the backend started,
finished or returned before publication was interrupted. No exact saved response
was found. Historical same-prompt responses have a different protocol/runtime seed
and are not valid restoration sources.

## Execution-contract change and scientific limits

This is an explicit exception to `unresolved_intent: halt-no-regeneration`, not a
claim that the original execution contract is unchanged. The original protocol file
and SHA stay untouched; the exception is a separately pinned amendment.

At most **one** additional physical recovery dispatch is permitted. Logical quality
attempts remain at the original maximum of two for this document. The replacement
fills the logical first-attempt slot without claiming to be the lost physical call.
If that returned text is rejected, the original runner may still use its normal
second, revision-prompt attempt after a separately authorized experiment resume.
Thus this document can have up to **three physical dispatches conservatively**:
one original indeterminate, one replacement, one ordinary logical quality retry.
This is why the additional allowance must be disclosed rather than called a free retry.

The previously derived semantic-construction upper bound becomes 7,585 rather than
7,584; the uncached full-study availability bound becomes 87,553 rather than 87,552.
The protocol's generic 208,800 ceiling is not edited. No other incident receives an
exception. A further interruption requires a new explicit decision, not an automatic
second recovery or a fresh namespace that hides an unknown call.

Targets, question/gold/doc IDs, source-only selection, models, prompts, seeds, retry
instructions, RCD and denominators remain unchanged. No output is selected for its
favorability and no source/target final result is used to decide recovery. This
preserves the declared logical construction method while changing physical-call
accounting. It cannot recover the lost output, prove bitwise equivalence to an
uninterrupted run, or establish scientific/factual validity. Any completed study
must disclose this single amended execution. If strict adherence requires zero
additional physical dispatches, this amendment must not be used.

## Mechanism and files

New code only:

1. `src/experiments/single_intent_recovery.py`: fixed incident allowlist, full protected
   inventory, plan/source bindings, one-dispatch journal, explicit publication and
   amended physical accounting. Does not modify the original guard or generator.
2. `scripts/recover_hotpotqa_single_intent.py`: `prepare`, `execute`, `publish`, `verify`.
   The internal worker loads scientific generation code from the original clean
   `ade475d` checkout. It checks frozen dependencies and complete model-file hashes
   before any recovery intent is written. Model loading occurs only in an explicitly
   approved worker execution, never in preparation, verification or publication.
3. `tests/test_single_intent_recovery.py`: synthetic backends and synthetic incident
   policies only, with no real authorizations or experimental outputs.

Preparation writes a proposed amendment outside the original experiment and both
code checkouts. No original file is touched. The retained initial offline draft is
`/private/tmp/hotpotqa-transfer-recovery-proposal-v1/amendment.draft.final.json`.
Its SHA-256 is
`76bc1859427e3c9ec216babe33fb35342862527e86cfdfaa4abc614dfb8060ce`.
All draft files are historical planning artifacts and must not be executed.
The initial draft binds the helper bytes but is deliberately non-executable because
its executor was uncommitted. Final pre-execution preparation commits the reviewed
helper locally and writes `/private/tmp/hotpotqa-transfer-recovery-proposal-v1/amendment.reviewed.json`.
Its exact clean-executor commit and SHA are recorded in the external final preparation
report; embedding that future SHA in this same commit would be circular.
A clean plan still requires explicit user approval before any execution or publication.

Future physical outputs live only in the fresh namespace
`/private/tmp/hotpotqa-transfer-single-intent-recovery-v1/`:

- `replacement.intent.json`: separately identifies `replacement-1`, original status
  indeterminate, exact frozen request, runtime seed, amendment pin and executor provenance.
- `replacement.response.json`: actual future capture, raw/effective prompt, tokens,
  elapsed time, content hashes and explicit physical-call accounting.
- `replacement.error.json`, if an exception is observed: evidence of an exception,
  not an inferred statement that the backend completed or did not execute.

If an intent exists without a response, an error exists, or an unpublished atomic
file remains, the helper refuses another dispatch. A saved complete response can be
replayed without a backend call. The original candidate writer lock and cooperating
model lease prevent concurrent writers/model dispatch. No output is overwritten.

### Separate explicit publication, not an original response

`execute` never publishes into the experiment. After a successful capture, a future
explicit `publish` operation may create the previously absent original-path
`00.response.json` as a **clearly tagged logical resolution receipt**. It carries
`is_original_response: false`, original status indeterminate, the amendment SHA,
external replacement path/hash, actual captured generation and accounting. This is
not the original uninterrupted response. The original intent and every pre-existing
checkpoint/response remain byte-identical. An already existing differing response
always causes refusal, even if its text looks plausible.

The receipt is compatible with the unchanged original reader and becomes hash-bound
by the later candidate-library seal. Required audit evidence includes BOTH the
parent execution artifacts and the external amendment/recovery bundle. Verification
checks the protected original inventory, recovery evidence and receipt, and retains
the original store guard for any unrelated later missing response.

Publication is an integrity operation, not an opportunity to discard an unfavorable
replacement. There is only one candidate replacement. Do not regenerate, cherry-pick
or manually change semantic rejection outcomes. The original attack validator decides
whether it is a valid poison when the original runner is separately resumed.

### Physical accounting

The resolution receipt reports `backend_call_executed: false`: publishing/replaying
it performs no inference. The actual separate recovery response is counted once.
Final incident accounting must add the external replacement to base-stage actual calls
and keep the original indeterminate dispatch separate. Immediately after successful
recovery, before any subsequent experiment work, expected accounting is:

- 1,275 original completed response pairs (confirmed recorded completions).
- One separately completed replacement, yielding 1,276 recorded completions.
- One original indeterminate dispatch: conservative consumed count 1,277, not a claim
  that all 1,277 are confirmed completed backend calls.

Do not sum mirrored receipt and replacement as two successful model calls, and do not
hide the indeterminate dispatch. `verify` emits this amended accounting explicitly.
Cache timings are not invented; replacement timing comes from the actual capture.

## Future execution plan — NOT AUTHORIZED BY THIS DOCUMENT

1. Review the code, diff and offline results. Commit the reviewed helper on its own
   branch, leaving the original `ade475d` execution worktree unchanged. No push is
   needed to satisfy this local gate; pushing remains a separate decision.
2. Confirm no original runner is active and no model job competes for memory.
3. Prepare a fresh clean-executor amendment using the command below. Archive the
   full parent inventory and amendment to durable storage. Do not edit the draft
   into an approval. Submit the new exact plan SHA for explicit execution approval.
4. Only after approval for one physical replacement, execute the worker once. It
   rechecks source, helper, parent, protocol, model and environment bindings first.
5. If a response is safely committed, explicitly approve/publish the labeled receipt
   after integrity checks, regardless of whether its poison text is favorable.
   If recovery is interrupted, stop without another attempt.
6. Verify the resolution and amended accounting. Normal experiment resume requires
   a separate explicit authorization; no resume is performed by this helper.

Command sequence by stage. Preparation is metadata-only and is performed once
during final pre-execution preparation. Do not rerun `prepare` over an existing plan.
The exact future execution/verification commands with the resulting literal SHA are
provided in the external final preparation report. The model and publication stages
below remain unexecuted and require explicit approval:

```bash
set -e
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
HELPER=/private/tmp/rag-hotpotqa-single-intent-recovery/scripts/recover_hotpotqa_single_intent.py
PLAN=/private/tmp/hotpotqa-transfer-recovery-proposal-v1/amendment.reviewed.json
RECOVERY=/private/tmp/hotpotqa-transfer-single-intent-recovery-v1
REQUEST=dec08535d5e02ffaa9838f4f35ca3061c3c7b530d550a3c90c4ddda31e22f9ec
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
# Metadata only; run after committing the reviewed helper, not by editing the old draft.
"$PY" "$HELPER" prepare --output "$PLAN" --recovery-dir "$RECOVERY"
PLAN_SHA=$(shasum -a 256 "$PLAN" | cut -d ' ' -f 1)
# STOP: obtain explicit approval of PLAN_SHA and the one-extra-physical-call allowance.
# The following commands are a future plan, not authorization to execute them now.
"$PY" "$HELPER" execute --plan "$PLAN" --plan-sha256 "$PLAN_SHA" \
  --approve-request-fingerprint "$REQUEST" --extra-physical-call-allowance 1
# STOP on error/indeterminate state; no retry or new recovery namespace.
# This distinct operation creates a labeled resolution receipt, not an original response.
"$PY" "$HELPER" publish --plan "$PLAN" --plan-sha256 "$PLAN_SHA" \
  --approve-request-fingerprint "$REQUEST" --extra-physical-call-allowance 1
"$PY" "$HELPER" verify --plan "$PLAN" --plan-sha256 "$PLAN_SHA"
# No FULL_TRANSFER_COMMANDS.sh invocation is included: normal resume is not authorized.
```

The CLI opt-in flags record an operator action; they are not authenticated human
identity, a signature, independent factual review or supervisor sign-off. Actual
user authorization must precede their use. Synthetic test policies/flags do not
constitute any production approval.

## Offline verification

| Check | Result |
| --- | --- |
| New recovery cases (included in focused run) | 32 passed |
| Final focused recovery/reliability/transfer tests | 57 passed, 0 failed, 0 skipped (5.13 seconds) |
| Full offline suite | 1,244 passed, 0 failed, 0 skipped (128.86 seconds) |
| Python compilation, source/new-file whitespace | PASS |
| Future shell command syntax | PASS; not executed |
| Production model calls / recovery dispatches / publications / resumes | 0 / 0 / 0 / 0 |

The tests use synthetic incident policies, source bindings and backend outputs.
They cover authorization, unrelated intents and namespaces, source/model-input
provenance, conflict refusal, physical-call accounting, interrupted recovery,
completed-response replay, labeled publication, the unchanged legacy reader and
checkpoint integrity. They do not establish scientific or numerical equivalence
of the lost response to any future replacement.

Logs: `/private/tmp/hotpotqa-single-intent-recovery-new-final-v2.log`,
`/private/tmp/hotpotqa-single-intent-recovery-focused-release.log`,
`/private/tmp/hotpotqa-single-intent-recovery-full-final-v2.log`.
The full offline suite had permitted access to existing local cache locks; there
were no unresolved environmental test failures. An earlier new-file whitespace
check found one extra blank line at EOF; it was removed and checks rerun.

Production metadata-only preparation rechecked the exact protected parent inventory.
The original protocol, intent, 7,386 checkpoints and 1,275 completed response pairs
remain unchanged. The 17,214 original Week 9–10 sealed construction/evaluation files
also passed hash verification. The original `00.response.json` and the production
recovery directory remain absent. Default legacy resume still fails closed.

The implementation diff and final integrity record are in
`/private/tmp/hotpotqa-transfer-recovery-proposal-v1/implementation.patch` and
`/private/tmp/hotpotqa-transfer-recovery-proposal-v1/offline_integrity_report.final.json`.
The initial implementation milestone performed no inference, recovery, publication,
experiment resume, commit or push. Final pre-execution preparation adds only a
reviewed local commit, a fresh clean-executor plan, and repeated offline checks.
No compute, publication, resume, push or merge is authorized by preparation.

## Final pre-execution preparation

The four files were compared against the original implementation diff and offline
integrity report before review. No recovery source changes were required. The full
offline suite, compilation, whitespace and protected artifact checks are repeated
before the authorized local commit. Exact rerun outcomes, commit, clean-plan SHA and
future commands are recorded outside the experiment in
`/private/tmp/hotpotqa-transfer-recovery-proposal-v1/FINAL_PREEXECUTION_REPORT.md`.
The frozen scientific checkout remains unchanged at `ade475d`.
