# Natural Questions lexical intensity 3 — completed matched Dense–RCD QA

**Date:** 9 November 2026  
**Study:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Status:** **COMPLETED, AGGREGATED — EXPLORATORY**. The Mac operator's terminal receipt reports 1,200 of 1,200 sealed QA requests verified, followed by a successful aggregate. This public report has not independently re-read private QA journals.

## Frozen protocol and provenance

- **Evaluation cohort:** 300 distinct frozen Natural Questions validation questions (plus separate 50-question development set), using pooled NQ long-answer candidate passages. The corpus is **not** the full Wikipedia open-domain NQ index.
- **Attack:** lexical influential-token poisoning, intensity **3** (three poison documents per evaluation question as recorded in the construction protocol). The target assignments are frozen and shared with the separate intensity-1 experiment. A non-gold target is not independently proven factually false.
- **QA design:** each question × Dense/RCD × clean/poisoned = **1,200 real model-call observations**, paired by the **300 question IDs**. RCD uses the frozen Dense-primary/BM25-auxiliary composite configuration.
- **Generator:** local MLX Qwen2.5-7B-Instruct-4bit, greedy 64-token QA per frozen plan. The terminal receipt is evidence of completed execution, not independent local model-file rehashing.
- **Final log:** `ALL_QA_REQUESTS_VERIFIED`, `completed: 1200`, `planned: 1200`, `remaining: 0`; subsequent `COMPLETE_EXPLORATORY_SEALED_NQ_LEXICAL_QA` with `qa_calls_verified: 1200`.

| Private artifact | SHA-256 *reported by operator* |
| --- | --- |
| Frozen NQ cohort manifest | `1b99fe49fff3b1224c6351fb20f58897e0e664a69c33a6400b4a56855c05f8c7` |
| Target assignments | `f6bd7dd19fab2093d6730f51cb55e8980ce4d6543d71e1514a7c876c888c54bc` |
| Intensity-3 poison construction | `4de1da06acd16486ac8c901475606b8d06a6795688e66064f048be8192936ae2` |
| Intensity-3 QA plan | `53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2b8f46d968a2e7b5` |
| Private intensity-3 aggregate JSON | `146cb2749ab01bb5e5d70c06c2041f34dcf36db0fafa2443c3deb021f50e8dc5` |

The private aggregate SHA is not the SHA of [the sanitized public JSON](../paper/results/nq_lexical_i3_2026-11-09/aggregate_public.json). Private identifiers, poisoned documents, prompts, response journals, query-level outputs and any locally identifying paths are not committed.

## Final intensity-3 results

| Metric | Dense | RCD | Descriptive RCD − Dense |
| --- | ---: | ---: | ---: |
| Clean exact match | 94/300 (**31.33%**) | 97/300 (**32.33%**) | +1.00 pp |
| Poisoned exact match | 54/300 (**18.00%**) | 51/300 (**17.00%**) | −1.00 pp |
| Clean F1 | **0.43558** | **0.43272** | −0.00287 |
| Poisoned F1 | **0.23787** | **0.23094** | −0.00693 |
| Target-answer matching (runner's `targeted_asr` field) | 126/300 (**42.00%**) | 129/300 (**43.00%**) | +1.00 pp |
| Injected poison visible in generator top 3 | 267/300 (**89.00%**) | 265/300 (**88.33%**) | −0.67 pp |
| Clean-correct → poisoned-wrong answer flips | **49** | **56** | +7 cases |

Target-answer matching is **not necessarily independently source-verified false-answer ASR**. The results are descriptive; no paired uncertainty interval is derived from these group totals alone.

## Across-intensity descriptive comparison

The prior completed [intensity-1 results report](NQ_LEXICAL_INTENSITY_1_RESULTS_2026-11-09.md) uses the same nominal 300 frozen evaluation questions and the shared target-assignment seal.

| Outcome | I1 Dense | I3 Dense | I1 RCD | I3 RCD |
| --- | ---: | ---: | ---: | ---: |
| Poisoned EM | 27.67% | **18.00%** | 27.67% | **17.00%** |
| Poisoned F1 | 0.37881 | **0.23787** | 0.38146 | **0.23094** |
| Target-answer matching | 16.00% | **42.00%** | 16.67% | **43.00%** |
| Poison visible in top 3 | 84.33% | **89.00%** | 80.33% | **88.33%** |
| Clean-correct → poisoned-wrong flips | 19 | **49** | 21 | **56** |

At intensity 3, both pipelines exhibited substantially more target-answer matching and worse poisoned-answer accuracy. The clean-EM and clean-F1 group means were stable across intensities. These observations support describing a **descriptive dose response** within the two frozen constructions, but **not** a causal intensity effect or statistically significant pipeline difference without per-question paired comparisons, an appropriate uncertainty model and validity review.

**RCD does not show a uniform defense advantage in these results:** its poisoned EM and target-answer matching were descriptively worse than Dense at intensity 3. Reduced top-3 poison visibility alone does not imply lower attack success.

## Interpretation and validity boundaries

1. **Paired statistics pending (master task 3):** raw private question-level matched rows are necessary for question-cluster bootstrap confidence intervals, joint I1/I3 interaction comparisons, exact discordances and multiplicity handling. Do not compute fictitious p-values or infer significance from aggregate point differences.
2. **Historical exposure unresolved:** freezing this evaluation cohort did not establish that it was never inspected or used in past development. Keep the work labeled exploratory, not untouched prospective test.
3. **False evidence not source-adjudicated:** the generated target is non-gold by construction; its actual factual falsity, aliases and answer-type ambiguity need source-backed checks. Do not conflate target matching, poison exposure, clean-to-wrong flips or verified attack-induced false outputs.
4. **Passage-index benchmark:** pooled NQ long-answer candidates constitute a restricted document pool, not the conventional large-scale Wikipedia index. Sampling via streaming and shuffle is nonuniform.
5. **Private output integrity:** the reported 1,200-call receipt and SHA pins should be reverified against the Mac's private files for final reproducibility. The public report is an exact aggregate transcription, not an independent per-request audit.
6. **Not project closeout:** intensity-3 completion closes **master task 2**, but semantic poisoning, actual adaptive retrieval, poison detection, robustness, audit and full results publication remain open. This PR is not a substitute for the final cross-study PR.

## Publication artifacts and checklist

- [Sanitized intensity-3 JSON aggregate](../paper/results/nq_lexical_i3_2026-11-09/aggregate_public.json).
- [Completed intensity-1 report](NQ_LEXICAL_INTENSITY_1_RESULTS_2026-11-09.md) and its separate public aggregate.
- **Task 1: Complete. Task 2: Complete. Task 3: Pending full paired analysis. Tasks 4–12: retain their separate completion criteria.**

The researcher's professor prepares the paper. This repository update preserves the experimentally grounded evidence and explicit caveats for later manuscript use.
