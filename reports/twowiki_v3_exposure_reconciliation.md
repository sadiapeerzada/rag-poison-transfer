# 2Wiki V3 exposure reconciliation — 4 November 2026

**Verdict: the prospective design remains NO-GO.** The historical sweep's exact 25 IDs were not recovered. All concretely recovered IDs are already within the 900 exclusions. The available pinned/materialized development pool contains 300 unique IDs, all excluded, leaving **zero** potentially eligible IDs. This does not imply the full upstream training split is exhausted. No cohort was selected, no candidate questions/answers were inspected, and no inference or evaluation ran.

## What can and cannot be established

| Question | Evidence-based finding |
|---|---|
| Which 25 IDs did the older sweep use? | **Unknown.** No contemporaneous run-bound ID ledger or executed sampling invocation was recovered. No IDs were guessed or historically resampled. |
| Which dataset revision? | The contemporaneous report identifies `Salesforce/ContextualBench`, config `2WikiMultihopQA`, revision `9823f70484dea525100394220b0ea5184d0eeb7b`. This is a documented revision claim, not a recovered runtime binding. |
| Are those 25 already excluded? | **Cannot determine for that missing run.** Every concrete ID observed in recovered sources is excluded; that does not establish the missing run's membership. |
| Any additional exposed IDs recovered? | **No additional unique IDs.** Recovered metadata adds provenance for existing exclusions, without increasing the 900-ID union. |
| Can a fresh 25-query cohort be selected now? | **No.** The available 300-ID pool is exhausted and historical custody remains unresolved. Selection was not attempted. |
| Is certification complete? | **No.** No human custodian attestation or independent approval was created. |

The original sweep commit is recorded in `search_summary.json` (short SHA `d232fdf`, dated 6 September 2026). Its `src/attacks/sweep.py` returned aggregate attack/intensity/retriever rows, without query IDs, a query fingerprint, dataset revision or sampling invocation. Its `results/week5_6_2wiki_sweep.csv` has 16 aggregate rows, each reporting 25 attacked queries. Those aggregates cannot uniquely identify the underlying queries. The report identifies a 218-document pooled corpus, which also cannot establish query membership.

A critical provenance distinction prevents substituting baseline IDs: the four 300-query baseline JSONLs record revision `e37a4050605363be62f1d02e6eb888fe5f56530e` and split `validation`, while the later sweep report and changed loader/configs name revision `9823f704…`. The loader's default maps `validation` to `dev`, but an unrecorded caller can override split, seed, sample count or revision. Baseline configurations and loader defaults do not prove the actual sweep invocation. We therefore did not label the first 25 baseline IDs, or a newly reconstructed sample, as recovered sweep evidence.

Contemporaneous primary sources: [sweep implementation](https://github.com/sadiapeerzada/rag-poison-transfer/blob/d232fdf/src/attacks/sweep.py), [aggregate CSV](https://github.com/sadiapeerzada/rag-poison-transfer/blob/d232fdf/results/week5_6_2wiki_sweep.csv), and [Week 5–6 report](https://github.com/sadiapeerzada/rag-poison-transfer/blob/d232fdf/docs/WEEK5_6_BENCHMARK_VALIDATION_REPORT.md). Their Git object IDs and SHA-256 projections are preserved in the accompanying inventory.

## Recovery scope and limits

The audit started directly from `6912653922ea0008a97b8e3ddb0cc8a8be68b287` in an isolated worktree on `audit/twowiki-v3-exposure-reconciliation`. Searches covered:

- 37 worktree/local-repository locations, 23 still available and 14 absent, across two physical Git object stores. The second independent repository at `Downloads/rag-poison-transfer-final` was checked separately.
- 38 reachable candidate file versions across those stores, six unreachable commit trees and 62 unreachable loose blobs from the main store. The second store reported no unreachable objects. The 100 Git blob observations yielded no missing sweep ledger or additional IDs. These are bounded candidate searches, not proof that no ignored/untracked artifact ever existed.
- Existing experiment/results/checkpoint/review metadata, downloaded review bundles and local copies: the combined inventory contains 1,790 source observations, including copies and repeated versions. These are not independent experiments or exposures.
- Four older repository ZIPs, which contained no sweep/notebook candidate members; two backup TAR member inventories, which contained only relevant code/configuration paths or no 2Wiki candidates. TAR archives received member-name inspection, not full archive SHA-256 certification; this limit is explicit in the summary.
- The local `Downloads/rag-poison-transfer.xpynb` is zero bytes (SHA-256 `e3b0c442…`). Its emptiness is not evidence of non-exposure or proof that the original executed notebook was empty.
- Narrowly matched available Codex session logs and shell history. Matches provide later documentation/search references, not an executed historical 25-query invocation. Unrelated history and credentials were not exported. Non-JSON logs were additionally checked for explicit query-ID tokens; six known IDs were found, none new.
- Public GitHub committed result/notebook directory metadata at the historical commit. The committed notebook directory contains only `.gitkeep`; the result tree provides the same aggregate artifacts. This does not inventory a hosted notebook's runtime filesystem or private/deleted exports. The connector rejected the Actions listing URL, so no Actions-artifact census is claimed.

The OS denied access to `/Users/sadiapeerzada/.Trash` (`PermissionError: Operation not permitted`). No original hosted execution export, authoritative private runtime inventory or custodian ledger was supplied. Absent worktrees may have held ignored/untracked data that Git cannot reconstruct. No missing/empty/unparsed source was treated as proof of non-exposure. Exact search counts, paths, source hashes and limitations are in `search_summary.json`, `worktree_inventory.json`, `git_object_inventory.json`, `remote_checks.json`, and `unresolved_history_register.json`.

Only typed query-ID/revision metadata was projected; question, answer, prompt and generated prose fields were discarded from report outputs. Held-out exclusions remain the existing metadata-only 300-ID list; no held-out content or candidate semantic quality was inspected.

## Registry reconciliation

All 30 inherited source hashes and metadata projections were rechecked and match (`parent_source_rechecks.json`). The new `reconciled_registry.json` preserves every inherited source record, provenance hash, historical gap and exclusion decision, binds the exact parent registry SHA-256, and appends recovery observations. The original preparation registry, source plan, protocol, driver and GO/NO-GO files were not overwritten.

The union remains **900**: 300 historical baseline IDs, 300 reserved held-out IDs and the 300 existing development-cohort IDs, with recovered later pilot/review/regression IDs falling within that union. No new unique ID was added. A typed ID's appearance is conservative exclusion evidence, not proof of complete exposure accounting or an independent approval. Source copies, schema variants, raw-response logs and Git versions may duplicate the same event. Unparsed or zero-ID observations remain explicitly uncertain rather than certified clean.

`certification` remains `null`, status remains `incomplete_not_certified`, and the original prospective scientific gate still rejects this registry. Machine-verifiable hashes/membership checks cannot replace a custodian's evidence-based completeness attestation.

## Metadata-only pool assessment

The original `/cohorts/train` metadata lists 300 development IDs. Both available local materializations (`twowiki-v2-development-recovery-20261103/development_data.json` and `twowiki-v2-binding-20261103/local-v2/dataset.json`) have SHA-256 `58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43` and the same 300-ID membership. Every ID is already excluded, so each assessment has 300 available, 300 excluded, zero potentially eligible. Copies do not create a 600-query pool.

The audit did not rank IDs by the prospective selection hash or call the selector. Cardinality was assessed by set difference only. A count of at least 25 would be necessary but not sufficient: complete certified history and the other original gates would still apply. No broader train ID census was available in the searched local materializations/default HF caches. The absence of those local files is not a claim about the upstream dataset's size or globally available records.

See `metadata_eligibility.json` for exact source pins, counts and limits. The audit does not inspect candidate questions/answers or perform the content-based near-duplicate check; zero ID-eligible records already suffices to block the available pool.

## Least disruptive defensible alternatives

1. **Preserve the prospective design unchanged and obtain missing custody evidence.** Request the original executed notebook/kernel version, raw query/poison ledger or run-bound export, plus custodian reconciliation of other local/remote/deleted exposures. If only sampling code is recovered, it must be bound to the actual executed version, dataset revision/row order, split, seed and environment before any historical reconstruction can be treated as evidence. No reconstruction was performed here.
2. **If genuine freshness is required, separately document a broader development-data source.** An IDs-only export from the full 2Wiki training split at the same pinned revision is the least disruptive source expansion to assess first. Its eligible count is **unknown**, not asserted to exceed 25. It requires a reviewed pool/source amendment, provenance and the still-missing custody resolution; a larger pool alone cannot remove uncertain historical exposure. No upstream records were fetched or silently substituted, and no alternative cohort was selected. An independently curated new query collection would be a different study requiring its own source/version and protocol.
3. **If custody cannot be resolved, use the already exposed pool only for an explicitly non-prospective development diagnostic.** A separately versioned construction-only engineering study could assess relation correctness, abstentions and logging without claiming fresh-cohort improvement or unbiased generalization. This preserves V3 implementation and existing data, but changes the scientific claim; it is not a workaround granting GO to the current prospective protocol. A new protocol and separate model-call authorization would be required. No such study was launched or authorized here.

The immediate recommendation is **NO-GO**, not weaker certification. The existing infrastructure remains available for independent review, but scientific cohort readiness, independent reviewer/custodian approvals, runtime pins and inference authorization remain missing.

## Verification and preservation

**41 offline tests passed.** Relevant offline tests exercise typed-field projection without prose inspection, empty/missing/unparsed evidence handling, JSONL/CSV metadata, monotone preservation of inherited exclusions, no synthetic certification, counts without selection, real registry rejection, exhausted pool assessment, and the existing checkpoint/authorization/review gates. Exact passing output and the command are retained alongside the verification JSON.

All 509 frozen-run file hashes were compared before/after the audit. The original staged user changes were preserved. All audit changes are additive; no frozen Stage 2 result, configuration, checkpoint, provenance hash, production selection rule or scientific gate was modified. No inference, QA, Dense/RCD or held-out evaluation ran.
