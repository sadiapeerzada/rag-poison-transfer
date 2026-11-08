# 2WikiMultiHopQA: validated Dense–RCD result interpretation

**Recorded:** 8 November 2026. **Status:** analysis of an author-supplied **frozen, successfully validated aggregate**, subject to scientific review. This document is **not** an independently adjudicated semantic-validity study and **not** a completed source-crafted cross-pipeline transfer study.

## Evidence and reproduction pins

- Source: `execution/aggregate.json` from the approved, historically risk-disclosed 300-query 2Wiki run, uploaded by the researcher and independently parsed/recalculated for this report.
- SHA-256 of uploaded `aggregate.json` bytes: `721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96`. This identifies the uploaded copy, not a newly audited off-device archive.
- Frozen source commit: `b1466db04c4f8f0314c7e537d8e7ec390c8c3b29`.
- Protocol SHA-256: `40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4`.
- Construction-seal SHA-256: `e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44`.
- Evaluation-completion SHA-256: `db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519`.
- The operator reported the frozen runner returned `{"scope":"heldout","status":"validated_aggregate_written"}` after an independent 22,446-file evaluation hash audit and verification of 12/12 cell rows.
- Design: two attack families (lexical influential token; semantic fluent false evidence) × intensities 1 and 3 × seeds 42, 43 and 44; Dense and RCD evaluated on the **same** 300 query IDs per condition. Three repeated seeds **are not 900 independent queries**.

## Primary endpoint: attempted-population end-to-end targeted ASR

Lower ASR indicates fewer target-answer successes. The denominator is **all 900 attempted constructions per condition**, including construction failures; failures are **not credited as successful defense outcomes**. Dense − RCD is positive when RCD has lower attack success.

| Attack condition | Dense successes / attempts | RCD successes / attempts | Dense − RCD (percentage points) | Nominal 95% paired cluster-bootstrap CI (pp) |
| --- | ---: | ---: | ---: | ---: |
| Lexical, intensity 1 | 382/900 (42.44%) | 428/900 (47.56%) | **−5.11** | **[−8.67, −1.78]** |
| Lexical, intensity 3 | 652/900 (72.44%) | 629/900 (69.89%) | +2.56 | [−1.22, +6.22] |
| Semantic, intensity 1 | 134/900 (14.89%) | 133/900 (14.78%) | +0.11 | [−1.00, +1.22] |
| Semantic, intensity 3 | 104/900 (11.56%) | 104/900 (11.56%) | 0.00 | [−0.56, +0.67] |

**Uncertainty:** the frozen, per-condition 2,000-replicate bootstrap resamples `query_id` clusters while retaining three attack seeds and both pipeline arms. Intervals are **nominal/unadjusted**; the four conditions and other metrics create multiple comparisons. Only lexical intensity 1 has a nominal interval excluding zero. The remaining primary intervals include zero. These intervals do not justify a pooled/general defense ranking.

## Construction feasibility, valid-only targeted ASR and generator exposure

The **same construction** is fed into both arms. Across 3,600 attempted construction records, 1,800 were mechanically valid; **552** were target-construction failures and **1,248** were semantic-construction failures. Overall valid coverage = 50.0%. Failure counts are **not defense successes**.

| Attack condition | Mechanically valid / attempted | Dense ASR given valid | RCD ASR given valid | Dense poison exposure given valid | RCD poison exposure given valid |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical, intensity 1 | 762/900 (84.67%) | 50.13% | 56.17% | 96.19% | 94.36% |
| Lexical, intensity 3 | 762/900 (84.67%) | 85.56% | 82.55% | 97.51% | 97.90% |
| Semantic, intensity 1 | 167/900 (18.56%) | 80.24% | 79.64% | 96.41% | 94.61% |
| Semantic, intensity 3 | 109/900 (12.11%) | 95.41% | 95.41% | 99.08% | 100.00% |

The relatively low *end-to-end* semantic ASR is largely a **construction-feasibility effect**, not evidence that either pipeline is strongly resistant to viable semantic attacks. Conversely, very high *conditional* ASR on the small accepted subset cannot be generalized to all attempted semantic constructions. Mechanically accepted semantic examples are **not independently verified false evidence**.

## Legitimate answer quality on valid-construction subsets

Exact match (EM) is the QA answer-correctness measure against the frozen gold answers.

| Attack condition | Dense clean EM | RCD clean EM | Dense poisoned EM | RCD poisoned EM |
| --- | ---: | ---: | ---: | ---: |
| Lexical, intensity 1 | 37.01% | 33.46% | 23.88% | 18.11% |
| Lexical, intensity 3 | 37.01% | 33.46% | 5.64% | 7.48% |
| Semantic, intensity 1 | 16.77% | 12.57% | 5.99% | 4.19% |
| Semantic, intensity 3 | 11.93% | 7.34% | 0.92% | 0.00% |

RCD has lower **clean EM** in all four selected valid-construction subsets. Robustness comparisons must therefore be accompanied by utility, untargeted degradation and exposure analysis. Clean QA answers repeat across attack seeds; their replicated counts must not be treated as independent samples. Low poisoned EM can also reflect a weak clean baseline.

## Protocol accounting

| Account | Aggregate value |
| --- | ---: |
| Actual model backend calls | 4,108 |
| Clean-cache hits | 3,092 |
| Logical QA generation observations | 7,200 |
| Paired cell summaries | 12 |
| Cluster bootstrap replicates per condition | 2,000 |

## Defensible interpretation

1. **No uniform RCD robustness gain.** RCD has *higher* targeted ASR for low-intensity lexical poisoning (47.56% vs Dense 42.44%; Dense − RCD −5.11 pp, nominal CI excludes 0). Lower RCD exposure in that condition does **not** translate into fewer targeted outputs; this is a candidate for a paired failure-case audit, not proof of mechanism.
2. **Possible but uncertain high-intensity lexical advantage.** RCD's point-estimate ASR is lower at intensity 3; the paired CI crosses zero. The separately reported nominal interval for untargeted degradation favors RCD in this condition but is exploratory among multiple endpoints.
3. **Semantic construction is the main bottleneck.** Only 18.56% and 12.11% of semantic attempts were mechanically valid at intensity 1 and 3. End-to-end versus valid-only results must both be reported with denominators and validation limitations.
4. **Utility remains an issue.** RCD's lower clean EM complicates attribution of apparent changes in attack response to a successful defense rather than baseline accuracy differences.
5. **Scope is matched Dense/RCD, not source→target transfer.** The separately planned source-crafted BM25/Dense/Hybrid/Reranker attack-selection and five-target transfer matrix remains unfinished. Do not advertise this 2Wiki study as its substitute.

## Limitations and remaining work

- **Historic exposure:** these 300 2Wiki subjects belong to a historically risk-disclosed replication, not a custody-certified prospective untouched test. The separate semantic-quality V3 prospective stream still lacks its own approvals/fresh-pool certification.
- **Semantic validity:** automatic construction checks do not replace independent human examination; avoid claims of independently verified factual falsity, representativeness or broad adversarial generalization.
- **Inference:** bootstrap CIs are nominal/unadjusted; the 300 unique queries are the independent resampling units, and multiple metrics/conditions demand restraint. Do not invent significance tests or claims of null equivalence from overlapping intervals.
- **Results review:** inspect a transparent, predeclared sample of paired disagreement cases (particularly lexical intensity 1), including retrieved and generator-visible evidence, target and gold answers, answer-extraction issues, and clean answer correctness. Do not tune after observing held-out data.
- **Cross-dataset audit:** compare these results with independently validated HotpotQA outcomes, identifying any differences in dataset, attack construction, protocol and denominator definitions.
- **Recovery:** an iCloud local tar archive of protocol, construction seal and evaluation was created and was locally readable, but its full off-device restoration has not been certified. It omits the complete construction tree, so a full recoverable experiment backup is still needed; do not upload raw checkpoints/weights to GitHub without permission and licensing review.
- **Manuscript scope decision:** seek supervisor approval for either a specifically authorized source-crafted transfer experiment or a narrower manuscript on matched Dense/RCD vulnerability and construction feasibility.

**Release rule:** documentation and aggregate-derived statistics only. Do not edit the frozen dataset/protocol, experiment code, checkpoints, original local result tree, or prompt/weights. This report presents an analysis of an already validated aggregate, **not** a fresh model run or independent raw-artifact reproduction.
