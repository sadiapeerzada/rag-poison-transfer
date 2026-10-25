# Phase 4D: development-only nomination method v2

Prepared from main `5fe2e34` after Phase 4C merged. This is an explicitly
versioned **development-only** method, not a promotion into the held-out runner
or an adopted preregistration. No held-out question/gold text was inspected.
Only the original verified development artifact and frozen ID-only manifest were
used for this analysis. No model generation, matrix, human approvals, reviewer
signatures or new factual evidence were produced by the method.

## Mechanical coverage and independent correctness

| Measure | Existing method | Development v2 |
| --- | ---: | ---: |
| Mechanically eligible questions | 114/300 | 155/300 |
| Unsupported or uncertain | 186 | 145 |
| Category/question-pattern failures | 155 | 120 |
| Answer-shape failures | 22 | 14 |
| No different eligible source candidate | 9 | 11 |

The net gain is **41** questions: 42 newly eligible and one newly abstained case.
The loss is query `5ae35e8c5542990afbd1e120`: its gold is a biographical paragraph
about Don Jeffrey Meldrum. V2 rejects a sentence-shaped person label rather than
extracting a name, rewriting the gold, or pretending its aliases are resolved.
Of the original 186 failures, 42 become mechanically eligible and 144 remain
blocked. The total 145 remaining includes this one previously eligible case.

**Independently verified semantic/factual correctness: zero independently reviewed
pairs; accuracy is unmeasured, not 0%.** All proposed candidate strings remain
unverified. Earlier Phase 4A preparer recommendations are not independent
approvals and are not counted as such. No new source access or factual verification
is claimed. Eligibility means that a deterministic same-category source candidate
exists under the shape/form rules; it does not mean the target is false, a distinct
entity, plausible for the exact question, or likely to succeed in an attack.

## Analysis of every original failure

`original_186_failures.csv` contains exactly the original 186 failed development
queries with unchanged ID, question and gold; structural label; answer-label
shape; baseline category/reason; candidate availability; v2 rule/category/reason;
and number of pending candidates. `development_analysis.json` covers all 300,
including regressions and exact question/gold hashes, source-linked ordered
candidates and explicit unverified semantic status. `summary.json` binds original
artifact/manifest bytes, historical development hashes and method source hashes.
The script requires the exact pinned original inputs before parsing nominations.

Original failures by structure (deterministic, mutually exclusive labels):

| Structure | Count |
| --- | ---: |
| Choice/comparison cue, including conservative incidental-cue abstentions | 39 |
| Direct interrogative head | 67 |
| Embedded/descriptive request | 66 |
| Temporal request | 9 |
| Terminal who request | 5 |

Baseline inferred categories: unknown 154, date 16, quantity 5, transport place 2,
and one each animal, biological taxon, brewery, distance, empire, instrument
family, language, river and sports venue. Label shapes: 153 entity/text labels,
nine full calendar dates, 14 qualified numeric/mixed labels, five multi-value or
alias labels, two descriptive labels, two integer counts and one year.

Ignoring the gold-shape gate, 164 of these failures have no different same-category
pool string, one has 1–4, and 21 have at least five. This does not add 164 new
candidate-availability failures: category abstentions also lack a usable category
pool, while shape failures can have strings that still cannot be used. The
baseline first-failure accounting remains 155 + 22 + 9 = 186.

## Implemented extensions and conservative boundaries

- Direct attribution ending in “written/directed/created/replaced/voiced by
  who/whom” requests a person. Bare “created by?” remains unsupported because
  the answer might be an organization. Broad “by who” characterization questions
  are not treated as authorship; no book title is coerced into a person.
- Explicit answer heads recognize county, city/capital and province/region
  separately from generic places; university and school separately; sport,
  sports team and nationality. Bounded modifiers recognize film actresses,
  models, aristocrats, politicians and television personalities, and
  name-of-film/movie requests. Predicate/preposition boundaries prevent
  incidental school/county/film mentions from becoming the requested type.
- The phrase “film actress/director” denotes a person, not a film title.
  Capital requests take precedence over an incidental when clause. Question
  wording and gold strings are preserved exactly throughout.
- Full English calendar dates are validated against the calendar and kept in a
  separate category from years. Both month-day-year and day-month-year formats
  retain their original source strings. Invalid dates, date ranges, month-only
  labels and full dates substituted into explicit year requests remain blocked.
  An explicit “what date in/during/of YYYY” constraint filters candidate years.
- Sentence-shaped person labels, unresolved textual alias pairs, nationality
  labels ending “-born”, and university labels naming a school-of subunit are
  not repaired or silently coerced. Existing broad category support is reused
  only in this separate development version.

School recognition has only a singleton usable source here, so it produces no
eligible school nomination. Recognition alone is not counted as coverage.
The implementation leaves distance, comparative/choice answers, arbitrary
“what kind/type” classes, qualified numeric units, month/year periods, lists and
insufficient-source categories unsupported. The existing yes/no predicate
behavior is retained; it is not a new third-entity comparison protocol.

Candidates come solely from exact answer strings of other verified development
queries in the same v2 category. They retain all source IDs; source-label
provenance does not establish target falsehood. Order remains casefold/exact,
normalized-alias deduplication and first five. NFKC/case-folded gold matches and
any aliases genuinely supplied in the input are excluded. The code invents no
aliases, does not attest alias completeness, and does not extract replacements
from descriptive labels. Factual falsehood and coherent, question-specific
compatibility remain mandatory human requirements.

Important unresolved risks include national versus club/college teams, actor
versus author roles, regional/country membership, neighborhood versus city,
release chronology, co-correct alternatives and semantic aliases among differently
named source labels. The mechanical categories cannot establish those facts.
Every candidate requires independent adjudication against the unchanged question;
a reviewer must reject it if those constraints are not met. No coverage gain is
presented as validated semantic compatibility.

## Protocol changes requiring human adoption before any held-out access

1. Independently assess the new patterns and all resulting candidate quality on
   development data. Decide whether the added coverage justifies the method;
   do not treat these structural tests or preparer analysis as semantic approval.
2. If adopting v2, version the nomination protocol, pool, classifier/shape rules,
   category policy, source pins and reviewer instructions explicitly. Phase 4C's
   v1 drafts and baseline outputs are deliberately unchanged and still reproduce.
   Do not relabel a v1 registration as v2 or reuse its pins.
3. The current Phase 4B authenticated loader does not accept the new categories
   and still uses the old classifier. Any future integration must explicitly
   version and validate these changes while preserving independently signed
   decisions, exact dataset/query/gold/target bindings, aliases, evidence,
   provenance, seed determinism and all-300 coverage. There is no legacy bypass
   or approval conversion in this work.
4. Broader comparisons/closed-choice answers would need their own protocol,
   explicit within-question alternatives, reliable exclusion evidence and
   development validation. Unit-bearing numeric answers and intervals need
   unit/comparator/granularity semantics, not permissive regexes. Additional
   singleton-category candidates require independently verified development-only
   source data; no target strings or evidence should be invented to fill gaps.
   These are proposals, not implemented relaxations.
5. Resolve the Phase 4C full-query-fingerprint bootstrap and scientific governance
   decisions before genuine preregistration and held-out text distribution.
   Held-out coverage remains unknown. The frozen 300-query selection and the rule
   to stop if any one lacks a genuine approval remain unchanged. Neither smoke
   nor full-matrix execution is authorized by this development audit.

## Reproduction

From repository root, without dataset download or model calls:

```bash
.venv/bin/python scripts/audit_phase4d_development_coverage.py --check

# Write the same analysis to a fresh directory; existing files are not overwritten.
.venv/bin/python scripts/audit_phase4d_development_coverage.py \
  --output-dir /tmp/phase4d-development-audit
```

The check reconstructs every row/candidate/source and compares exact UTF-8 bytes.
No wall-clock date, reviewer information, signatures or factual-source claims are
populated. Historical results, frozen configs/IDs, Phase 4A evidence, Phase 4B
approval checks and Phase 4C drafts remain unchanged.

## Validation executed

```text
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q
840 passed in 93.27s; 0 failed

HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q \
  tests/test_development_targets_v2.py --tb=short
50 passed in 0.30s

.venv/bin/python -m compileall -q src scripts tests
exit 0

.venv/bin/python scripts/audit_phase4d_development_coverage.py --check
exit 0

git diff --check
exit 0
```

The full suite uses its existing offline training-data caches and mocked
held-out loaders. No real held-out text/gold loader or MLX generation was invoked
for this method audit. Existing cryptographic primitive tests exercise non-review
test messages; they are not reviewer signatures or approval records. All 50 new
regressions use synthetic structural cases or the verified development artifact,
cover every new category/pattern, typed/date/year constraints, incidental-head
rejections, alias/source/order invariants, pinned-input rejection, the retained
Phase 4C baseline and exact audit reproduction. These checks cannot establish
independent factual or semantic correctness.
