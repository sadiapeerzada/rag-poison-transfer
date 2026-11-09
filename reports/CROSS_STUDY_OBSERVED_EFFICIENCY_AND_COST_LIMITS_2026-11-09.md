# Cross-study measured resource and efficiency ledger — 9 November 2026

**Research:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Scope:** Exploratory **observed resource-cost proxies** from four independently recorded checkpoints. **No new model inference or rerun was performed.**

## Executive conclusion

The paper can report local **retrieval time, QA generation/wall time, inner retrieval operations, and actual-versus-logical backend call accounting** from existing logs. These show a non-trivial robustness–utility–work trade-off. **It cannot responsibly report cloud dollars per query, platform-invariant speedups, hardware-normalized throughput, or a single pooled cross-dataset latency effect**: those measurements are absent or incomparable.

The [machine-readable aggregate-only ledger](../paper/results/cross_study_efficiency_2026-11-09/observed_efficiency_public.json) is derived exclusively from previously published measurements and pins each public input path. No raw questions, poisoned text, private response logs or personal device paths are included.

## 1. Natural Questions lexical single-hop comparison

Source: [NQ full paired and resource report](NQ_LEXICAL_I1_I3_FULL_PAIRED_AND_EFFICIENCY_2026-11-09.md); frozen 300-question cohort, I1 and I3, Dense vs RCD, clean and poisoned QA, local MLX Qwen. Each intensity/retriever's resource mean averages **300 clean + 300 poisoned** records with 300/300 available for each condition. Results are matched but **these are descriptive resource measurements, not randomized timing trials**.

| NQ lexical condition | Dense retrieval (ms) | RCD retrieval (ms) | Dense inner ops | RCD inner ops | Dense generation (s) | RCD generation (s) | Poisoned EM (Dense / RCD) | Target match (Dense / RCD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Intensity 1 | 12.31 | 101.06 | 1 | 5 | 3.26 | 3.18 | 27.7% / 27.7% | 16.0% / 16.7% |
| Intensity 3 | 11.93 | 100.58 | 1 | 5 | 3.08 | 2.97 | 18.0% / 17.0% | 42.0% / 43.0% |

- RCD's measured **retrieval** component is ~**8.21×** Dense at I1 and ~**8.43×** Dense at I3, with **five versus one reported inner retrieval operations** per QA. This difference must **not** be described as an 8× end-to-end slowdown: the generation component (~3s/request) is much larger.
- The poisoned-answer EM and target-match columns show why a work increase is not justified by a demonstrated RCD security advantage in this cohort: the published RCD−Dense answer-outcome nominal CIs include zero.
- These NQ runs use a restricted pooled long-answer-candidate passage corpus, not full Wikipedia NQ; historical exposure/unseen-data certification is unavailable.

## 2. Exploratory 2Wiki RCD component ablations

Source: [audited 2Wiki RCD ablations](2wiki_rcd_ablation_v1_question_cluster_audit_2026-11-09.md). **480** true completed local QA observations, **240** matched clean/poison pairs, six variants, 40 selected attack/intensity cell positions per variant but only **36 distinct question IDs** across the four cells. These post-hoc, valid-construction-only outcomes are not a random draw from all construction attempts.

| 2Wiki exploratory RCD variant | Retrieval (ms) | Generation mean (s) | Median (s) | p95 (s) | Inner ops/QA | Poison exposure | Poisoned EM | Target match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full RCD k=3 | 34.90 | 3.59 | 3.29 | 6.27 | 4 | 95.0% | 12.5% | 75.0% |
| No rewrites k=3 | 17.42 | 3.71 | 3.38 | 6.48 | 2 | 95.0% | 10.0% | 77.5% |
| No agreement k=3 | 36.06 | 4.02 | 3.51 | 7.22 | 4 | 92.5% | 12.5% | 77.5% |
| No conflict k=3 | 35.97 | 4.06 | 3.58 | 7.09 | 4 | 95.0% | 10.0% | 77.5% |
| Full RCD k=1 | 35.15 | 13.88 | 2.39 | 5.15 | 4 | 72.5% | 2.5% | 67.5% |
| Full RCD k=5 | 35.35 | 18.20 | 6.53 | 13.78 | 4 | 97.5% | 15.0% | 75.0% |

- Removing rewrites from k=3 reduces measured mean retrieval latency from **34.90 ms** to **17.42 ms** and inner operations from **4** to **2**, but does **not** establish improved poisoned accuracy or reduction in attack-target matching. This is an observed component-cost reduction in the selected subset, not a validated new defense.
- At k=1, poison exposure drops from 95.0% to 72.5%, while poisoned EM drops from 12.5% to 2.5%; this is a **security–utility trade-off**, not an unconditional improvement.
- Two extreme generation timings (~**903s** in k=1, ~**914s** in k=5) inflate raw generation means. Typical recorded times are better reflected by median and p95; neither extreme is removed from the audit.
- Retrieval timings originated during prompt preparation; generation timings came from separate recorded model execution. Do not sum them into a certified concurrent end-to-end service latency.

## 3. Historical HotpotQA Week 9 retrieval/QA checkpoint (October 2026)

Source: [archived Week 9 `latency_and_calls.csv`](../paper/results/hotpotqa_week9_2026-10-26/latency_and_calls.csv), **24** rows across 12 attack/intensity/seed cells, two target retrievers (Dense, RCD). The aggregation weights each cell by the reported **normal clean+poison retrieval-call count** and excludes separately logged diagnostic retrievals. It represents **955 selected valid attack/intensity/seed positions and 1,910 normal QA observations per retriever**; repeated underlying questions or seeds are **not independent test samples**.

| Source scope | Dense mean normal retrieval (ms) | RCD mean normal retrieval (ms) | Dense inner ops/QA | RCD inner ops/QA | Dense QA wall (s) | RCD QA wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| All Week 9 cells, selection-weighted | 160.00 | 202.08 | 1.00 | 4.03 | 3.63 | 3.51 |
| Lexical cells only | 126.40 | 94.72 | 1.00 | 4.02 | 3.57 | 3.60 |
| Semantic cells only | 347.74 | 801.83 | 1.00 | 4.04 | 3.97 | 2.96 |

The historical Week 9 weighted normal-retrieval time ratio is **1.26× RCD/Dense**, **not** the NQ ratio. Its lexical-cell mean actually favors RCD retrieval time while semantic-cell mean disfavors it; variability and selection are substantial, and the pools have different counts. The QA wall-time measures are also not identical to the NQ per-generation seconds.

**Timing data-quality warning:** Five condition/cell entries have a reported *model_seconds_mean* exceeding their *QA_wall_seconds_mean* by more than 50%, including early lexical and semantic cells. That cannot be understood as a coherent same-boundary timing decomposition without further clock/source investigation. Therefore **model-reported seconds were excluded** from the weighted summary; only source-labelled QA wall and retrieval timing appear here. These entries should not be used for calibrating cost claims.

## 4. Later HotpotQA held-out cross-pipeline transfer experiment

The separate [HotpotQA transfer public aggregate](../paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json) reports:
- **41,000 logical generation observations**.
- **21,175 actual physical backend calls**.
- **19,825 clean-condition cache hits**; the arithmetic matches logical minus actual calls.

This establishes the actual-versus-logical *call accounting* for the cached experimental design; it does **not** provide calibrated per-call compute time, a machine-independent generator cost, or a new independent model-evaluation sample of 41,000 physical calls. It is **not** the same checkpoint as the October Week 9 timing table; do not combine its population or cache accounting with Week 9 seconds.

## 5. Original 2Wiki 300-query study and missing costs

The original [2Wiki 300-query Dense/RCD scientific results](2wiki_300_dense_rcd_scientific_results_2026-11-08.md) reports paired QA outcomes, but a source-verified, directly comparable public per-request timing/call-cost export is **not currently available** in the evidence reviewed here. The separate 480-call ablation does **not** fill that original 300-query execution's cost series. Mark the original 2Wiki production-representative efficiency endpoint **unmeasured**.

Further unavailable inputs across these studies: calibrated monetary energy/cloud costs, GPU-hours and pricing, peak RAM/Metal memory, cold corpus/index construction cost, backup/storage accounting, concurrency-tail latency, repeated-run hardware calibration, source-based poison factuality, and unbiased attack-population selection.

## 6. Manuscript-ready scientific takeaway

> In the observed local RAG evaluation checkpoints, increasing retrieval work did not consistently improve answer robustness against knowledge poisoning. The NQ single-hop paired study measured higher RCD retrieval cost with no demonstrated accuracy or target-match advantage; the 2Wiki exploratory ablations showed that removing rewrites roughly halved measured retrieval operations and latency without clear improvements in attack resistance, while reducing evidence depth lowered poison exposure at a substantial utility cost. HotpotQA historical timings varied by attack family and should not be pooled with the other experiments. These findings motivate explicit cost–quality accounting and caution against claiming universal retrieval defense superiority.

**Task 10 status:** Complete as a **source-backed observational efficiency and computational-work ledger**. **NOT** a verified monetary cost, portable end-to-end service benchmark, or full multi-dataset same-protocol timing comparison. All such missing evidence is explicitly retained as a limitation for the manuscript and final audit.

**Reproducibility:** Every table is derived from the listed public inputs; this report adds no model calls, results of unseen experiments, independent truth review or statistical significance claims.
