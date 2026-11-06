# 2Wiki semantic-quality V3: historical-25 development diagnostic v1

**Decision, 6 November 2026: NO-GO for execution.** The study-specific preparation
is ready for human review. Target/evidence reviews, signed study review, resource
allocation/backup evidence and actual model-call authorization are missing. There
are no new model outputs or experimental results.

Engineering commit `7e471dd3b5f6b9187f6e8b810952f891557eb2ba` was verified and
reviewed; PR #114 merged into main `3feaa6c`. Its original offline suite passed
again: **519 passed in 16.84s**. The preparation branch adds a separate diagnostic
admission contract, an offline packet/freezing tool and synthetic tests. The full
relevant suite including the new tests passed: **540 passed in 16.27s**.

## Study and interpretation

Identifier: `twowiki-semantic-quality-v3-nonprospective-diagnostic/v1`.
This is construction-only development work on previously used material. It is
not fresh, held-out, prospective evidence or independent confirmation. The exact
25 IDs and their order come from the existing `semantic-quality-25/v1` V2
protocol; no new selection, replacement, census or exposure certification occurs.

Available records cannot certify a prospective cohort: exact historical sweep
IDs/revision, deleted and remote exposures, and complete accountable custody are
unresolved. The uncertified registry and its gaps are retained. More IDs outside
known exclusions do not establish nonexposure. The prospective selector and its
custody requirements remain unchanged and NO-GO. This diagnostic does not satisfy
those requirements and cannot authorize the separate frozen 300-query Dense/RCD
replication.

The scientific V3 method is unchanged: supplied evidence-gated false targets,
question-bound grammar, prompts, validator, metrics, explicit greedy sampling,
seed 42, intensities 1/3, two attempts per document and 150 completion tokens per
call. Retain all 25 queries, 50 query/intensity records and 100 document slots.
At most 200 reserved backend calls and 30,000 completion tokens are allowed.
Target abstentions and semantic failures remain in the denominator; partial
constructions are archived and never injected. There is no retrieval, QA or
held-out evaluation stage. Historical V2 outputs are not regenerated or replaced;
a later authorized V3 diagnostic would create new, separately labelled outputs.

## Exact prepared inputs

Local packet (new files, write-once publication):

`~/Documents/rag-research-results/twowiki-v3-nonprospective-diagnostic-v1-20261106-r2/`

Reserved output namespace, currently absent:

`~/Documents/rag-research-results/twowiki-v3-nonprospective-diagnostic-v1-20261106-run01`

| Binding | Exact artifact / requirement |
| --- | --- |
| Historical population | `historical_protocol.json`, byte-identical copy of `twowiki-semantic-quality-25-v2-20261104/protocol.json`; SHA-256 `6ea932386b8ba4e3e544bed55ccb22ea991f589d1311fb138b6baa689557abf8` |
| Original development content | `twowiki-v2-development-recovery-20261103/development_data.json`; SHA-256 `58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43` |
| Diagnostic content | `development_data.json`: exact 25 original query objects in documented order; entire original 1,979-document development corpus, no new source content; explicit train/source metadata |
| Dataset declaration | Salesforce/ContextualBench, 2WikiMultihopQA, train, revision `9823f70484dea525100394220b0ea5184d0eeb7b` |
| Exposure evidence | Exact copy `exposure_registry.uncertified.json`; original SHA-256 `799c87aa83f6cb8ded2a16d0cbf110f35d1512b359d725dd27fa342422a68e65`; gaps and null certification retained |
| Population/receipt | `documented_25.ids.json`, `cohort.reused.json`, `reuse_receipt.json`; explicitly **not** a prospective pre-content freeze |
| Scientific sources | `profile.json` contains all 15 existing V3 source/config pins, unchanged |
| Engineering sources | `packet.index.json` pins the shared driver, journal, preparation/review, MLX/resource modules and diagnostic admission/launcher; new source pins require human engineering review |
| Model | `mlx-community/Qwen2.5-7B-Instruct-4bit`, revision `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`; all nine snapshot files including tokenizer/weights match the historical inventory |
| Runtime | `runtime.proposed.json`: full installed package version inventory, Python 3.13.7; MLX 0.32.2, mlx-lm 0.31.3, NumPy 2.5.2, transformers 5.16.1, tokenizers 0.23.1, psutil 7.2.2 |

The earlier preparation snapshot without the `-r2` suffix is retained unchanged
and superseded for review by this source-pinned packet revision. Neither has
authorization or model results.

`packet.index.json` contains exact paths and SHA-256 values for the generated
inputs. `files.sha256.json` inventories the delivered packet. Model files were
hashed, never loaded. No Dense/RCD embedder or reranker is needed here.

`targets.blank.json` contains 25 ID/query/hash-bound forms; every entry is pending.
`candidate_packet.blank.json` describes an empty candidate/evidence/review record.
There are **zero actual new factual candidate approvals**. Existing AI reviews,
old nominations or V2 successes cannot be promoted to V3 human approvals.

## Human evidence required before freezing

Keep original blank/proposed files unchanged. Save completed intake as
`targets.reviewed.json`, `runtime.reviewed.json`, and then `study_review.signed.json`.
These filenames alone do not establish approval. The following evidence must be
real, attributable and independently checked.

1. **Each of the exact 25 query IDs in `targets.blank.json`:** a human nominator
   supplies candidate(s) or an explicit reason to abstain. A different human
   reviews each actual candidate. Preserve query bytes/hashes and receipt binding.
   Do not replace unsupported queries or change target after generation failure.
2. **Each candidate's factual packet:** pin exact document IDs, character spans
   and quotes including every gold-support document; establish the requested
   referent/relation, entity type/role, gold/alias/date equivalence, corpus-relative
   contradiction, chronology and geographic granularity. Every typed fact needs
   evidence-index citations. Mere non-gold string inequality is insufficient.
   Common facts: `relation_kind`, `referent`, `referent_type`, `target_type`,
   `gold_aliases`, `corpus_gold_answer`. Place answers additionally need gold/target
   granularity; kinship needs compatible roles, target/referent birth and target
   death; birth/death questions need referent birth/death. Unknown evidence means
   abstention. Supplied original queries have no independently certified complete
   alias inventory: do not treat an empty list as proof of completeness. Record
   the alias audit; if required support is missing, abstain. Any proposed content
   enrichment requires its own reviewed version and fresh bindings before calls.
3. **Candidate review records:** actual nominator/reviewer IDs, human type, date
   after the reuse receipt, payload digest, all six review checks, decision,
   substantive evidence-based notes and explicit uncertainty. Rejections and
   uncertainties are retained; no flags may be changed to manufacture approval.
4. **Independent inventory review:** verify the actual cached snapshot, tokenizer,
   complete installed environment and new source pins. Set the real execution
   deadline in `runtime.reviewed.json`; then bind the complete inventory excluding
   `inventory_certification` with `digest(inventory)`. The reviewer supplies their
   actual ID and `complete_model_and_tokenizer_inventory` /
   `complete_environment_inventory` attestations. These are not auto-generated.
5. **Study signatures:** six accountable roles in `study_review.blank.json`:
   responsible researcher, distinct supervisor, independent inventory reviewer,
   target-review custodian, semantic-review custodian and resource operator.
   Other roles may overlap only with disclosed/approved conflicts. Each real
   signature record references a separate hash-pinned retained human approval
   JSON with `signer_id`, `role`, `review_payload_sha256`, `decision: approve` and
   attached signature/custody evidence. The software binds records; it does not
   authenticate a human or cryptographically validate signatures. A custodian must
   verify identity/authenticity externally. No assistant signs for anyone.
6. **Blinded review plan, signed before generation:** name reviewer A, reviewer B,
   adjudicator and private-map custodian, record conflicts/independence and retain
   their signed agreements with the semantic custodian's evidence. A/B must be
   different humans, independent of nomination, with no access to each other's
   judgments or the private map. Adjudication follows both immutable first passes.
   Reuse `pilot_prep/twowiki_semantic_v3/independent_semantic_review_rubric.md`.
   Review every saved output attempt, including rejects and duplicates. Exported
   A/B forms are generated only after actual sealed construction; no forms are
   misrepresented as completed reviews now.
7. **Resource and backup sign-off:** approve the allocation below, nominate the
   operator and record the backup location, capacity, manifest hashes and an
   actual restore verification. The resource/operator evidence must include this
   information and acceptance of boundary-monitoring limits. No backup exists or
   is certified merely because this packet describes one.
8. **Separate current model-call authorization after freeze:** real human identity,
   issue/expiry, manifest/protocol/resource-policy digests, exact run01 namespace,
   construction-only development scope, 200-call envelope and explicit diagnostic
   exposure acknowledgment. `authorization.blank.json` has calls disabled and
   no identity/signature. The responsible authority retains externally pinned
   signed evidence; no authorization is inferred from study signatures or tests.

## Resource proposal — not an allocation or benchmark

The host observation found 16 GiB unified RAM, approximately 3.84 GiB available,
32.6 GiB filesystem free, and normal kernel pressure. The cached model/tokenizer
snapshot is 4,295,887,610 logical bytes (about 4.00 GiB); prepared packet size was
3,353,730 bytes before supplementary reports. These are dated observations, not
capacity reservations. The pressure probe worked outside the managed sandbox;
inside it the kernel query is denied. Execute only where actual telemetry works.

| Resource | Conservative review proposal |
| --- | --- |
| Calls/tokens | 200 reserved calls maximum; <=30,000 completion tokens; no QA calls. For planning only, allow up to 4,096 input tokens/call (819,200 total); actual reviewed prompts/tokenizer lengths must fit the approved memory/context allowance. This is not a new prompt truncation rule or an enforced input-token cap. |
| Initial host headroom | At least 8 GiB available before each process that may load the model; close competing workloads. The observed 3.84 GiB does **not** meet this launch prerequisite. |
| RAM/Metal | Plan 8–10 GiB process/model working allowance on this 16 GiB host; 4 GiB is weights alone. KV cache, activations, allocator cache and shared Metal memory are additional and unmeasured. Operator must confirm suitability; no safe peak is claimed. |
| Runtime guards | Proposed RSS ceiling 10 GiB, available-memory floor 2 GiB, normal pressure only. These do not enforce a hard Metal allocation limit or reserve RAM. Monitor unified memory/pressure/swap, including during loading. |
| Disk | Keep >=12 GiB filesystem free; logical run-output ceiling 512 MiB; one writer/model process. Rough reserve: 512 MiB output + two 512 MiB checkpoint copies + >=8 GiB OS/swap/temporary headroom. Existing weights need not be downloaded/copied onto the run volume. Current free space exceeds this proposal, but must be checked at launch and each call. |
| Backup | Off-device target with >=8 GiB free for exact source, packet, existing 4 GiB snapshot/blobs or verified content-addressed recovery, plus >=2 GiB for rotating checkpoint/review copies. Verify cache symlink targets, package recovery and restore hashes. Do not delete historical evidence to make space. |
| Checkpoint growth | Up to 200 intent/response pairs, 50 cell records, up to 200 resource observations, clock/manifest/seal and optional infrastructure evidence. Raw prompts/responses occur in journals and attempt logs. 512 MiB is a conservative admission allocation, not a proved size bound; one active publication/call may overshoot. |
| Time | Proposed 72-hour cumulative elapsed allocation, including pauses/downtime and immediate export. Actual deadline is deliberately blank. 200 calls at 10/60/300/600 seconds imply 0.56/3.33/16.67/33.33 hours of generation alone; these are scenarios, not measured speed. Hashing, up to 50 model reloads, tokenization and review add uncertainty. |

The prepared runtime policy contains the numerical proposal, but its deadline and
inventory certification are absent. Human approval must include initial headroom,
Metal uncertainty and backend/runtime compatibility. No real-model integration,
performance or peak-memory validation has occurred. Failure-aware limits remain
mandatory even if the run produces no accepted constructions.

## Freeze and execution handoff

Use the clean source commit in the packet's `delivery.json`; preserve/backup a
checkout of that exact commit before approval. Original staged work is in a
different checkout and must remain untouched. Do not regenerate this packet over
itself. The one-time `prepare` operation has already completed; do not rerun it.

The following offline steps become executable after humans supply the completed
intake files described above:

```bash
SOURCE=/private/tmp/rag-v3-engineering
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
PACKET=/Users/sadiapeerzada/Documents/rag-research-results/twowiki-v3-nonprospective-diagnostic-v1-20261106-r2
cd "$SOURCE"
# Confirm HEAD equals delivery.json's source_commit and the checkout is clean.
"$PY" -B scripts/prepare_semantic_v3_diagnostic.py review-payload --packet "$PACKET"
```

The returned `review_payload_sha256` binds all reviewed inputs, source hashes and
the immutable output namespace. Obtain actual signed role evidence on that digest
and complete `study_review.signed.json`. Any intake change invalidates the digest
and requires renewed review. Then freeze once, still without model loading:

```bash
"$PY" -B scripts/prepare_semantic_v3_diagnostic.py freeze --packet "$PACKET"
```

Freeze rejects absent/incomplete human evidence. It publishes byte-identical,
write-once snapshots of reviewed targets/runtime/study-review, then the protocol
and manifest. An interrupted/partially published freeze requires explicit custody
review; do not delete or automatically overwrite it. The frozen manifest status
means ready for a **separate authorization**, not permission to execute. Record
its returned SHA-256 and protocol/resource-policy digests in the actual human
model-call authorization. Archive and independently verify the freeze and signed
records before constructing anything.

Only **after** that authorization, resource allocation, headroom and backup/restore
requirements are fulfilled:

```bash
: "${MANIFEST_SHA256:?Externally verified frozen manifest digest required}"
: "${AUTHORIZATION_SHA256:?Externally verified actual human authorization digest required}"
AUTHORIZATION="$PACKET/authorization.signed.json"

# Offline: no MLX/model/tokenizer loading or new output namespace.
"$PY" -B scripts/prepare_semantic_v3_diagnostic.py preflight \
  --packet "$PACKET" --manifest-sha256 "$MANIFEST_SHA256" \
  --authorization "$AUTHORIZATION" --authorization-sha256 "$AUTHORIZATION_SHA256"

# Read-only host launch-headroom check, outside the restricted sandbox.
"$PY" -B - <<'PY'
from src.experiments.semantic_v3_resources import system_sample
root='/Users/sadiapeerzada/Documents/rag-research-results/twowiki-v3-nonprospective-diagnostic-v1-20261106-run01'
s=system_sample(root)
assert s['available_memory_bytes'] >= 8*2**30, 'Insufficient pre-load headroom'
assert s['memory_pressure'] == 'normal', 'Pressure not normal'
print(s)
PY

# Authorized inference: one NEW complete query/intensity cell per invocation.
"$PY" -B scripts/prepare_semantic_v3_diagnostic.py construct \
  --packet "$PACKET" --manifest-sha256 "$MANIFEST_SHA256" \
  --authorization "$AUTHORIZATION" --authorization-sha256 "$AUTHORIZATION_SHA256"
```

**No inference command above has been executed in this preparation.** A batch
returns `paused_after_complete_cell`; intensity 1 can consume <=2 new calls and
intensity 3 <=6. Verify/back up the batch before repeating the identical command,
with the same source, manifest, authorization bytes and namespace. There can be
50 cell batches plus one invocation to publish the completion seal. Small batches
re-hash the model and may reload it, increasing latency. No automatic loop/retry
is supplied. Once the seal exists, use the same real authorization while current:

```bash
"$PY" -B scripts/prepare_semantic_v3_diagnostic.py summary \
  --packet "$PACKET" --manifest-sha256 "$MANIFEST_SHA256" \
  --authorization "$AUTHORIZATION" --authorization-sha256 "$AUTHORIZATION_SHA256"
"$PY" -B scripts/prepare_semantic_v3_diagnostic.py export \
  --packet "$PACKET" --manifest-sha256 "$MANIFEST_SHA256" \
  --authorization "$AUTHORIZATION" --authorization-sha256 "$AUTHORIZATION_SHA256"
```

Summary prints JSON; retain it under a new, write-once custody record. Export
directories are exclusive/write-once. Keep `postrun-review-private`
away from the two blinded reviewers. Export promptly within the authorization and
elapsed window; the actual A/B review may then proceed on the retained export.
There is no evaluation/QA command for this study.

Completed responses replay exactly, without regeneration. Unresolved intent,
recorded error, orphan response, pending publication, altered seal or context
mismatch means **STOP and independent incident review**. Do not remove the intent,
reclaim budget, change hashes, or create another namespace to silently repeat an
indeterminate call. Expiry and resource/source checks occur before each reservation
and immediately before generation, including after model loading. An active call
can cross a boundary; preserve its response and stop further calls. A late denial
after reservation is an error that blocks automatic replay. Time includes downtime;
new authorization or a longer deadline is an explicit reviewed amendment, never a
silent resume patch.

## Acceptance and reporting criteria to sign before calls

- Operational completion requires an intact seal binding all 50 records, journal,
  source/authorization context, resources and elapsed clock; <=200 reserved calls;
  no unresolved infrastructure events or missing raw attempts. Otherwise report
  incomplete, with exact reason and preserved accounting.
- Scientific diagnostic reporting requires both independent blinded passes over
  every saved attempt, original judgments frozen before adjudication, explicit
  missing/uncertain/disagreement counts and retained adjudication evidence.
- Report target coverage/abstentions, heuristic full/partial/failure counts,
  semantic review dimensions, duplicate slots and uncertainty for the exact
  25-query denominator at each intensity. Cluster by query; attempts and duplicate
  texts are not independent observations. No numerical success rate is invented
  now, and no minimum acceptance rate is introduced to force a positive result.
- Zero accepted constructions is a valid diagnostic outcome. It cannot trigger
  extra retries, replacement queries/targets or altered grammar/validator. No
  automatic progression to the full replication follows a positive outcome.
- Every report must say previously exposed, nonprospective development diagnostic;
  no pristine-cohort, causal Dense/RCD, targeted-ASR or independent-confirmation
  claim follows from these data.

**Current decision:** offline preparation and synthetic engineering checks PASS;
prospective certification NO-GO; nonprospective diagnostic execution NO-GO pending
the enumerated human reviews/signatures, actual allocation/backup evidence,
pre-load headroom and current separately pinned authorization. No historical or
frozen 300-query protocol/evidence was edited.
