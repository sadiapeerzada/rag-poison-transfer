# Prospective 2Wiki Semantic Quality V3 preparation — 2026-11-04

**Overall verdict: NO-GO for cohort selection and inference.** Infrastructure is implemented and offline-tested; historical exposure certification, a genuinely fresh cohort, target reviews, runtime pins and explicit authorization are missing. The completed work is ready for independent code/protocol review, not for model execution.

## Verified baseline and boundaries

The preparation branch starts directly at `fba2583ae4569d6e5114052ac1854ad545dc3c16` (`experiment/twowiki-semantic-quality-v3-development`) in isolated worktree `/private/tmp/twowiki-semantic-v3-prospective-pilot-prep`. Its ancestry includes frozen implementation `07499fd7d3dc750d9ec876465c76c4972a9c70df`. The V3 descriptor, configuration and implementation hashes match the prior verification artifact. The revision report, prospective protocol and three original audit reports were read, including the complete 50-row taxonomy. No older implementation was substituted.

All changes are additive. Existing V3 source, frozen registries, evaluation runners and historical metrics are unchanged. The 509-file frozen-run SHA-256 inventory matches before/after preparation and tests. The separate frozen implementation checkout remains clean, and the original checkout's six staged user changes remain intact. No model weights were loaded; no construction pilot, Dense/RCD, QA or held-out matrix was launched. Unit tests use only deterministic stubs and saved regression strings.

## Exposure and cohort readiness: blocked

The existing cohort policy explicitly records `complete_historical_nonoverlap_certified=false` and “exact IDs unrecovered” for an earlier 25-query sweep. The frozen semantic-quality protocol reiterates this uncertainty. No custodian certificate resolves it. This is an evidence blocker, not a selection failure to work around.

The inventory tooling projected IDs from 30 declared old metadata sources into a conservative union of 900 exclusions: 300 historical baseline IDs, 300 held-out IDs from metadata only, and the 300 existing development-cohort IDs. Later pilot, regression and target-review IDs found in the declared source projections fall within that union. All 25 audit IDs and all V3 regression query IDs are excluded. Source paths, original SHA-256, projection details, per-source ID exports and the union are bundled. Several manifests/summaries yield zero recognized IDs; this is not proof that those runs exposed no queries. The registry explicitly lists unresolved gaps and remains `incomplete_not_certified` with `certification=null`.

This inventory is not exhaustive across raw response logs, remote/deleted artifacts, notebooks, model review sessions or other checkouts. No claim of completeness is made. Held-out exclusion uses `cohort_manifest.json` → `cohorts.dev`, containing IDs/question hashes only; no held-out content was inspected. The existing development cohort is conservatively excluded rather than recycled as fresh. No new pool/content was opened, no real selection ran, and no ordered prospective 25-ID list was fabricated.

The implemented selector requires a complete externally pinned custodian attestation, all exposure source classes, a consistent exclusion union and no historical gaps. It uses exactly the predeclared SHA-256 rule, chooses 25 by metadata only, and publishes an immutable ordered list and timestamped freeze receipt before the target-content handoff. Fewer than 25 eligible IDs fails closed. No unsuitable-query replacement exists. Hash-bound custody records document attestations but do not authenticate identity or prove absence of unlogged exposures.

## Independent target review: workflow ready, approvals absent

The tooling emits blank per-query forms only after verifying cohort selection/certification/receipt, before reading development content. Completed ledgers preserve the exact 25-ID order, query hashes and freeze-receipt hash. Every candidate uses the unchanged V3 evidence packet: exact relation/referent/type, gold/aliases, target, cited source spans, corpus-relative contradiction, role/chronology/geography evidence, nominator, distinct human reviewer, explicit uncertainty and payload-bound approve/reject/uncertain decision. Review timestamps must postdate the cohort freeze. Uncertain or insufficient evidence results in an explicit abstention; pending review blocks execution. Selection happens before generation and is the same for intensities 1 and 3.

No target was nominated or approved in this task. Blank forms and synthetic tests are not independent approvals. If alias or source evidence cannot be established under the pinned query/data contract, abstain; do not silently edit the frozen cohort/data binding to force eligibility. Geographic/chronological and factual judgments remain evidence/reviewer tasks rather than heuristic certification.

## Immutable construction infrastructure

The standalone driver verifies exact manifest/protocol/artifact hashes and driver/V3 source fingerprints, development/train scope, complete cohort/target correspondence, fixed decoding/budgets, model/environment pins and their inventory-review record. It requires a separately recorded, externally pinned human authorization binding purpose, scope, namespace, manifest/protocol hashes, 200-call cap and valid timestamps **before** the lazy backend factory can be invoked. Draft artifacts and blank authorization fail closed. Actual model/runtime pins and a real backend integration remain untested and missing.

A fresh canonical namespace uses a single-writer lock. Checkpoints are written with fsync and atomic no-overwrite publication, then made read-only. Requests are persisted before calls; exact raw outputs/backend prompts and generation metadata are persisted before semantic validation. Resume invokes the unchanged V3 API through a call journal: known responses replay byte-for-byte without regeneration, while only unstarted calls can reach the backend. Reconstructed attempt records include prompts, outputs, reasons, seeds, profile/model versions and validator assessments. Infrastructure errors are archived separately and never converted into construction failures.

An unresolved intent without a durable response stops automatic resume. It is impossible to infer whether an external call ran across that crash boundary; conservative refusal is required. Recorded infrastructure errors likewise require independent resolution, not automatic retry. Reserved intents conservatively consume the budget, including ambiguous/error calls; the maximum remains 200. Scientific retries remain at most two per document, no target substitution occurs, and all declared slots are attempted. Incomplete intensity-3 constructions keep partials but expose no injectible documents. Duplicate texts are retained/reported, not claimed as corroboration.

The final seal binds all 50 construction records and every call-journal file's bytes, authorization context and call count. Sealed resume verifies rather than rewrites or loads a backend. OS permissions plus hash checks guard accidental/API changes, not an owner altering both records and seals; a future final seal must enter independent custody. Expired authorization or ambiguous/error checkpoints require human resolution rather than deleting evidence or silently changing authorization.

## Scientific review and reporting

Blinded export verifies completed seals and includes every saved output attempt, including heuristic rejections. Two blank review passes receive randomized blinded IDs and the question/target/gold/evidence needed for assessment. Heuristic labels, rejection reasons, intensity/slot/retry order and QA fields remain in a separate private map. The rubric distinguishes exact relation, target support, corpus-relative contradiction, plausibility, malformations, duplicates and uncertainty. Both independent reviews must be frozen before adjudication/unblinding; original disagreements remain preserved.

The construction summary reports attempted queries, valid constructions, target abstentions, semantic failures, duplicates and pending independent review, grouped by intensity. It evaluates no retrieval or QA metric and computes no targeted ASR. No RCD effectiveness claim is supported or made. The old 25-query cohort is inspected regression material, not prospective improvement evidence.

## Offline verification and deliverables

**508 offline tests passed.** The accompanying verification JSON records the exact test command and result. Tests cover deterministic selection and exclusions; uncertified-history stops before content access; target abstentions and independent-review enforcement; protocol/source/artifact mismatch rejection; missing/expired/mismatched authorization; fresh namespace and single writer; crash after response with exact replay; ambiguous intent refusal; infrastructure classification; immutable seals and journal tampering; bounded retries and exact 200-call cap; duplicate reporting; intensity-3 all-or-none behavior; and inclusion/blinding of rejected attempts. Relevant V3 regressions and legacy compatibility tests are included. No actual exposure certification, reviewer approval or model authorization is created by these synthetic tests.

Deliverable map:

- `pilot_prep/twowiki_semantic_v3/`: blocked draft protocol/manifest, pinned V3 descriptor, source plan, incomplete known-exclusion registry/exports, JSON Schemas, blank forms, semantic rubric and explicit GO/NO-GO checklist.
- `scripts/prepare_semantic_v3_pilot.py`: metadata inventory, deterministic selection/freeze receipt and guarded blank target-form handoff; no inference subcommand.
- `src/experiments/semantic_v3_preparation.py`, `semantic_v3_checkpoint.py`, `semantic_v3_pilot.py`, `semantic_v3_review.py`: preparation gates, atomic storage/call replay, gated standalone driver and independent review/reporting export.
- `tests/test_semantic_v3_pilot_prep.py`: synthetic offline workflow/interruption/budget tests; existing V3 fixtures/tests remain unchanged.

JSON Schema documents were parsed and runtime contracts tested. The optional `jsonschema` package is unavailable, so a formal JSON Schema validation run is not claimed. See the bundle README for contracts, commands, limitations and exact-resume behavior.

## Readiness verdict

| Dimension | Verdict |
|---|---|
| Infrastructure | Offline-tested and ready for independent code review; actual model/runtime integration not tested |
| Scientific cohort | **NO-GO:** incomplete exposure history and missing custodian certification; no fresh cohort selected |
| Independent review | Workflow/rubric/forms ready; reviewer roster, target evidence and actual approvals missing |
| Authorization to infer | **NO-GO:** no explicit authorization or final model/environment/protocol pins; no calls permitted |

Resolve the exposure evidence first. Then freeze metadata selection, obtain actual target evidence/reviews, complete model/environment and protocol pins, and obtain separately recorded explicit model-call authorization. This task does not authorize any of those future model calls.
