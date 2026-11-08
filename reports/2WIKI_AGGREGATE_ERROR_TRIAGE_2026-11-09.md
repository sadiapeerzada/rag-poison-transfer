# 2Wiki aggregate-level error triage — before case review

**Scope:** exploratory, read-only aggregate-level diagnosis of the completed 2Wiki study. **Not** a human or independent case-level semantic adjudication. Source: uploaded, validated `aggregate.json` SHA-256 `721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96`.

## Candidate paired disagreements and failure modes

The table pools the three seeds within each condition, **not** treating them as independent queries. All counts are over the same valid construction population in each arm.

| Condition | Valid construction cases | Dense targeted successes | RCD targeted successes | Dense poison visible | RCD poison visible | Dense clean correct | RCD clean correct | Dense poisoned correct | RCD poisoned correct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical I1 | 762 | 382 | 428 | 733 | 719 | 282 | 255 | 182 | 138 |
| Lexical I3 | 762 | 652 | 629 | 743 | 746 | 282 | 255 | 43 | 57 |
| Semantic I1 | 167 | 134 | 133 | 161 | 158 | 28 | 21 | 10 | 7 |
| Semantic I3 | 109 | 104 | 104 | 108 | 109 | 13 | 8 | 1 | 0 |

**Priority A — lexical intensity 1:** RCD produced **46 more** target matches than Dense (428 vs 382) despite **14 fewer** poison-visible observations (719 vs 733). RCD's clean EM also trails (255 vs 282). This is not sufficient to claim RCD is intrinsically more gullible *after equal exposure*: the observed exposed sets and clean baseline differ. Sample paired **RCD-only versus Dense-only** target successes and inspect actual generator-visible evidence, generation/extraction, retriever rankings, and target/gold alias handling.

**Priority B — lexical intensity 3:** RCD has **23 fewer** targeted successes (629 vs 652), although poison visibility is **three observations higher** (746 vs 743). It also preserves 14 more correct poisoned answers (57 vs 43). The primary paired targeted-ASR CI includes zero; investigate heterogeneity rather than presenting RCD as unambiguously protective.

**Priority C — semantic constructor and validity:** Among 900 attempted constructions per condition, target failures = **138** at both intensities; semantic construction fails **595** at intensity 1 and **653** at intensity 3. This yields **167/900** and **109/900** mechanically valid cases, respectively. High valid-only targeted ASR is selection-conditioned. Human reviewers must distinguish validator rejection due to syntax from (i) lack of target assertion, (ii) incompatible entity/relation/time/alias constraints, and (iii) evidence that is *actually false*, not just non-gold-labeled. Review rejected examples as failures, **without reclassifying them in frozen metrics**.

**Priority D — clean-answer utility:** Within the lexical-valid query subset, clean EM is Dense **282/762 (37.01%)** versus RCD **255/762 (33.46%)**. Because these include repeated observations on the same queries across three seeds, they are not 762 distinct baseline questions. Case-level clean-only disagreements are essential before attributing a lower poisoned EM or ASR to defense behavior. Semantic valid subsets differ across conditions and must not be described as the same set as lexical.

**Priority E — exposure versus diagnostic retrieval:** RCD's diagnostic PRR@10 and the actual generator-visible evidence are different windows in the frozen protocol. Inspect `generation_evidence_doc_ids` and matching raw prompts, **not only diagnostic rank**, when trying to explain why a poisoned document affected an answer.

## Review criteria and stopping rule

Use the [frozen-case census and deterministic review packet](../scripts/audit_2wiki_paired_cases.py) from the [operator runbook](../docs/2WIKI_RECOVERY_AND_PAIRED_ERROR_AUDIT_RUNBOOK.md). The packet is **post hoc** and outcome-revealing; it is not a blinded confirmatory sample. Require documented third-party sources for claims of factual falsehood. Resolve reviewer disagreement and record unresolved/uncertain judgments explicitly. Do not invent a human verdict, infer a generalizable false-positive rate from this targeted sample, retune the held-out experiment, or silently change any denominator.

**Status:** aggregate-level triage DONE; case-level comparison and independently sourced semantic adjudication **PENDING** until the operator exports the 3,600 paired records and humans judge the packet.
