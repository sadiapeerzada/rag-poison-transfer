# 2Wiki RCD component ablations V1 — exploratory results and scientific interpretation

**Research:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Date:** 9 November 2026  
**Study status:** Completed **exploratory**, post-hoc, mechanically-valid-only ablation; **not** confirmatory, not independently adjudicated semantic truth, and not an attempted-population ASR estimate.

## Source and reproducibility

- Evidence: operator-provided aggregate of 480 **new, completed** Qwen 64-token greedy QA observations, six RCD variants, four attack-family/intensity cells, ten selected query-stratum positions per cell, matched clean and poisoned conditions.
- Input aggregate SHA-256: `9ae68bd2050bef08782d4bc96ba924ffa936d3e7f8d096aa550af964d2bb9466`. The private source file and all per-request checkpoints remain **outside public GitHub**. This report is derived from the supplied aggregate, rather than a second run of the inference experiment.
- Initial 2Wiki retrieval preparation independently matched **80/80** original k=3 RCD baseline evidence comparisons according to the operator run receipt; original test corpus and frozen held-out artifacts were not modified.
- Original frozen 2Wiki protocol SHA-256: `40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4`; evaluation completion SHA-256: `db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519`. Private prompt-plan hash is held with the operator and not redistributed.
- Public aggregate: [`aggregate_public.json`](../paper/results/2wiki_rcd_ablation_v1_2026-11-09/aggregate_public.json). Machine-readable group data: [`stratum_metrics.csv`](../paper/results/2wiki_rcd_ablation_v1_2026-11-09/stratum_metrics.csv); paired intervals: [`paired_nominal_intervals.csv`](../paper/results/2wiki_rcd_ablation_v1_2026-11-09/paired_nominal_intervals.csv). These contain only summary statistics, not question IDs, prompts or model replies.

## Experiment and denominators

The variants are `full_k3` (unaltered composite RCD), `no_rewrites_k3`, `no_agreement_k3`, `no_conflict_k3`, `full_k1` and `full_k5`. Candidate-retrieval depth stays 10; k=1,3,5 refers to **generator-visible evidence count**, not candidate pool size.

Each group contains ten selected valid question positions and their matched clean/poisoned outputs. The four cells share some question IDs and reuse the original seed 42. **Forty positions per variant are not forty independent random test queries.** The 40 poisoned observations per variant exclude failed poison constructions. Poison visibility means a known injected poison document ID appears in the generator-visible evidence; it does not establish a source's factual falsity.

## Aggregate descriptive outcomes

| Variant | Clean EM ↑ | Poisoned EM ↑ | Poisoned target matches ↓ | Poison visible ↓ | Mean clean F1 ↑ | Mean poisoned F1 ↑ | Internal retrieval calls ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| `full_k3` | 7/40 (17.5%) | 5/40 (12.5%) | 30/40 (75.0%) | 38/40 (95.0%) | 0.312 | 0.163 | 320 |
| `no_rewrites_k3` | 8/40 (20.0%) | 4/40 (10.0%) | 31/40 (77.5%) | 38/40 (95.0%) | 0.337 | 0.138 | 160 |
| `no_agreement_k3` | 8/40 (20.0%) | 5/40 (12.5%) | 31/40 (77.5%) | 37/40 (92.5%) | 0.342 | 0.151 | 320 |
| `no_conflict_k3` | 7/40 (17.5%) | 4/40 (10.0%) | 31/40 (77.5%) | 38/40 (95.0%) | 0.312 | 0.138 | 320 |
| `full_k1` | 8/40 (20.0%) | 1/40 (2.5%) | 27/40 (67.5%) | 29/40 (72.5%) | 0.366 | 0.102 | 320 |
| `full_k5` | 10/40 (25.0%) | 6/40 (15.0%) | 30/40 (75.0%) | 39/40 (97.5%) | 0.448 | 0.194 | 320 |

### Target matches by attack and intensity

| Attack / intensity | Full k=3 | No rewrites | No agreement | No conflict | Full k=1 | Full k=5 |
|---|---:|---:|---:|---:|---:|---:|
| Lexical · intensity 1 | 6/10 | 7/10 | 7/10 | 7/10 | 8/10 | 6/10 |
| Lexical · intensity 3 | 8/10 | 8/10 | 8/10 | 8/10 | 7/10 | 8/10 |
| Semantic · intensity 1 | 6/10 | 6/10 | 7/10 | 6/10 | 6/10 | 7/10 |
| Semantic · intensity 3 | 10/10 | 10/10 | 9/10 | 10/10 | 6/10 | 9/10 |

Target matching is matching the preselected attack target string, **not** necessarily a causal attack flip from a previously correct answer. Higher EM/F1 is better; lower target matching or exposure is preferable, conditional on retained utility.

## Mechanism interpretation and negative findings

1. **Evidence-depth reduction has the largest observed target-matching change, with a clear utility cost.** `full_k1` decreased target matches from 30/40 (75.0%) at full k=3 to 27/40 (67.5%), and poison visibility from 38/40 (95.0%) to 29/40 (72.5%). However, poisoned EM decreased from **5/40 (12.5%) to 1/40 (2.5%)**. This is a security–utility trade-off, **not** a claim that k=1 is a better defense.
2. **Query rewriting had limited observed impact on target answers in this subset, despite added retrieval cost.** `no_rewrites_k3` recorded 31/40 target matches versus 30/40 at full k=3, with **160** internal retrieval calls versus **320**. Both had 38/40 poison-visible cases. Rewrites are not proven redundant across unobserved datasets, seeds or attack families.
3. **Cross-retriever agreement and temporal conflict features showed small and inconsistent effects.** `no_agreement_k3` and `no_conflict_k3` each produced 31/40 target matches versus full RCD's 30/40. The conflict feature is a narrow year-disagreement heuristic, not a general semantic contradiction detector. The experiment does not support strong attribution or a universal benefit for either component.
4. **Increasing depth to five did not lower target matches.** `full_k5` produced 30/40 targets, raised visible poison to 39/40 and increased clean EM to 10/40. Larger contexts can improve useful answer coverage and increase contaminated evidence exposure simultaneously.
5. **Semantic intensity 3 warrants follow-up, not a headline claim.** Full k=3 produced 10/10 target matches, versus 6/10 at k=1. The nominal paired-bootstrap interval for `full_k3 − full_k1` is **+10 to +70 percentage points**; this is one of 20 unadjusted planned contrasts and is exploratory.

## Paired uncertainty and limits of this aggregate

- The attached public aggregate contains **20** per-cell paired, question-bootstrap intervals (2,000 replicates each). They are **nominal, not corrected for multiple comparisons**. Only the semantic intensity-3 k=1 contrast strictly excludes zero at nominal 95%.
- Several zero-width intervals arise from **zero observed paired differences in ten cases**, and should not be interpreted as population-level certainty.
- This aggregate has **group sums, not per-question assignments**. It cannot support a new pooled, cross-cell query-cluster bootstrap, exact matched flip table or robust latency outlier analysis without accessing the original private per-request checkpoint files.
- Mechanically valid construction is not independently source-verified false evidence; the 131-case qualitative packet is AI-assisted rather than human adjudicated. Report construction failures in the separate original attempted-population study, never as defense successes.
- The original historical 2Wiki study was exposure-risk-disclosed and the ablation questions are post-hoc selected. **These results must not be pooled with the frozen original held-out results as independent confirmations.**

## Efficiency (observed, not hardware-general)

| Variant | Mean measured retrieval seconds / QA observation | Mean measured generation seconds / QA observation |
|---|---:|---:|
| `full_k3` | 0.0349 | 3.59 |
| `no_rewrites_k3` | 0.0174 | 3.71 |
| `no_agreement_k3` | 0.0361 | 4.02 |
| `no_conflict_k3` | 0.0360 | 4.06 |
| `full_k1` | 0.0351 | 13.88 |
| `full_k5` | 0.0354 | 18.20 |

Two group-level generation means are extremely high (about **48.2 seconds** for semantic intensity 1 / k=1 and **52.6 seconds** for semantic intensity 3 / k=5). Do not infer intrinsic k=1/k=5 latency penalties from these averages: inspect the private per-request timings, startup/scheduler effects, and token output distribution first. Retrieval durations may exclude corpus/index construction. The no-rewrite call reduction is a measured count; duration reductions are environment-specific.

## Recommended scientific conclusion

> In a small exploratory sample of mechanically valid 2Wiki knowledge-poisoning constructions, removing individual RCD scoring components or query rewriting produced little consistent change in target-answer matching. Restricting the evidence passed to generation reduced poison exposure and sometimes target matching but also reduced poisoned-condition answer accuracy. Thus, these ablations do not establish universal RCD superiority; they instead expose a retrieval-depth, robustness and clean-utility trade-off.

## Follow-up for final paper

Recompute pooled matched comparisons with source question IDs, query-level clustered uncertainty, a declared multiple-testing strategy, response-flip and poison-exposure cross-tabs, and per-response latency quality checks **offline**, using the existing private checkpoints only; no new Qwen inference is required for these audits. Keep the paper's separate Natural Questions, adaptive/iterative retrieval, and poison-detection work scoped to separately frozen experiments. See [original 2Wiki primary study](2wiki_300_dense_rcd_scientific_results_2026-11-08.md) for broader attempted-population results.
