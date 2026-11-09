# Knowledge-Poisoning Transfer Across Retrieval Pipelines: Paired Vulnerability, Construction Coverage, and Retrieval-Cost Trade-offs

**Full scoped manuscript draft, 9 November 2026**  
**Author:** Sadia Peerzada (affiliation, co-authors and corresponding-author details to be confirmed before submission)  
**Status:** **DRAFT — author/supervisor scientific review, data rights and venue formatting pending.** This is not a publication acceptance or an approved full 12-task study.

## Abstract

Retrieval-augmented generation (RAG) is vulnerable to manipulation of the external knowledge it retrieves. We investigate the transfer of controlled knowledge-poisoning attacks across retrieval pipelines and examine whether a retrieval-consistency heuristic, RCD, reduces chosen-target answer production without unacceptable utility or computational overhead. A frozen HotpotQA experiment evaluates source-crafted lexical and semantic attacks across four source and five target retrieval pipelines; matched Dense–RCD evaluations on HotpotQA and 2WikiMultiHopQA measure clean utility, poisoned-answer outcomes, evidence exposure and construction feasibility. Additional exploratory experiments comprise a 300-question Natural Questions lexical-intensity comparison and 480 real Qwen responses across six RCD ablations. Results are heterogeneous. In the original 2Wiki lexical-intensity-1 comparison, RCD produced more chosen-target matches than Dense (47.56% versus 42.44%; paired Dense−RCD difference −5.11 percentage points, nominal 95% interval [−8.67, −1.78]). Stronger NQ lexical poisoning increased targeted-output rates in both arms without establishing an RCD target-match or poisoned-accuracy advantage. In a post-hoc 2Wiki RCD ablation, removing rewrites halved measured internal retrieval calls and retrieval latency without clearly reducing target matching; decreasing context depth reduced poison exposure while also lowering poisoned-answer exact match. Semantic attack construction had low mechanically valid coverage, and neither mechanical acceptance nor chosen-target matching establishes factual falsehood. These findings motivate source-aware, denominator-correct evaluation and explicit robustness–utility–retrieval-cost reporting rather than unconditional defense-superiority claims.

**Keywords:** Retrieval-augmented generation; knowledge poisoning; cross-pipeline transfer; retrieval consistency; question-cluster bootstrap; adversarial evaluation.

## 1. Introduction

RAG couples text generation to an external retriever and knowledge corpus. This architecture increases the importance of the retrieved evidence supply chain: content introduced into the corpus may be retrieved, passed to the generator and reflected in its final answer. Work such as PoisonedRAG [R1] and BadRAG [R2] studies this threat surface, while other work examines single-document and multi-hop poisoning [R3]. Separately, research on Adaptive-RAG [R4], IRCoT [R5] and Self-RAG [R6] shows that adaptive retrieval and generation can involve more sophisticated routing, intermediate retrieval or reflection. These approaches are conceptually distinct from the fixed composite RCD retriever evaluated here.

A common evaluation pitfall is to conflate successful poison construction, retrieved poison exposure, production of the attacker's chosen target string, and a verified *false factual conclusion*. These are not identical outcomes. Another pitfall is to count failed attack constructions as successful defenses. Multi-seed RAG studies can also overstate precision when hundreds of question-seed/target-pipeline observations are mistaken for independent questions.

We make four measured contributions. First, the frozen source-crafted HotpotQA study records how attack outcomes transfer between four source pipelines and five target pipelines under a common selected instance. Second, matched Dense–RCD HotpotQA and 2Wiki experiments expose heterogeneous and sometimes unfavorable RCD outcomes instead of selecting only favorable comparisons. Third, an exploratory NQ lexical-intensity study and a six-variant 2Wiki ablation quantify exposure, answer utility and retriever-work trade-offs. Fourth, we separate attempted and valid-only populations, cluster repeated-question uncertainty, reconcile logical versus actual backend calls and preserve explicit integrity and factuality limits.

**Scope:** Our contribution is a retrospective analysis of the already completed, pinned experiments. It is not a new unseen-adaptive attack, independently adjudicated semantic factuality corpus or completed document-level poison detection benchmark.

## 2. Related work

**Knowledge-base poisoning:** PoisonedRAG [R1] formalizes corpus-side knowledge corruption that induces target answers. BadRAG [R2] studies retrieval poisoning and downstream generator behaviors. One Shot Dominance [R3] considers the importance of single injected documents for complex queries. These studies motivate differentiating construction, retrieval and final-answer outcomes. We do not claim to reproduce their methods or compare their published percentages directly with our different setup.

**Adaptive and iterative retrieval:** Adaptive-RAG [R4] routes by question complexity; IRCoT [R5] interleaves reasoning and retrieval; Self-RAG [R6] integrates conditional retrieval and self-reflection. Our repository implements a bounded evidence-dependent second-round retriever, but this component has **not yet been measured in matched poisoned end-to-end QA**, so its reliability is not included as a completed result in this paper.

**Measurement:** Our methodological emphasis is paired source/target transfer, correct construction denominators, nominal query-cluster uncertainty, and measured computational work. Higher retrieved-poison exposure is not sufficient evidence of a generated false answer.

## 3. Threat model and evaluation endpoints

An adversary can inject selected documents into the retrieval corpus, seeking to have the RAG generator output a chosen target answer to a question. The frozen records cover two broad poison-construction families: a lexical influential-token strategy and a fluent false-evidence strategy. Two observed poison intensities (1 and 3) and three poison seeds occur in the original matched HotpotQA/2Wiki studies. Separate development retrieval sweeps include intensity 5 and a lower global poison rate; these are explicitly **not** part of the final paired answer-level matrix.

The primary **attempted-population target-answer match rate** divides the count of generated chosen-target matches by *all* attempted query–seed constructions, including failed target nomination or document construction. It should not be renamed "verified factually false attack success". **Valid-only target match** conditions on construction success and uses a different denominator. We separately report retrieved poison visibility/PRR, clean and poisoned exact match (EM), answer F1 where available, and the retrieval-work/latency variables recorded by each source protocol.

The matched comparison contrasts Dense with a composite Retrieval-Consistency Defense (RCD). Its scoring and rewriting heuristics are frozen according to source experiment versions; the various study checkpoints do not share an identical timing environment. We never interpret an unadjusted nominal interval or a lack of significant difference as proof of defense equivalence.

## 4. Datasets and experimental organization

### 4.1 Original HotpotQA source-crafted transfer

The held-out source-crafted transfer study uses **300 fixed HotpotQA questions**, lexical and semantic attack families at intensities 1 and 3 across seeds 42–44, four source pipelines (BM25, Dense, Hybrid and Reranker) and five targets (those four plus RCD). The selected source instance is sealed before target evaluation. The public aggregate records **240 source–target × attack × intensity × seed cells**, **41,000 logical generation observations**, **21,175 physical backend calls** and **19,825 clean-cache hits**. The operator-reported raw selection/evaluation inventory audit passed; optional original candidate-stage inventory was not inspected. Repeated seeds/pipelines do not create independent questions.

The public transfer matrix reports conditional ATR using final source successes in the denominator, alongside attempted-population end-to-end target matching. Full condition-level results and query-cluster intervals are in the [released aggregate](../results/hotpotqa_transfer_43f3f652460a/aggregate_public.json).

### 4.2 Matched HotpotQA and 2Wiki

The separate frozen Dense–RCD experiments compare both arms on the same poisoned query construction per cell. Each dataset has **300 question identities**, repeated across three seeds in four attack/intensity strata, producing **900 attempted query–seed positions per stratum**. Original HotpotQA/2Wiki frozen source commits and minor protocol details differ and are not interpreted as an across-dataset causal randomization. The original 2Wiki cohort has known historical exposure uncertainty.

### 4.3 Natural Questions and exploratory ablations

The NQ follow-up uses **300 matched evaluation questions** in a restricted pooled long-answer-candidate corpus, not unrestricted Wikipedia retrieval. Lexical I1 and I3 each compare Dense and RCD under clean/poisoned conditions, totaling **2,400 recorded QA observations**. The operator re-executed the read-only paired verifier and confirmed exact source aggregate, plan, manifest and response fingerprints, without new inference.

The 2Wiki exploratory ablation uses **480 completed Qwen QA observations**, six RCD variants, one original seed and **40 deliberately selected valid construction positions per variant** across four strata. These represent **36 distinct question IDs**. Paired pooled question-cluster contrasts and latency anomaly checks were computed offline; these are not representative attempted-population estimates.

## 5. Results

### 5.1 Original attempted-population target-answer matching

| Condition | Hotpot Dense | Hotpot RCD | 2Wiki Dense | 2Wiki RCD |
|---|---:|---:|---:|---:|
| Lexical I1 | 143/900 (15.89%) | 155/900 (17.22%) | 382/900 (42.44%) | 428/900 (47.56%) |
| Lexical I3 | 314/900 (34.89%) | 301/900 (33.44%) | 652/900 (72.44%) | 629/900 (69.89%) |
| Semantic I1 | 59/900 (6.56%) | 66/900 (7.33%) | 134/900 (14.89%) | 133/900 (14.78%) |
| Semantic I3 | 45/900 (5.00%) | 45/900 (5.00%) | 104/900 (11.56%) | 104/900 (11.56%) |

In 2Wiki lexical I1, Dense−RCD = **−5.11 percentage points** with a nominal 95% paired question-cluster interval **[−8.67, −1.78] pp**. This particular condition disfavors RCD. Other original 2Wiki primary intervals include zero, and the unadjusted analysis does not establish a global direction. The original HotpotQA outcome differences are smaller or mixed; do not infer equivalence merely because intervals include zero.

### 5.2 Semantic-construction attrition

In the original 2Wiki study, **276 of 1,800 semantic construction attempts** were mechanically valid (**15.33%**); **276** were target-nomination failures and **1,248** were semantic-construction failures. At I1, **167/900** attempts were valid (18.56%); at I3, **109/900** (12.11%). Thus the relatively low attempted-population semantic chosen-target rate is strongly confounded by construction feasibility. It is incorrect to interpret failed constructions as security protection by RCD.

A selected post-hoc qualitative audit covers **131 cases / 102 distinct questions**, including **107 mechanically valid cases** and 24 construction failures requiring fuller context. It identifies probable role/type mismatches but does not authenticate factual falsehood, source quotes, or human agreement. The [semantic and robustness supplement](../../reports/SCOPED_SEMANTIC_AND_ROBUSTNESS_RESULTS_2026-11-09.md) details the evidence limits.

### 5.3 Natural Questions lexical intensity and paired effects

At NQ intensity 1, poisoned gold EM was **27.67% for both Dense and RCD**, with chosen-target matches **16.00%** versus **16.67%**. At intensity 3, poisoned gold EM fell to **18.00% Dense / 17.00% RCD**, and target matching rose to **42.00% / 43.00%**. The paired RCD−Dense target-match nominal 95% intervals include zero at both intensities (I1 **[−2.67, +4.00] pp**; I3 **[−2.00, +4.33] pp**). Increasing lexical intensity from 1 to 3 was associated with **+26.00 pp** target match in Dense and **+26.33 pp** in RCD, without implying a randomized cross-dataset effect.

### 5.4 RCD ablation: evidence depth, rewriting and utility

Within the selected 2Wiki ablation, full k=3 RCD yielded **95.0%** poison exposure, **75.0%** target matches and **12.5%** poisoned EM. Disabling rewriting at k=3 yielded **95.0%**, **77.5%** and **10.0%**, while reducing recorded internal retrieval operations **4→2** and retrieval time **34.90→17.42 ms**. Using k=1 reduced exposure to **72.5%** and target matches to **67.5%** but lowered poisoned EM to **2.5%**. The latter is a cost–utility–exposure trade-off, not an unconditional defense benefit. Two extreme generation latencies exceeding 900 seconds in k=1/k=5 require median and p95 reporting; raw means alone are misleading.

### 5.5 Historical development-only robustness and resource accounting

An existing **48-cell** retrieval-only development sweep includes HotpotQA intensity 5 (**25 attacked query positions per retriever**) and 30% corpus poisoning (**8 positions per retriever**), plus 2Wiki intensity 1/3 slices. For HotpotQA semantic intensity 5, PRR@3 ranges from **0.92 BM25** to **1.00** for Dense/Hybrid/Reranker. At 30% poison rate, all four retrievers show PRR@3 **1.00** in both attack families among only eight attacked positions. These are retrieved-poison visibility measures, not proof of generated false targets or held-out end-to-end robustness. No unseen-family condition was empirically included in these sweeps.

The separate NQ efficiency study records RCD mean retrieval latency approximately **8.2–8.4×** Dense, with five versus one inner retrieval operations, while generator time dominates; the historical HotpotQA timing ratio differs substantially. These **different experiments must not be pooled** as a calibrated global speedup. Monetary cost, energy use and fully portable throughput were not measured.

## 6. Discussion and practical implications

**Negative findings matter.** Across the original and exploratory checkpoints, increasing retrieval work or enforcing consistency heuristics did not consistently reduce chosen-target outputs. Defense evaluation should always pair attack success with clean EM/F1, poisoned gold-answer utility and the number of internal retrieval operations.

**Exposure is a mechanism, not a conclusion.** Injected evidence can be retrieved but not selected for generation, selected but ignored by the model, or absent even when the chosen target appears. A targeted string may already appear on a clean question. Strict answer aliases and answer-role compatibility require explicit validation.

**Source transfer and model family are separate issues.** Reusing a frozen poisoned document across retrieval targets tests transfer under the selected source-craft policy; it does not imply that the same outcome generalizes to all generators. The supplementary Phi-4 Mini replay had different output caps from Qwen and does not remove family/cap confounds.

**Poison detection and adaptive routing remain hypotheses.** A documented heuristic detector and a bounded two-round retriever exist in code, but no authentic held-out document-level detector AUROC/AUPRC/F1 or matched poisoned multi-round QA outcome is claimed here. Simulation tests establish software behavior, not measured defense efficacy.

## 7. Threats to validity and research ethics

The frozen 2Wiki cohort has unresolved historical exposure and custodian independence. The NQ corpus is restricted; its results are not standard open-domain NQ. The six-variant ablation is valid-only and post-hoc with 36 unique questions, vulnerable to selection bias. Nominal question-cluster intervals are not corrected for multiplicity. Low semantic mechanical-construction coverage and answer-type ambiguity complicate target-match interpretation. AI-assisted assessment is not an independently source-verified factual falsehood judgment. The public repository contains 57 tracked result files with potential prompts, questions and generated text; individual redistribution rights and privacy review remain open. Same-Mac archive restoration does not fully certify an independent off-device recovery of model and data dependencies.

These restrictions are reported explicitly rather than silently excluded or treated as evidence of a defense.

## 8. Conclusion

The completed RAG experiments demonstrate substantial cross-pipeline transfer measurement, heterogeneity in RCD’s paired outcomes, and meaningful utility/retrieval-work trade-offs. The strongest defensible takeaway is methodological and empirical: **robustness claims must account for construction failures, repeated-query dependencies, clean utility, visibility of injected evidence and the computational work of retrieval.** A universal RCD defense improvement, source-verified semantic falsehood success, validated poison detection or adversarial adaptive-controller benefit is not established by these data. Further independent source/custody checks and separately authorized empirical studies are needed for those broader claims.

## References

[R1] Zou, W., Geng, R., Wang, B., & Jia, J. (2025). [PoisonedRAG](https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag). *USENIX Security 25*.

[R2] Xue, J., Zheng, M., Hu, Y., Liu, F., Chen, X., & Lou, Q. (2024). [BadRAG](https://arxiv.org/abs/2406.00083). arXiv preprint.

[R3] Chang, Z., et al. (2025). [One Shot Dominance](https://aclanthology.org/2025.findings-emnlp.1023/). *Findings of EMNLP 2025*.

[R4] Jeong, S., et al. (2024). [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/). *NAACL 2024*, 7036–7050.

[R5] Trivedi, H., Balasubramanian, N., Khot, T., & Sabharwal, A. (2023). [Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions](https://aclanthology.org/2023.acl-long.557/). *ACL 2023*.

[R6] Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024). [Self-RAG](https://proceedings.iclr.cc/paper_files/paper/2024/hash/25f7be9694d7b32d5cc670927b8091e1-Abstract-Conference.html). *ICLR 2024*.

See the [bibliographic verification sheet](VERIFIED_RELATED_WORK_REFERENCES_2026-11-09.md) for full authors and publisher sources.

## Reproducibility and release addendum

The immutable frozen result reports, public aggregate JSON, 57-file rights inventory, private source-ledger runner, NQ source SHA pins and 2Wiki archive receipt are linked from the [scoped research release candidate](SCOPED_RESEARCH_RELEASE_CANDIDATE_2026-11-09.md). This manuscript is a **draft**, not a final venue-styled manuscript; publication format, exact citations, contributor approval, released raw-data rights and CI must be approved before final submission.
