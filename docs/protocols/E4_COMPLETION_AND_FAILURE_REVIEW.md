# E4 completion and separate construction-failure review

This follow-up implements the professor's mandatory factuality and
construction-failure review under the operator's 13 November 2026 instruction.
It does not alter the [original 100-case selection](E4_SOURCE_ASSISTED_CASE_REVIEW.md),
its historical 20 annotations, experiments, target labels or model settings.
Earlier partial reports remain historical receipts. The new completion report
supersedes their incomplete-review status without overwriting their artifacts.

The full 100-case packet has SHA-256
`8e0a4d54977dc44d4a4259d359e11f5228827ef15bd1496cc073eb98497b1f12`.
The original 20-entry ledger has SHA-256
`e45a969d98bf30ad561060eab5340a754a5644d9327ee4a1bc56a39afa450a6a`.
The completed private ledger contains those same 20 records unchanged, followed
by 80 new case-specific assistant reviews. It remains bound to the same packet.
The validator rejects omission or alteration of any original annotation,
incomplete case coverage, duplicate questions, invalid excerpts and unbound
review records. Checksums establish provenance, not factual correctness.

All remaining cases were read in frozen packet order, including unsuccessful
attacks and disagreement/exposure strata. Each new review records central
target relation, gold support/qualifications, observed aliases, uncertainties,
native supporting-document excerpts and any external source corroboration.
All original poison documents, full native contexts and paired historical
measurements remain in the packet. A companion private index supplies explicit
alias/exhaustiveness and uncertainty fields for all 100 without editing the
original 20 records. An observed name is not proof of an exhaustive alias check.
External citations record their exact supported proposition and coverage limit;
contradictory counts, dates, editions and access failures remain in the ledger.

## Predefined supplementary failures

The original valid-construction sample cannot answer how constructions fail.
A separate design was frozen before examining the selected failure contents:

- 24 distinct questions, excluding every question in the original 100.
- Four cases in each of six available family × intensity × failure-status
  cells: target-assignment failures in lexical/semantic I1/I3, and semantic
  evidence failures in semantic I1/I3.
- Order: semantic-evidence failure before target-assignment failure; semantic
  before lexical family; intensity 3 before 1. Within each cell, SHA-256 ordering
  uses seed `20261113-failures-v1` and the complete native instance identity.
- One question globally across the supplementary sample. Raise on shortage;
  never relax uniqueness or replace cases after factuality review.
- All four original sources and three seeds are eligible provenance. They are
  not independent question replications or additional strata to balance.

`scripts/prepare_e4_failure_review.py` verifies the original packet, clean
context, native protocol, candidate completion and selection seal. It hashes
the selected native files and retains every candidate band (0, 1, 2), selected
record, generated attempt, rejection, partial document and target assignment
for each chosen question. Input/output pins and achieved allocation are public;
question text, IDs, target/gold answers, generated text and reviews stay private.
The receipt reports the historical failed-instance frame before exclusions;
that frame's repeated sources/seeds must not be read as independent questions.

Review evaluates target validity only when a target exists, and separately
evaluates gold/question support and generated evidence. A missing target is
`absent_not_reviewable`, never a false target. Rejected text can contain a
fluent false assertion, a truthful correction, a contradiction or a changed
relation. None automatically establishes a valid construction, an effective
attack or a resistant defense. All frozen failure statuses remain unchanged.
No victim answers are fabricated for failures.

One supplementary city/neighbourhood interpretation received a more cautious
qualification on review. Both private annotation versions are retained; the
final summary uses v2 and records the geographic overlap as ambiguous. The
selection and original 20 annotations are unaffected. This preserves dissent
and interpretation changes rather than hiding them.

## Evidence and completion boundaries

All 124 cases have a completed **source-assisted review record**. An ambiguous
conclusion or absent target is a legitimate completed review, not a verified
fact. Native-context evidence shares benchmark provenance; external primary
sources sometimes corroborate only one hop and are read by the same assistant.
There has been no independent human adjudication. No inter-rater reliability,
fully verified false-target rate or factuality-adjusted attack score is claimed.

Counts apply only to the two qualitative samples, reported separately. The
original sample used outcomes for selection; the supplementary sample uses
failure status. Neither supports benchmark-wide proportions, confidence
intervals, a causal defense ranking or corrected E1/E2 experimental results.
Ancillary poison sentences and all-world aliases were not exhaustively checked.
Future human adjudication or new sources must append versions and preserve
uncertainties. Do not repair a benchmark label in frozen experiments based on
this qualitative review.

`scripts/complete_e4_review.py` validates both complete ledgers, preserves the
initial annotations, checks all failure bands/attempt counts, and emits only
aggregate counts and hashes. Use `python -m scripts.complete_e4_review --help`
for its private-input arguments. It refuses to overwrite a prior output.
The integrity receipt binds the private review bundle and confirms unchanged
E1/E2 checkpoint hashes and E5 report bytes. No inference, model initialization,
E3 reanalysis, RCD change or E5 baseline execution is part of this work.
