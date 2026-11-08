# 2Wiki 300-query matrix: construction completion (pre-audit)

**Record date:** 2026-11-08  
**Evidence level:** operator-supplied local supervisor terminal log; independently validated provenance **pending**  
**Release status:** CONSTRUCTION_REPORTED_COMPLETE / SEAL_REPORTED_WRITTEN / QA_NOT_STARTED / NOT SCIENTIFICALLY CERTIFIED

## What the frozen construction supervisor reported

- Matrix: 2 attack families × 2 intensities × 3 seeds = **12 construction cells**, with **300 query IDs per cell**.
- Recorded construction checkpoints: **3,600 / 3,600**.
- Completed cells: **12 / 12**.
- Final runner status: `all_construction_frozen_no_evaluation`.
- Final supervisor message: `CONSTRUCTION COMPLETED AND SEALED. Validate the seal separately before any QA evaluation.`
- Reported seal SHA-256: `e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44`.
- Reported free disk following construction: **38 GiB** (context only, not a scientific result).

These numbers are **checkpoint/coverage counts, not valid attack counts**. The log alone does not establish that all poisons were successfully constructed, nor any attack success rate, Dense/RCD performance, or scientific validity.

## Frozen-study context and limitations

- This is the historically **risk-disclosed** replication, not the separately blocked prospective Semantic V3 study.
- Historical non-exposure and independent target/semantic adjudication are **not certified** by this record.
- The operator's prior execution handoff identified source revision `b1466db04c4f8f0314c7e537d8e7ec390c8c3b29` and protocol SHA-256 `40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4`; these pins are **not re-verified in this GitHub report**.
- Raw journals, local model weights, private file paths and datasets are deliberately **not** committed with this metadata-only record.

## Next gate: independent construction seal audit

Before any QA evaluation, an authorized reviewer must inspect the immutable local execution artifacts and independently:

1. Verify the original frozen execution checkout, pinned protocol, model identity and input binding.
2. Recompute the SHA-256 of the local `construction.seal.json` and compare it to the recorded digest above; preserve the externally pinned digest.
3. Use the original runner's validators to inspect **all twelve** cell manifests, query/checkpoint population, construction journals and completion seal. Resolve any discrepancy, incomplete generation intent, error response or temporary debris explicitly; never silently regenerate.
4. Report attempted, valid, failed and unavailable construction records with the appropriate **3,600-record denominator**, separating validity from measurement availability.
5. Document explicit GO/NO-GO for evaluation and ensure sufficient disk, RAM/Metal headroom, verified backup/recovery and compute authorization.

**No evaluation is authorized by this report.** Following independently documented GO, use the same frozen source/protocol/constructed seal to run resumable paired Dense/RCD evaluation, validate its completion pin, and then aggregate.

## Scope of this GitHub checkpoint

This PR changes **documentation only**. It records an operator-reported major milestone **before** the independent seal audit, so the audit remains a separately reviewable event. It neither modifies nor freezes the actual local research artifacts and must not be mistaken for a validated scientific result.
