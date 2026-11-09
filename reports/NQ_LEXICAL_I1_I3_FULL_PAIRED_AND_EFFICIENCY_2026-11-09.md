# NQ lexical I1/I3: complete exploratory paired analysis and measured resource costs

**9 November 2026 • Full Task-3 statistical checkpoint • NQ-specific Task-10 resource checkpoint**

## Source and verification

The owner supplied the complete JSON emitted by `scripts/nq_paired_statistics_offline.py`. The report has status `VERIFIED_OFFLINE_PAIRED_NQ_ANALYSIS_EXPLORATORY`, with **300 unique matched evaluation question IDs**, **2,400 logical clean/poisoned QA observations**, and **2,000 question-cluster percentile bootstrap replicates** at seed `20261109`. The local script reports validating the original frozen plans, prior private aggregate SHA-256 fingerprints, exact response fingerprints, matched question anchors, and direct recomputation of source aggregate means. It did **not** run new model inference. In this GitHub publication, the provided full aggregate was independently checked for **internal arithmetic consistency** across all **35** comparisons and for complete resource fields; private QA journals were not externally available for re-execution.

All observed mean outcome denominators are **300 questions per retriever × intensity**, with 300 observations in each clean and poisoned condition. Target-match numerator counts are **48/300 Dense and 50/300 RCD in I1; 126/300 Dense and 129/300 RCD in I3**. Poisoned EM numerators are **83/300 for both retrievers in I1; 54/300 Dense and 51/300 RCD in I3**. These numerators are derivable from the source aggregate and verified against the public I1/I3 reports. See accompanying [complete sanitized machine-readable aggregate](../paper/results/nq_lexical_i1_i3_paired_2026-11-09/full_comparisons_resource_public.json).

Source-file SHA pins (hashes, **not source-data dumps**):
- Intensity 1 original private aggregate: `0126f5998d07b5f0430d93f1fcf610dc7118b819b385065bcca60e02188b9ac9`.
- Intensity 3 original private aggregate: `146cb2749ab01bb5e5d70c06c2041f34dcf36db0fafa2443c3deb021f50e8dc5`.

## Paired analysis: RCD minus Dense within each intensity

All deltas are matched on the **same question**, not calculated from independent arms. “pp” means percentage points. F1 differences are unscaled F1 scores (range 0–1).

| Metric (RCD − Dense) | Intensity 1 Δ | I1 nominal 95% CI | Intensity 3 Δ | I3 nominal 95% CI |
|---|---:|---:|---:|---:|
| Poisoned EM | 0.00 pp | [-3.00 pp, 3.00 pp] | -1.00 pp | [-3.67 pp, 1.67 pp] |
| Poisoned F1 | 0.0027 | [-0.0280, 0.0328] | -0.0069 | [-0.0307, 0.0178] |
| Target-answer match | 0.67 pp | [-2.67 pp, 4.00 pp] | 1.00 pp | [-2.00 pp, 4.33 pp] |
| Poison visible top 3 | -4.00 pp | [-6.67 pp, -1.67 pp] | -0.67 pp | [-3.00 pp, 1.67 pp] |
| Clean-correct → poisoned-wrong | 0.67 pp | [-2.33 pp, 3.67 pp] | 2.33 pp | [-0.67 pp, 5.33 pp] |
| Clean EM | 1.00 pp | [-1.67 pp, 3.67 pp] | 1.00 pp | [-1.67 pp, 3.67 pp] |
| Clean F1 | -0.0029 | [-0.0267, 0.0216] | -0.0029 | [-0.0267, 0.0216] |

**Interpretation:** At I1, RCD exposure is lower by 4.00 pp (nominal CI [−6.67, −1.67] pp), but target matching and poisoned answer accuracy do not show a corresponding reliable advantage. At I3, exposure difference and all other RCD-versus-Dense intervals span zero. Neither result proves pipeline equivalence. The I1 exposure interval is **not corrected for multiple comparisons** and should not be presented as a multiplicity-adjusted discovery.

## Within-pipeline change as lexical intensity increases from 1 to 3

| Outcome (I3 − I1) | Dense Δ | Dense nominal 95% CI | RCD Δ | RCD nominal 95% CI |
|---|---:|---:|---:|---:|
| Poisoned EM | -9.67 pp | [-13.67 pp, -5.67 pp] | -10.67 pp | [-14.67 pp, -6.67 pp] |
| Poisoned F1 | -0.1409 | [-0.1829, -0.1024] | -0.1505 | [-0.1932, -0.1093] |
| Target-answer match | 26.00 pp | [20.33 pp, 31.67 pp] | 26.33 pp | [21.00 pp, 32.00 pp] |
| Poison visible top 3 | 4.67 pp | [2.33 pp, 7.33 pp] | 8.00 pp | [5.00 pp, 11.00 pp] |
| Clean-correct → poisoned-wrong | 10.00 pp | [6.33 pp, 13.67 pp] | 11.67 pp | [8.00 pp, 15.67 pp] |
| Clean EM | 0.00 pp | [0.00 pp, 0.00 pp] | 0.00 pp | [0.00 pp, 0.00 pp] |
| Clean F1 | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |

Both pipelines exhibit **more target-answer matching** and **worse poisoned-answer accuracy** at intensity 3. Clean outcomes are identical between intensities in this recorded paired evaluation; that is not an assertion that independent retraining or model responses would always be invariant.

## Pipeline × intensity difference-in-differences

| Outcome: (RCD−Dense) change from I1 to I3 | Δ | Nominal 95% CI |
|---|---:|---:|
| Poisoned EM | -1.00 pp | [-5.00 pp, 2.67 pp] |
| Poisoned F1 | -0.0096 | [-0.0488, 0.0283] |
| Target-answer match | 0.33 pp | [-4.67 pp, 5.00 pp] |
| Poison visible top 3 | 3.33 pp | [0.00 pp, 6.67 pp] |
| Clean-correct → poisoned-wrong | 1.67 pp | [-1.33 pp, 5.00 pp] |
| Clean EM | 0.00 pp | [0.00 pp, 0.00 pp] |
| Clean F1 | 0.0000 | [0.0000, 0.0000] |

**No nondegenerate interaction interval excludes zero.** For clean EM and clean F1 the paired difference is identically zero in this frozen dataset and the nominal interval is [0,0]; this is a structural property of the comparison, not evidence that the pipelines are generally equivalent.

## Measured efficiency and resource accounting — NQ cohort only

All listed values are averages over **both clean and poisoned questions** within each retriever × intensity condition; each component has **300/300 available records** per condition. The latencies are measured on the experiment's local MLX/hardware configuration, not production cloud costs.

| Mean per QA request, average of clean & poisoned | I1 Dense | I1 RCD | I3 Dense | I3 RCD |
|---|---:|---:|---:|---:|
| Retrieval latency (ms) | 12.31 | 101.06 | 11.93 | 100.58 |
| Model generation latency (s) | 3.26 | 3.18 | 3.08 | 2.97 |
| Reported inner retrieval operations | 1 | 5 | 1 | 5 |
| Prompt tokens | 370.46 | 360.08 | 343.61 | 332.66 |
| Completion tokens | 5.10 | 4.99 | 5.07 | 5.03 |

- RCD retrieval latency is **8.21× Dense** at I1 and **8.43× Dense** at I3. RCD reports **5 inner retrieval operations** versus **1** for Dense in every measured condition.
- Model generation times are broadly comparable (around 2.6–3.4 seconds per QA condition). On this local hardware, **generation dominates per-request latency**, even though RCD costs more retrieval work.
- **Do not infer dollars per query**: this was local MLX inference and this record has no calibrated electricity, cloud/GPU rate, memory peak, full indexing cost or integrated end-to-end concurrency benchmark. Other datasets have not been unified into this cost audit.

## Statistical and construct-validity limitations

1. The 35 reported comparisons are **nominal, exploratory, percentile 95% question-cluster bootstrap intervals**. They have **no multiple-comparison adjustment**; this report does not add invented p-values, familywise claims or confirmatory tests.
2. “Target-answer matching” means a generator answer matches the attacker's target string. It does **not** guarantee the target is factually false or that the causal route is certified without source-backed adjudication.
3. The experiment uses pooled NQ long-answer candidate passages, not official large-scale Wikipedia NQ retrieval. Sampling and historical exposure risks remain; an untouched confirmatory cohort is not independently certified.
4. Recomputed aggregate and response-hash checks were executed on the operator's Mac. This publication verifies **internal arithmetic and structure** of the uploaded aggregate, not full independent custody/source authentication for 2,400 original model executions.
5. This completes the **NQ matched paired statistical analysis (master Task 3)** to its exploratory-reporting standard; it does not close the separate semantic attack, iterative retrieval, authentic detection, robustness, source factuality, cross-dataset resource, end-to-end validity or final public research package work.
6. All experimental raw rows, original targets, prompts, model outputs and private journals remain outside GitHub. Public numbers are sufficient to reproduce report tables; recomputing the bootstrap from raw questions requires authorized access to the separately retained private artifacts.

## Related publications

- [Intensity 1 results](NQ_LEXICAL_INTENSITY_1_RESULTS_2026-11-09.md)
- [Intensity 3 results](NQ_LEXICAL_INTENSITY_3_RESULTS_2026-11-09.md)
- [Initial selected paired statistics](NQ_LEXICAL_I1_I3_PAIRED_STATISTICS_2026-11-09.md)

This expanded report is additive; the earlier selected-statistics checkpoint was correct but incomplete in scope.
