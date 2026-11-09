# Semantic attack feasibility and retrieval-only robustness — verified result supplement

**9 November 2026** · **Retrospective analysis of already measured results; no new inference**  
**Status:** Real experimental **descriptive findings** with strict boundaries. Tasks 4 and 7 are **not** fully completed at the original planned end-to-end/semantic-ground-truth scope.

## A. Semantic false-evidence *construction feasibility*

The 2Wiki original run contains **3,600 attempted query–seed construction positions** over lexical/semantic × intensity 1/3 × three seeds, with 300 underlying questions repeated over seeds. Exactly **1,800** were mechanically valid overall. The semantic family alone has **1,800 attempted**, with **276 mechanically valid** (15.33%), **276 target nomination failures** and **1,248 semantic construction failures**; the lexical family has 1,524 mechanically valid out of 1,800.

| Original 2Wiki semantic stratum | Attempts | Valid construction | Valid rate | Dense target matches (attempted population) | RCD target matches (attempted population) |
|---|---:|---:|---:|---:|---:|
| Semantic intensity 1 | 900 | 167 | 18.56% | 134/900 (14.89%) | 133/900 (14.78%) |
| Semantic intensity 3 | 900 | 109 | 12.11% | 104/900 (11.56%) | 104/900 (11.56%) |
| **Total semantic** | **1,800** | **276** | **15.33%** | **238/1,800** | **237/1,800** |

**These numbers are target-answer matching under mechanically valid construction, not independent confirmation that each generated semantic assertion is factually false or causally responsible for a changed answer.** The low semantic attempted-population outcome is substantially affected by *construction attrition*, not proof of successful RCD defense.

The separate original HotpotQA Dense–RCD matched comparison reports semantic target matches of **59/900 Dense versus 66/900 RCD at I1**, and **45/900 for each at I3**. Differing corpus, eligibility and source protocol prevent direct causal comparison with the 2Wiki counts. See [matched cross-study analysis](HOTPOTQA_VS_2WIKI_PAIRED_COMPARISON_2026-11-09.md).

## B. Existing semantic factuality triage (not independent verification)

The separate, post-hoc **131-case / 102-distinct-question** 2Wiki review packet contains **107 mechanically valid cases**, 16 target nomination failures and 8 semantic construction failures. Of 107 valid cases, **45 both-target, 20 Dense-only, 19 RCD-only and 23 neither-target**. These are sample counts from outcome-stratified selection, not unbiased benchmark prevalence.

Automated source-free error triage flagged **33** selected cases for at least one of four person/country/kinship/location answer-role mismatches; **28 distinct questions** were involved. In the sampled semantic-valid subset, **21/51** cases were flagged, which is **not** a verified semantic-error rate. The 24 construction-failure cases require recovery of original question/gold context; the selected packet alone lacks this context.

The new [private source-citation ledger validator](../scripts/audit_2wiki_source_factuality_ledger.py) can create a separate 131-row private worksheet and audit any actual dated source quotations without publishing the cases. **The tool does not check live web sources or authenticate truth.** The user may keep review AI-assisted; do not call it human-adjudicated.

## C. Authentic historical retrieval robustness (development only)

The frozen historical [48-row retrieval sweep](../results/week5_attack_intensity_sweep_full.csv) contains HotpotQA intensity 1/3/5 and a 30%-poison-rate slice, plus 2Wiki intensity 1/3 retrieval sweeps, across four retrievers. The independent aggregate-only reconciliation is [here](../paper/results/robustness_retrieval_dev_2026-11-09/verified_prr_slices_public.json).

PRR@k = whether injected poison was retrieved in the top k. **It is not** generator targeted ASR, factual falsehood, or poison-detection quality.

### HotpotQA intensity 5, 25 attacked development query positions per retriever

| Attack | BM25 PRR@1 / @3 | Dense PRR@1 / @3 | Hybrid PRR@1 / @3 | Reranker PRR@1 / @3 |
|---|---:|---:|---:|---:|
| Lexical, 5 poison documents | 1.00 / 1.00 | 0.68 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| Semantic fluent, 5 poison documents | 0.72 / 0.92 | 0.80 / 1.00 | 0.84 / 1.00 | 1.00 / 1.00 |

### HotpotQA 30% global poison rate, 8 attacked development query positions per retriever

| Attack | BM25 PRR@1 / @3 | Dense PRR@1 / @3 | Hybrid PRR@1 / @3 | Reranker PRR@1 / @3 |
|---|---:|---:|---:|---:|
| Lexical, 1 poison document | 1.00 / 1.00 | 0.75 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| Semantic fluent, 1 poison document | 0.75 / 1.00 | 0.75 / 1.00 | 0.625 / 1.00 | 0.875 / 1.00 |

The global-rate and full-rate cohorts differ in number and potentially identity of attacked questions (8 vs 25); **no matched causal effect** is estimated. No real unseen-attack-family condition or held-out model-generation analysis at intensity 5 / 30% was found among these published sweeps.

## D. Empirical scope map

| Requested research task | Completed existing observation | What is still missing to call it FULLY finished |
|---|---|---|
| Task 4: semantic poisoning evaluation | Frozen HotpotQA/2Wiki semantic construction, attempted-population target matching and partial AI-assisted post-hoc error taxonomy | Source-backed falsehood and answer-role verification, broader semantic construction coverage and explicit valid/invalid denominator interpretation |
| Task 5: adaptive/iterative retrieval | A genuine evidence-dependent two-round policy is **implemented**; synthetic unit tests exist; private clean retrieval diagnostic CLI exists | Real matched clean/poison NQ and multi-hop QA runs with generator, bounded controller, trace/call and latency report |
| Task 6: poison detection | Document-level identity score, AUROC/AUPRC, dev-only threshold and F1/FPR evaluators are implemented and synthetically tested | Authentic per-document `last_diagnostics`, global injected poison identity labels, source/corpus pins and disjoint dev/test empirical scores |
| Task 7: robustness | Historical real 48-cell development retrieval sweep verified, including intensity 5 and 30% slices | Real held-out generation, matched seeds/cohorts, a genuinely new unseen attack family and query-cluster uncertainty |
| Task 9: semantic factuality | 131-case AI-assisted diagnostic packet, outcome-stratified error taxonomy and new source-citation ledger schema | Actually inspected independent citations for accepted cases; complete source context for the 24 construction failures, ambiguities and honest abstentions |
| Task 12: final package | Scoped release candidate and source-index on main; this supplement adds concrete semantic/robustness results | Full manuscript template/reference list, rights and licensing decision for 57 raw files, model/data custody, CI and author approval |

## E. Implications for a defensible manuscript today

The observed data support a narrow paper on **transfer patterns, construction feasibility, negative RCD results, ablation sensitivity and local retrieval-work trade-offs**. It is appropriate to include the measured small robustness retrieval probes as a development appendix. The evidence does **not** support claims of fact-checked semantic poisoning, validated poison detection, adversarial adaptive retrieval robustness, or full unseen-family evaluation.

The source data, original experiment outcomes and frozen protocols were not modified. New files are appendices and validation infrastructure only.
