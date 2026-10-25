# Phase 4E: constrained development method and full-cohort decision

Started from latest main after Phase 4D merged (`4f1b98b`). The exact original
300-query development artifact is pinned by SHA-256 before extraction; the
existing extractor rechecks revision, historical fingerprints, unique IDs and
zero overlap with held-out IDs. Only the ID-only held-out manifest was read.
No held-out questions/gold answers, MLX generation or poisoning matrix were used.

## Coverage result — full coverage is not established

| Development measure | v2 | v3 |
| --- | ---: | ---: |
| Mechanically nominated | 155/300 | 177/300 |
| Unsupported/uncertain | 145 | 123 |
| Independently verified new semantic/factual pairs | 0 | 0 |

V3 adds **22** cases and loses none: 16 have the other explicitly stated question
option; six have declared numeric/temporal counterfactual constructions. Thus
171 cases have source-string or question-option candidates, and six additional
cases use constructed strings. The latter are proposed counterfactuals, **not
observed facts, sourced falsehood evidence, approved targets or demonstrated
semantic correctness**. All 177 remain pending independent review. Accuracy is
unmeasured, not 0%; no recommendation or mechanical test counts as an independent
judgment. Held-out coverage is unknown; development coverage is not its estimate.

Full-300 targeted support has not been achieved. Do not run a subset. The
[full-300 fallback proposal](FULL_300_FALLBACK_PROPOSAL.md) requires actual
supervisor approval and a separately registered threat model; it is not currently
approved. If the original targeted estimand is mandatory, execution must wait
until all 300 genuine assignments can pass the unchanged approval gate.

## Audit of all 145 original failures

`original_145_failures.csv` has every failed v2 development question, exact gold,
structure, label shape, request terms, original category/reason, v3 diagnosis and
candidate count. `development_analysis.json` covers all 300, with unchanged
question/gold hashes, exact candidate provenance and unverified status.
`summary.json` binds source/config bytes, development hashes and method sources.
The CSV and JSON are planning/audit data, not executable assignment artifacts.

Original causes: 120 category/question-pattern abstentions, 14 shape failures,
11 cases with no different typed source. Structures: 39 conservative
choice/comparison cues, 53 direct heads, 52 embedded/descriptive requests and one
terminal-who request. V3 routes these 145 to 32 question-local-choice analyses,
16 numeric/temporal analyses, two explicit-cardinality sets, 11 source-scarcity
requests and 84 unresolved entity/relationship cases. All cases are retained;
there is no rejection-ledger sampling.

The remaining 123 cases have these exact first-failure diagnoses:

| Cause | Count |
| --- | ---: |
| Entity/relationship lacks typed source or exclusion evidence | 62 |
| Open/hierarchical category requires constraints and exclusion evidence | 9 |
| Hierarchical/overlapping labels need disjointness evidence | 4 |
| No different typed verified development source | 11 |
| Descriptive gold/aliases unresolved; no rewriting | 2 |
| No safe declared scalar transformation | 8 |
| Approximation or one-sided bound may be co-correct | 2 |
| Comparative options/gold aliases unresolved | 7 |
| Choice gold-alias alignment/distinctness unresolved | 4 |
| Comma-bearing options need boundary review | 4 |
| Subjective/nonexclusive choice predicate | 4 |
| Choice option boundaries unresolved | 3 |
| Multiple choice connectives ambiguous | 1 |
| Set members lack separate typed development provenance | 2 |

## Implemented method, constraints and scientific limits

### Comparative and choice questions

The parser recognizes “Between A and B, which …”, an explicitly comma-separated
“A or B”, limited no-comma chronology forms after first/earlier/later, and the
literal public/private or democratic/republican property choices. Exactly one
option must match gold or a genuinely supplied alias under the existing
normalizer. The target is the other literal question span; both options, exact
character offsets and question hash are preserved. No third entity is supplied.

Expanded gold names that do not match a stated option remain unresolved; the
method does not invent identity aliases. Known alias equivalence on both options,
multiple or-connectives, ambiguous comma-bearing names and subjective/nonexclusive
predicates abstain. For example, the comma in “University of California,
Berkeley” must not cause a parser to nominate only “Berkeley”. Ties, alternate
interpretations and co-correct answers still require independent factual review.
The single-correct-option premise is not established by the gold string alone.

### Quantities, units, dates and ranges

The six constructions have a fixed declared rule and gold-label provenance:

- Census population: increment the integer count by one, preserving the exact
  census-year suffix and thousands-separator style.
- Scaled passenger count: add one original scale unit, preserving decimal places,
  scale word and passengers unit. This separates the proposed number from the
  source label at its displayed resolution, but does not verify actual rounding,
  measurement precision or falsehood.
- Exact single-unit height/distance label: add 100 original units, preserving the
  unit. The acceptable resolution/domain and contextual plausibility remain
  independent-review requirements; no automatic falsehood proof is claimed.
- Broadcast channel label: increment the integer, subject to separate domain,
  virtual/physical-channel, alternate-channel and falsehood review.
- Whole-year interval: propose the next disjoint, equal-duration interval. Reject
  invalid/zero years, reversed/out-of-domain intervals and explicit question
  numerals whose temporal role has not been resolved. Complete tenure, endpoint
  conventions and any repeated tenure require independent evidence.
- Month/year: use the next month without changing the year. December-to-next-year
  rollover is blocked; exact event-date conventions still need review.

About/approximately, one-sided bounds such as “more than”, dual-unit labels,
ordinal ranks, ambiguous periods and nonmatching answer shapes are not coerced.
A nearby bound can also be true: “more than 120” does not make “more than 121”
false. The original gold label is never rewritten or replaced by an extracted
number/name. Constructions are clearly labelled synthetic candidate strings,
not fabricated source facts or false-evidence passages. A reviewer may reject
any or all six; reported coverage must then decrease accordingly.

### Multi-value answers and source scarcity

A fixed-cardinality country-set constructor preserves the stated 2/3 cardinality,
member delimiter and unchanged members, replacing only the final member with an
exact label from a different, country-typed development source. Every original
member must also have a separate typed development source; duplicates, unknown
member types, missing cardinality or unverified exclusivity remain blockers.
No original development set passes those prerequisites, so this component adds
**zero** measured coverage. Its structural behavior is regression-tested; it is
not claimed as a validated full-coverage solution. Geopolitical scope and
exhaustiveness still require genuine review, even when the structural checks pass.

Non-exhaustive food lists and “what month” with a multi-month gold are not turned
into arbitrary false lists. Unsupported entity, heritage, religion, relationship,
work-subtype and singleton-source categories are not pooled merely to increase
counts. Broad type similarity cannot establish disjointness or preserve an
embedded role/premise. Eleven source-scarce cases remain explicitly blocked.

The new source types are literal alternatives in the verified development
question and declared transformations of its verified label. They supplement v2's
cross-query gold-label sources, with full origin/operation provenance. No external
candidate facts were admitted. One attempted primary-source request to
[UN Member States](https://www.un.org/en/about-us/member-states) returned **403**;
page contents were not accessed and no membership claim or evidence was extracted.
A failed request is not a verified source. No source-access event is represented
as an independent review or approval.

## Proposed source-acquisition and protocol decisions

Before any held-out access, a human coordinator should decide whether to adopt
v3 at all, particularly its six unverified construction rules. Required next
work includes independently checking development gold correctness, choice aliases,
ties, numerical units/resolution, interval conventions, set cardinality/member
identity and whether each candidate admits coherent false evidence under the
unchanged question. Preserve every rejection, not just successes.

Additional development-only candidate catalogues may be justified for scarce
categories, but must contain real source references, exact supported type/role
claims, source-access scope/limitations and a reproducible snapshot/hash. Define
category/relationship granularity, a fixed source/candidate budget, deterministic
ordering and bounded adjudication before use; verify that new source IDs and
question data are development-only. Source documentation is not approval, and
positive evidence for a candidate's type is not evidence it is false here. No
catalogue facts, sources or approval records should be fabricated to fill slots.

Promotion requires human scientific adoption and new versioned preregistration,
category/rule policy, source pool and review schemas. The current runtime rejects
these new method categories and still requires exactly 300 independently approved
assignments. Its source/data/hash/signature/alias checks, frozen query selection,
all-300 stop rule and replay/aggregate checks are unchanged. V2/Phase 4C reports
remain reproducible. The fingerprint-bootstrap/access-policy issue from Phase 4C
also remains unresolved. Neither this method nor the fallback is authorized for
held-out nomination or real-model execution.

## Reproduction

```bash
.venv/bin/python scripts/audit_phase4e_development_coverage.py --check

# Rebuild only into a fresh directory; existing artifacts are not overwritten.
.venv/bin/python scripts/audit_phase4e_development_coverage.py \
  --output-dir /tmp/phase4e-development-audit
```

These commands use the pinned development artifact and ID-only manifest. They
make no dataset downloads, model calls, evidence fetches, signatures, approvals
or reviewer metadata. Reproduction checks exact UTF-8 bytes, including candidate
spans and transformation/source provenance. No wall-clock fields are populated.

## Validation executed

```text
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q
889 passed in 94.02s; 0 failed

HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q \
  tests/test_development_targets_v3.py --tb=short
49 passed in 0.67s

.venv/bin/python -m compileall -q src scripts tests
exit 0

.venv/bin/python scripts/audit_phase4e_development_coverage.py --check
exit 0

git diff --check
exit 0
```

The 49 new tests cover literal choice spans, alias alignment, uncertain/malformed
options, comma-bearing names, scalar units/precision/anchors, disjoint ranges and
year formatting, invalid bounds/dates, explicit set cardinality, original-member
and replacement provenance, source scarcity, pinned-input rejection and exact
reproduction of both v3 and historical v2 reports. No test supplies a genuine
human approval or independent evidence judgment. The full offline suite uses
existing training-data caches and synthetic held-out fixtures; existing signature
primitive tests concern non-review test messages. No real held-out query/gold
loader, MLX generation, smoke test or poisoning matrix was executed here.
