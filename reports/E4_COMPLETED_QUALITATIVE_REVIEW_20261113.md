# E4 complete source-assisted review — 13 November 2026

The mandatory source-assisted review is complete for the **unchanged 100-case
sample** and a separately predefined **24-case construction-failure supplement**.
All 20 earlier annotations are preserved exactly; 80 new annotations complete
the original packet. Original cases were neither replaced nor resampled.
The original, supplementary and completed private artifacts have separate
checksum-bound receipts. No independent human adjudication occurred.

| Sample / evidence | Completed reviews |
| --- | ---: |
| Original valid-construction cases | 100 |
| Original annotations preserved / new annotations | 20 / 80 |
| Native-context-only / external-primary-source-assisted, original sample | 88 / 12 |
| Separate supplementary failures, native-source-assisted | 24 |
| Independent human adjudications | 0 |
| Unreviewed selected cases, either sample | 0 |

Within the original sample, available sources contradict the central target
relation in 77 cases, support an alternative target in one, and leave 22
ambiguous, question-defective, time-dependent or insufficiently evidenced.
These are assistant source-assisted judgments, not 77 independently proved
falsehoods. A target differing from gold or appearing in an answer is not itself
proof of misinformation. The supported alternative and every uncertainty are
retained. All 100 preserve complete historical poison documents and context;
the review does not adjudicate every ancillary sentence or possible alias.

| Historical outcome stratum in original sample | Reviewed | Source contradicts target | Source supports target | Ambiguous |
| --- | ---: | ---: | ---: | ---: |
| All three defenses target-match | 48 | 33 | 1 | 14 |
| RCD target-match with baseline disagreement | 12 | 8 | 0 | 4 |
| Baseline target-match, RCD does not | 15 | 14 | 0 | 1 |
| No target-match, some generator poison exposure | 25 | 22 | 0 | 3 |

The 80 additional reviews broaden the original queue, which had
reviewed only all-three-target-match cases. No eligible original case had both
no target match and no generator-visible exposure; the full selection receipt
retains that coverage limitation. Exposure uses saved generator evidence IDs,
not deeper diagnostic retrieval.

Review themes include nonexclusive answers, missing referent/year identifiers,
company-versus-person or country-versus-region mismatches, dates with rounding,
changing offices or lineups, aliases and pseudonyms, and unsupported authorities
inside poisons. Source contradictions are retained: nomination versus award,
publication versus award/edition dates, differing numerical totals and historical
versus renamed taxa. External sources may corroborate one link only; inaccessible
pages are marked as search-extract evidence rather than full-page verification.
The private records preserve the evidence and the exact limits of each claim.

## Supplementary construction failures

The supplement contains four cases in each of six available family/intensity/
failure-status cells, frozen before content review, with 24 distinct questions
and no overlap with the original 100. It retains all three candidate bands for
each case. The [selection receipt](E4_FAILURE_SELECTION_20261113.json) records
the deterministic design, source-file checksums and actual allocation.

| Supplementary finding | Count |
| --- | ---: |
| Selected target-assignment failures / semantic-evidence failures | 16 / 8 |
| Candidate bands inspected | 72 |
| Bands without targets / with targets but failed semantic construction | 54 / 18 |
| Historical generated attempts retained | 67 |
| Retained partial documents / accepted poison documents | 1 / 0 |
| Cases with no target, target factuality not adjudicable | 16 |
| Cases with target relation contradicted / ambiguous in source-assisted review | 5 / 3 |

Target-assignment failure is distinct from evidence-generation failure. Some
otherwise answerable questions never receive a target; other failures expose
defective gold labels, conflated roles, incomplete co-founder answers or
unqualified temporal/version boundaries. The absent 16 targets are not labeled
false. One supplied gold label directly conflicts with a death date in its own
native context; current life status of the alternative was not independently
asserted. These are retained findings, not edits to frozen benchmark labels.

Semantic failures include affirmative but filtered relations, truthful
corrections after false denials, internal contradictions, quantifier/referent
drift, invented or unverified credits, non-location slogans used for geographic
questions, unit/number-format differences and incomplete multi-document output.
One geographic answer overlaps at city level despite a conflicting neighbourhood;
both annotation versions are preserved and the final verdict is ambiguous.
These observations motivate caution about equating a heuristic failure status
with text factuality. They do not establish a classifier error rate or justify
changing frozen validators. All historical failure statuses are preserved.

## Provenance, limits and experimental status

[The complete factuality receipt](E4_COMPLETE_FACTUALITY_20261113.json) binds
both final ledgers and reports family/intensity/outcome counts separately.
[The integrity receipt](E4_COMPLETION_INTEGRITY_20261113.json) binds the original
selection, initial annotations, new annotations, alias/uncertainty index and
both supplementary annotation versions. Private data remain outside Git;
public files contain aggregate findings and checksums only. Validation rules
and the supplementary design are in [the completion protocol](../docs/protocols/E4_COMPLETION_AND_FAILURE_REVIEW.md).

Neither sample estimates benchmark-wide factuality or failure proportions.
Outcome/failure stratification, uniqueness constraints, historically exposed
questions, visible outcomes and one assistant reviewer limit interpretation.
There is no independent human review, adjudicator agreement, corrected ASR,
causal defense comparison or complete ancillary-claim/alias audit. Uncertainty
is preserved rather than counted as a fact. The completed work is qualitative
review, not newly completed answer-level experiments.

E1/E2 remain the primary experimental priority, with all four verified
checkpoint pins unchanged and zero generation intents. Their already documented
memory-pressure/authorization blockers remain; this work neither initializes
Qwen nor changes resources, methodology or frozen configurations. Preparation
and retrieval-only observations are not promoted to completed answers. E5's
PoisonedRAG feasibility decision and both report checksums are unchanged:
execution remains deferred. E3 was not repeated and RCD was not redesigned.
