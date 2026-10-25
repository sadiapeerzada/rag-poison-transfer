# Full-300 fallback proposal — NOT APPROVED

The supervisor's requirement that **all 300 frozen queries be evaluated** is
binding. It does not approve this proposed change of research question. No
eligible-subset experiment, dummy target, missing-approval exception, automatic
approval or execution path is introduced here.

## Decision requiring supervisor action

The original all-300 answer-compatible targeted-poisoning study remains blocked.
Development v3 nominates only 177/300 mechanically; no new pair has independent
semantic/factual verification. Held-out coverage is unknown and was not measured.
Question-local alternatives, scalar transformations and typed source acquisition
cannot guarantee a defensible false target for an ambiguous or incorrectly
labelled question. Full targeted support cannot honestly be promised.

The supervisor must choose between:

1. **Retain the original targeted research question and postpone execution.**
   Continue development-only source acquisition and independent verification;
   resolve method/label obstacles; then preregister and seek genuine approvals
   for every one of the unchanged 300 queries. If any fails, stop the whole
   primary study. Do not evaluate a targeted eligible subset.
2. **Explicitly approve a separate, target-free, full-300 robustness study** as
   described below. This changes the threat model and estimands; it cannot be
   presented as the original answer-compatible targeted attack evaluation.

There is no currently supervisor-approved fallback. A code change or document
cannot supply that approval. If neither route is approved, the experiment stays
paused; partial poisoning results are not a substitute.

## Proposed complete-cohort robustness design

Research question: how does adding a fixed, independently vetted background
corpus affect matched Dense/RCD retrieval and answer quality across the entire
frozen query set? This evaluates robustness to corpus contamination/interference,
not success at inducing an approved false answer.

- Retain all 300 manifest IDs, their order, dataset revision/split, original
  question/gold strings, frozen retrieval/RCD settings and historical artifacts.
  Every query receives both clean and contamination conditions. Apply the same
  policy to all queries; never choose a policy based on target eligibility.
- Freeze a development-only background-document pool, exact document bytes and
  source provenance before held-out access. Use a query-blind deterministic
  sampling rule with seeds 42/43/44 and intensities 1/3. Do not inspect held-out
  questions to select favorable documents, remove accidentally helpful documents
  or optimize attack success. Some background material may be helpful; retain
  and report that outcome rather than filtering queries/documents adaptively.
- One policy, two intensities and three seeds would define **six new matched
  cells**, not the historical twelve targeted cells. Both pipelines use the
  exact same corpus snapshot in each cell. Preregister any alternative design
  explicitly; do not silently reuse the old attack names or cell schemas.
- Require genuine independent approval of the policy, provenance, source
  separation and **every query's attack assignment** before execution. A new
  immutable review-gated artifact must bind the exact 300 IDs, query/dataset
  fingerprints, document IDs/bytes, policy, seeds, intensity and real review
  decisions. Keep independently authenticated provenance through replay,
  checkpoints, raw results and aggregates. No such artifact is created here.
- Run the generator on all 300 queries in each condition, with unchanged answer
  prompts and frozen pipeline settings. Never treat an unattackable query as a
  clean-only control, fill an absent target with a sentinel, or count a missing
  target as a targeted-ASR failure.

## Outcomes and denominator

Primary descriptive outcome: paired change in agreement with the **unchanged
frozen labels** (EM/F1), over all 300 queries, with matched per-query records.
Call this label agreement, not proven factual correctness when a label is
uncertain. Also report clean and contaminated retrieval of original gold
support, background-document exposure/rank, latency and actual generation counts.
Retain negative, positive and unchanged effects.

Report every seed separately and any preregistered pooled estimate with query
clusters; repeated seeds do not turn 300 questions into independent new queries.
Publish complete-case accounting for all 300 IDs in every condition. A missing
output or incomplete cell fails validation; it is never silently dropped or
imputed as success/failure. Label-quality annotations may flag ambiguity, but
cannot remove records or replace original labels in the primary full-300 table.
Additional independently judged answer-quality outcomes require a separate
blinded rubric and genuine judgments for all 300, not synthetic judgments.

Targeted ASR and answer-compatible false-target transfer are **not defined** for
this study and must not be reported. Do not combine eligible-query targeted
results with unsupported-query background contamination into one estimand.

## Implementation and authorization still required

This proposal does not alter the current runner. Its requirement for 300 approved
false targets continues to fail closed. A target-free experiment would require
separate preregistration, actual supervisor approval, independent review,
versioned assignment/cell/aggregate schemas, complete-cohort validation and
regression tests. Only after those steps could a separately authorized smoke be
considered, followed by a separate execution decision. No smoke, matrix,
background-document selection or real-model call was made for this proposal.

Before any held-out text access, the coordinator must also resolve Phase 4C's
fingerprint/bootstrap procedure and freeze the agreed method and access policy.
No post-access method amendment may be represented as an unexposed
preregistration. All scientific changes and limitations must be disclosed.
