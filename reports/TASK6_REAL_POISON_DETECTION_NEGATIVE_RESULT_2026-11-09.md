# Task 6 — Authentic saved 2Wiki RCD poison-identity detection: exploratory negative result

**Date:** 9 November 2026  
**Evidence type:** User/operator-reported output from completed read-only `scripts/evaluate_saved_2wiki_rcd_poison_detection.py`; the exact private JSON result file has **not** been independently fetched in this GitHub preparation step.  
**Verdict:** **REAL EXPERIMENTAL METRICS OBSERVED, POOR DISCRIMINATION / NO VALIDATED DEFENSE**.

## Reproducibility receipt and provenance

On their Mac, the operator fast-forwarded to `main` merge commit `10c626823a5cfac7d4932a7ae783bc08bc5758fe`, which includes merged PR #155. They ran the authentic saved-data detection evaluator with explicit `--allow-shared-document-ids`; local source-code tests returned **17 passed in 0.16 s**. The CLI returned:

- `status: REAL_PINNED_2WIKI_EXPLORATORY_POISON_IDENTITY_DETECTION`
- **36 distinct question IDs**, deterministic **18 development / 18 test** split
- Original **40 post-hoc, valid-only full_k3 poisoned stratum positions**, deduplicated to one source cell per original question
- **54 shared candidate document IDs** across dev and test (allowed and reported, **not** document-disjoint)
- Only saved RCD candidate consistency/conflict/score diagnostics and sealed construction identities; **no new Qwen inference**
- Private aggregate receipt filename: `task6-real-detector-20261109T123552Z_PRIVATE.json`; no raw prompts, source documents, per-case answers or identifiers are published here.

The accompanying [public console aggregate](../paper/results/2wiki_poison_detection_exploratory_2026-11-09/operator_console_aggregate_public.json) exactly transcribes the operator-shared values and adds transparent mathematical baselines. The original private report should remain outside Git and may be hashed in a later independent custody review; a hash is not invented here.

## Actual exploratory test metrics

| Metric | Observed point value | Nominal 95% question-cluster bootstrap interval |
|---|---:|---:|
| AUROC | **0.5208** | [0.4494, 0.5828] |
| Average precision / AUPRC | **0.3932** | [0.3000, 0.5003] |
| F1 at the dev-selected threshold | **0.5178** | [0.4467, 0.5880] |
| False-positive rate | **1.0000** | [1.0000, 1.0000] |
| Test poison-candidate prevalence | **0.34936** | Not reported |
| Shared candidate IDs between splits | **54** | Not applicable |

There were **2,000 defined question-cluster bootstrap replicates per interval**; nominal and not multiplicity-adjusted. There were only **18 test question clusters**, so this cannot be treated as a high-powered generalization estimate.

## Baseline comparison — important negative result

The observed F1 is **exactly equal** to the trivial **predict-all-positives** classifier at prevalence `p=0.34935897435897434`:

```
F1(all-positive) = 2*p/(1+p)
                 = 0.517814726840855
Observed F1      = 0.517814726840855
Observed FPR     = 1.0
```

At the chosen threshold **every negative (clean) candidate is marked as poison**. The F1 equivalence demonstrates that this selected decision rule offers **no F1 improvement over a trivial all-positive decision**. AUROC exceeds 0.5 by only **0.0208**; its nominal interval includes 0.5. Average precision exceeds the positive prevalence baseline by **0.0439**, but this modest descriptive ranking difference does not establish a useful deployable classifier. Do not infer rigorous statistical equivalence from a CI crossing 0.5.

## Scientific interpretation

This is a meaningful **negative result** for the studied predeclared RCD rank-instability/conflict heuristic and decision threshold, **not** an indication that poison detection has never worked or that no alternative threshold, labels or features might do better. The current test does **not** justify claiming a functional detector, a low-false-alarm operating point, generalization to unseen documents or independently source-adjudicated factual falsity.

The negative finding strengthens the research paper's general message: a sophisticated RCD signal pipeline is **not automatically an effective poison identifier**. Candidate-level identity labels in this evaluation mean the document was inserted by the controlled attack, not that a human or external source proved the text false.

## Checklist decision

- **Task 6 — Empirical exploratory evaluation:** **COMPLETE / NEGATIVE FINDING** for this specifically bounded 2Wiki saved-ablation subset; real AUROC, AUPRC, F1 and FPR exist. No more Qwen generator calls were needed.
- **Task 6 — Original full validated poison detector:** **STILL NOT VALIDATED**, due to 18-query test set, 54 overlapping candidate identities, retrospective selection, lack of independent document holdout and unusable 100% FPR threshold.
- **Full original 12-workstream research tracker:** **5 fully scoped tasks plus Task 6 exploratory negative study**, not 12/12 and **not** a successful poison defense. Keep the pending broader evidence explicitly open.
- **Task 12:** Include this as a negative, exploratory appendix/subsection in the manuscript, not a headline state-of-the-art detection claim.

## What would justify stronger detector claims?

Run a genuinely **question- and document-disjoint** larger study with independent new poison identities, development-only threshold/model selection, prespecified false-positive constraint and held-out AUROC/AUPRC/F1/FPR (optionally confidence intervals clustered by question *and* document). **Do not run this automatically or call it complete without real evidence.**

Keep the operator's private result file and all original sealed source artifacts unchanged. No original experimental results were altered to create this summary.
