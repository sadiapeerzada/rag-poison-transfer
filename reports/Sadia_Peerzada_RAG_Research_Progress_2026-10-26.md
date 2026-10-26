# Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG

## Interim research progress — Sadia Peerzada

**26 October 2026 — prepared for professor review**

**Status: verified progress snapshot; final research execution is incomplete.**
This report was prepared with AI assistance from inspected source documents,
repository implementation, frozen experimental records, and independently
recomputed statistics. It is not independent human review, supervisor sign-off,
or certification of semantic poison correctness. The final results handoff will be revised after transfer and replication
complete. No favorable result has been assumed. The existing README has received
factual status updates while retaining its headings, images, historical tables
and presentation. This is an interim research handout, not a manuscript.

## Executive assessment

Week 7–8 RCD development was approved and closed in the October 13 supervisor
review. The completed Week 9–10 HotpotQA matched Dense/RCD experiment now passes a
read-only integrity audit. All 12 declared conditions preserve the 300-query
population, matched poison instances and failure records. Independently
recomputed metrics and all 16 stored paired bootstrap comparisons agree with the
aggregate. No confirmed implementation bug was identified in that frozen run. Release
reverification subsequently found eight unsealed Finder metadata files; sealed
contents remain unchanged, as documented below.

The findings are scientifically reportable as a **constrained, label-conditioned
non-gold-target poisoning study**. They do not establish broad RCD superiority.
Lexical end-to-end targeted ASR increases with intensity, but semantic end-to-end
ASR does not because construction coverage declines sharply. All four primary
Dense–RCD paired targeted-ASR 95% intervals include zero. Low construction
coverage and heuristic acceptance limit generalization; construction failures are
not defense successes.

The majority of implementation work and the primary HotpotQA experimental study
are complete. Publication tables and figures have been exported and checked.
Bounded source-only transfer, risk-disclosed 2Wiki replication and new reliability
paths passed software checks, but neither remaining full experiment has run. The historical 25-query 2Wiki sweep
IDs could not be recovered. The new cohort excludes the 300 known baseline IDs,
but **complete historical non-overlap cannot be certified**. Substantial new compute requires approval; a test suite or metadata preflight
cannot substitute for real-model experiment validation. Both workflows are
prepared with documented limitations, including a new bounded cache/resume smoke,
storage headroom and the unresolved 2Wiki pilot exposure.

## Milestone status

| Milestone | Status | Evidence | Remaining blocker |
|---|---|---|---|
| Scientific audit | COMPLETE for frozen HotpotQA | `SCIENTIFIC_AUDIT.md`; 17,214 sealed files; independent metrics and bootstrap checks | External factual/semantic adjudication remains a limitation |
| HotpotQA tables and figures | COMPLETE as validated exports | `week9-publication-2026-10-26-v1/`, CSV/Markdown/LaTeX tables and SVG/PDF/PNG figures | Author/journal presentation review; not a claim of completed full paper |
| Cross-pipeline transfer | PARTIAL | Source-only bounded selection, tests, frozen budget; verified 40-condition development smoke | Full compute approval, execution and validation; bounded smoke passed |
| 2Wiki replication | PARTIAL | Frozen 300 train + 300 dev IDs; train-only preparation; metadata preflight; tested adapter | Unknown historical exposure; full execution approval and validation |
| Existing README | UPDATED | Original headings, section order, images and historical tables retained; factual status changes only | Final result updates after remaining studies |
| Interim professor handout | PREPARED | This evidence-backed report and linked publication package | Final experimental report after the two full studies |

## Comparison with the binding plan and October 13 review

Both supplied original documents were read. Their local SHA-256 values are:

- `Sadia_Peerzada_RAG_Research_Experiment_Plan.docx`:
  `ee361dfca338c532a8811e0d9847d77bbde42b2684c2173eb188f17c1c5c68eb`.
- `Sadia_Current_GitHub_and_Week9_Readiness_Review_2026-10-13.pdf`:
  `53b63a883dcd7e0bf4c5423b3d560e3930028b34aa428927063dff0478ca9477`.

| Requirement | Verified progress | Remaining work / interpretation |
|---|---|---|
| Composite RCD development, frozen before held-out evaluation | October 13 review approves Week 7–8 closure; Dense backbone with BM25 signal and up to three additional unique rule rewrites | No retuning on held-out results; one RCD defense, not four wrappers |
| Development readiness | exp_026: 300 unique development rows, EM 0.400, F1 0.5047, R@3 0.7533, MRR@10 0.9424, clean commit `a0a2d1793087e3c2ab9669d93bb040a60b822e34` | These are development retrieval/QA metrics, not held-out defense effects |
| Matched HotpotQA before broader studies | Frozen 12-cell study complete and audited | Coverage limits remain visible; exploratory exp_028b and 10-query exp_029 are not confirmatory evidence |
| Source-crafted cross-pipeline transfer | BM25/Dense/Hybrid/Reranker implementation exists; new bounded source-only selection runner prepared | Existing matched Dense/RCD results do not answer source-crafted transfer RQ; no new transfer results yet |
| Separate multi-hop replication | 2Wiki cohort frozen, development answers prepared and metadata checked | No replication outcomes; unknown historical 25-query exposure disclosed |
| Attack severity and robustness | Intensities 1 and 3, three poison seeds, both attack families complete for primary study | Original broader intensity-5/low-rate analyses are not completed here |
| Utility, latency, statistics and error analysis | Paired EM/F1, PRR/exposure, latency exports, query-cluster bootstrap, construction failure audit | Latency caveats, multiplicity, manual representative error analysis, detection/faithfulness analyses remain |
| Broader journal evidence | One completed matched dataset/model study | Second model, ablations, full transfer/replication and remaining plan analyses are unfinished |

The supervisor's later clarification replaces mandatory individual signed target
assignments for this held-out protocol with frozen outcome-independent
construction. It does not create independent factual verification. Historical
human-review functionality remains available for other experiments.

The original single-hop versus multi-hop question is not resolved by two
multi-hop datasets alone. Pipeline-sensitivity hypotheses also require the
uncompleted source-crafted comparisons; the matched Dense/RCD study is not a
substitute for them. No ablation-based mechanism claim or second-model robustness
claim is made here.

## Implemented retrieval and poisoning components

The four baseline pipelines use a shared build/retrieve interface: BM25 sparse
retrieval; normalized BGE dense embeddings with cosine ranking; Hybrid reciprocal-
rank fusion; and a dense candidate pool followed by cross-encoder reranking.
These are implemented components with prior real baseline/sweep evidence. They
must not be mistaken for completed Week 9–10 source-crafted transfer results.
RCD is a fifth, defended target in the transfer workflow, not four RCD wrappers.

The lexical influential-token attack repeats question-derived terms and asserts
its intended non-gold answer. Semantic fluent false evidence uses the local MLX
generator to produce an affirmative reference-style paragraph. The frozen study
uses intensities one and three, exact document-count requirements, two semantic
attempts per document, and retained raw attempts/reasons. Earlier Week 5–6 sweeps
also explored intensity five and low poison rate; those historical PRR results
do not supply final source-crafted ATR or replace the current held-out study.

## Frozen RCD implementation and configuration

The single composite defense uses a Dense primary retriever, BM25 evidence signal,
and up to three additional unique rule-based rewrites. Its frozen score is
`0.45 × consistency + 0.00 × redundancy − 0.10 × conflict + 0.45 × base rank`.
The candidate pool is 10 and generator evidence depth is three. Consistency
combines document-presence agreement, rank stability and rewrite stability.
Conflict detection is a narrow year-disagreement heuristic with lexical overlap,
not a general semantic contradiction detector. Redundancy is implemented but has
zero frozen weight. No weight, retrieval implementation or query rewrite was
retuned for this release or for the observed HotpotQA outcomes.

## Exact HotpotQA findings

Dataset: fixed 300 HotpotQA validation IDs, revision
`1908d6afbbead072334abe2965f91bd2709910ab`; reconstructed corpus 2,958 documents.
Conditions: lexical influential-token and semantic fluent false evidence,
intensities 1/3, poison seeds 42/43/44, matched Dense and composite RCD.
Greedy Qwen2.5-7B-Instruct-4bit MLX model, revision
`c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`.

### Construction accounting

- All 12 cells retain 300 IDs: 3,600 query/cell constructions.
- 955 valid (26.53%), 1,980 target-construction failures (55.00%),
  665 semantic-construction failures (18.47%). These are repeated query/cell
  counts, not counts of distinct questions.
- The same 165 unique queries fail target nomination in every cell. Lexical
  construction is valid for 135/300 (45.00%) in each condition.
- Main target failure cause: entity/relationship lacks typed source or exclusion
  evidence, 115/300 unique queries. The audit lists all remaining categories.
- Semantic valid counts, seeds 42/43/44: intensity 1 = 35/30/32; intensity 3 =
  16/13/19. Only 41 unique queries have any successful semantic construction;
  9 succeed in all six semantic conditions.
- 2,968 semantic calls: 400 accepted by the heuristic, 2,568 rejected. Of 1,620
  requested documents, 1,220 exhaust the fixed two-attempt budget. Only 241
  accepted documents are injected; 159 are archived partials of incomplete
  intensity-3 constructions.
- 7,200 arm records = 1,910 valid-arm records and 5,290 explicit null failed-arm
  records. There are 3,820 actual clean/poison QA calls. Failure records contain
  no invented poisoned QA, retrieval, EM/F1 or latency.

This attrition is expected frozen-policy behavior and a scientific limitation,
not demonstrated missing-data or infrastructure bugs. Conservative grammar may
reject valid paraphrases; accepting a paragraph is not independent entailment or
proof that its target is factually false.

### Targeted attack success pooled over three seeds

End-to-end denominator is 900 query/seed observations per attack/intensity and
arm; inference resamples 300 query clusters. Conditional denominators are shown.

| Attack / intensity | Valid / 900 | Dense successes | Dense E2E ASR | RCD successes | RCD E2E ASR | Dense conditional ASR | RCD conditional ASR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lexical / 1 | 405 | 143 | 15.89% | 155 | 17.22% | 35.31% | 38.27% |
| Lexical / 3 | 405 | 314 | 34.89% | 301 | 33.44% | 77.53% | 74.32% |
| Semantic / 1 | 97 | 59 | 6.56% | 66 | 7.33% | 60.82% | 68.04% |
| Semantic / 3 | 48 | 45 | 5.00% | 45 | 5.00% | 93.75% | 93.75% |

Failed construction contributes zero targeted successes to end-to-end ASR and
is not counted as a successful defense. Conditional results describe a selected
subset; higher conditional semantic ASR at intensity 3 cannot be interpreted as
an isolated causal intensity effect over identical valid questions.

### Paired statistical findings

Positive differences below mean higher ASR for Dense, hence lower ASR for RCD.
95% percentile intervals use 2,000 paired query-cluster bootstrap replicates,
seed 20261025, preserving each query's repeated poison-seed observations.

| Attack / intensity | Dense minus RCD E2E ASR, percentage points | 95% interval, percentage points |
|---|---:|---:|
| Lexical / 1 | −1.333 | [−3.333, 0.556] |
| Lexical / 3 | 1.444 | [−0.444, 3.333] |
| Semantic / 1 | −0.778 | [−1.889, 0.000] |
| Semantic / 3 | 0.000 | [0.000, 0.000] |

**No primary interval excludes zero.** The degenerate last interval reflects
identical observed paired success flags, not an equivalence test. RCD's point
ASR is worse at intensity 1 in both attack families. A secondary lexical
intensity-3 degradation contrast favors RCD by 6.667 percentage points,
95% interval [0.995, 12.468]; lexical intensity-1 exposure difference is 3.210
points [0.466, 6.468]. These are nominal, unadjusted secondary findings and do
not establish general RCD protection.

Clean QA on the 135 lexical-valid unique queries: Dense EM 80/135 = 59.26%,
F1 0.65743; RCD EM 75/135 = 55.56%, F1 0.62273. The clean EM contrast interval
includes zero. These are not clean-QA estimates over all 300 queries. At semantic
intensity 3, both arms' poisoned EM is 0/48, illustrating severe conditional
utility loss despite limited construction coverage.

Full per-cell PRR@1/3/5/10, generator exposure, EM/F1 retention, degradation,
retrieval overhead and timing are in the [committed export package](../paper/results/hotpotqa_week9_2026-10-26/INTERPRETATION.md).
Useful entries are [targeted ASR](../paper/results/hotpotqa_week9_2026-10-26/targeted_asr.md),
[retrieval/exposure](../paper/results/hotpotqa_week9_2026-10-26/retrieval_and_exposure.md),
[utility](../paper/results/hotpotqa_week9_2026-10-26/utility_retention.md),
[paired intervals](../paper/results/hotpotqa_week9_2026-10-26/paired_effects.md) and
[latency](../paper/results/hotpotqa_week9_2026-10-26/latency_and_calls.md).
Figures show [intensity](../paper/results/hotpotqa_week9_2026-10-26/intensity_asr.svg),
[coverage](../paper/results/hotpotqa_week9_2026-10-26/construction_coverage.svg) and
[paired effects](../paper/results/hotpotqa_week9_2026-10-26/paired_asr_effects.svg). Backend-reported
generation time and measured outer QA time are retained separately; occasional
backend timing spikes and cache/index variation preclude a universal latency
claim. No inference is made from unconstructed attacks' absent measurements.

## Transfer preparation and compute implications

The completed development smoke used schema
`rag-poison-transfer.bounded-source-selection/v1` at reviewed `8c55b3c`.
The reliability release now uses the separately frozen `/v2` execution schema. Maximum three
predeclared candidates per query/seed, no outcome-driven budget growth. Candidate
construction precedes source screening; select using the source alone, then seal
all selections before final target QA. BM25, Dense, Hybrid and Reranker are sources;
these four plus one composite RCD are targets. The final source is reevaluated in
the selected corpus so ATR's denominator is final source success, not screening
success. Zero source success yields null ATR. Identical poison instances and
query pairing are preserved across target pipelines within each source condition.

The development protocol is frozen at `/private/tmp/oct26-transfer-smoke-protocol-v2.json`,
SHA-256 `94eae69b146f02f64825fbf67fca6768cb4eb76c12088e46350426dfafa7046d`.
Its maximum was 220 local model calls. That specifically authorized development smoke completed and was
independently checked: **211 model calls**, **40 source/target conditions**,
**478 sealed files verified**; all 40 diagnostic ATR bootstrap intervals
independently reproduced and held-out ID overlap verified zero. Fifteen zero-source-success conditions correctly
report null ATR. See the [development smoke report](TRANSFER_DEVELOPMENT_SMOKE_2026-10-26.md) and
[verification receipt](OCT26_TRANSFER_DEVELOPMENT_SMOKE_VERIFICATION.json). This is execution evidence
for two development queries, not a completed transfer study.
The full proposal retains 240 source/target arm conditions. The original all-valid
mechanical ceiling was 208,800 calls; 279.5 model-hours multiplied that ceiling
by historical mean backend timing and was not a guaranteed time limit. The
unchanged selector supports 135/300 queries, yielding a tighter conservative
93,960-call ceiling without cache savings while preserving every population ID.
With all planned exact clean-input cache hits, the projection is 62,235 calls,
approximately 57.4 model-hours at measured smoke rates, plus indexing, validation,
restart and hardware overhead. Misses can increase calls toward the uncached
ceiling. Full compute is not authorized by this report.

The transfer follow-up reuses the original fixed HotpotQA cohort after its
matched-study aggregate is known. It therefore is not a newly untouched test
cohort. The existing nomination method and RCD are unchanged; the bounded
source-only selection protocol is frozen before follow-up compute and cannot
be optimized against final target outcomes. Diagonal source-to-self conditions
are sanity checks, not independent evidence of cross-pipeline transfer.

## 2Wiki provenance and interpretation

One bounded read-only provenance search did not recover the historical 25-query
sweep IDs. Introducing commit `d232fdf3b38aca9134c9728e85dad00605c6f069`
contains aggregated CSV/report material without a reconstructable query ledger.
Known exp_017–020 baselines share 300 IDs; all are excluded. Raw baseline revision
`e37a4050605363be62f1d02e6eb888fe5f56530e` differs from the new pinned revision;
no silent equivalence or complete historical cleanliness is claimed.

New dataset revision: `9823f70484dea525100394220b0ea5184d0eeb7b`.
A frozen metadata-only SHA-256 ordering with seed 42 selected 300 train development
and 300 dev held-out IDs, excluding known IDs and normalized exact/near question
duplicates under a 3-token-shingle Jaccard >=0.85 rule. ID overlap is zero;
selected near-duplicate conflicts are absent under that rule. This is not a
semantic non-overlap proof. Questions, not answers or success rates, determine
hygiene exclusions.

The initial cohort selection and preflight used metadata only. In the reliability
phase, the 300 already-frozen held-out examples were materialized locally from
the pinned revision, with exact ID order, question hashes, gold/supporting labels
and corpus fingerprints preserved for future execution. This was input preparation,
not held-out optimization or new target selection. **No 2Wiki model calls occurred.**
Development and held-out local-input metadata preflights passed. Cohort manifest SHA-256:
`3f51077946601cc0f58c0866716bf6c4650306dfd497cb98ed2973a466ca2cd4`.
Replication input specification SHA-256:
`a589c54d0153b20d76e63fbd58bd5328957efe413e5c28b6272f96139172d59e`.

Unknown sweep exposure materially limits an *untouched confirmatory* claim.
A disclosed secondary replication with fixed RCD and no tuning remains
scientifically manageable. Up to 25/300 could overlap that particular sweep;
this does not certify or bound other historical exposure. If pristine confirmatory
status is required, independently sourced evaluation data and a new protocol are
needed. Full replication has not run. Its all-valid ceiling is 21,600 model calls without
cache savings, or 15,000 with planned identical clean hits (approximately 14.9
model-hours at the transfer-smoke proxy rates). Neither this proxy nor the earlier
29.5-hour historical-rate estimate is a verified 2Wiki wall-time bound. A bounded
real-model smoke and full-compute approval remain prerequisites.

## Reproducibility and outputs

Frozen HotpotQA source:
[7a24a40c0a25399e1defc02844eb3a1de44b4a19](https://github.com/sadiapeerzada/rag-poison-transfer/commit/7a24a40c0a25399e1defc02844eb3a1de44b4a19).
Development readiness:
[a0a2d1793087e3c2ab9669d93bb040a60b822e34](https://github.com/sadiapeerzada/rag-poison-transfer/commit/a0a2d1793087e3c2ab9669d93bb040a60b822e34).
Final handoff branch:
[`research/oct26-execution-reliability`](https://github.com/sadiapeerzada/rag-poison-transfer/tree/research/oct26-execution-reliability).
Reviewed base: `8c55b3c1d1b8730c9a24dc5504c931af57fd5aa3`;
initial reliability implementation: `8ef82c1f7110fdb616de07cda93067623aa86465`.
The branch includes the earlier research-deliverable commits and final confirmed
resume fixes. The final execution manifest records the exact clean release commit;
a later merge commit requires a new execution freeze if used for inference.
Branch publication/review is not supervisor scientific sign-off or a merge.


| Evidence | Exact external location |
|---|---|
| Audit | [Scientific audit with release addendum](WEEK9_HOTPOTQA_SCIENTIFIC_AUDIT_2026-10-26.md) |
| Authoritative aggregate | `/private/tmp/week9-protocol-heldout/aggregate.json` |
| Tables, figures and export manifest | [`paper/results/hotpotqa_week9_2026-10-26/`](../paper/results/hotpotqa_week9_2026-10-26/INTERPRETATION.md) |
| 2Wiki cohort and preparation | `/private/tmp/week9-2wiki-protocol-2026-10-26-v1/` |
| Development metadata preflight | `/private/tmp/week9-2wiki-preflight-2026-10-26.json` |
| Held-out metadata preflight | `/private/tmp/week9-2wiki-heldout-metadata-preflight-2026-10-26.json` |
| Final implementation worktree | `/private/tmp/rag-oct26-execution-reliability/` |
| Final offline test log | `/private/tmp/oct26-release-final-full-tests.log` |

Aggregate SHA-256:
`0449d379d9f27270b4d6a9f474e60e86faeeab4508a68f22325900979f8b0dd4`.
Construction seal:
`e82bd61a4081a627b0bd398a17b3704ca6fa1e129f38065c6716f4268bec9360`.
Evaluation completion:
`881a6263c6c52e9b15f4db8613f6538b23fb8f49ac30107aecbb037cecfae4f1`.
The export manifest records exact producer-script hash, package versions, source
commit and its then-dirty state; export provenance is not misrepresented as a
clean experimental run. Figures use isolated plotting packages without modifying
the MLX environment. Audit cannot authenticate all historical device/runtime
behavior solely from stored records or prove absence of prior inspection.

## Execution reliability and current verification

The new implementation provides exclusive atomic checkpoints, per-query source
screening records, immutable generation intents/responses, 25-query scheduling,
query-pair/batch reassembly and full poisoned-corpus evaluation. Exact-input
clean-QA caching binds the model/tokenizer snapshots, configuration, corpus,
ordered evidence and scores, effective prompt, decoding and seed. Only clean QA
is cached; semantic generation, source screening and poisoned QA are not.
Origin text, prompts and original timing remain available; cache/replay lookup
time and actual backend-call accounting are separate. The MLX template and RCD
retrieval logic remain unchanged. Large model hashes now stream rather than
allocating whole weight files in memory.

A single-writer stage lock and cooperating-process MLX lease reduce accidental
parallel resource pressure. Completed checkpoints are reused; an unresolved intent
or inconsistent journal halts and is never silently regenerated. Recovery is not
a promise that an unknown interrupted model output can be reconstructed.

Final verification: **1,024 offline tests passed, zero failed, 110.82 seconds**;
focused reliability checks and compilation/whitespace checks passed. Fixture
cached/resumed and uncached answers, EM/F1, attack outcomes and paired summaries
agree, including the transfer ATR intervals. Final transfer calls in that fixture
fell from 80 to 45 without metric changes; the 2Wiki fixture exercises matched
resume and aggregation. These are synthetic software tests, not MLX or semantic
quality validation. The new cache/resume real-model path has not been run.

Final review corrected two execution defects: aggregation now recomputes and
compares existing outputs instead of refusing safe revalidation, and 2Wiki
construction now honors the accepted batch limit. Tampered aggregates are rejected
without replacement. No scientific selection, retry, defense or metric definition
changed. Details and exact commands are in the
[execution handoff](../docs/OCT26_FINAL_EXECUTION_HANDOFF.md).

For both remaining studies the decision is **READY WITH DOCUMENTED LIMITATIONS**
for workflow preparation. Before starting full compute, verify a new bounded
real-model development smoke, adequate disk/memory headroom, exact clean-source
provenance and explicit compute approval. No full real-model study is certified by
these preparation checks. The 16 GB machine needs serial execution; observed disk
headroom remains roughly 8–10 GiB, below the recommended operating margin.

## Finding classification

- **CONFIRMED BUG:** none demonstrated in the frozen HotpotQA results. A new
  transfer-protocol metadata inconsistency was caught before compute and corrected
  with a regression test; it does not invalidate the historical experiment.
- **EXPECTED PROTOCOL BEHAVIOR:** typed construction abstentions, discarded
  partials, zero end-to-end contribution and null unperformed QA measurements.
- **SCIENTIFIC LIMITATION:** low/type-selected construction coverage, incomplete
  alias knowledge, label-conditioned targets, heuristic semantic screen, one-model
  evidence, conditional clean QA, multiplicity and historical 2Wiki exposure.
- **NEEDS FURTHER EVIDENCE:** source-crafted transfer outcomes, 2Wiki replication,
  independently adjudicated factual/semantic correctness and broader generalization.

## Prioritized decisions and remaining work

1. Professor reviews the negative/mixed HotpotQA findings and limitations. Preserve
   the frozen results; do not tune RCD, regenerate targets or retry failures to
   improve the observed outcome.
2. Review the completed bounded development transfer smoke, including its
   semantic limitations and 15 null-ATR conditions, before any full transfer run.
3. The smoke execution and integrity checks passed; review and approve the full
   source-selection compute budget before proceeding. Execute all intended conditions and independently validate ATR and
   query-cluster intervals before claiming transferability.
4. Accept the disclosed 2Wiki historical exposure limitation for secondary
   replication, or require an independently sourced cohort. Approve full compute
   only after preflight and scientific review. Do not call metadata preparation
   a completed replication.
5. Complete planned ablations, second-model and error-analysis requirements or
   explicitly narrow the publication claims with supervisor agreement. Address
   multiplicity rather than selecting favorable secondary comparisons.
6. The existing README and this interim handout are now updated under explicit
   release authorization. After both remaining studies are validated, revise
   only the relevant result statements and hand off final analysis to the
   professor, who will handle manuscript writing. No manuscript is claimed
   complete, and the branch must be merged by the researcher, not automatically.

**Publication assessment:** the completed HotpotQA matched study is reportable
with its stated denominators and limitations. The original broader transfer and
replication research program is not complete and is not yet ready to be presented
as fully validated research.

## Final execution and manuscript handoff

The exact reproducible two-study commands and checkpoint locations are maintained
in [OCT26_FINAL_EXECUTION_HANDOFF.md](../docs/OCT26_FINAL_EXECUTION_HANDOFF.md)
and [OCT26_FULL_COMMANDS.sh](../docs/OCT26_FULL_COMMANDS.sh). Recommended order is
bounded new-path development smoke, full 2Wiki construction/evaluation/validation,
then transfer candidate construction, source-only screening, global selection
seal, final target evaluation and aggregation. None of those full runs was
started for this release. Planned pauses return 75; repeat the same command,
protocol, source commit and output namespace. Other errors require investigation.

Current frozen execution artifacts are separate from the historical protocols:
`/private/tmp/oct26-reliable-release-2026-10-26-v1/EXECUTION_MANIFEST.json` records
actual hashes, code commit, configurations and output paths. Data/model caches and
raw model journals remain external and must be archived durably before publication.
Only compact publication outputs, audit reports and metadata-only cohort policy/
ID manifests are included in this GitHub handoff.

After each remaining full run, validate all population IDs and construction failure
categories, recompute raw-answer metrics and paired uncertainty, inspect limitations,
and then update comparative tables/figures. The professor's manuscript handoff
should include the validated datasets' summaries, effect sizes/intervals, retrieval/
exposure, utility/latency accounting, manifests and caveats. No favorable transfer
or replication outcome is assumed in advance.

## Release archive integrity addendum

All 17,214 originally sealed construction/evaluation files were rehashed: **zero
missing and zero changed**. Eight unsealed `.DS_Store` files now appear in the
original archived directories, so strict inventory validation of that directory
correctly fails. Nothing was deleted, cleaned or resealed. Numerical reverification
used a new manifest-exact copy, verifying every copied file against its existing
seal. The 24 arm/cell rows, all 16 paired bootstrap comparisons and 37 publication
file hashes matched. No primary ASR interval excluded zero.

See [the machine-readable receipt](OCT26_RESULTS_REVERIFICATION.json) and the
[archived audit/addendum](WEEK9_HOTPOTQA_SCIENTIFIC_AUDIT_2026-10-26.md).
This is a documented filesystem-inventory limitation, not altered experimental
measurements or permission to disable provenance checks.
