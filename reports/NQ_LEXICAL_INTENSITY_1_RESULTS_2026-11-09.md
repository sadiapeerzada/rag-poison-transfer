# Natural Questions lexical intensity 1: matched Dense–RCD QA results

**Project:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Date:** 9 November 2026  
**Status:** **COMPLETED AND AGGREGATED — EXPLORATORY** (operator-verified 1,200/1,200 inference requests).  
**Evidence boundary:** This report records the researcher's terminal completion receipt and generated aggregate. It is **not** an independent reanalysis of private response journals or certification of semantic truth.

## Design and immutable provenance

- **Benchmark:** 300 frozen Natural Questions validation questions, from a separately frozen 50-development/300-evaluation cohort. The retrieval corpus consists of pooled **NQ long-answer candidate passages**; it is **not** the standard open-domain Wikipedia-index benchmark.
- **Attack:** one sealed lexical injected document per evaluation query (intensity **1**), constructed with deterministic non-gold target assignments. Non-gold targets do **not** prove factual falsehood.
- **Retrieval / QA comparison:** Dense versus the frozen composite RCD (Dense primary with auxiliary BM25), both under **clean** and **poisoned** evidence conditions. The runner specifies local MLX Qwen2.5-7B-Instruct-4bit, greedy generation with a 64-token limit; exact local model-file fingerprints remain in the private provenance.
- **Denominator:** 300 question IDs × 2 arms × 2 conditions = **1,200 logical real QA calls**. There are **300 distinct evaluation questions**, not 1,200 independent observations. Both arms use the same frozen question and attack-target assignments.
- **Execution receipt:** operator log reported `ALL_QA_REQUESTS_VERIFIED` with `completed=1200`, `planned=1200`, `remaining=0`. Final aggregation returned `COMPLETE_EXPLORATORY_SEALED_NQ_LEXICAL_QA` and `qa_calls_verified=1200`.

### Recorded SHA-256 identifiers (operator-provided)

| Artifact | Reported SHA-256 |
| --- | --- |
| NQ cohort manifest | `1b99fe49fff3b1224c6351fb20f58897e0e664a69c33a6400b4a56855c05f8c7` |
| Non-gold target assignments | `f6bd7dd19fab2093d6730f51cb55e8980ce4d6543d71e1514a7c876c888c54bc` |
| Lexical intensity-1 construction | `745bbba2a917db8271c111c55d66fd805c5f5e9b371a7c906ea7d93e9495a1ee` |
| Matched intensity-1 QA plan | `66104bd1b922bd79a465593cb134b12820b71271fba08567c4bc529dd912f6c6` |
| **Private** intensity-1 aggregate JSON | `0126f5998d07b5f0430d93f1fcf610dc7118b819b385065bcca60e02188b9ac9` |

The SHA on the final row refers to the **private source aggregate**, **not** the public summarized JSON in this PR. This publication reproduces values from the provided completion receipt; the private bytes and per-query records were not made available to independently recompute hashes, pairwise intervals or individual classifications.

## Observed results

| Metric | Dense | RCD | Descriptive reading |
| --- | ---: | ---: | --- |
| Clean exact match (EM) | 94/300 = **31.33%** | 97/300 = **32.33%** | RCD +1.00 percentage point |
| Poisoned exact match (EM) | 83/300 = **27.67%** | 83/300 = **27.67%** | Equal aggregate poisoned accuracy |
| Clean mean F1 | **0.4356** | **0.4327** | Similar descriptive utility |
| Poisoned mean F1 | **0.3788** | **0.3815** | Similar descriptive utility |
| Target-answer matching (runner field `targeted_asr`) | 48/300 = **16.00%** | 50/300 = **16.67%** | RCD +0.67 pp; lower is preferable |
| Poison visible in generator top 3 | 253/300 = **84.33%** | 241/300 = **80.33%** | RCD −4.00 pp |
| Clean-correct to poisoned-wrong answer flips | **19** | **21** | Counts, not causally validated targeted flips |

### Interpretation

RCD exposed the generator to an injected document **less often** in the visible top-three evidence (80.33% versus 84.33%) but did **not** lower the rate of responses matching the preselected attack target (16.67% versus 16.00%). Both arms had identical poisoned exact-match accuracy (27.67%). This is a descriptive **exposure–outcome mismatch** worth examining, **not** evidence of a statistically significant advantage or disadvantage from these aggregates alone.

The generator may encounter a poison yet ignore it, and an output matching a non-gold target does not by itself establish that a factually false answer was induced. Clean-to-wrong flips are a separate failure measure; do not substitute raw target matching for causally attributable flips.

## Scientific limitations and guardrails

1. **Exploratory, not certified untouched:** the 300-question NQ subset was frozen, but prior historical exposure exclusions were **not** supplied/certified. Dataset streaming/shuffle sampling is not uniform.
2. **Benchmark scope:** the pooled candidate-passage corpus and its gold annotations are not interchangeable with the full open-domain Wikipedia retrieval benchmark; aliases and annotation disagreements may affect EM/F1.
3. **Factual validity:** attack targets are deterministic non-gold strings, **not source-verified factual falsehoods**. No independent semantic adjudication of these targets is claimed.
4. **Uncertainty not yet calculated:** only grouped totals are published here. Proper **paired question-level comparisons**, confidence intervals, discordances and multiplicity policy require the immutable **private** per-question records. Neither a p-value nor equivalence conclusion is supported by this report.
5. **No conflation with other studies:** this NQ lexical-I1 study is a separately versioned extension; it must not be pooled as independent evidence with HotpotQA transfer or historically risk-disclosed 2Wiki replication.
6. **Privacy and reproducibility:** source questions, attack documents, gold targets, exact prompts, per-response texts, per-question IDs and raw journals remain off public GitHub. Local model file hashes and private runtime timing quality checks remain for the later reproducibility audit.

## Public artifact

- [Sanitized machine-readable aggregate](../paper/results/nq_lexical_i1_2026-11-09/aggregate_public.json).

The public aggregate retains denominators, numerator counts and exact reported means. It intentionally excludes identifiers, private inputs, model outputs and any synthetic/pseudo-replicated paired confidence intervals.

## Next steps in the 12-task research closeout

- **Master task 1 — COMPLETE:** NQ lexical intensity 1, 1,200 real QA requests and final aggregate.
- **Master task 2 — IN PROGRESS:** prepare/freeze and finish the distinct **intensity-3** 1,200-call experiment, with no overwrite of intensity-1 outputs.
- **Master task 3 — PENDING:** carry out the paired Dense–RCD analysis on original private matched rows from both intensities, reporting ASR/target-matching, poisoned exposure, EM/F1, target validity, clean-to-wrong flips, paired uncertainty and per-question/attempted-construction denominators.
- **Master tasks 4–12 — NOT CLOSED BY THIS PR:** semantic factuality/attack evaluation, true adaptive retrieval, poison detection, broader robustness, remaining ablations, efficiency, error analysis, final reproducibility audit and final research package publication.

**Supervisor / manuscript handoff note:** These results can be incorporated into the evidence package as an exploratory NQ lexical-I1 result. Professor-led manuscript preparation is outside this PR. Do not advertise the project as entirely completed on the strength of this single stage.
