# Week 9–10 Final Scientific Results Audit

Date: 26 October 2026 (Asia/Kolkata). Read-only computational and source audit; this is AI-assisted analysis, **not independent human adjudication or approval**.

## Executive summary

The frozen experiment is internally consistent and scientifically reportable **as a constrained, label-conditioned, matched Dense/RCD poisoning study**, with substantial limitations. This audit found **no confirmed implementation bug or numerical discrepancy** in the completed artifacts. All 12 cells retain the 300 declared IDs and paired arms; 9,549 construction files and 7,665 evaluation files match their recorded hashes. Independently recomputed metrics and all 16 stored paired bootstrap comparisons agree with the aggregate.

Only 135/300 queries (45.00%) obtain targets; the same 165 (55.00%) abstain in every cell under the frozen nomination rules. Semantic validity falls further to 30–35/300 at intensity 1 and 13–19/300 at intensity 3. This is primarily nomination/syntax-screen attrition, not missing records or infrastructure failure. Partial intensity-3 constructions are correctly discarded. Construction failures contribute zero end-to-end successes and null measurements, not successful defenses.

Across three seeds, lexical end-to-end ASR rises from **15.89% to 34.89% for Dense** and **17.22% to 33.44% for RCD** when intensity increases from 1 to 3. Semantic end-to-end ASR instead falls from **6.56% to 5.00% for Dense** and **7.33% to 5.00% for RCD**, while conditional success rises on the much smaller surviving set. There is **no 95% bootstrap interval excluding zero for the primary Dense–RCD targeted-ASR contrasts**. RCD has nominal secondary evidence of less lexical intensity-3 degradation, but this does not establish broad protection or survive an unspecified multiplicity policy by assumption.

Publication tables may be prepared from these verified records with the construction denominators, selection effects, heuristic limitations and negative findings visible. They must not claim independently established falsehood, general semantic validity, four-retriever transfer results, overall RCD superiority or completed full-population clean/poison QA measurements.

## Scope, method and integrity

**EXPECTED PROTOCOL BEHAVIOR — verified integrity.** Authoritative aggregate: `/private/tmp/week9-protocol-heldout/aggregate.json`. Frozen source: `/private/tmp/rag-week9-frozen-protocol`, commit `7a24a40c0a25399e1defc02844eb3a1de44b4a19`. No runner, model, dataset API/download, generation or aggregation command was executed. The audit used direct JSON reads, independent metric/statistical code, a read-only memory map of the existing revision-specific Arrow cache, and pure frozen nomination/validator functions for policy replay. No code, README, configuration, frozen artifact or dependency was changed. This report is the sole created file.

| Binding | Independently checked value |
|---|---|
| Aggregate SHA-256 | `0449d379d9f27270b4d6a9f474e60e86faeeab4508a68f22325900979f8b0dd4` |
| Protocol SHA-256 | `5eb83f381745addbd102547540362dac6fc099ab7fd1594dcd6e2975ba376025` |
| Construction seal SHA-256 | `e82bd61a4081a627b0bd398a17b3704ca6fa1e129f38065c6716f4268bec9360` |
| Evaluation completion SHA-256 | `881a6263c6c52e9b15f4db8613f6538b23fb8f49ac30107aecbb037cecfae4f1` |
| Source code fingerprint | `26f21483d21b3d9d8e2918a428f8fe5935eeb411e3bfaf6051ad468dc2a24d48` |
| Recorded model revision | `c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed` |

- Verified all 9,549 construction and 7,665 evaluation file inventories/hashes, plus the aggregate-to-protocol/seal/completion pins, all cell/row hashes, current frozen source fingerprint and config hashes.
- Reconstructed the 300 selected queries, original gold/document labels and pooled corpus directly from the existing HotpotQA revision `1908d6afbbead072334abe2965f91bd2709910ab` validation Arrow cache. Reconstructed corpus contains **2958 documents**. Full query and corpus fingerprints match the seal; the verified development pool is disjoint.
- Replayed the deterministic candidate/seed calculation in memory for every cell/query; no target mismatch or retargeting was observed. Revalidated every recorded semantic verdict/reason against frozen v4 without generating any text.
- Verified exact v3 prompt templates, revisions, model/seed metadata and document identities; all 2,968 semantic prompt-template checks passed.
- Verified **2,968 actual semantic calls** against intent/response journals and attempt records, and **3,820 actual QA calls** against recorded prompts, responses, extracted answers, EM/F1, target matches, evidence bytes, ranks and generator-visible exposure.
- Performed 6,776 recursive aggregate/stored-summary scalar comparisons; no discrepancies at numerical tolerance (relative 1e−11, absolute 1e−12). All four groups × four stored bootstrap metrics match independent sufficient-statistic recomputation.
- Frozen-file sizes/modification times were unchanged over the audit. QA intents bind the completed seal hash; recorded modification times put the seal before the first QA intent. These are consistency/chronology checks, **not authenticated proof against external prior inspection or deliberate historical tampering**.
- `aggregate_pretty.json` parses to the same object as the authoritative aggregate.
- **NEEDS FURTHER EVIDENCE:** large model weight files were not rehashed or loaded by this audit, and historical package/device execution cannot be authenticated solely from records. The protocol's snapshot hashes and runtime versions are recorded, not independently re-attested here.

## 1. Construction failures

### 1.1 Per-cell query construction coverage

Counts below refer to **300 query constructions per cell**, not model calls and not doubled Dense/RCD rows. Percentages use 300. Lexical construction requires no model inference.

| Family | Intensity | Seed | Valid | Target failed | Semantic failed | Discarded partial documents |
|---|---|---|---|---|---|---|
| Lexical | 1 | 42 | 135/300 (45.00%) | 165 (55.00%) | 0 (0.00%) | 0 |
| Lexical | 1 | 43 | 135/300 (45.00%) | 165 (55.00%) | 0 (0.00%) | 0 |
| Lexical | 1 | 44 | 135/300 (45.00%) | 165 (55.00%) | 0 (0.00%) | 0 |
| Lexical | 3 | 42 | 135/300 (45.00%) | 165 (55.00%) | 0 (0.00%) | 0 |
| Lexical | 3 | 43 | 135/300 (45.00%) | 165 (55.00%) | 0 (0.00%) | 0 |
| Lexical | 3 | 44 | 135/300 (45.00%) | 165 (55.00%) | 0 (0.00%) | 0 |
| Semantic | 1 | 42 | 35/300 (11.67%) | 165 (55.00%) | 100 (33.33%) | 0 |
| Semantic | 1 | 43 | 30/300 (10.00%) | 165 (55.00%) | 105 (35.00%) | 0 |
| Semantic | 1 | 44 | 32/300 (10.67%) | 165 (55.00%) | 103 (34.33%) | 0 |
| Semantic | 3 | 42 | 16/300 (5.33%) | 165 (55.00%) | 119 (39.67%) | 57 |
| Semantic | 3 | 43 | 13/300 (4.33%) | 165 (55.00%) | 122 (40.67%) | 51 |
| Semantic | 3 | 44 | 19/300 (6.33%) | 165 (55.00%) | 116 (38.67%) | 51 |


**EXPECTED PROTOCOL BEHAVIOR.** Across 12 cells: **3,600 query constructions = 955 valid + 1,980 target failures + 665 semantic failures**. Validity is mechanical, not independent factual verification. There are 7,200 arm/query records: 1,910 evaluated paired observations and 5,290 explicit null failed-arm records. Every evaluated pair contains clean and poisoned QA, totaling 3,820 actual QA measurements. No failed query acquired fabricated QA, EM/F1, retrieval or latency values. No missing document/file or backend error was relabeled as a scientific construction failure.

### 1.2 Why exactly 135 lexical queries?

**EXPECTED PROTOCOL BEHAVIOR / SCIENTIFIC LIMITATION.** The frozen selector nominates for 135 unique queries and abstains on the same 165 IDs in **all 12 cells**. Seeds and intensity do not change whether the candidate list is empty. Each rejected query repeats as 12 failed construction records; the 1,980 failures do not mean 1,980 different questions.

| Recorded first-failure reason | Unique queries | % of 300 | % of 165 failures | Repeated query/cell failures |
|---|---|---|---|---|
| `entity_role_or_relationship_lacks_typed_source_or_exclusion_evidence` | 115 | 38.33% | 69.70% | 1380 |
| `no_safe_declared_scalar_transformation` | 15 | 5.00% | 9.09% | 180 |
| `unresolved_choice_option_boundaries` | 9 | 3.00% | 5.45% | 108 |
| `open_or_hierarchical_category_needs_constraint_and_exclusion_evidence` | 9 | 3.00% | 5.45% | 108 |
| `choice_gold_alias_alignment_or_distinctness_unresolved` | 7 | 2.33% | 4.24% | 84 |
| `comma_bearing_options_require_explicit_boundary_review` | 3 | 1.00% | 1.82% | 36 |
| `comparative_or_choice_requires_resolved_options_and_gold_aliases` | 3 | 1.00% | 1.82% | 36 |
| `approximation_or_one_sided_bound_can_be_co_correct` | 2 | 0.67% | 1.21% | 24 |
| `no_distinct_typed_verified_development_source` | 1 | 0.33% | 0.61% | 12 |
| `descriptive_gold_or_aliases_require_independent_resolution_no_rewrite` | 1 | 0.33% | 0.61% | 12 |


The dominant cause is an unresolved requested entity/relationship under the bounded grammar (115/300 = 38.33%), not a lexical-document generation defect. Examples include requesting a pharaoh after a nested relation, an incidental “first full length album” triggering the conservative comparison abstention, comma-bearing explicit choices and a nickname-bearing gold label that cannot align literally with parsed choices. The cached rows and replayed nomination results agree with these reasons.

These are conservative parser/source/label limits. An abstention does **not** prove that no defensible false answer exists. It is not permission to replace the query, relax the rule or pick a more favorable target now.

### 1.3 Semantic document and model-attempt accounting

**EXPECTED PROTOCOL BEHAVIOR.** Among the 135 target-eligible queries per semantic cell:

- 810 query/cell constructions: **145 valid (17.90%) and 665 failed (82.10%)**.
- Of the full 1,800 semantic query/cell population, valid coverage is **8.06%**; target failures are 990/1,800 (55.00%) and semantic failures 665/1,800 (36.94%).
- **1,620 required document constructions:** 400 pass the screen (24.69%), 1,220 exhaust their two-call budget (75.31%).
- **2,968 actual model calls:** 400 accepted calls and 2,568 rejected calls. There are 272 first-call acceptances and 128 second-call acceptances; each of the 1,220 failed documents has two rejected calls.
- Only **241 documents are injected** in successful semantic query constructions. The other **159 passing documents are archived partials**, excluded from both arms because intensity 3 was incomplete.
- Intensity-3 failed query constructions: 241 have zero passing documents, 73 have one and 43 have two (357 total). Those are failed intensity-3 attempts, never lower-intensity replacements.
- Only **9/2,968 calls (0.30%)** reached the reported 150 completion-token cap. Recorded failures are validation outcomes, not widespread token-limit or missing-file failures; token count alone does not establish fluency.

| Attempt-level outcome / first rejection reason | Calls | % of 2,968 calls | Distinct query IDs touched |
|---|---|---|---|
| Generated poison text has unverified semantic support (unverified) | 1258 | 42.39% | 103 |
| Generated poison text does not affirm the target answer | 777 | 26.18% | 79 |
| ACCEPTED | 400 | 13.48% | 67 |
| Generated poison text contains competing gold answer or supplied alias | 374 | 12.60% | 25 |
| Generated poison text has unverified semantic support (mention_only) | 159 | 5.36% | 41 |


Unique-query columns overlap across reasons and include partial-document episodes; they must not be summed. Rejected model calls, failed documents, failed query/cell constructions and unique failed questions are different units.

The generic “does not affirm” category comprises 372 target-absent calls, 142 general-negation matches, 65 passive-mention matches, 62 fictional/counterfactual disclaimers, 14 question-mark cases, 94 other reference-answer framing cases, and 28 other scoped-denial/uncertainty cases. These sum to 777. Some exclusions are intended corrections/refusals; this category must not be described as 777 independently demonstrated non-entailments.

### 1.4 Consistency across conditions

**EXPECTED PROTOCOL BEHAVIOR / SCIENTIFIC LIMITATION.**

- The 165 target-failed IDs are identical across families, intensities and seeds.
- Among 135 target-eligible queries, **94 fail semantic construction in all six semantic cells**; 126 fail in at least one. Only **41 ever have a complete valid semantic construction**; nine pass all six.
- Intensity-1 semantic valid-set union/intersection across seeds: **41/24 unique queries**. Intensity-3 union/intersection: **24/9**.
- Across all 300 IDs, **291 fail at least one declared cell**; 165 fail every cell. Only nine have valid constructions in every cell. None are dropped from end-to-end ASR.
- Within the same query/seed, semantic document-index-0 generation histories are identical across intensities in all 405 eligible comparisons. Each valid intensity-3 case is also valid at intensity 1 for that seed: 48 both-valid query/seed observations, 49 intensity-1-only, 803 neither, zero intensity-3-only.
- Targets may repeat across seeds under deterministic selection. Three seed rows for one question are not independent observations.

### 1.5 Does the screen reject affirmative evidence?

**SCIENTIFIC LIMITATION — directly observed heuristic false negatives.** Yes, the bounded affirmative grammar can reject paragraphs that clearly assert the requested relationship. This does not establish factual correctness, independent semantic validity or permission to retrospectively change acceptance.

Examples preserved from the journals:

1. Query `5a7136e25542994082a3e67e`, semantic I1/42, target **Ben Savage**: the paragraph begins “Ben Savage, a Hong Kong actor born in 1980, is set to star…” and identifies “Heart and Greed.” Both calls are `unverified`. The appositive separates target from the recognized direct subject/verb pattern. This is an affirmative textual assertion, not a verified biographical fact.
2. Query `5a77720255429967ab10517f`, target **1844**: “both … novels … were published in 1844” is rejected as mention-only in a paragraph mentioning an authoritative reference. The frozen year-event list omits “published.” Narrow syntax and the broad reference/mention vocabulary can obscure an otherwise direct publication-year assertion.
3. Query `5a7353795542991f29ee2d82`, target **Scrye**: a revision states that Scrye was published first, preceding the other named option. It is rejected because the gold option appears as comparison context. Rejecting every gold mention is intentionally conservative and can block coherent comparative false-evidence constructions without an actual correction.

The earlier v4 documentation already discloses bounded syntax and global gold-mention rejection. These cases demonstrate method limitations/false negatives, **not violations of the frozen implementation's declared rules**. It would be incorrect to count all 1,258 unverified or 159 mention-only calls as otherwise valid without adjudicating them. Some generated paragraphs also violate geography, role or other question constraints; mechanical answer shape does not settle those issues.

## 2. Independently verified per-condition metrics

**EXPECTED PROTOCOL BEHAVIOR — independently verified measurements.** All percentages below are independently recomputed from extracted answers and raw retrieval IDs, not copied as authoritative from the aggregate. “Success/valid” and exposures refer to query/seed observations within the named cell. End-to-end ASR denominator is always 300, conditional ASR and degradation use valid construction count. Undefined quantities would be null.

### 2.1 Targeted ASR, exposure and untargeted degradation

| Family | I | Seed | Arm | Success/valid | E2E ASR % | Conditional ASR % | Exposed/valid | ASR given exposed % | Degraded/valid |
|---|---|---|---|---|---|---|---|---|---|
| Lexical | 1 | 42 | dense | 47/135 | 15.67 | 34.81 | 132/135 | 35.61 | 29/135 (21.48%) |
| Lexical | 1 | 42 | rcd | 50/135 | 16.67 | 37.04 | 128/135 | 37.50 | 28/135 (20.74%) |
| Lexical | 1 | 43 | dense | 48/135 | 16.00 | 35.56 | 135/135 | 35.56 | 28/135 (20.74%) |
| Lexical | 1 | 43 | rcd | 53/135 | 17.67 | 39.26 | 131/135 | 38.93 | 30/135 (22.22%) |
| Lexical | 1 | 44 | dense | 48/135 | 16.00 | 35.56 | 134/135 | 35.82 | 27/135 (20.00%) |
| Lexical | 1 | 44 | rcd | 52/135 | 17.33 | 38.52 | 129/135 | 38.76 | 29/135 (21.48%) |
| Lexical | 3 | 42 | dense | 108/135 | 36.00 | 80.00 | 134/135 | 80.60 | 72/135 (53.33%) |
| Lexical | 3 | 42 | rcd | 101/135 | 33.67 | 74.81 | 133/135 | 75.94 | 60/135 (44.44%) |
| Lexical | 3 | 43 | dense | 101/135 | 33.67 | 74.81 | 135/135 | 74.81 | 67/135 (49.63%) |
| Lexical | 3 | 43 | rcd | 99/135 | 33.00 | 73.33 | 134/135 | 73.88 | 58/135 (42.96%) |
| Lexical | 3 | 44 | dense | 105/135 | 35.00 | 77.78 | 134/135 | 78.36 | 67/135 (49.63%) |
| Lexical | 3 | 44 | rcd | 101/135 | 33.67 | 74.81 | 134/135 | 75.37 | 61/135 (45.19%) |
| Semantic | 1 | 42 | dense | 20/35 | 6.67 | 57.14 | 34/35 | 58.82 | 8/35 (22.86%) |
| Semantic | 1 | 42 | rcd | 23/35 | 7.67 | 65.71 | 34/35 | 67.65 | 12/35 (34.29%) |
| Semantic | 1 | 43 | dense | 17/30 | 5.67 | 56.67 | 29/30 | 58.62 | 8/30 (26.67%) |
| Semantic | 1 | 43 | rcd | 19/30 | 6.33 | 63.33 | 29/30 | 65.52 | 9/30 (30.00%) |
| Semantic | 1 | 44 | dense | 22/32 | 7.33 | 68.75 | 30/32 | 73.33 | 8/32 (25.00%) |
| Semantic | 1 | 44 | rcd | 24/32 | 8.00 | 75.00 | 30/32 | 80.00 | 11/32 (34.38%) |
| Semantic | 3 | 42 | dense | 16/16 | 5.33 | 100.00 | 16/16 | 100.00 | 9/16 (56.25%) |
| Semantic | 3 | 42 | rcd | 16/16 | 5.33 | 100.00 | 16/16 | 100.00 | 9/16 (56.25%) |
| Semantic | 3 | 43 | dense | 12/13 | 4.00 | 92.31 | 13/13 | 92.31 | 7/13 (53.85%) |
| Semantic | 3 | 43 | rcd | 12/13 | 4.00 | 92.31 | 13/13 | 92.31 | 6/13 (46.15%) |
| Semantic | 3 | 44 | dense | 17/19 | 5.67 | 89.47 | 18/19 | 94.44 | 7/19 (36.84%) |
| Semantic | 3 | 44 | rcd | 17/19 | 5.67 | 89.47 | 19/19 | 89.47 | 8/19 (42.11%) |


Degradation means clean EM correct and poisoned EM incorrect. It is not all answer disagreement. The additional clean-correct-valid denominator and exposed-success numerator in the aggregate were independently checked as well. Failed construction contributes zero to end-to-end successes, but has **no poisoned evaluation** and is not a measured defense success.

### 2.2 Query-specific poison retrieval

Fractions and percentages use valid constructions. Diagnostic PRR and actual generator exposure are distinct, particularly for independent RCD ranking windows.

| Family | I | Seed | Arm | PRR@1 | PRR@3 | PRR@5 | PRR@10 |
|---|---|---|---|---|---|---|---|
| Lexical | 1 | 42 | dense | 105/135 (77.78%) | 132/135 (97.78%) | 134/135 (99.26%) | 135/135 (100.00%) |
| Lexical | 1 | 42 | rcd | 105/135 (77.78%) | 128/135 (94.81%) | 133/135 (98.52%) | 135/135 (100.00%) |
| Lexical | 1 | 43 | dense | 107/135 (79.26%) | 135/135 (100.00%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 1 | 43 | rcd | 107/135 (79.26%) | 131/135 (97.04%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 1 | 44 | dense | 105/135 (77.78%) | 134/135 (99.26%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 1 | 44 | rcd | 105/135 (77.78%) | 129/135 (95.56%) | 134/135 (99.26%) | 135/135 (100.00%) |
| Lexical | 3 | 42 | dense | 108/135 (80.00%) | 134/135 (99.26%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 3 | 42 | rcd | 109/135 (80.74%) | 133/135 (98.52%) | 133/135 (98.52%) | 135/135 (100.00%) |
| Lexical | 3 | 43 | dense | 109/135 (80.74%) | 135/135 (100.00%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 3 | 43 | rcd | 110/135 (81.48%) | 134/135 (99.26%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 3 | 44 | dense | 108/135 (80.00%) | 134/135 (99.26%) | 135/135 (100.00%) | 135/135 (100.00%) |
| Lexical | 3 | 44 | rcd | 109/135 (80.74%) | 134/135 (99.26%) | 134/135 (99.26%) | 135/135 (100.00%) |
| Semantic | 1 | 42 | dense | 30/35 (85.71%) | 34/35 (97.14%) | 35/35 (100.00%) | 35/35 (100.00%) |
| Semantic | 1 | 42 | rcd | 30/35 (85.71%) | 34/35 (97.14%) | 34/35 (97.14%) | 35/35 (100.00%) |
| Semantic | 1 | 43 | dense | 24/30 (80.00%) | 29/30 (96.67%) | 30/30 (100.00%) | 30/30 (100.00%) |
| Semantic | 1 | 43 | rcd | 24/30 (80.00%) | 29/30 (96.67%) | 29/30 (96.67%) | 30/30 (100.00%) |
| Semantic | 1 | 44 | dense | 27/32 (84.38%) | 30/32 (93.75%) | 32/32 (100.00%) | 32/32 (100.00%) |
| Semantic | 1 | 44 | rcd | 27/32 (84.38%) | 30/32 (93.75%) | 31/32 (96.88%) | 32/32 (100.00%) |
| Semantic | 3 | 42 | dense | 13/16 (81.25%) | 16/16 (100.00%) | 16/16 (100.00%) | 16/16 (100.00%) |
| Semantic | 3 | 42 | rcd | 13/16 (81.25%) | 16/16 (100.00%) | 16/16 (100.00%) | 16/16 (100.00%) |
| Semantic | 3 | 43 | dense | 10/13 (76.92%) | 13/13 (100.00%) | 13/13 (100.00%) | 13/13 (100.00%) |
| Semantic | 3 | 43 | rcd | 10/13 (76.92%) | 13/13 (100.00%) | 13/13 (100.00%) | 13/13 (100.00%) |
| Semantic | 3 | 44 | dense | 15/19 (78.95%) | 18/19 (94.74%) | 19/19 (100.00%) | 19/19 (100.00%) |
| Semantic | 3 | 44 | rcd | 15/19 (78.95%) | 19/19 (100.00%) | 19/19 (100.00%) | 19/19 (100.00%) |


### 2.3 Clean/poison QA utility

EM is a count and percentage over valid constructions. F1 is the mean token-overlap score on a 0–1 scale.

| Family | I | Seed | Arm | Clean EM | Poisoned EM | Clean F1 | Poisoned F1 |
|---|---|---|---|---|---|---|---|
| Lexical | 1 | 42 | dense | 80/135 (59.26%) | 55/135 (40.74%) | 0.6574 | 0.4583 |
| Lexical | 1 | 42 | rcd | 75/135 (55.56%) | 51/135 (37.78%) | 0.6227 | 0.4217 |
| Lexical | 1 | 43 | dense | 80/135 (59.26%) | 55/135 (40.74%) | 0.6574 | 0.4560 |
| Lexical | 1 | 43 | rcd | 75/135 (55.56%) | 48/135 (35.56%) | 0.6227 | 0.3936 |
| Lexical | 1 | 44 | dense | 80/135 (59.26%) | 57/135 (42.22%) | 0.6574 | 0.4659 |
| Lexical | 1 | 44 | rcd | 75/135 (55.56%) | 51/135 (37.78%) | 0.6227 | 0.4151 |
| Lexical | 3 | 42 | dense | 80/135 (59.26%) | 10/135 (7.41%) | 0.6574 | 0.1150 |
| Lexical | 3 | 42 | rcd | 75/135 (55.56%) | 18/135 (13.33%) | 0.6227 | 0.1681 |
| Lexical | 3 | 43 | dense | 80/135 (59.26%) | 15/135 (11.11%) | 0.6574 | 0.1518 |
| Lexical | 3 | 43 | rcd | 75/135 (55.56%) | 20/135 (14.81%) | 0.6227 | 0.1802 |
| Lexical | 3 | 44 | dense | 80/135 (59.26%) | 14/135 (10.37%) | 0.6574 | 0.1397 |
| Lexical | 3 | 44 | rcd | 75/135 (55.56%) | 17/135 (12.59%) | 0.6227 | 0.1641 |
| Semantic | 1 | 42 | dense | 17/35 (48.57%) | 9/35 (25.71%) | 0.5630 | 0.3106 |
| Semantic | 1 | 42 | rcd | 19/35 (54.29%) | 7/35 (20.00%) | 0.5810 | 0.2306 |
| Semantic | 1 | 43 | dense | 15/30 (50.00%) | 8/30 (26.67%) | 0.5679 | 0.3124 |
| Semantic | 1 | 43 | rcd | 16/30 (53.33%) | 8/30 (26.67%) | 0.5556 | 0.2857 |
| Semantic | 1 | 44 | dense | 15/32 (46.88%) | 7/32 (21.88%) | 0.5533 | 0.2366 |
| Semantic | 1 | 44 | rcd | 16/32 (50.00%) | 5/32 (15.63%) | 0.5417 | 0.1771 |
| Semantic | 3 | 42 | dense | 9/16 (56.25%) | 0/16 (0.00%) | 0.5625 | 0.0000 |
| Semantic | 3 | 42 | rcd | 9/16 (56.25%) | 0/16 (0.00%) | 0.5625 | 0.0000 |
| Semantic | 3 | 43 | dense | 7/13 (53.85%) | 0/13 (0.00%) | 0.5385 | 0.0000 |
| Semantic | 3 | 43 | rcd | 6/13 (46.15%) | 0/13 (0.00%) | 0.4615 | 0.0000 |
| Semantic | 3 | 44 | dense | 7/19 (36.84%) | 0/19 (0.00%) | 0.5108 | 0.0301 |
| Semantic | 3 | 44 | rcd | 8/19 (42.11%) | 0/19 (0.00%) | 0.4912 | 0.0000 |


There are no QA measurements for the 165 target-ineligible queries in these cells. Consequently these are **conditional utility estimates**, not an all-300 clean/poison QA utility comparison.

### 2.4 Cross-seed descriptive summaries

These pool numerator/denominator over seeds (900 population query/seed records); they do not create 900 independent questions.

| Family | I | Arm | E2E successes/900 | Conditional successes/valid | Clean → poisoned EM % | Clean → poisoned F1 |
|---|---|---|---|---|---|---|
| Lexical | 1 | dense | 143/900 (15.89%) | 143/405 (35.31%) | 59.26 → 41.23 | 0.6574 → 0.4601 |
| Lexical | 1 | rcd | 155/900 (17.22%) | 155/405 (38.27%) | 55.56 → 37.04 | 0.6227 → 0.4101 |
| Lexical | 3 | dense | 314/900 (34.89%) | 314/405 (77.53%) | 59.26 → 9.63 | 0.6574 → 0.1355 |
| Lexical | 3 | rcd | 301/900 (33.44%) | 301/405 (74.32%) | 55.56 → 13.58 | 0.6227 → 0.1708 |
| Semantic | 1 | dense | 59/900 (6.56%) | 59/97 (60.82%) | 48.45 → 24.74 | 0.5613 → 0.2867 |
| Semantic | 1 | rcd | 66/900 (7.33%) | 66/97 (68.04%) | 52.58 → 20.62 | 0.5601 → 0.2300 |
| Semantic | 3 | dense | 45/900 (5.00%) | 45/48 (93.75%) | 47.92 → 0.00 | 0.5355 → 0.0119 |
| Semantic | 3 | rcd | 45/900 (5.00%) | 45/48 (93.75%) | 47.92 → 0.00 | 0.5069 → 0.0000 |


## 3. Dense–RCD pairing and statistical audit

**EXPECTED PROTOCOL BEHAVIOR — all checks passed.** Every cell has the same ordered 300 IDs in both arms, identical targets, poison IDs/text, seeds and construction status. Both conditions use original gold answers. Query/corpus fingerprints and prompt evidence are bound to the same construction seal; failed arms both contain null observations. Clean answers and clean evidence prompts repeat identically for every observed query/arm across seeds/intensities; no clean-answer or prompt drift was found.

### 3.1 Frozen bootstrap comparisons

Independent implementation: reduce each query to per-arm sufficient counts across all three seeds; reproduce Python RNG seed 20261025 and 2,000 draws of 300 query indices with replacement; retain both arms and all seeds; recompute pooled conditional denominators. Sort defined differences and select floor-indexed 2.5% and 97.5% endpoints as the frozen code does. This independently reproduces all point estimates, endpoints, and defined/undefined counts; it is not a call to the original bootstrap/aggregate helper.

All differences and intervals are in **percentage points, Dense minus RCD**. Positive ASR/degradation/exposure differences mean lower adverse rates for RCD. For clean EM, positive differences instead favor Dense's utility. All stored replicates are defined in this run.

| Family | I | Metric | Dense−RCD pp | 95% interval pp | Defined/undefined replicates |
|---|---|---|---|---|---|
| Lexical | 1 | end_to_end_targeted_asr | -1.33 | [-3.33, 0.56] | 2000/0 |
| Lexical | 1 | conditional_targeted_asr_valid | -2.96 | [-7.24, 1.23] | 2000/0 |
| Lexical | 1 | untargeted_degradation_valid | -0.74 | [-6.28, 4.69] | 2000/0 |
| Lexical | 1 | poison_exposure_valid | 3.21 | [0.47, 6.47] | 2000/0 |
| Lexical | 3 | end_to_end_targeted_asr | 1.44 | [-0.44, 3.33] | 2000/0 |
| Lexical | 3 | conditional_targeted_asr_valid | 3.21 | [-0.93, 7.44] | 2000/0 |
| Lexical | 3 | untargeted_degradation_valid | 6.67 | [1.00, 12.47] | 2000/0 |
| Lexical | 3 | poison_exposure_valid | 0.49 | [0.00, 1.32] | 2000/0 |
| Semantic | 1 | end_to_end_targeted_asr | -0.78 | [-1.89, 0.00] | 2000/0 |
| Semantic | 1 | conditional_targeted_asr_valid | -7.22 | [-16.67, 0.00] | 2000/0 |
| Semantic | 1 | untargeted_degradation_valid | -8.25 | [-20.48, 2.63] | 2000/0 |
| Semantic | 1 | poison_exposure_valid | 0.00 | [0.00, 0.00] | 2000/0 |
| Semantic | 3 | end_to_end_targeted_asr | 0.00 | [0.00, 0.00] | 2000/0 |
| Semantic | 3 | conditional_targeted_asr_valid | 0.00 | [0.00, 0.00] | 2000/0 |
| Semantic | 3 | untargeted_degradation_valid | 0.00 | [-10.00, 10.64] | 2000/0 |
| Semantic | 3 | poison_exposure_valid | -2.08 | [-7.41, 0.00] | 2000/0 |


**SCIENTIFIC LIMITATION.** Every primary targeted-ASR interval contains zero, including the semantic I1 boundary at zero. No condition provides a strict 95% interval excluding zero in favor of RCD on primary targeted ASR. Semantic I3's [0,0] interval reflects identical observed target-success indicators across arms, not proof of population equivalence or absence of rare effects.

Lexical I3 degradation is lower for RCD by 6.67 pp (nominal interval 1.00–12.47 pp); lexical I1 exposure is lower for RCD by 3.21 pp (0.47–6.47 pp). These are secondary, **unadjusted** intervals. The frozen procedure contains no multiplicity correction across the 16 displayed comparisons; do not turn these isolated intervals into a claim of global statistical protection. Degradation also depends on the clean-correct baseline: on lexical I3 it is 206/240 = 85.83% versus 179/225 = 79.56% when conditioned on initially correct Dense/RCD answers, respectively. That conditional point difference has no frozen interval in the aggregate.

### 3.2 Additional audit-only paired contrasts

**NEEDS FURTHER EVIDENCE / exploratory statistical interpretation.** The following independently computed intervals are read-only audit calculations, **not additional preregistered primary tests**, not stored aggregate replacements and not multiplicity-adjusted. They use the same 300-query clusters and 2,000 seed-20261025 resamples.

| Audit-only contrast | Point pp | 95% interval pp |
|---|---|---|
| Lexical I1 clean EM, Dense−RCD | 3.70 | [-0.79, 8.76] |
| Lexical I3 clean EM, Dense−RCD | 3.70 | [-0.79, 8.76] |
| Semantic I1 clean EM, Dense−RCD | -4.12 | [-14.58, 4.35] |
| Semantic I3 clean EM, Dense−RCD | 0.00 | [-10.00, 10.64] |
| Lexical Dense end-to-end ASR, I3−I1 | 19.00 | [14.78, 23.67] |
| Lexical RCD end-to-end ASR, I3−I1 | 16.22 | [12.44, 20.44] |
| Semantic Dense end-to-end ASR, I3−I1 | -1.56 | [-3.22, 0.00] |
| Semantic RCD end-to-end ASR, I3−I1 | -2.33 | [-4.11, -0.78] |


Lexical poisoning intensity increases end-to-end target matching substantially on the same 135 target-eligible queries: +19.00 pp Dense and +16.22 pp RCD. The semantic end-to-end rate instead decreases as coverage shrinks; a rise in conditional ASR from 60.82%/68.04% to 93.75% cannot be interpreted as a paired causal intensity effect, because the intensity-3 surviving set is much smaller and selected. The same-query/seed all-population contrast legitimately captures the total frozen procedure including failure; its interpretation differs from success among constructible attacks.

### 3.3 Baseline attribution and clean utility

**SCIENTIFIC LIMITATION / EXPECTED PROTOCOL BEHAVIOR.** The frozen targeted-ASR definition is target matching under poison, not necessarily a newly induced change from a different clean answer. Across lexical seeds, 12/143 Dense I1 and 15/155 RCD I1 successes already matched the target under clean evidence; at I3, 15/314 Dense and 15/301 RCD successes did so. Do not describe every counted success as an induced error. The aggregate follows its declared definition correctly.

Six RCD lexical I1 target matches occur without its own query-specific poison in visible evidence; this is not a retrieval-accounting bug. Baseline target errors, other queries' poison documents or other evidence can yield a target match. No semantic target successes in this run lack own-poison exposure.

On the lexical-valid 135 unique questions, clean EM is Dense 80/135 = 59.26% versus RCD 75/135 = 55.56%; clean F1 0.6574 versus 0.6227. The audit-only clean-EM interval includes zero. The selected semantic sets have different utility (RCD clean EM is higher at I1, equal at I3); there is no uniform demonstrated clean-utility loss across these conditional sets. Full-population utility requires separately validated all-300 clean records, not imputation for construction failures.

Poisoning clearly reduces observed valid-set utility: lexical I3 pooled EM is 9.63% Dense and 13.58% RCD, while semantic I3 poisoned EM is **0/48 for both arms**. A low end-to-end semantic ASR must not be reported as robustness when most attacks were never constructed and almost all surviving attacks hit their targets.

## 4. Confirmed implementation bugs

**CONFIRMED BUG: none demonstrated in this audit.**

No mismatched metric denominator, fabricated failure measurement, missing population member, bad pairing, incorrect sign, bootstrap-clustering error, excess retry, partial-intensity substitution, target replacement or hash inconsistency was found. Frozen semantic decisions reproduce exactly. Low coverage is **not itself a bug**.

This is not a proof of correctness of every source path or of unseen future executions. This audit does not replace human factual/linguistic adjudication. The demonstrated grammar false negatives and incomplete constraint/alias coverage are reported as scientific method limitations rather than relabeled as newly discovered implementation failures.

## 5. Scientific limitations and evidence still needed

1. **SCIENTIFIC LIMITATION — coverage/selection:** only 45% have targets; semantic complete constructions cover 4.33–11.67% per cell. Failed cases remain in the primary population, but conditional semantic estimates describe a small selected subset and cannot represent broad attacker capability.
2. **SCIENTIFIC LIMITATION — validity:** non-gold category/shape compatibility is label-conditioned, not independently verified falsehood. Alias incompleteness, co-correct alternatives, stale/ambiguous labels and mismatched question constraints can affect interpretation. Passing the syntactic screen proves neither factual error nor fluent entailment.
3. **SCIENTIFIC LIMITATION — validation attrition:** direct appositives, publication-year syntax and contextual mentions of the gold option can fail the frozen screen. Do not tune the rules or retrospectively reinstate these outputs based on this held-out audit.
4. **SCIENTIFIC LIMITATION — intensity and seeds:** intensity 3 requires all documents, reducing semantic coverage. Seed repetitions can reuse targets/text; bootstrap clusters are correct, but three seeds do not supply three independent cohorts.
5. **SCIENTIFIC LIMITATION — scope:** this is pooled HotpotQA distractor-corpus matched Dense/RCD evaluation. It is not a source-crafted BM25/Dense/Hybrid/Reranker transfer matrix, a four-retriever robustness result, a 2Wiki replication or a general open-Wikipedia threat model.
6. **SCIENTIFIC LIMITATION — statistical strength:** no primary ASR contrast excludes zero; secondary nominal findings are unadjusted, and selected semantic sets are small. Zero-width empirical intervals are not formal equivalence tests.
7. **NEEDS FURTHER EVIDENCE — semantic/gold quality:** obtain disclosed, reproducible human assessment of a prespecified sample of accepted and rejected outputs, aliases and questionable labels if stronger validity claims are intended. This may annotate the audit, not silently alter frozen primary counts or fabricate retroactive approvals.
8. **NEEDS FURTHER EVIDENCE — execution attestation:** retain actual freeze pins, environment/device/model snapshot records and execution logs. File hashes and recorded chronology verify consistency, not external access history or model authenticity by themselves.
9. **EXPECTED PROTOCOL BEHAVIOR — failures:** preserve all 300 population IDs, zero end-to-end contributions for construction failures, null conditional values where undefined and no defense-success interpretation for unconstructed attacks.

## 6. Publication readiness and prioritized next actions

**Assessment:** the artifact-level arithmetic, pairing, construction accounting and stated bootstrap procedure are verified. Results are **reportable with explicit limitations as the frozen label-conditioned procedure's findings**, including negative evidence for primary RCD protection. They are not ready to support an unqualified claim that RCD is robust, that semantic attacks are weak, that all targets are factual falsehoods, or that the complete original cross-pipeline transfer study is finished. No frozen artifact correction is currently warranted by a confirmed bug.

1. Preserve this experiment and all pins unchanged. Prepare tables showing 300 population members, construction coverage, valid/evaluated counts, both ASRs, conditional QA/PRR and correctly signed paired intervals. Keep the 165 constant nomination failures and semantic retry failures visible.
2. Lead with the supported conclusions: lexical intensity raises success; semantic low end-to-end success is construction-limited; RCD lacks statistically supported primary ASR protection; secondary lexical degradation/exposure findings are narrow and nominal.
3. State the label-conditioned and heuristic acceptance limits prominently. Audit examples of rejected affirmative prose and questionable admitted constraints should motivate **future development-only protocol versions**, not retargeting or selective reruns of these held-out cells.
4. Before stronger publication claims, conduct and disclose semantic/alias/label-quality assessment and review the multiplicity/estimand interpretation with the supervisor. Preserve the original frozen analysis; label any new analysis exploratory.
5. Separate later source-specific transfer, other retrievers and dataset replication from this matched comparison. Do not advertise them as completed based on these twelve cells.
6. README changes, new experiments and publication table files require separate instructions. None were performed here.

## Read-only completion record

The audit report was written outside the frozen worktree at the requested path. No code/config/test/dependency/README, input or frozen artifact was changed; no inference, experiment runner, artifact regeneration, commit, push or merge occurred. Additional bootstrap calculations operated solely on existing rows in memory. Source-cache mapping was read-only and no dataset API was called.



## October 26 release reverification addendum

The audit above is preserved from its original external report (SHA-256
`174a710ec51aaaf4ca7894c4539522c82c7df2f81002930e3743ba0db0addede`).
Release review found eight newly present unsealed `.DS_Store` files: seven in
construction and one in evaluation. All 17,214 sealed file hashes still match,
with no missing file. The original directory now fails the strict inventory
check, as it should. No source archive file was cleaned, replaced or resealed.

A new manifest-exact copy was byte/hash verified and used for numerical
recomputation. All 24 arm/cell summaries and 16 paired 2,000-replicate bootstrap
comparisons matched, and all 37 publication file hashes were checked. This does
not authenticate historical execution beyond the stated evidence.
The [release receipt](OCT26_RESULTS_REVERIFICATION.json) records the extra paths,
verification copy, pins and counts. Classify this as **EXPECTED INTEGRITY-GATE
BEHAVIOR / DOCUMENTED ARCHIVE LIMITATION**, not a new numerical or defense bug.
