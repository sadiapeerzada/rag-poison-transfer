# Research release candidate — narrow, evidence-backed scope

**Date:** 9 November 2026  
**Project:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Status:** **INTERNAL RESEARCH RELEASE CANDIDATE — NOT A FINAL FULL-PLAN / HUMAN-ADJUDICATED PUBLICATION APPROVAL**

This packet is a draft-ready scientific synthesis of existing results, not a new experimental result or an authorization to release raw data. Source questions, generated responses, prompts, private journals and full private model weights are not introduced in these documents.

## Proposed working title

**Knowledge-Poisoning Transfer Across Retrieval Pipelines: Paired Vulnerability, Construction Coverage, and Retrieval-Cost Trade-offs**

Do not title this a verified "Adaptive RAG Defense" or claim a new defense is universally robust: neither finding is supported by the measured results. Likewise, the original source-crafted HotpotQA study and 2Wiki matched Dense/RCD run are distinct designs.

## Abstract — manuscript draft

We investigate how knowledge-poisoning attacks affect retrieval-augmented generation pipelines, emphasizing paired evaluation, transferability, and the utility costs of retrieval-consistency heuristics. A frozen source-crafted HotpotQA study examines four source retrievers and five target pipelines, including a composite Retrieval-Consistency Defense (RCD), using lexical and semantic attack families at two intensities and three seeds. Complementary matched Dense–RCD experiments on HotpotQA and 2WikiMultiHopQA evaluate targeted answer matching while retaining construction failures in attempted-population denominators. A separate 300-question Natural Questions single-hop lexical study provides two-intensity paired comparisons, and a 480-observation exploratory 2Wiki ablation examines six RCD component configurations. Results are heterogeneous: the original 2Wiki lexical intensity-1 condition yields more targeted answer matches under RCD than Dense, whereas several other paired contrasts are uncertain. NQ lexical poisoning increases target-answer matching markedly from intensity 1 to 3, without a demonstrated poisoned-answer advantage for RCD. Removing RCD query rewriting roughly halves internal retrieval operations in a selected 2Wiki ablation subset; limiting context depth lowers poison exposure but also reduces poisoned-answer accuracy. These observations support denominator-aware evaluation and explicit accounting of retrieval work rather than a universal defense ranking. The studies remain limited by historical exposure uncertainty, post-hoc valid-only ablation selection, unadjudicated semantic target truth, and incomplete dataset/model redistribution custody.

**Abstract safety:** All numerical comparisons below use source-reported, already completed experimental observations. The abstract intentionally does not claim human source adjudication, poison-detection AUROC, or actual iterative-controller evaluation.

## 1. Core evidence map

| Study | Evidence actually available | Independent statistical unit | What it can support | Principal source |
|---|---|---|---|---|
| HotpotQA source-crafted transfer | 240 source–target × family × intensity × seed cells; 20,500 matched source-target paired comparisons; 41,000 logical generation observations, including cache hits | 300 fixed query IDs, retaining repeated seeds and pipelines | Transfer patterns among five target retrieval systems, with construction-failure accounting | [HotpotQA transfer aggregate](../results/hotpotqa_transfer_43f3f652460a/aggregate_public.json), [raw-verification receipt](../../reports/HOTPOTQA_TRANSFER_RAW_ARTIFACT_VERIFICATION_2026-11-09.md) |
| Frozen HotpotQA Dense–RCD comparison | 3,600 construction attempts over four family/intensity conditions × three seeds | 300 query IDs, not 900 independent questions | Within-dataset Dense–RCD vulnerability and paired uncertainty | [Cross-dataset matched comparison](../../reports/HOTPOTQA_VS_2WIKI_PAIRED_COMPARISON_2026-11-09.md) |
| Frozen 2Wiki Dense–RCD comparison | 3,600 construction attempts, 1,800 mechanically valid (1,524 lexical and 276 semantic) | 300 query IDs reused across seeds | Within-dataset clean utility, poison exposure, construction coverage and targeted-output matches | [2Wiki scientific results](../../reports/2wiki_300_dense_rcd_scientific_results_2026-11-08.md) |
| Exploratory NQ lexical study | 300 questions × two arms × clean/poison × two intensities = 2,400 saved QA observations, 35 paired contrasts | 300 questions | Lexical intensity response and Dense–RCD single-hop utility/cost trade-off | [NQ paired report](../../reports/NQ_LEXICAL_I1_I3_FULL_PAIRED_AND_EFFICIENCY_2026-11-09.md) |
| Exploratory 2Wiki RCD ablations | 480 genuine saved Qwen QA observations, 240 clean/poison pairs, six variants and 50 pooled pairwise metrics | **36** distinct question IDs across 40 selected stratum positions | Post-hoc component sensitivity and observed local cost, not full attempted-population ASR | [2Wiki ablation audit](../../reports/2wiki_rcd_ablation_v1_question_cluster_audit_2026-11-09.md) |
| Cross-study efficiency ledger | NQ, separate 2Wiki ablation and historical HotpotQA timing logs; later HotpotQA backend/cache accounting | Dataset/protocol specific | Descriptive retrieval operations, component latency and caching; not dollars or common hardware speedup | [Efficiency and cost limits](../../reports/CROSS_STUDY_OBSERVED_EFFICIENCY_AND_COST_LIMITS_2026-11-09.md) |
| AI-assisted 2Wiki error triage | 131 outcome-stratified case rows, 102 question IDs, 107 selected valid constructions | Selected cases; repetitions remain | Exploratory error mechanisms requiring independent source verification | [Qualitative report](../../reports/2WIKI_QUALITATIVE_ERROR_AUDIT_PUBLIC_2026-11-09.md) |

## 2. Main quantitative results that can go into the paper

### 2.1 Matched Dense–RCD attempted-population target matches

Denominator per condition is **900 attempted query–seed constructions** (300 unique questions × three seeds). Failures remain in the denominator, **not** counted as defense successes. Positive Dense−RCD difference means RCD has fewer target matches.

| Attack family/intensity | HotpotQA Dense | HotpotQA RCD | 2Wiki Dense | 2Wiki RCD |
|---|---:|---:|---:|---:|
| Lexical I1 | 143/900 (15.89%) | 155/900 (17.22%) | 382/900 (42.44%) | 428/900 (47.56%) |
| Lexical I3 | 314/900 (34.89%) | 301/900 (33.44%) | 652/900 (72.44%) | 629/900 (69.89%) |
| Semantic I1 | 59/900 (6.56%) | 66/900 (7.33%) | 134/900 (14.89%) | 133/900 (14.78%) |
| Semantic I3 | 45/900 (5.00%) | 45/900 (5.00%) | 104/900 (11.56%) | 104/900 (11.56%) |

In 2Wiki lexical I1, Dense−RCD = **−5.11 percentage points**, nominal 95% paired query-cluster CI **[−8.67, −1.78] pp**. Thus in this condition RCD produced *more* target matches, not fewer. Other original 2Wiki condition intervals span zero. These are **unadjusted** intervals, not a multiple-comparison-corrected discovery or proof of universal behavior.

### 2.2 Natural Questions lexical intensities

Target-answer matching at intensity 1: **16.00% Dense vs 16.67% RCD**; at intensity 3: **42.00% Dense vs 43.00% RCD**. Poisoned exact match at intensity 1: **27.67% for both**; at intensity 3: **18.00% Dense, 17.00% RCD**. For target matching, the paired **RCD−Dense** intervals include zero for both intensities (I1: **[−2.67, +4.00] pp**; I3: **[−2.00, +4.33] pp**). The intensity-associated within-arm rise in target matching was **+26.00 pp Dense** and **+26.33 pp RCD**, again nominal, not a cross-dataset causal claim.

The NQ study uses **pooled long-answer candidate passages**, not the standard unrestricted Wikipedia open-domain NQ corpus.

### 2.3 2Wiki component sensitivity and measured work

Selected valid-only RCD k=3: **95.0% poison visibility, 75.0% target matching, 12.5% poisoned gold EM**, with four internal retrieval operations per QA. Removing rewrites gives **95.0%, 77.5%, 10.0%** respectively, with **two** inner retrieval operations and measured retrieval time declining **34.90→17.42 ms**. Full k=1 lowers poison visibility to **72.5%** but poisoned gold EM to **2.5%**. Therefore lower exposure is *not* the same as a demonstrated improved useful answer. The **40 selected stratum positions contain only 36 unique questions**; results are exploratory.

Two generation latencies around **903 and 914 seconds** contaminate the k1/k5 arithmetic means; use the already-published median and p95 alongside means. Do not pool timing across NQ, 2Wiki and HotpotQA as if hardware/protocol boundaries were identical.

## 3. Core contribution positioning

1. **Transferability:** paired source→target HotpotQA evaluation across four source and five target retrieval pipelines, retaining failed constructions.
2. **Negative/heterogeneous defense evidence:** matched HotpotQA and 2Wiki Dense–RCD comparisons demonstrate conditions where retrieval-consistency heuristics do not reliably reduce targeted matches and may coincide with worse performance.
3. **Mechanistic sensitivity:** completed, post-hoc 2Wiki six-variant ablation separates the cost of rewrites and evidence depth from measured target matching, poison exposure and gold-answer utility.
4. **Reporting discipline:** 300-query clustering across repeated seed/pipeline observations, separate attempted/valid-only denominators, signed paired effects, execution/cache accounting, and transparent negative results.

**Not contributions without new evidence:** independently adjudicated semantic falsehoods, a validated poison detector, genuinely iterative multi-round controller results, prospectively untouched 2Wiki V3 cohort, broad unseen-family/low-rate stress tests, dollar-cost estimates or generality across model families without matching token caps.

## 4. Evidence boundaries that must appear in Methods/Threats to validity

- **Target matching ≠ independently verified successful factual poisoning.** The generated target may be wrong-type, an alias ambiguity, or already present in a clean reply.
- **Semantic constructed-valid ≠ factually false/true.** AI-assisted case triage is not independent ground truth; 24 failure cases in the 131-row selected packet lacked complete contextual records.
- **Historical exposure:** Frozen 2Wiki has known unresolved historical custody; no prospective untouched-cohort claim. Fresh V3 execution is separately NO-GO.
- **Sampling:** 2Wiki ablations are post-hoc, valid-only, one seed, n=36 unique questions; sample-selection bias persists despite question-cluster bootstrap.
- **Statistical uncertainty:** nominal percentile CIs for many comparisons are **not** adjusted for multiplicity; the same 300 query IDs recur across seeds.
- **Compute:** local hardware and token caps differ among studies. Phi-4 Mini @128 versus Qwen @64 is a **confounded second-model comparison**, not architecture-invariant generalization.
- **Release rights:** Git-tracked `results/` includes 57 files that still require per-file public redistribution and privacy clearance. No top-level license/right-to-redistribute determination is inferred from GitHub availability.
- **Reproducibility:** public aggregate arithmetic, local original SHA checks and same-Mac archive restoration passed, but full independent dataset/model-cache custody and off-device disaster recovery are not certified.

## 5. Research/claim decision for the supervisor

**Route A — finish a carefully scoped, exploratory manuscript now (recommended to avoid more inference).** Primary claims center on the *completed* HotpotQA transfer and paired HotpotQA/2Wiki vulnerability evidence. NQ, ablations and efficiency become complementary exploratory analyses. Limit the conclusions to target-output matching and measured retrieval work. Clearly mark semantic-factuality limitations. The manuscript still requires responsible author review, a real reference list/citations and publishing-rights sign-off.

**Route B — insist on all 12 original workstreams.** This is **not complete**. Actual adaptive multi-round evaluation, a genuine document-level poison detector, extended robust/intensity/unseen attacks, credible source factuality and model/dataset custody require distinct work. We cannot label these as finished by writing, running synthetic tests or merging a reporting PR.

## 6. Current 12-task tracker

| Number | Workstream | Status as of this packet |
|---|---|---|
| 1 | NQ I1 | COMPLETE — exploratory |
| 2 | NQ I3 | COMPLETE — exploratory |
| 3 | NQ paired inference | COMPLETE — exploratory |
| 4 | Semantic evaluation | PARTIAL |
| 5 | Adaptive/iterative controller | PARTIAL |
| 6 | Document poison detection | NOT VALIDATED |
| 7 | Robustness/intensity/unseen family | PARTIAL |
| 8 | 2Wiki RCD ablation | COMPLETE — exploratory |
| 9 | Semantic factuality | AI-ASSISTED, UNADJUDICATED |
| 10 | Resource/cost-proxy ledger | COMPLETE — measured proxies |
| 11 | Reproducibility and integrity | LOCAL MECHANICAL PASS; global rights/custody/semantic PARTIAL |
| 12 | Final research package | **THIS DRAFT PREPARED; FULL RELEASE NOT APPROVED** |

**Count:** **5 of 12** completed at defined limited scope. A scoped paper and reproducibility index can be assembled without pretending the other seven are complete.

## 7. Final author/release checks (not automated)

- [ ] Sign off paper scope, author list, affiliations and conference/journal format; insert the actual related-work bibliography before submission.
- [ ] Examine the [57-file tracked-result rights inventory](nov09_tracked_result_rights_inventory.json). Decide individually whether dataset excerpts, prompt text and generated source passages may be publicly redistributed; preserve research originals privately. Do not delete or rewrite without explicit authorization.
- [ ] Confirm raw private NQ, 2Wiki, HotpotQA model/data weights/caches, exact SHA pins and backup-origin evidence. Retain documented unavailable assets as limitations.
- [ ] Check latest GitHub `main` CI results when completed and inspect any failed/queued jobs.
- [ ] Review semantic target truth with real independent sources where claims need them, or retain cautious target-string-match language.
- [ ] Prepare final figures from verified published aggregate tables; avoid plots that imply unavailable per-query-level confidence intervals or full same-protocol latency comparison.
- [ ] Approve and tag a **scoped research release** only after rights/privacy and supervisor review. If these gates remain open, leave it as a **draft release candidate**, not `GO`.

## 8. Publication-ready links

- [Original HotpotQA 240-cell source-crafted transfer aggregate](../results/hotpotqa_transfer_43f3f652460a/aggregate_public.json)
- [Original 2Wiki result interpretation](../../reports/2wiki_300_dense_rcd_scientific_results_2026-11-08.md)
- [Cross-dataset matched comparison](../../reports/HOTPOTQA_VS_2WIKI_PAIRED_COMPARISON_2026-11-09.md)
- [NQ 35 paired results and resource accounting](../../reports/NQ_LEXICAL_I1_I3_FULL_PAIRED_AND_EFFICIENCY_2026-11-09.md)
- [2Wiki 50 question-cluster contrasts](../results/2wiki_rcd_ablation_v1_2026-11-09/question_cluster_audit_public.json)
- [Cross-study efficiency ledger](../results/cross_study_efficiency_2026-11-09/observed_efficiency_public.json)
- [Task 11 public integrity inventory](../results/reproducibility_gate_2026-11-09/public_evidence_inventory.json)
- [Task 11 report and scientific validity gate](../../reports/REPRODUCIBILITY_AND_VALIDITY_RELEASE_GATE_2026-11-09.md)
- [Private-result publication review inventory (no raw content)](nov09_tracked_result_rights_inventory.json)
