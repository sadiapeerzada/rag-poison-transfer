# Research reproducibility and validity release gate — 9 November 2026

**Project:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Status:** **PUBLIC AGGREGATE INTEGRITY PASS; GLOBAL REPRODUCIBILITY / SCIENTIFIC VALIDITY NOT YET CERTIFIED**  
**Checked main revision:** `2c8b906eea77a244a8282d1ef41b1b3c00e598b4` (PR #148 merge).  
**Purpose:** A current, denominator-aware snapshot of what has truly been completed, what has been verified only through the researcher's local receipts, and what cannot be asserted for a final full-claims research release.

The [machine-readable public-evidence inventory](../paper/results/reproducibility_gate_2026-11-09/public_evidence_inventory.json) pins **eight GitHub blob identities** and records **nine passing structural/accounting checks**. Git blob SHA-1 is an identifier for publicly retrieved Git file content, **not** independent verification of original private source data or model execution.

## Gate decisions

| Evidence gate | Current verdict | Verification boundary / missing evidence |
|---|---|---|
| **Public GitHub results inventory** | **PASS (public only)** | Eight published JSON sources re-fetched and parsed; nine source-to-source invariants passed. The same records could be rechecked after a repository change using the listed paths and blob identities |
| **NQ lexical I1 and I3 frozen experimental reporting** | **PASS as operator-reported exploratory run; external raw custody pending** | 300 matched questions, 1,200 logical Qwen observations/intensity; 2,400 combined; 35 question-cluster paired contrasts, SHA pins and complete local resource means. Public I1/I3 reports match the later full paired aggregates. Separate independent re-hashing of all original private NQ raw journals and local model snapshot file hashes **not demonstrated by these public aggregates** |
| **2Wiki 300-query historically disclosed original run** | **PASS local manifest and same-machine restore; exposure gap retained** | Original construction/evaluation manifests and 37,534-file full-run archive reported audited; restore from `Downloads` verified against digest `faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82`. This demonstrates restoration into a **different directory of the same Mac**, not an attested off-device recovery or fresh historically unexposed cohort |
| **HotpotQA source-crafted cross-pipeline transfer** | **PASS operator-reported source selection/evaluation audit; candidate archive optional unchecked** | 240 source-target cells; 20,500 paired comparisons, two inventories hash-checked by operator (61,601 selection / 158,037 evaluation file records), and 240 keyed values match public aggregate. Optional original candidate-stage inventory was **null / not checked**. These numbers are not counts of independent questions |
| **RCD 2Wiki six-variant ablation** | **PASS exploratory post-hoc scope** | 480 locally verified response/intent records, 240 clean-poison pairs, **36 distinct question IDs across 40 selected cell positions**, 50 question-cluster contrasts and generator latency audit; no prospective unbiased construction or real semantic-truth certification |
| **Cross-study resource accounting** | **PASS local observational metrics only** | NQ, 2Wiki ablations and historical HotpotQA measurements summarized with separate timing boundaries; 41,000 logical / 21,175 physical HotpotQA model observations plus 19,825 cache hits reconciled. No hardware-normalized or monetary cost estimate, and no source-comparable original 2Wiki 300-query latency export |
| **Semantic false-answer truth / causal poisoning** | **NOT CERTIFIED** | The 131-case, 102-question 2Wiki case packet and 107 mechanically valid selected rows were AI-assisted, post-hoc and outcome-stratified. 24 failed-construction cases lacked full context in the packet. Target-string matching, mechanical acceptance or poison exposure is not independently verified factual falsehood or a demonstrated causal flip |
| **Prospective / historical data independence** | **NO-GO for fresh 2Wiki V3 claim** | Previous exposure reconciliation could not recover exact old sweep IDs and had no complete custodian certificate or fresh certified cohort; no authority to relabel historic results as prospectively untouched. Original 2Wiki data remain historically risk-disclosed |
| **External reproducibility assets** | **PARTIAL** | The full 2Wiki run tar is intact/restorable, but independent online origin of the downloaded archive and recovery of model weights, tokenizer snapshots, embeddings and dataset caches outside the archive were not attested |
| **CI and repository-wide release audit** | **PARTIAL** | The earlier Task 8 PR test completed successfully. At this gate inspection, the latest main-commit check API showed **one successful test run and one still in progress**; no final green verdict for every run is asserted. A new full tracked-tree privacy/licensing/secret scan and complete environment recreation are **not** established by publication of eight aggregate JSON files |

## Nine published-source integrity checks

The eight re-fetched JSON artifacts were all syntactically parseable, with these passing public-evidence invariants:

1. NQ I1 and I3 each record **300 distinct questions**.
2. Each intensity accounts for **1,200 logical QA observations**; combined paired output accounts for **2,400**, with **35 paired comparisons**.
3. The separately published I1/I3 group rates, exact counts and poison visibility agree with the complete paired statistical JSON for both Dense and RCD.
4. The 2Wiki private original aggregate SHA-256 fingerprint is identical in the published original ablation aggregate and later question-cluster report.
5. The 2Wiki ablation reports **480** records, **24** cell × variant groups, **36** distinct question IDs, **50** pooled effects.
6. All 2Wiki ablation variant means reconcile with the published 24 group metrics; all 50 point contrasts equal `full_k3 minus alternate variant`.
7. HotpotQA has **240** grouped source-target cells and a reconciled **21,175 + 19,825 = 41,000** physical/cache/logical generation count.
8. The cross-study cost ledger points to its four published resource inputs.
9. Public source pins and recorded Git blob identities are pinned for later changed-file detection.

*The checklist counts source and cross-file checks in thematic groups; the actual machine-readable manifest contains the exact **nine** validation items and must be used as the numerical test ledger.*

## What these checks do **not** prove

They do not establish whether an original dataset/model was never exposed, whether a generated semantic assertion is false, whether raw Qwen calls physically occurred apart from the local receipts, whether all raw data have transferable publication rights, or whether all the required model/dataset assets exist in an independent disaster-recovery copy. A machine-readable checksum cannot substitute for a real accountable custodian, original source evidence or documented approval.

The user has preferred **no new external human review** for these results; accordingly, semantic review must continue to be labelled **AI-assisted and unadjudicated**. A narrow paper with these explicit limitations is possible, but it cannot advertise independently human-verified factuality or a confirmatory untouched 2Wiki cohort.

## Fastest remaining read-only actions, in order

1. **Close CI on the merged main revision** and retain a dated successful workflow URL. Do not call the release CI-verified while any required checks remain running or failed.
2. **Preserve external-archive custody facts**: if the existing 2Wiki archive really was downloaded via iCloud.com, record a factual dated provenance receipt and the already pinned SHA; do not invent off-device or cross-machine recovery. Inventory separate Qwen/embedding/tokenizer/data caches and choose to back them up or explicitly document their unrecoverability.
3. **HotpotQA optional candidate inventory**: if present, run the existing read-only verifier with the real `--candidate-dir` rather than silently declaring the optional source stage checked. Existing selection+evaluation raw audit is already PASS by operator receipt.
4. **NQ original per-response asset audit**: optionally add a read-only SHA/journal test on the same pinned 2,400 observation corpus, using the already merged `nq_qa_runner.py` and `nq_paired_statistics_offline.py`. Do not rerun inference or publish the private question/target files.
5. **Semantic source ledger and study scope decision**: for Tasks 4 and 9, record source-cited statement/target facts and abstentions (including the 24 context-incomplete 2Wiki cases) or explicitly narrow claims. A full-scale objective poison-detection (Task 6), iterative retrieval (Task 5) or expanded robustness (Task 7) claim still requires separate actual results, not a paper-text fix.
6. **Run repository-wide release/privacy/license scan**, review raw tracked result files and model/data redistribution rights, publish aggregate-only figures and reproducibility commands, and decide whether the final product is a narrower exploratory paper or the full original 12-workstream protocol.

## Task-count and paper-readiness verdict

- **Tasks 1, 2, 3, 8, 10:** completed and published at their explicitly **exploratory/scoped** evidence standards; the NQ 35-comparison and 2Wiki 50-comparison analyses are present.
- **Task 11:** this public-artifact and provenance inventory is **complete**, but **global scientific integrity and reproducibility certification remain PARTIAL** due to missing custody/exposure/semantic/asset/licensing gates. **Do not increment the full-task completion count from 5/12 solely for this report.**
- **Tasks 4, 5, 6, 7, 9 and 12:** cannot be marked finished based on this audit.

**Overall:** A limited, caveated paper using existing original and exploratory experiments can be drafted; the requested entire original research program is **not completed**. Publication approval and broad claims require explicit scientific scope review, not a generated GO flag.

## Pointers

- [NQ matched statistics](NQ_LEXICAL_I1_I3_FULL_PAIRED_AND_EFFICIENCY_2026-11-09.md)
- [2Wiki final ablation audit](2wiki_rcd_ablation_v1_question_cluster_audit_2026-11-09.md)
- [HotpotQA raw source audit receipt](HOTPOTQA_TRANSFER_RAW_ARTIFACT_VERIFICATION_2026-11-09.md)
- [2Wiki restore verification](2WIKI_RESTORED_ARCHIVE_VERIFICATION_2026-11-09.md)
- [Cross-study cost ledger](CROSS_STUDY_OBSERVED_EFFICIENCY_AND_COST_LIMITS_2026-11-09.md)
- [2Wiki AI-assisted case audit](2WIKI_QUALITATIVE_ERROR_AUDIT_PUBLIC_2026-11-09.md)
- [Prospective 2Wiki V3 gate](../reports/twowiki_v3_exposure_reconciliation/GO_NO_GO.md)
