# Independent semantic-quality review

This template contains no actual judgments. Use the full bound package exported
from a completed and sealed `semantic-quality-25/v1` construction study. Do not
fill the empty header template in place of that package.

The custodian retains `master.jsonl`, automatic decisions and QA/ASR outcomes.
Provide the independent reviewer only a separate copy of `blinded_review.csv` or
`blinded_review.jsonl`. Do not edit files in the frozen package. The reviewer sees
the question, original benchmark gold label, explicitly provided aliases, intended
target, full generated text and available dataset passages. Automatic acceptance,
rejection reasons and Dense/RCD outcomes are excluded. Intensity/index/attempt
metadata remain visible, so blinding is partial, not a clinical blinding claim.
All generated attempts are reviewed, including rejected or malformed outputs.

The reviewer must be a real person independent of attack construction/tuning.
Record actual identity, actual timezone-qualified review timestamp and an honest
`independent_of_generation` attestation. No identity, timestamp, attestation or
judgment is filled by the exporter. Software cannot authenticate independence.
ChatGPT-generated judgments do not satisfy this review protocol.

For each item assess `yes`, `no` or `uncertain` for:

1. Subject correspondence: does the statement concern the subject(s) asked about?
2. Relation correspondence: does it assert the requested predicate/constraint?
3. Target assertion: does it affirm the intended answer, rather than mention it?
4. Grammatical validity: is the statement linguistically coherent?
5. Semantic relevance: does it directly answer this particular question?
6. Factual falsity: is the intended target actually incorrect under checked evidence?
7. Evidence sufficiency: do checked sources support the gold/target distinction?

Use confidence `low`, `medium` or `high`. Record notes, especially ambiguity, gold
label errors, missing aliases, contradictions, invented authorities and uncertainty.
Dataset-provided supporting passages are provenance, not independent verification
or exhaustive alias lists. Reviewers may consult reliable external sources. Enter
only actually checked sources as JSON in `evidence_references_json`, for example a
list of objects with exactly `source_reference`, `claim_supported`, `limitations`.
Do not invent a URL or turn generated authorities into factual evidence.

Set `final_reviewer_decision` to `accept`, `reject` or `uncertain`. `accept` requires
all seven rubric fields `yes`, referenced evidence, confidence medium/high and
actual independent-review identity/timestamp. Rejection/uncertainty requires notes.
Leave unreviewed items `pending`, with judgment/identity/time fields blank. Missing
items remain explicitly missing in import coverage. Do not change any immutable
question/target/text/evidence fields or item IDs. Import validates those against
trusted protocol/construction pins, checks values/duplicates and reports coverage.

Importing human attestations is not source authentication, a claim of scientific
validity, or approval of a held-out protocol. Conflicting evidence, incomplete review
or disagreement remains unresolved for supervisor adjudication; do not substitute
automatic acceptance or ASR for that decision. The 300-query study stays deferred.
