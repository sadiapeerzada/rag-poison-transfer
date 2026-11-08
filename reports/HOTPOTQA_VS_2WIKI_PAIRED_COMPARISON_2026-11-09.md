# HotpotQA vs 2WikiMultiHopQA: paired Dense/RCD post-run comparison

**Date:** 9 November 2026. **Evidence status:** read-only cross-study reanalysis of the independently audited [HotpotQA Week 9 report](WEEK9_HOTPOTQA_SCIENTIFIC_AUDIT_2026-10-26.md) and the author-provided, frozen validated 2Wiki aggregate (SHA-256 `721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96`). This comparison **does not independently reprocess the full raw HotpotQA files** and does not imply identical protocol implementations or independent semantic validity.

## Study/protocol compatibility

| Dimension | HotpotQA (October 2026) | 2Wiki (November 2026) |
| --- | --- | --- |
| Query IDs | 300 frozen HotpotQA validation `distractor` IDs | 300 frozen 2Wiki IDs; historically risk-disclosed exposure |
| Shared design | two attack families × intensities 1/3 × seeds 42/43/44 | same nominal matrix |
| Paired comparison | Dense vs composite RCD, same constructed poison per query/cell | Dense vs composite RCD, same constructed poison per query/cell |
| Observations | 3,600 attempted query–cell constructions and two arms | 3,600 attempted query–cell constructions and two arms |
| Original source commit | `7a24a40c0a25399e1defc02844eb3a1de44b4a19` | `b1466db04c4f8f0314c7e537d8e7ec390c8c3b29` |
| Integrity evidence | 9,549 construction + 7,665 evaluation files independently audited, per source report | 15,081 construction and 22,446 evaluation files verified by operator; frozen aggregator validated |
| Evaluation provenance | HotpotQA audit: independently recomputed and reviewed from its local raw results | 2Wiki: the aggregate is available here; source operator verified its local raw results, but this comparative report has not independently reloaded those 37k source files |
| Study limitation | bounded *label-conditioned* target nomination; low coverage | same broad label-conditioned limitation; older exposures/custody caveat and different frozen code version |

Only the broad experimental structure and **within-dataset** Dense/RCD comparisons are aligned. Different dataset, query eligibility, observed response distributions, and execution/source commits prevent a causal claim about dataset difficulty, model strength or defense improvements.

## Attempted-population end-to-end targeted ASR

The denominator is **900 attempted query–seed constructions per condition**, including cases with failed target or poison construction. It is **not 900 independent questions**: the inferential unit for frozen paired bootstrap is 300 unique query IDs, retaining all seeds and both arms. Lower ASR is preferable.

| Attack | Hotpot Dense | Hotpot RCD | Hotpot Dense−RCD (pp) | 2Wiki Dense | 2Wiki RCD | 2Wiki Dense−RCD (pp) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical I1 | 143/900 (15.89%) | 155/900 (17.22%) | −1.33 | 382/900 (42.44%) | 428/900 (47.56%) | −5.11 |
| Lexical I3 | 314/900 (34.89%) | 301/900 (33.44%) | +1.44 | 652/900 (72.44%) | 629/900 (69.89%) | +2.56 |
| Semantic I1 | 59/900 (6.56%) | 66/900 (7.33%) | −0.78 | 134/900 (14.89%) | 133/900 (14.78%) | +0.11 |
| Semantic I3 | 45/900 (5.00%) | 45/900 (5.00%) | 0.00 | 104/900 (11.56%) | 104/900 (11.56%) | 0.00 |

Across both studies, RCD is not uniformly better than Dense. The intensity effect is strongly visible in lexical poisoning. These are **within-dataset** estimates, not randomized between-dataset treatment effects.

## Paired 95% query-cluster bootstrap intervals

All intervals are nominal and unadjusted for testing multiple conditions/metrics. A positive Dense−RCD value means the RCD arm had fewer targeted successes.

| Attack | Hotpot point (pp) | Hotpot CI (pp) | 2Wiki point (pp) | 2Wiki CI (pp) |
| --- | ---: | --- | ---: | --- |
| Lexical I1 | −1.33 | [−3.33, +0.56] | −5.11 | [−8.67, −1.78] |
| Lexical I3 | +1.44 | [−0.44, +3.33] | +2.56 | [−1.22, +6.22] |
| Semantic I1 | −0.78 | [−1.89, 0.00] | +0.11 | [−1.00, +1.22] |
| Semantic I3 | 0.00 | [0.00, 0.00] | 0.00 | [−0.56, +0.67] |

The 2Wiki lexical-I1 *nominal* interval excludes zero in the direction **opposite** an RCD benefit. In HotpotQA all four primary intervals include zero (at the boundary for semantic I1); none supports a broad RCD defense claim. A degenerate HotpotQA semantic-I3 interval reflects observed identical arm-level targeted outputs in that condition, **not a proof of pipeline equivalence**.

## Construction feasibility: the primary cross-study confounder

| Construction outcome, 3,600 attempts | HotpotQA | 2Wiki |
| --- | ---: | ---: |
| Mechanically valid constructions | 955 (26.53%) | 1,800 (50.00%) |
| Target construction failures | 1,980 (55.00%) | 552 (15.33%) |
| Semantic construction failures | 665 (18.47%) | 1,248 (34.67%) |
| Target-eligible distinct questions | 135 / 300 (45.00%) | 254 / 300 (84.67%) |
| Lexical mechanically valid per condition | 405 / 900 (45.00%) | 762 / 900 (84.67%) |
| Semantic I1 mechanically valid | 97 / 900 (10.78%) | 167 / 900 (18.56%) |
| Semantic I3 mechanically valid | 48 / 900 (5.33%) | 109 / 900 (12.11%) |

The **per-condition targeted success denominator** includes failed attempts, so changes in target/semantic feasibility can increase end-to-end ASR without any change in the defense's behavior on successful constructions. Compare conditional metrics, not just the headline.

## Valid-only targeted ASR (selection-conditioned)

| Attack | Hotpot Dense | Hotpot RCD | 2Wiki Dense | 2Wiki RCD |
| --- | ---: | ---: | ---: | ---: |
| Lexical I1 | 143/405 (35.31%) | 155/405 (38.27%) | 382/762 (50.13%) | 428/762 (56.17%) |
| Lexical I3 | 314/405 (77.53%) | 301/405 (74.32%) | 652/762 (85.56%) | 629/762 (82.55%) |
| Semantic I1 | 59/97 (60.82%) | 66/97 (68.04%) | 134/167 (80.24%) | 133/167 (79.64%) |
| Semantic I3 | 45/48 (93.75%) | 45/48 (93.75%) | 104/109 (95.41%) | 104/109 (95.41%) |

Valid-only ASR is conditional on a **selected subset**; it is not a propensity-corrected estimate for all questions. The frozen mechanical semantic validator is not an independent factuality oracle. In both datasets, semantic-I3 exhibits very high conditional ASR among very few accepted constructions; interpreting low end-to-end ASR as strong defense robustness would conflate **construction failure** with **defense success**.

## Clean utility, exposure, errors and caveats

- **Clean accuracy is subset-dependent.** Hotpot lexical valid-only clean EM: Dense 59.26%, RCD 55.56%; 2Wiki lexical valid-only: Dense 37.01%, RCD 33.46%. These cannot be called all-300 clean QA baselines; failed constructions have no corresponding paired clean/poison QA in the frozen matched study.
- **2Wiki low-intensity lexical:** Dense target success 382 vs RCD 428 even though the RCD generator was exposed to poisoned documents on 719/762 valid cases versus 733/762 for Dense. This motivates a paired-case disagreement review and must **not** be attributed to a particular RCD component without examining raw evidence.
- **2Wiki high-intensity lexical:** Dense target success 652 vs RCD 629, but the nominal confidence interval for the primary contrast crosses zero. Untargeted degradation is lower for RCD (223/762) than Dense (254/762); this is a descriptive secondary endpoint, not standalone proof of defense efficacy.
- **Semantic falsehood remains unconfirmed independently.** Evaluate a documented, reviewer-judged sample of accepted texts for target assertion, actual falsity, question constraints and gold-answer/alias contradictions. Review rejected semantic generations separately to identify overly conservative validator patterns without post-hoc changing the held-out protocol.
- **Exposure and diagnostic PRR differ.** For RCD, the top-3 generator-visible window and diagnostic top-10 retrieval ranking can differ. Inspect actual `generation_evidence_doc_ids` and source text before discussing how an attack reached the generator.
- **No direct cross-dataset superiority claims**: pooling these two datasets or treating their 600 query IDs as exchangeable without a planned stratified analysis is not supported. Source commits and cohort histories differ.
- **No source-crafted transfer**: these are matched pipeline outcomes on the same preconstructed attack instances, not the planned four-source/five-target transfer matrix.

## Result status and research handoff

**Completed:** the two frozen matched-comparison runs, 2Wiki aggregate validation, aggregate-derived cross-study table, correct failed-construction accounting, and transparent interval interpretation.

**Pending:** verified remotely downloaded/restored **full** 2Wiki archive including construction and evaluation; direct local paired-case export and independent human semantic/answer-quality adjudication; supervisor decision whether to authorize full source-crafted transfer or narrow manuscript scope; publication write-up/figures.

The accompanying tools [`scripts/backup_2wiki_full_run.py`](../scripts/backup_2wiki_full_run.py) and [`scripts/audit_2wiki_paired_cases.py`](../scripts/audit_2wiki_paired_cases.py) prepare these *remaining* checks without modifying the frozen source tree. Do not describe them as completed until the actual operator outputs and review judgments are available.
