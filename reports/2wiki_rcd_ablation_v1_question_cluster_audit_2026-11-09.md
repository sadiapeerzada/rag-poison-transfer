# 2Wiki RCD ablations — completed exploratory question-cluster and latency audit

**Date:** 9 November 2026  
**Study:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Scope:** Master Task 8 experimental ablation closeout **at its exploratory/post-hoc scope**; does **not** imply source-verified truth or untouched confirmatory evaluation.

## 1. Final audited evidence

The operator completed the read-only `scripts/audit_2wiki_rcd_ablations_offline.py` audit on the sealed private prompt plan and original checkpoint tree. Their Mac terminal receipt reported:
- **480/480** Qwen QA responses and matching intent journals verified; **240** clean/poison pairs.
- Six variants across four attack-family/intensity cells, each with **10 selected query-stratum positions** per variant, but only **36 distinct question IDs** across all four cells. Repeated question IDs were kept together in pooled bootstrap resampling.
- **5/5** local tests passed. A separate replay of all 480 Qwen model calls was **not** done.
- The original private aggregate SHA-256 matched the already-published public source aggregate: `9ae68bd2050bef08782d4bc96ba924ffa936d3e7f8d096aa550af964d2bb9466`.
- **50 pooled matched comparisons** (5 variants × 10 outcomes), all based on **2,000 question-ID-cluster bootstrap replicates**, seed `20261109`. Every reported point estimate reconciles exactly with the published variant-group means; all 24 source cell × variant group aggregates reconcile with the prior public results.

See the [sanitized full audit aggregate](../paper/results/2wiki_rcd_ablation_v1_2026-11-09/question_cluster_audit_public.json), existing [ablation aggregate](../paper/results/2wiki_rcd_ablation_v1_2026-11-09/aggregate_public.json) and the [original detailed report](2wiki_rcd_ablation_v1_scientific_results_2026-11-09.md).

**Provenance boundary:** This publication checks the uploaded aggregate and its consistency with previous public outputs. The local auditor checked original private records; those records are not reproduced or published here. It is not independent third-party data-custody certification.

## 2. Full RCD versus component ablations

All descriptive rates below use 40 selected cell positions per variant; these are not 40 fully independent questions.

| Configuration | Clean EM | Poisoned EM | Poison exposure in generated evidence | Target-answer match | Mean internal retrieval calls / QA |
|---|---:|---:|---:|---:|---:|
| Full RCD (k=3) | 17.5% | 12.5% | 95.0% | 75.0% | 4 |
| Remove rewrites (k=3) | 20.0% | 10.0% | 95.0% | 77.5% | 2 |
| Remove agreement feature (k=3) | 20.0% | 12.5% | 92.5% | 77.5% | 4 |
| Remove conflict feature (k=3) | 17.5% | 10.0% | 95.0% | 77.5% | 4 |
| Full RCD (k=1) | 20.0% | 2.5% | 72.5% | 67.5% | 4 |
| Full RCD (k=5) | 25.0% | 15.0% | 97.5% | 75.0% | 4 |

### Cluster-bootstrap comparisons

The signs below are **full k=3 MINUS the named alternative** (not the reverse).

| Comparison | Estimate | Nominal 95% question-cluster CI |
|---|---:|---:|
| Poison visibility: full k=3 minus k=1 | **+22.50 pp** | **[+10.81, +36.84] pp** |
| Target match: full k=3 minus k=1 | +7.50 pp | [−11.11, +27.03] pp |
| Poisoned EM: full k=3 minus k=1 | +10.00 pp | [0.00, +22.22] pp |
| Clean F1: full k=3 minus k=5 | −0.1358 | [−0.2725, −0.0157] |
| Target match: full k=3 minus no rewrites | −2.50 pp | [−7.89, 0.00] pp |
| Inner retrieval calls/QA: full k=3 minus no rewrites | +2.00 | [2.00, 2.00] |
| Measured retrieval latency: full k=3 minus no rewrites | +17.48 ms | [+16.27, +18.76] ms |

The **exposure difference for k=1** is distinct at the nominal, unadjusted 95% level, but poisoned answer EM also falls from 12.5% to 2.5%. Therefore, reducing evidence depth changes the **security–utility trade-off**, not a validated net security improvement. The target-match comparison interval spans zero; **we cannot establish that k=1 reduces targeted false-answer success**.

Removing query rewrites halves the observed internal retrieval operations (4→2) and lowers measured retrieval latency (about 34.90→17.42 ms). It **does not** demonstrate an improvement in target-answer matching or poisoned EM. The recorded call count contrast is structurally constant in this design, not evidence of universal system speedup.

### Mechanism findings

Agreement/conflict-feature removal produced small and mixed paired answer changes. `full_k5` has higher observed clean F1 than `full_k3`, but also more poison exposure. Its observed target-match rate is the same as the full k=3 variant. These are exploratory comparisons in a selected sample; they should not be promoted to universal defense recommendations.

## 3. Generator latency outlier audit

| Variant | Mean generation (s) | Median (s) | p95 (s, nearest rank) | Maximum (s) |
|---|---:|---:|---:|---:|
| Full k=3 | 3.59 | 3.29 | 6.27 | 8.18 |
| No rewrites k=3 | 3.71 | 3.38 | 6.48 | 8.20 |
| No agreement k=3 | 4.02 | 3.51 | 7.22 | 10.40 |
| No conflict k=3 | 4.06 | 3.58 | 7.09 | 9.95 |
| Full k=1 | **13.88** | **2.39** | 5.15 | **902.99** |
| Full k=5 | **18.20** | **6.53** | 13.78 | **913.78** |

Each variant has 80 underlying generation records. **One >900-second response in k=1 and one in k=5 strongly inflate both corresponding means.** Do not describe the raw mean differences as intrinsic k-depth generation costs. Report medians and p95, inspect startup/scheduler/cache conditions, and, if desired, run a separately labelled offline sensitivity analysis excluding identified outliers without deleting or modifying observations. The present analysis retains all measured data.

All retrieval times were recorded during prompt construction, while generation times were logged in the separate completed Qwen execution; **they do not constitute a calibrated end-to-end production benchmark**.

## 4. Statistical limits and claims

- All **50 pooled confidence intervals are nominal exploratory percentile intervals**, unadjusted for multiple testing. Reused question IDs are grouped in the bootstrap, but this cannot cure the post-hoc, valid-only selection of 10 examples per attack/intensity cell.
- Only **36 unique question IDs** underlie 40 positions. Results cannot be generalized as an independently sampled 40-question benchmark or pooled with historical study results as new external replications.
- Target-answer matching is **not** source-adjudicated factual falsehood, and a visible poison document ID does not prove causal model misinformation.
- Failed construction attempts were excluded. This study **cannot estimate attempted-population attack success** or demonstrate successful poison detection.
- The original 2Wiki exposure, licensing, independent human semantic review, model generality and broader generalization limitations remain open. This final offline audit does not resolve them.

## 5. Research closeout decision

**Task 8 (RCD component ablations): complete at the explicitly exploratory evidence/reporting scope.** The six configurations were executed, 480 sealed QA observations verified locally, 50 question-cluster pooled intervals recomputed, and latency anomalies documented. No new inference is needed for this defined analysis.

This does **not** close master Tasks 4 (semantic evaluation), 5 (adaptive retrieval), 6 (true poison detection), 7 (robustness), 9 (source-backed semantic adjudication), 10 (cross-dataset cost audit), 11 (global data custody and reproducibility), or 12 (complete manuscript/release package).

**Public files contain aggregate-only results.** Private questions, per-request prompts/responses, source passages and poison documents remain outside GitHub.
