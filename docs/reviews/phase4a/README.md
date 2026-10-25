# Phase 4A: pending development false-target review set

This package is for independent assessment only. It contains **24 questions**
from the verified 300-query development artifact and **zero approved targets**.
No held-out question text, model generation, paid API, or poison execution was
used. All query–target pairs have evidence status **unverified** and human
decision **pending**. Reviewers and review timestamps are blank.

## Follow-up evidence audit

The [evidence report](EVIDENCE_REPORT.md) audits all 24 initial nominations.
The [updated review sheet](review_sheet_audited.csv) includes current preparer
classifications and source URLs; use it instead of the initial CSV for this
assessment. [Recorded assessments and source catalogue](evidence_audit.json)
and [summary](evidence_audit_summary.json) are machine-readable. The original
package and sheet remain intact as the reproducible initial draft.

- Recommended to submit for independent review: p02, p03, p06, p07, p08, p09,
  p10, p12, p13, p15, p16, p17, p18, p21, p22, p23 (16).
- Needs revision or stronger evidence: p04, p11, p14, p20, p24 (5).
- Reject the original nomination: p01, p05, p19 (3).

These are **preparer classifications**, not independent reviewer decisions.
All approvals remain unset/false, reviewer identity and timestamp blank, and
human decisions pending. `recommended_for_independent_review` does not mean
approved, scientifically validated, or ready for execution. Credits-based
negative inferences (notably p02 and p23) require independent end-credit checks.

The audit records 52 opened source pages and three checked indexed excerpts
whose scope is explicitly limited. Some full-page requests failed; the report
lists these separately and does not represent their contents as fully opened.
Sources include institutional/studio/publisher/archival material and labelled
secondary references. Claims, section locators, access dates and limitations
are recorded per source. No full source pages were copied into the repository.

The earlier p12 preparation flag incorrectly suggested Mario Lanza. The checked
chain is **Franco Corelli → Tosca (1956) → Cinecittà/Rome**. The updated sheet
replaces the stale flag while preserving the original question/gold/target.
Other substantive findings include unsupported show-membership premises in
p01/p05, VCU roots-versus-merger ambiguity, historical airline headquarters,
Kirton End’s borough/town mismatch, time-varying stadium capacity and the lack
of complete soundtrack exclusion evidence. Original-score credits cannot
exclude separately licensed music such as Lujon/Slow Hot Wind.

Seven replacement leads are recorded for p01, p04, p05, p14, p19, p20 and p24.
Their questions and exact candidate answer strings are taken only from verified
development records. Five proposals replace the question entirely because a
target-only swap cannot repair a premise/convention or available-pool problem;
p04 and p24 suggest another target for the same question. They are all explicitly
unverified and are not inserted into the original package. In particular, the
p24 Double Agent suggestion still requires cue-sheet evidence; it is not a
cleared improvement. p11 remains on hold until corporate identity and time
are resolved; no target-only substitution was presented as a solution.

Reproduce the follow-up outputs offline:

```bash
.venv/bin/python scripts/render_phase4a_evidence_audit.py \
  --artifact results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl \
  --manifest configs/exp_027_hotpotqa_heldout_manifest.json \
  --package docs/reviews/phase4a/review_package.json \
  --audit docs/reviews/phase4a/evidence_audit.json \
  --output-dir docs/reviews/phase4a
```

This rechecks extraction provenance, exact original-package bytes, all 24
identities/hashes, source references, replacement membership and pending states.
It renders the recorded assessments without fetching web pages or performing
new factual verification. Offline tests cannot authenticate source access or
substitute for an independent factual/semantic review. The reviewed experiment
runner/manifest/replay integration remains blocked as documented previously.

## Files and reproducibility

- `review_package.json`: canonical machine-readable package, including exact
  questions/gold answers, proposed targets, source query records/fingerprints,
  compatibility rationale, specific claims, local supporting-fact references,
  partial external evidence, ambiguity flags and blank decision fields.
- `review_sheet.csv`: the same 24 proposals in a spreadsheet-friendly sheet.
  Nested evidence/source cells contain JSON to preserve exact references.
- `validation_summary.json`: counts, package hash and all rejection reasons.
- [Nomination plan](../../../configs/phase4a_development_review_plan.json):
  explicit development nominations and partial source checks, without approvals.

Run from repository root:

```bash
.venv/bin/python scripts/build_development_review_package.py \
  --artifact results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl \
  --manifest configs/exp_027_hotpotqa_heldout_manifest.json \
  --plan configs/phase4a_development_review_plan.json \
  --output-dir docs/reviews/phase4a
```

The command revalidates original development count, revision/split, historical
hashes and held-out ID separation before producing outputs. It never downloads
data or fetches web evidence. Reruns preserve recorded source-check annotations;
they do not claim to recheck live pages. Source retrieval dates are preparation
dates, never reviewer timestamps. A regression test rebuilds all three artifacts
from the original pinned data and compares their exact serialized contents.
Paths and current wall-clock time do not affect generated bytes.

The existing commit `a8c5d86` was present, the branch was
`experiment/answer-compatible-targets-v2`, and the tree was clean at task start.
Frozen data, manifests and IDs remain unchanged.

## Selection and mechanical validation

This is a purposive starter set, not a representative sample or precision
estimate. Preparer nominations prioritize concrete roles, geographic granularity,
year answers and numeric units. Category equality is insufficient; each row has
a question-specific compatibility explanation and unresolved constraints.
All target strings are exact gold answers from a *different verified development
query*. Candidate provenance does not establish falsehood for the destination.

| Category | Selected |
|---|---:|
| Person | 6 |
| Place | 6 |
| Date (four-digit years) | 5 |
| Quantity (integer counts) | 3 |
| Film | 2 |
| Yes/no | 2 |

Thirty-two nominations were screened in fixed recorded order: 24 preparer
proposals plus eight deliberately retained diagnostic negative controls. The
24 proposals survived the mechanical gates; the eight controls appear only in
the rejection ledger. This is not an estimated rejection rate over the
development candidate pool. These include an airport/channel-number substitution,
a capital misclassified as a date, a named person misclassified as a quantity,
a chronology substitution, an actor/country swap, a gold-equal same-query target,
a repeated nomination, and a missing source ID. Reason counts overlap: one
nomination can fail multiple checks. Duplicate target checks apply across this
starter package, including normalized aliases; target uniqueness is a sampling
choice here, not a new requirement on future experiments.

The gates reject normalized gold equality, repeated queries/targets, incompatible
inferred categories and obvious answer-shape errors, unknown/choice questions,
and missing source records. Unsupported chronology/choice questions abstain;
boolean questions about equality retain their supported yes/no answer space.
Question and candidate provenance is reconstructed, not accepted from editable
proposed target strings. Missing supporting-fact references or a changed input
fingerprint abort packaging. No classifier or legacy attack protocol changed.

These gates do not resolve all aliases, geographic subtypes, actor credits,
negation scope, multi-hop identity, numeric magnitudes, units or temporal
boundaries. All rows carry manual-review flags. Two film substitutions are
particularly exploratory; reviewers may reject their contextual plausibility.
Other supported categories were omitted when the available cross-query pool
could not provide a defensible initial alternative without added assumptions.

## Evidence scope

All 24 records contain genuine `gold_supporting_facts` references (Wikipedia
article title/sentence index) from the original pinned development artifact.
These references are leads, not independently checked factual evidence; historical
Wikipedia sentence indices can drift. No generated model answer is used as a
source. The four source statements below were opened and inspected during
preparation on 2026-10-25:

- [Moscow State University faculty history](https://www.phys.msu.ru/eng/about/history/):
  supports its 1755 founding year. The Tokarev affiliation hop remains to check.
- [VCU quick facts](https://www.vcu.edu/about-vcu/): gives 1838 as its founding year;
  distinguish institutional roots from the 1968 merger/name and verify the team link.
- [J.K. Rowling official biography, page 1](https://www.jkrowling.com/wp-content/uploads/2025/03/J.K.-Rowling-Biography-2025.pdf):
  supports Harry Potter authorship; verify the Rupert Grint link and candidate exclusion.
- [Florida Senate description](https://www.flsenate.gov/about): states membership
  of 40; verify Ken Pruitt's chamber and applicability during his service period.

Each external annotation's `source_statement_status: verified` applies only to
that stated source fact. It is **not** a verified query-target pair, compatibility
decision, falsehood approval or authenticated independent review. Aggregate
pair evidence remains **0 verified, 24 unverified**. The other 20 rows have local
source leads only. A positive source for the gold does not always prove that an
alternative is false (coauthors, multiple roles and aliases can coexist).

## Independent review and v3 approval instructions

1. Work from the exact query, gold, proposed target and hashes. Resolve all hops,
   time periods and entity identities; preserve the frozen question/gold strings.
2. Find reliable sources establishing the correct answer and specifically excluding
   the proposed alternative. Record source URLs/references, relevant facts,
   retrieval dates, and rationale. Reject aliases, co-correct alternatives,
   category errors, malformed questions and unresolved ambiguity.
3. Assess question-specific semantic compatibility, required qualifiers (nationality,
   place subtype, year, unit, film-title constraint), and whether the target permits
   a coherent grammatical false-evidence assertion. Shared type is insufficient.
4. Leave disputed cases pending or reject them. An independent reviewer supplies
   their actual identity and actual timezone-aware review timestamp. Never copy
   a preparer evidence-check date into a reviewer field. Keep private reviewer
   information out of public Git commits; use an access-controlled review record
   if appropriate under the agreed review protocol.
5. Only after explicit independent approval, create a **separate** file using
   `protocol_version: answer-compatible-targets/v3-reviewed` with `assignments`.
   For each approved row, retain query ID/category/question and gold SHA256, put
   the exact reviewed proposal in `target_answer`, and set `reviewed_target_sha256`
   to SHA256 of that exact UTF-8 string. Record reviewer, `reviewed_at`, and
   source-backed `review_evidence`; set `approved: true`, `review_status: approved`,
   `semantic_compatible: true`, `factually_false: true`, and
   `coherent_false_evidence: true` only when the reviewer explicitly attests each.
   No automatic conversion/approval command is provided.
6. Validate that separate artifact with `load_reviewed_assignments` and match each
   query with `select_reviewed_target`. A schema-valid attestation still does not
   authenticate a reviewer or independently verify evidence.

The package has a distinct schema, uses `records` instead of `assignments`, has
no approved protocol header, leaves `target_answer` blank, and sets every row's
`approved` to false. Tests verify loader rejection and direct-mapping rejection,
including if someone merely adds an approved-protocol header.

Stop at independent assessment. The reviewed runner/manifest/replay integration
identified in the prior audit is still incomplete. This package authorizes no
smoke test, poisoning cell, matrix execution, merge or scientific-validity claim.

## Validation execution

Executed during package preparation:

```text
.venv/bin/python -m pytest tests/test_development_review_package.py -q
17 passed in 0.27s

HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q
692 passed in 92.70s; 0 failed, 0 skipped

.venv/bin/python -m compileall -q src scripts tests
passed

git diff --check
passed
```

The offline full suite used authorized access to existing local cache files;
no dependency download or install was needed. Frozen input byte hashes match
the previous audit. JSON output SHA256 is recorded in `validation_summary.json`
and verified by the artifact-reproduction test.

## Follow-up evidence-audit validation

```text
.venv/bin/python -m pytest tests/test_evidence_audit.py tests/test_development_review_package.py -q
41 passed in 0.63s

HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q
716 passed in 92.07s; 0 failed, 0 skipped

.venv/bin/python -m compileall -q src scripts tests
passed

git diff --check
passed
```

The first new focused run rejected an invalid source date correctly but failed
one diagnostic-message assertion (22 passed, 1 failed). The validator now wraps
the underlying calendar error with an actionable source-date message; the
focused and full reruns above passed. New tests cover stale package and raw
artifact provenance, complete/unique nomination coverage, source scopes,
approval-state rejection, development-only replacements and deterministic
artifact reproduction. These are integrity tests, not factuality scores.

The original development file, held-out manifest, initial review-package JSON
and initial CSV were compared byte-for-byte with HEAD and remain unchanged.

The staged check additionally caught two trailing spaces inherited from source
questions in the Markdown report. The renderer now trims display-only trailing
whitespace; JSON/CSV and their exact question identities remain unchanged.
Final focused rerun: 41 passed in 0.58s. Final full offline rerun after this fix:
**716 passed in 91.17s; 0 failed, 0 skipped**. Compilation and staged whitespace
checks passed after the correction.
