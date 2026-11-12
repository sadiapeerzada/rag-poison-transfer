# E4 qualitative case review

On 13 November 2026 the operator approved 100 valid historical HotpotQA cases,
25 per lexical/semantic family × intensity 1/3. This is a newly specified
operational sampling plan, frozen before this factuality review, not an earlier
preregistration. Existing historical outcomes are used for stratification.

`scripts/prepare_e4_case_review.py` reads pinned native selection and paired
evaluation files. The unit is a source-selected attack instance; one question
may appear only once across the sample. All four original sources and all three
original seeds are eligible. Dense, Reranker and frozen RCD outcomes define five
mutually exclusive bins: all three match; RCD matches with baseline disagreement;
at least one baseline matches and RCD does not; no match with some generator
poison exposure; no match and no exposure. Exposure uses generator evidence IDs,
not deeper diagnostic retrieval. This is qualitative outcome coverage, not an
unbiased estimate of attack prevalence or defense superiority.

Each family/intensity initially requests five per bin. Scarce strata are chosen
first: semantic I3, semantic I1, lexical I3, lexical I1. Within each stratum,
SHA-256 ordering with seed 20261113 chooses eligible cases, excluding questions
already chosen. Shortfalls are filled from the least-filled available bin,
breaking ties in the declared bin order. Failure to find 25 distinct questions
raises an error; it never silently relaxes uniqueness. Source/seed proportions
are reported, not claimed balanced. Failed constructions remain in the source
coverage receipt but are ineligible for this valid-case review. They must not
disappear from experimental end-to-end denominators.

Private outputs preserve the design, selection manifest, full poison documents,
original supporting context and saved paired measurements. They are immutable
versioned artifacts outside Git. Public receipts contain only counts and hashes.
The selection receipt pins every native file read. This checks the sealed inputs
used here; it does not repeat the completed E3 analysis or its full raw audit.

Factuality review records the question-specific relation, referent and time
scope, target proposition, gold support, and limitations. A different string
from the gold label is insufficient to establish falsehood. Check alternative
valid answers, approximate dates, answer types, changing membership/office,
ambiguous titles and unsupported negative claims. Invented authorities inside
poisons are never evidence. Reviewing one central proposition does not validate
every ancillary sentence in a multi-document poison set.

Evidence levels are explicit:

- **Native source-assisted:** assistant reads the original supporting documents;
  these share the benchmark's provenance and are not independent ground truth.
- **External primary-source-assisted:** assistant records a primary source URL,
  access date, short excerpt, exact supported proposition and coverage limit.
  External publication is independent of the attack artifact, but the reviewer
  remains the same assistant. Partial multi-hop corroboration stays partial.
- **Unadjudicated:** no factual conclusion. Unsupported or ambiguous relations
  remain unresolved, including when the benchmark labels a target incorrect.
- **Independent adjudication:** requires actual separate reviewers and a
  documented decision process. None has occurred in this pass. Neither valid
  citation metadata nor the ledger validator establishes factual correctness.

The initial review queue is the first five retained cases per family/intensity
in the frozen packet (20 total), without replacing difficult or negative cases.
The remaining 80 are explicitly unreviewed. Future reviews append a new private
ledger version bound to the same packet. Preserve earlier versions and dissent.
Do not derive a factuality-adjusted ASR, inter-rater agreement or population
confidence interval from this partial, outcome-stratified assistant review.

Reproduction uses only Python's standard library and local historical files:

```sh
python -m scripts.prepare_e4_case_review --native-root "$NATIVE_ROOT" \
  --clean "$CLEAN_JSON" --private-output "$NEW_PRIVATE_DIR" \
  --public-receipt "$NEW_PUBLIC_RECEIPT"
python -m scripts.summarize_e4_review --packet "$PRIVATE_PACKET" \
  --ledger "$PRIVATE_LEDGER" --output "$NEW_PUBLIC_SUMMARY"
```

Both commands refuse existing output paths. Do not put private packet/ledger
content in a public pull request. No inference or protocol/model changes occur.
