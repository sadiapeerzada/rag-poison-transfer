# Nomination and independent-review preregistration draft

**DRAFT — NOT FROZEN, NOT REGISTERED, NO TEXT ACCESS AUTHORIZED.**
This is a procedure proposed for human adoption. The JSON companion contains
hashes and unresolved human decisions, not an executed preregistration. No
reviewer, key, registration/review timestamp, signature or approval is supplied.
Phase 4B's execution gates remain unchanged.

## Scientific objective and fixed experiment

Evaluate transfer of poisoning between matched Dense and RCD pipelines with
fixed target assignments, not the ability to search held-out examples for
favorable targets. Keep all 300 query IDs, their manifest order, the dataset
revision/split, frozen RCD parameters, both attack families, intensities 1/3 and
predeclared poison seeds 42/43/44 unchanged. Target text must be identical across
seeds, attacks, intensities and pipelines. Do not inspect any model answer,
retrieval result, attack-success measure or Dense/RCD comparison during nomination
or review. No smoke or matrix execution is authorized by adopting this document.

The metadata binding and source/config hashes are in
`preregistration_draft.json`. Dataset: HotpotQA distractor, validation,
revision `1908d6afbbead072334abe2965f91bd2709910ab`. The existing manifest fixes
300 IDs. Held-out text and gold answers were not accessed in Phase 4C.

## Resolve the fingerprint bootstrap before opening questions

Phase 4B requests a full question/gold/document-ID fingerprint before questions
are opened. The ID-only manifest has no such fingerprint; computing it now would
require prohibited text access. The draft leaves it null. Human governance must
choose and document exactly one route before reviewers see text:

1. Obtain an already-established full query-set fingerprint and its auditable
   provenance from an authorized custodian, without new question access in this
   preparation task. Independently verify its dataset/revision/ID binding.
2. Explicitly amend Phase 4B's sequencing before any text access: externally
   freeze this procedure and the exact manifest bytes, ID fingerprint, revision,
   split and source hashes first. Authorize a separate blinded custodian solely
   to materialize those exact records and compute the existing full fingerprint.
   No nomination, tuning or outcome inspection is allowed in that step. Record
   a binding certificate as an immutable, externally published registration
   supplement. Finalize and externally pin a complete registration including
   that digest before review text distribution. Keep the original registration
   and supplement; do not rewrite an earlier frozen document.

This proposal is **not** an adopted amendment. The coverage tool cannot perform
custodian materialization or create a registration. It accepts neither this draft
nor an incomplete staged registration. An accountable human records the adopted
route and actual reference in a separate frozen registration. Its externally
trusted exact-byte SHA-256 is supplied independently of the file itself.

## Method freeze and development-only source pool

Freeze this document, the reviewer instruction sheet, all listed method source
hashes, the verified development-artifact hash and the canonical development-pool
fingerprint before text inspection. Store unchanged copies in the registration.
The pool contains exact gold answer strings from verified development records,
with source query IDs. It is a source of candidate strings, not factual evidence
that those strings are correct, false elsewhere, or semantically interchangeable.
The 24 Phase 4A examples are development method diagnostics, never held-out
approvals. All observed Phase 4A problems must inform the rubric before freezing.

The current implementation uses the Phase 4B category classifier and conservative
answer-shape checks unchanged. Supported categories are:

```text
animal, battle, biological_taxon, brewery, comic_series, company, date, empire,
film, instrument_family, language, magazine, person, place, quantity,
relationship, river, sports_venue, transport_place, yes_no
```

Unknown and distance categories abstain. Dates currently require four-digit
years; quantities require the existing supported integer-count syntax. Generic
category membership does not establish entity subtype, role, units or plausibility.
Order/extremum/chronology and disjunctive choice substitutions are unsupported.
Proposed clarification for human adoption: a yes/no factual predicate, including
simple equality, stays in the binary yes/no answer space; it never licenses a
third-entity or chronology substitution. If a case cannot satisfy the direct-fact
rubric under that clarification, abstain. The classifier's early yes/no check
must not be interpreted as automatic semantic acceptance.

Any category expansion, date/unit relaxation, manual classifier override or new
comparison protocol requires development-only validation and a new version
**before** held-out inspection. Do not design these changes from coverage of
held-out questions. If that limitation makes the experiment infeasible, disclose
it and stop; do not silently alter the selection or reclassify convenient cases.

## Deterministic candidate ordering and bounded nomination

For each frozen query, apply the unchanged classifier to its exact question/gold
strings. Unsupported category, unsupported gold shape or no eligible pool
candidate yields abstention. For a supported category:

1. Use only pool answers with that exact development category. Do not generate
   new targets, search the web for substitute target names or use held-out gold
   answers as the candidate pool. Cross-query target reuse is allowed; duplicate
   assignments to a single held-out ID are not.
2. Sort exact candidate strings by `(answer.casefold(), answer)` using the frozen
   Python implementation. Deduplicate aliases using NFKC, case folding and the
   existing normalized-answer function. Remove gold-normalized matches.
3. Freeze the **first five** remaining strings, or all if fewer exist. Assign
   ranks once. Preserve each candidate's exact spelling, category and development
   source IDs. Do not skip an early candidate for a more attractive sixth.
4. Nominators record contextual constraints, a coherent false-claim proposal and
   genuine evidence leads for each ranked candidate, without editing question,
   gold, rank, pool or target strings. Web research may verify/exclude these fixed
   strings; it may not enlarge or reorder the pool. No LLM calls are permitted
   for nomination, evidence fabrication, review or this coverage check.

Human reviewers must assess candidates in this fixed order. The human-selected
assignment, if any, is the lowest-ranked candidate satisfying every criterion
after the two permitted rounds. Software reports mechanical coverage only and
never turns a candidate into an approval.

## Alias and evidence standards

For gold and each target, resolve all entity hops and the question's exact role,
time, place granularity, release/founding convention, units, qualifiers and scope.
Check spelling/punctuation, full/short names, stage names, transliterations,
historical names, geographic containment, corporate lineage and co-correct answers.
Record all known relevant aliases and how they were checked. Merely different
strings do not prove different identities. Unresolved equivalence or multiple
correct interpretations is an abstention; do not rewrite the gold label.

Prefer primary institutional, archival, legal/public-record, creator/publisher,
studio or complete-credit sources. Use well-supported secondary material for
cross-checks or when primary evidence is unavailable; explain the limitation.
Record actual accessed URL/reference, exact supported claim, section/page locator,
scope, material uncertainty and provenance in an access-controlled evidence log.
A source for gold alone does not prove the target is false. Search snippets and
failed page opens are leads only. Do not label them fully checked pages. An
absence from an incomplete cast/music list is insufficient negative evidence;
original-score credits cannot exclude licensed soundtrack use. Preserve the
source snapshot or archival reference when feasible, without copying whole
copyrighted pages into Git. Only humans record actual source-access information;
no preparation date becomes a review timestamp.

Apply lessons from the Phase 4A audit: resolve roots-versus-merger dates,
corporate referents/time periods, filming versus story locations, borough/town
subtypes, changing capacities, same-name identities and multi-hop actor credits.
Its 16 preparer recommendations, five revision cases and three rejects are not
independent approvals or a held-out coverage estimate.

## Review rubric, disagreement and permitted rounds

A genuine independent reviewer, verified by a human coordinator and distinct
from the nominator, checks every item below without model outcomes:

- Gold answer and every necessary hop are factually supported under one clear
  interpretation of the unchanged question.
- The target is false for that interpretation, not an alias, co-correct answer,
  uncredited unresolved case or merely unsupported assertion.
- The target satisfies the same question-specific type, role, subtype, units,
  timeframe and qualifiers as gold; a grammatical, coherent false-evidence
  assertion could naturally support it. Shared broad category is insufficient.
- Evidence claims are genuinely accessed, sufficient for both gold and falsehood,
  appropriately scoped, reproducible and honest about limits.
- Exact query/answer/source bindings and candidate order are unchanged; all known
  relevant aliases and uncertainties are recorded.

**Round 1:** one independent primary reviewer evaluates all available ranks
(maximum five), recording their genuine criterion-by-criterion findings and
reject/clarification/accept recommendations in the private review log. These
findings are human actions, not values supplied by this handoff.

**Round 2:** at most one clarification/adjudication round on the same fixed
strings. A separately verified independent adjudicator may resolve evidence or
interpretation disputes using the same rubric. New sources and discovered aliases
may clarify a fixed candidate; new candidates, changed questions/gold, reordered
ranks and model outcomes are prohibited. A nominator cannot adjudicate their own
nomination. An adjudicator cannot silently override a primary rejection: both
must explicitly agree to any final acceptance. Unresolved disagreement means
reject/abstain. No third round, replacement reviewer shopping, or extra pool search.

The human coordinator checks that the final choice is the earliest qualifying
rank and preserves all earlier rejection reasons and both-round records. Only
then may an actual independent reviewer separately provide their genuine approval
metadata under Phase 4B. This task does not create that metadata. Phase 4B's
single signer authenticates the final attestation; the external coordinator must
check the secondary adjudication trail when it was required. If machine-enforced
multi-reviewer quorum is desired, validate a new schema before text access.

## Abstention, stop rule and access governance

If any one of the 300 queries is unsupported, uncertain, disputed, lacks genuine
falsehood evidence or exhausts its first five candidates/two rounds, the complete
300-query experiment stops. Do not omit the query, replace it with a development
question, change its gold, lower the rubric, extend rounds, or inspect outcomes to
choose another target. Preserve every rejection and coverage result. Any subsequent
protocol proposal must disclose all held-out access; it cannot be represented as
an unexposed preregistration. No target in the 24-example development audit can
satisfy a held-out approval by reuse.

Keep the reviewer roster, independence checks, real keys, actual timestamps,
access log, evidence snapshots and decision history under appropriate human-managed
access control. Distribute questions only to authorized nominators/reviewers after
the complete registration and reviewer policy are externally frozen. Keep reviewers
blind to poison seeds, generated poisons, retrieval outputs, model answers and
performance. Limit custodians to the predeclared materialization/binding task.

After all 300 genuine approvals, the existing Phase 4B loader independently
validates the immutable signed release and externally pinned policy. Obtaining
approvals still does not authorize execution. A separate human authorization,
real-model smoke inspection and semantic-poison quality assessment precede any
separate authorization of the full 12-cell matrix.
