# Natural Questions lexical I1/I3: paired Dense–RCD statistical checkpoint

**Date:** 9 November 2026  
**Status:** **OFFLINE QUESTION-PAIRED ANALYSIS VERIFIED; SELECTED STATISTICS PUBLISHED**. The complete local report contains additional paired statistics and resource-accounting data that have not yet been transferred for independent inspection or publication. Do not confuse this checkpoint with closure of all master Task 3 deliverables.

## Provenance

The researcher ran a fail-closed offline Python analyzer on the private Natural Questions intensity-1 and intensity-3 artifacts. Its stdout reported `VERIFIED_OFFLINE_PAIRED_NQ_ANALYSIS_EXPLORATORY`, `source_verified: true`, `n_questions: 300`, and `calls: 2400`. The script checked the two frozen plans and private aggregate SHA-256 values, each source observation's request/prompt fingerprints, complete same-question Dense/RCD clean/poison pairings, unchanged target assignments across intensities, and direct recomputation of the source aggregate means. **No Qwen inference was run during this analysis.**

- Frozen I1 aggregate SHA-256 reported by operator: `0126f5998d07b5f0430d93f1fcf610dc7118b819b385065bcca60e02188b9ac9`.
- Frozen I3 aggregate SHA-256 reported by operator: `146cb2749ab01bb5e5d70c06c2041f34dcf36db0fafa2443c3deb021f50e8dc5`.
- Bootstrap: **2,000** question-cluster replicates, nominal percentile **95% confidence intervals**, resampling **300 matched question IDs** rather than treating 2,400 responses as independent.
- Verification meaning: private records passed the **local script's** source/consistency checks; the raw files were not independently rehashed by the GitHub reviewer.

## Recomputed outcomes by attack intensity

| Metric | I1 Dense | I1 RCD | I3 Dense | I3 RCD |
|---|---:|---:|---:|---:|
| Clean EM | 31.33% | 32.33% | 31.33% | 32.33% |
| Poisoned EM | 27.67% | 27.67% | 18.00% | 17.00% |
| Clean F1 | 0.43558 | 0.43272 | 0.43558 | 0.43272 |
| Poisoned F1 | 0.37881 | 0.38146 | 0.23787 | 0.23094 |
| Poisoned target-answer matching | 16.00% | 16.67% | 42.00% | 43.00% |
| Injected evidence visible in top three | 84.33% | 80.33% | 89.00% | 88.33% |
| Clean-correct → poisoned-wrong | 19/300 | 21/300 | 49/300 | 56/300 |

## Verified selected paired confidence intervals

**Comparison orientation:** RCD minus Dense, where a negative target-match difference corresponds to fewer answers matching the injected target, but does *not* independently establish factual falsehood.

| Matched endpoint | Intensity | Point estimate | Nominal 95% paired bootstrap CI |
|---|---:|---:|---:|
| RCD − Dense poisoned EM | 1 | 0.00 percentage points | [−3.00, +3.00] pp |
| RCD − Dense poisoned EM | 3 | −1.00 pp | [−3.67, +1.67] pp |
| RCD − Dense target matching | 1 | +0.67 pp | [−2.67, +4.00] pp |
| RCD − Dense target matching | 3 | +1.00 pp | [−2.00, +4.33] pp |
| I3 − I1 target matching (Dense) | both | +26.00 pp | [+20.33, +31.67] pp |
| I3 − I1 target matching (RCD) | both | +26.33 pp | [+21.00, +32.00] pp |

The four RCD–Dense intervals include zero. That does **not** establish equivalence or an absence of effect; it means the observed effect is insufficiently precise to determine its sign at nominal 95% confidence. Both across-intensity target-match intervals are clearly positive, consistent with greater attack-target matching for intensity 3 in this experimental cohort.

The CIs are **unadjusted for multiple testing**. Intensity 3 produces more injected documents by construction; observed differences do not certify a generalizable causal dose-response mechanism.

## Scope and limitations

1. This is an **exploratory** study on a frozen 300-question NQ validation subset using pooled long-answer candidates, **not** full Wikipedia open-domain NQ. Historical exposure exclusions are not certified.
2. The poisoned target is **non-gold**, not necessarily a demonstrably false proposition. Thus the original runner's `targeted_asr` field is described here more narrowly as **target-answer matching**, pending source-backed adjudication.
3. No new statistical p-values, significant/insignificant labels from multiple-testing correction, or human factuality judgments were invented.
4. The original private per-question QA inputs, prompts, output texts and response journals remain unpublished. Source hashes identify original private files; the public aggregate has a distinct Git commit/blob identity.
5. The local analyzer also computes paired confidence intervals for F1, poison exposure, clean-correct→poisoned-wrong flips, within-intensity comparison, across-intensity comparison and difference-in-differences; its *full* output and latency/retrieval accounting have **not yet been received**. The present report intentionally claims only selected verified excerpts.
6. Confirm original model/back-end file fingerprints, prompt/answer extraction version, corpus rights, benchmark scope and backup custody in the final reproducibility audit.

## Next closeout action

Export the **full read-only offline analysis JSON** with the original local script's `--output` option under the private results root, inspect it, and publish only sanitized aggregates. This closes the remaining statistical comparisons without rerunning Qwen. Continue tasks 4–12 according to the master research checklist.

**Research tracker:** NQ lexical I1 and I3 model evaluation complete. Task 3 has now **passed source-verified paired statistical execution**, but full metric and efficiency review remains open before declaring its complete publication package.

[Selected machine-readable statistics](../paper/results/nq_lexical_i1_i3_paired_2026-11-09/selected_statistics_public.json).
