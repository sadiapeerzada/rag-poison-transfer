# Task 5 — Real matched 2Wiki iterative retrieval + Qwen QA: no target-match improvement

**Date:** 9 November 2026.  
**Source:** Researcher's original Mac terminal receipt, with private SHA-bound Qwen journal/plan and aggregate retained locally.  
**Scientific status:** **Bounded exploratory real-QA study complete**; **full prospective held-out generalization NOT complete**.

## Authentic run provenance

After [PR #159](https://github.com/sadiapeerzada/rag-poison-transfer/pull/159), [PR #160](https://github.com/sadiapeerzada/rag-poison-transfer/pull/160), and [PR #161](https://github.com/sadiapeerzada/rag-poison-transfer/pull/161) were merged, the owner reported successful original-source retrieval, immutable optimized-plan construction, **15/15 corrected optimizer tests**, and a locally executed original Qwen experiment.

- Original frozen 2Wiki sample: **40 selected query/cell positions, 36 distinct questions**, valid-only selected after observing prior results; one clean and one poisoned arm per position
- **80/80 independent original Dense evidence-ID + exact original full generator-prompt checks passed** on the Mac before any new inference
- Reused **77** exact same frozen Dense Qwen responses in the iterative arm, only when ordered evidence document IDs **and** full generator-prompt SHA-256 matched (one shared observation, not new inference)
- **3/3 new, genuine, locally executed Qwen observations verified** on the remaining changed prompts; receipt status `ITERATIVE_NEW_QWEN_COMPLETE`, `remaining=0`
- Iterative retrieval made **6/80** second-round retrieval invocations and reported **0 abstentions**
- Original real prepared-plan SHA-256: `5dacf18d8713018b2c89e567566257391518aea9db057655006f0a70f828c429`
- Real optimized-plan SHA-256: `9310139e642d92d0cc2e5fcdd20002c0f855cb6e641242068836359179cc0f90`
- Original private model-run directory basename: `task5-iterative-real-qwen-20261109T140623Z_PRIVATE`
- Private paired aggregate basename: `task5-iterative-summary-20261109T140652Z_PRIVATE.json`
- Final private paired aggregate status reported by actual runner: `REAL_QWEN_ITERATIVE_MATCHED_QA_EXPLORATORY_COMPLETE`

The full private source JSON, original queries, prompts, generated poison passages, checkpoint journals and model responses **were not attached to this PR**; this release report transcribes numerical fields from the owner's terminal receipt, and **does not independently re-open or certify those private files**.

## Measured results

| Real source-reported outcome | Original frozen Dense QA | Evidence-dependent iterative QA |
|---|---:|---:|
| Poisoned target-answer exact matches | 33 / 40 (82.5%) | 33 / 40 (82.5%) |
| Clean gold-answer correctness | 11 / 40 (27.5%) | 13 / 40 (32.5%) |

- Paired poisoned target-match rate difference, iterative minus Dense: **0.0000 = 0 percentage points**.
- Reported question-cluster nominal bootstrap 95% interval for that paired difference: **[0.0, 0.0]**. This is because the selected paired target effects show no variation in the produced numerical aggregate; it **does not prove equivalence in a wider benchmark population**.
- Observed clean-answer correctness difference: **+2 positions / 40 = +5 percentage points**. **No confidence interval for this difference was visible in the terminal receipt**; do not call it statistically significant.
- The 77 unchanged-prompt QA responses must not be misrepresented as independently generated iterative responses. Three changed-prompt generations, not 80, were newly executed.

## Research interpretation

**The implemented evidence-dependent two-round retrieval heuristic did not reduce targeted-answer matching on these sampled original attacks relative to exact historical Dense prompts.** There was a small absolute improvement in clean gold-answer correctness in the aggregate, but the selective post-hoc design, low independent question count, repeated questions, reuse of historical outputs and no reported clean-effect uncertainty prevent a strong causal, generalization or statistical improvement claim.

This is a **genuine negative outcome**, not a failed experiment; reporting it is preferable to inventing a successful defense.

## Essential limitations and remaining work

1. **Exploratory selected population.** The 40 question/cell positions come from a historical valid-only post-hoc sample and cover 36 distinct question IDs. This is neither a new, independently blinded 300-query replication nor a multi-dataset held-out evaluation.
2. **Source-verification gap.** Poisoned target-answer strings are not independently proven factual falsehoods. Tasks 4+9 still need real dated independent sources, answer-type/relationship verification and abstention on ambiguous cases.
3. **Shared answers.** The iterative arm reused identical source Qwen answers for 77/80 prompts. Paired differences are still descriptive for the deterministic method, but are not 80 independently regenerated samples.
4. **Limited additional adaptation.** Just 6/80 retrieval operations used the second round, and 3 generator inputs changed. Generalizing adaptive control efficacy requires broader populations and controller behaviors.
5. **Historical exposure/custody.** The original 2Wiki source sample, backup and model-corpus provenance have prior limitations. Do not erase them or infer that reuse grants independence.
6. **No strong defense finding.** Unchanged target matching (33/40 in both arms) is a negative result. It is also not evidence that the selected poison necessarily caused those target strings without clean/control examination and independent source verification.
7. **No controlled latency comparison.** Original Dense generation was saved from a prior run; new iterative retrieval timings and prior Dense generation wall times are not directly comparable as randomized same-environment measurements.
8. **Scope distinction.** The previously missing *real matched clean/poison iterative QA experiment* is now empirically performed, and its **bounded exploratory subtask can be closed**. The original strong-scope cross-family/fresh-held-out/generalization goal remains OPEN, primarily under Task 7 and broader Task 5 validation.

### Evidence and reproducibility

- Aggregate-only public machine-readable record: [operator-console aggregate](../paper/results/2wiki_task5_iterative_exploratory_2026-11-09/operator_console_aggregate_public.json) (private raw results retained off-repo).
- Existing execution/readme and source code: [Task 5 private execution handoff](../docs/TASK5_REAL_ITERATIVE_PAIRED_QA_EXECUTION_2026-11-09.md), [SHA-pinned runner](../scripts/run_2wiki_iterative_matched_qa.py).
- Master scope and unresolved scientific gates: [Issue #136](https://github.com/sadiapeerzada/rag-poison-transfer/issues/136).

**No original sealed 2Wiki source files, original model weights, prior results, dataset records or raw Qwen outputs were changed or published by this report.**
