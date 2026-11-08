# 2Wiki 300-query construction: technical audit results (post-seal)

**Recorded:** 2026-11-08  
**Audit evidence:** operator-shared terminal outputs from the frozen 2Wiki checkout, verified independently at the file-hash level and then rechecked by the frozen runner. This report does not claim an independently appointed human reviewer or semantic certification.  
**Decision:** TECHNICAL_INTEGRITY_PASS (including later model snapshot binding); **evaluation authorization pending**.

## Frozen run and seal pins

- Source commit: `b1466db04c4f8f0314c7e537d8e7ec390c8c3b29` — the operator's command checked Git HEAD equals this pin.
- Protocol SHA-256: `40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4` — pinned file verified.
- Construction seal SHA-256: `e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44` — independently recomputed from local file and matched the construction supervisor's reported digest.
- Matrix: lexical_influential_token and semantic_fluent_false_evidence × intensity 1/3 × seed 42/43/44; 12 cells, 300 query records each.

## Verified integrity

The operator's **read-only** Python audit reported:

- `PASS: 15081 sealed files verified` — exact file inventory and SHA-256 matched `construction.seal.json`.
- `PASS: 12 cells, 3600 records` — every sealed cell file contains exactly 300 records, and its digest matches the cell entry.

The later runner-native audit imported `scripts.run_week9_protocol_poison_matrix.load_sealed` from the frozen checkout and reported all checks passed:

- Source, protocol and seal pins.
- Frozen protocol/dataset binding.
- All 12 declared cell identities, cell validators and complete construction-journal checks.
- Clean dataset cohort size of 300 queries.
- Explicit terminal line: `NO EVALUATION EXECUTED`.

## Construction outcomes (not attack success)

| Family | Attempted | Mechanically valid | Target construction failure | Semantic construction failure |
|---|---:|---:|---:|---:|
| Lexical influential token | 1,800 | 1,524 | 276 | 0 |
| Semantic fluent false evidence | 1,800 | 276 | 276 | 1,248 |
| **Total** | **3,600** | **1,800** | **552** | **1,248** |

The lexical valid rate is 84.67% of attempted rows; semantic valid rate is 15.33%; overall 50%. These are mechanically validated poison-construction outcomes **only**. They do not demonstrate that a false claim is independently semantically correct/incorrect, that a poison was retrieved, that any target answer was induced, or that Dense/RCD mitigated anything. Preserve the 3,600-attempt denominator and distinguish the 1,800 valid-only evaluation population.

## Later model/runtime observation

The same model-binding operator log reported **38 GiB** available disk and **1,794.19 MiB swap in use**. Swap usage is not a stand-alone memory-readiness pass. Off-device backup/recovery, live RAM/Metal headroom, specific evaluation budget, human scientific sign-off, and external seal-pin custody remain subject to explicit human checks.

## Remaining GO/NO-GO conditions

1. Independently confirm research-risk disclosures, responsible human approval, provenance/exposure limitations, compute budget, verified recoverable backup and sustained disk/RAM/Metal headroom.
2. **Model binding technical check: PASSED on 2026-11-08.** The operator subsequently called the frozen `load_protocol(protocol, protocol_pin, snapshot)` and received `PASS: Frozen source, protocol, environment and MLX model snapshot` with model revision `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`; explicitly `NO EVALUATION EXECUTED`. This verifies protocol-level model snapshot byte/revision binding, not independent human sign-off.
3. Preserve current sealed construction unchanged. Execute evaluation only with the externally recorded construction-seal SHA-256 and the original frozen source/protocol, and only after explicit authorization.
4. Run resumable paired Dense/RCD evaluation; validate completion digest and then aggregate with failure-aware denominators.

**Scope:** GitHub receives audit summaries and hashes only. The 3,600 raw checkpoints, generation transcripts, local dataset, model weights and complete experiment journals remain outside GitHub and need a separate protected backup. This document is a metadata checkpoint, not an evaluation or publication result.
