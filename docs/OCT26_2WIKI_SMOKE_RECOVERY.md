# October 26 2Wiki development smoke incident and recovery

This is an implementation review, not authorization to run another diagnostic.
No model inference was performed during this investigation. Existing experiment
files, protocols and checkpoints must remain unchanged. Do not delete an intent,
copy a response from another execution, mark the unknown call as failed, or restart
the failed namespace. No commit or push is authorized before review of these changes.

## Observed incident

Parent protocol:
`/private/tmp/oct26-reliable-release-2026-10-26-v1/twowiki-development/protocol.json`

SHA-256:
`a8c7bcee0d01ff33cbb07eb41569076b1dd67e1416504155a0527b9b4899d80b`

Failed construction root: the protocol directory's `execution/construction/`.
Its observed inventory fingerprint is
`ba6e758191cfc5a5085ab89f261211d7413f48d0c1a7bee174f31323a935fb1f`.

| Observation | Finding |
| --- | --- |
| Scope | Two published-train development queries; both families, intensity 1, seed 42 |
| Query IDs | `69b461880bdc11eba7f7acde48001122`, `0e37823b099611ebbdb0ac1f6bf848b6` |
| Semantic intents | 3: 2 with completed responses, 1 unresolved; no recorded error response |
| Query checkpoints | 3/4: both lexical valid; first semantic exhausted its two recorded attempts; second semantic absent |
| Global construction seal | Absent; evaluation is not permitted |
| Active runner | No matching protocol/transfer Python runner observed during inspection |
| Interrupted query | `0e37823b099611ebbdb0ac1f6bf848b6` |
| Directory key | `271878b0581f68d6f1138efe0536c2091d9e0db1cac6784048f8c5789d7b2dc3` |
| Intent filesystem mtime | 2026-10-26 20:53:12.746189 +05:30 (15:23:12.746189 UTC); not an authenticated execution timestamp |
| Prompt SHA-256 | `daf9cad683bf2e3dfe42479595fd166e6d5b616dc43bea11a2fa2397a91066fb` |
| Model revision | `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed` |
| Generation limit | 150 completion tokens per semantic attempt |

**Root cause remains undetermined.** The surviving intent proves request publication,
not that backend execution started or completed. There is no demonstrated MLX/Python
crash, OOM, or protocol-budget exhaustion for the interrupted query. No failure cause
should be inferred from its missing response. Current free disk space cannot establish
historical resource availability.

## Audited generation path and independent defects

1. `construct()` loads pinned inputs, checks the construction plan and iterates frozen
   cell/query checkpoints. Semantic construction uses `JournalGenerator`.
2. `JournalGenerator.generate()` publishes the intent before `capture_generation()`.
   Capture calls the MLX backend, then extracts the answer and records timing, tokens,
   prompt and effective backend prompt.
3. `MLXGenerator.generate()` templates the prompt, calls MLX, then accounts for tokens.
   An interruption anywhere before durable response publication leaves an unknown call.
4. An ordinary `Exception` in capture is recorded as an error and re-raised. Process
   termination, `KeyboardInterrupt` or `SystemExit`, or response-publication failure
   can leave only the intent. This is a possible mechanism, not a diagnosis.
5. `SemanticFluent.generate()` retries only its predefined semantic-quality rejection,
   within the existing two-attempt limit. Unexpected exceptions propagate. The restart
   refusal is expected fail-closed behavior, not evidence of the original cause.

File/line references for this proposed working tree: `scripts/run_week9_protocol_poison_matrix.py:209` (journal), `:237` (new response hash), `:297` (construction), `:315` (early prior-journal scan); `src/evaluation/qa_records.py:36` (capture); `src/pipelines/generator.py:73` (MLX call and token accounting); `src/attacks/semantic_fluent.py:293` (quality-only retries); `src/experiments/execution_reliability.py:96` (store scan) and `:156` (QA journal).

Two independently reproduced defects were found using synthetic journals only:

- **Completed-response replay validation gap:** the legacy construction journal returned
  changed response text without validating its saved measurement. Later validation could
  catch it, but replay could reach semantic validation first. Replay now validates the
  QA record, exact prompt and, when present, its content fingerprint. New responses store
  that fingerprint. Existing hashless responses remain readable with structural checks;
  no claim of authenticated historical content is made.
- **Orphan response could trigger an extra call:** a response without its intent previously
  allowed a new intent and backend call before no-overwrite response publication failed.
  Both journal implementations now refuse an orphan before any generation. This defect
  is not present in the observed incident, which has the opposite missing-file pattern.

Construction now scans prior journals before loading a model or nominating a target.
Unknown, error, inconsistent, orphaned or corrupt prior calls block execution. None of
these changes modifies target rules, retry counts, RCD, seeds or metrics. Journal hashes
are integrity checks, not signatures or independent factual verification.

## Read-only incident diagnostic

From `/private/tmp/rag-oct26-execution-reliability`:

```sh
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
PARENT=/private/tmp/oct26-reliable-release-2026-10-26-v1/twowiki-development/protocol.json
PARENT_SHA=a8c7bcee0d01ff33cbb07eb41569076b1dd67e1416504155a0527b9b4899d80b
FAILED=/private/tmp/oct26-reliable-release-2026-10-26-v1/twowiki-development/execution/construction
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  "$PY" scripts/audit_2wiki_smoke_incident.py \
  --protocol "$PARENT" --protocol-sha256 "$PARENT_SHA" --construction-dir "$FAILED"
```

The tool emits `rag-poison-transfer.generation-incident-diagnostics/v1` JSON to
stdout only. It reports unmatched intents, completed/error/invalid/orphan responses,
query identities, file/request/prompt/model/provenance hashes, missing checkpoints,
plan consistency and seal presence. It neither invokes a backend nor repairs anything.
Checkpoint completeness here is a structural inventory, not full scientific seal
validation. File hashes are observations, not authenticated evidence of authorship.
Run against an inactive namespace to avoid a moving snapshot. Do not redirect output
into the incident namespace.

## Separately approved fresh diagnostic: metadata preparation

First review these changes and offline tests. Only after authorization to commit,
create a clean reviewed code commit. The old protocol intentionally cannot run against
changed source. Do not bypass the code provenance guard or edit its frozen source field.

The helper below can first be run **without `--freeze`** for a read-only plan. It
validates the pinned parent, exact two IDs, published train split/revision, both families,
intensity 1, seed 42, unchanged rules/config/input fingerprints and model snapshot bytes.
It exposes no scope or matrix override. Existing, nested or repository output namespaces
are refused. Model-file hashing does not load a model.

```sh
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
NEW=/private/tmp/oct26-2wiki-development-recovery-v1
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  "$PY" scripts/prepare_2wiki_recovery_smoke.py \
  --parent-protocol "$PARENT" --parent-protocol-sha256 "$PARENT_SHA" \
  --failed-construction-dir "$FAILED" --new-namespace "$NEW" --model-snapshot "$MODEL"
```

After review and a clean authorized commit, append `--freeze` to that command to create
metadata only. This is a new execution protocol with new code provenance and output paths,
plus an incident reference. Scientific fields `binding`, `rules`, `model` and `execution`
must exactly equal the parent. The failed parent is retained, not resumed or completed.
New files are `$NEW/protocol.json` and `$NEW/incident_reference.json`.
The helper is additive tooling; the scientific frozen protocol/version is unchanged.

## Fresh execution: requires separate explicit compute approval

Approval must name the new namespace and the additional diagnostic call budget: at most
**20 calls without cache savings**, or 16 with all planned exact-input clean hits. Typed
construction failures can reduce actual calls. The unresolved original call remains
unknown and is not erased from total compute accounting. New namespace creation is not
a way to silently extend the old retry budget. Report both attempts; do not select a
favorable diagnostic as a research result. No held-out/full run is authorized.

Only after that approval, with the newly frozen protocol, run these stages separately:

```sh
P="$NEW/protocol.json"
P_SHA=$(shasum -a 256 "$P" | cut -d ' ' -f 1)
C="$NEW/execution/construction"
E="$NEW/execution/evaluation"
# Scope is read from the pinned protocol, not this CLI's default scope option.
# The preparation helper must have frozen this exact two-query development protocol.
"$PY" -c 'import json,sys; from scripts.prepare_2wiki_recovery_smoke import validate_development_parent; validate_development_parent(json.load(open(sys.argv[1])))' "$P"
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 "$PY" scripts/run_week9_protocol_poison_matrix.py construct \
  --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" \
  --construction-dir "$C" --max-batches 1
```

Each batch limit counts cell batches. Repeat the same construction command only after a
normal batch pause with complete responses; an unresolved/error journal must stop further
execution, never be regenerated. Inspect diagnostics after construction. Only after the
global seal exists, verify its hash and evaluate:

```sh
C_SHA=$(shasum -a 256 "$C/construction.seal.json" | cut -d ' ' -f 1)
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 "$PY" scripts/run_week9_protocol_poison_matrix.py evaluate \
  --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" \
  --construction-dir "$C" --construction-seal-sha256 "$C_SHA" \
  --evaluation-dir "$E" --max-batches 1
```

Resume evaluation only after normal batch pauses; preserve its journals. After completion:

```sh
E_SHA=$(shasum -a 256 "$E/evaluation.complete.json" | cut -d ' ' -f 1)
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 "$PY" scripts/run_week9_protocol_poison_matrix.py aggregate \
  --protocol "$P" --protocol-sha256 "$P_SHA" --construction-dir "$C" \
  --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E" \
  --evaluation-completion-sha256 "$E_SHA" --output "$NEW/execution/aggregate.json"
```

Verify the actual completion filename against runner output before hashing. Neither a
metadata freeze nor software tests establish MLX runtime reliability or semantic validity.
The original interruption mechanism, 16 GB memory pressure and future disk availability
remain risks. Run one cooperating model process at a time. Full experiments remain gated.

## Offline verification completed in this working tree

- New recovery tests plus frozen-construction regression tests: **46 passed**.
- Final full offline pytest: **1051 passed in 111.89 seconds**;
  log `/private/tmp/oct26-smoke-recovery-full-tests-final.log`.
- The first full run had **1048 passed, 1 failed**: the old tampering fixture reached
  the new content-integrity check before its expected sealed-attempt comparison.
  The fixture now recomputes its synthetic journal hash to exercise that independent
  comparison; separate new tests reject invalid hashes. Two further recovery tests
  were added before the final full run.
- `compileall -q src scripts tests`: passed, with bytecode directed to the external
  `/private/tmp/oct26-smoke-recovery-pycache` directory.
- `git diff --check`: passed.
- Actual incident diagnostic: 2 completed responses, 1 unresolved intent, no errors,
  3/4 terminal checkpoints, no construction seal; recorded provenance references match.
- Actual fresh-smoke preparation **without `--freeze`**: passed exact development
  binding and model-file checks; zero model calls and no new namespace/files created.
- All 10 original construction files retain their pre-investigation SHA-256 hashes.

No MLX inference, fresh protocol freeze, full experiment, commit or push was performed.
The fixes and instructions await review. Runtime reliability and the cause of the
original interruption remain unverified; software tests do not establish either.
