# Independent reviewer instruction sheet

**Preparation package only. Do not open held-out questions yet.**
The preregistration is a draft; this sheet contains no reviewer assignments,
identities, keys, dates, signatures or approvals. Human governance must resolve
the fingerprint bootstrap and freeze the procedure before distributing text.

## Before accepting a handoff

1. The human coordinator verifies your actual identity, competence, independence
   from nomination and absence of conflicts. Do not reuse preparer credentials.
   Manage your own genuine keys outside this repository; this package creates none.
2. Obtain the externally published registration and amendment/supplement, its
   trusted exact-byte SHA-256, the frozen reviewer policy and its independently
   trusted hash. A hash copied only from the file being checked is insufficient.
   Confirm that the full query fingerprint, dataset revision, 300 IDs, method
   hashes and development pool agree. A draft or null fingerprint means stop.
3. Receive only authorized question/gold records, fixed candidate ranks, development
   source references and blank decision worksheets. Do not accept model answers,
   retrieval rankings, attack outcomes, Dense/RCD comparisons or poison-seed labels.
   Record actual access under the human-managed policy. Do not put private review
   information in public Git commits.

## For every frozen query and fixed candidate

- Preserve exact question, gold answer, query ID, candidate string and rank. Resolve
  all hops before deciding what the question actually asks. Check question
  ambiguity and whether the supplied gold is uniquely defensible. Do not repair
  a bad question by changing its text or gold.
- Establish gold from reliable sources. Check the target separately: different
  text, absence from a partial list, or evidence only for gold is insufficient.
  Check aliases, co-correct answers, timeframe, role, place granularity and units.
- Explain why the target would fit this particular question if asserted in false
  evidence. Broad category equality is only a mechanical screen. Reject role,
  genre, chronology, geographic or units mismatches.
- Use primary sources where feasible; document secondary-source dependence. Keep
  precise claim/locator, actual reference, scope and limitations. Mark snippets,
  failed opens and unverified leads honestly. Do not fabricate a source, infer an
  access event, or copy a preparer access date into your review timestamp.
- Keep criterion-by-criterion findings and the actual reasons for every rejection
  or clarification. Follow the fixed first-five order and maximum two rounds.
  Later-ranked favorable alternatives cannot displace an earlier qualifying one.

The Phase 4A audit is training material about the method, not approval evidence
for a held-out ID. Its recommendations and replacement leads remain unapproved.
Read `../phase4a/EVIDENCE_REPORT.md` for concrete lessons about identity chains,
founding conventions, corporate history, place types and nonexhaustive credits.
Those sources were recorded in an earlier audit; this handoff does not recheck
or renew them.

## Disputes, abstention and handback

Round 1 is the independent primary assessment of the first five candidates.
Round 2 may clarify those same candidates once, with an independently verified
adjudicator if needed. No new targets, reordering, third round or performance-based
selection. A primary rejection cannot become acceptance without explicit genuine
agreement from both reviewers. Unresolved dispute means abstain.

If no candidate qualifies, or the question/category/gold is unsupported, return
that result with its reasons. It blocks the complete 300-query experiment; nobody
may silently replace or omit the question. Retain negative findings, not just the
successful candidate. Do not sign a statement you cannot independently support.

This repository's Phase 4C tools cannot create a final decision, reviewer policy,
identity, key, timestamp, signature or executable assignment. After genuine human
agreement, the coordinator arranges a separate immutable release under
`../../PHASE4B_REVIEWED_TARGET_PROTOCOL.md`. Each reviewer supplies their own
actual decision metadata and, in that separately authorized phase, their own
signature. The current runtime schema authenticates one final signer per target;
retain any secondary adjudication trail externally for coordinator verification.
No automatic conversion from this worksheet to approval is provided.

## Fields and checks

`review_sheet_blank.csv` has 300 metadata-only slots in manifest order. Its
question, gold, category, target, rank, aliases, evidence and reviewer fields are
blank; `review_decision` is pending. After authorized materialization, use private
copies; do not fill the committed draft. Use one candidate-log row per rank and
round in `candidate_review_log_blank.csv` (header only until genuine work occurs).
Reviewer identity and actual time fields are filled only by the actual reviewer
when a real review occurs. Do not backdate, use placeholders or automatically
populate them.

The draft validator checks reproducible preparation and blank/pending state.
The future coverage command checks exact dataset/query bindings and mechanical
category/shape/candidate availability after the preregistration gate. Neither
checks factual correctness, authenticates an evidence-access claim, establishes
reviewer independence or grants approval. Final signed-artifact validation is a
separate Phase 4B function. Coverage, review completion and execution permission
are distinct states.
