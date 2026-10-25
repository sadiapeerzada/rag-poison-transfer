# Phase 4C reviewer handoff

**Draft preparation only. No human preregistration or review has occurred.**
This package was prepared from main `e575543` after Phase 4B merged. No held-out
question text/gold answers, dataset loader, MLX generation or poisoning matrix
was accessed or executed. Only the frozen manifest/config metadata and verified
development records were read. No reviewer identities, keys, timestamps,
signatures, approvals or new factual evidence were created.

## Coverage that can honestly be reported now

| Scope | Mechanical support | Unsupported/uncertain | Unassessed |
| --- | ---: | ---: | ---: |
| Frozen held-out 300 | Not determined | Not determined | 300 |
| Verified development 300 | 114 | 186 | 0 |

The held-out ID manifest has no category labels. Its 300 IDs and unchanged
fingerprint were verified through the existing metadata-only frozen-input check
permitted by Phase 4B's preflight procedure. Inferring categories, shapes,
candidate availability or semantic support would require prohibited question/gold
access. Held-out mechanical support is bounded only by **0–300**; the 300
unassessed records are not 300 demonstrated unsupported cases. No held-out support
percentage or category distribution is claimed. There are zero genuine approvals.

Development-only breakdown: 155 unsupported category/question-pattern cases
(154 unknown and one distance), 22 unsupported gold-answer shapes and nine without
a different eligible candidate in the fixed development pool. These are mutually
exclusive first-failure screening reasons. The 114 passing cases still need
independent factual/semantic review. Development results are not held-out counts,
acceptance rates, attack performance or representative estimates.

## Files

- `PREREGISTRATION_DRAFT.md`: proposed nomination, ordering, alias, evidence,
  rubric, bounded-round, disagreement and all-300 stop rules; bootstrap decision.
- `REVIEWER_INSTRUCTIONS.md`: independent-review checklist and handback procedure.
- `preregistration_draft.json`: reproducible draft bindings and outstanding human
  decisions; full question/gold fingerprint deliberately null, no registration
  timestamp or reviewer roster. It is not a frozen registration.
- `candidate_pool.json`: verified development-only answer strings and real source
  IDs, with development provenance. Not evidence of target falsehood.
- `review_handoff.json`, `review_sheet_blank.csv`: all 300 frozen IDs in their
  existing order, with blank question/gold/target/evidence/reviewer fields and
  pending decisions. Distinct schema, no executable `assignments` list.
- `candidate_review_log_blank.csv`: header only, for the subsequent private log
  of actual per-candidate/per-round findings. No observations are supplied.
- `coverage_metadata_only.json`: explicit unknown held-out coverage and separately
  labelled development screening. No guessed category counts.

All generated files are modest review materials; no experiment results or private
reviewer data are committed. Pool and draft pins refer to exact deterministic
pretty-printed UTF-8 bytes, including the final newline. Full final registration,
policy and assignment pins are provided externally by humans in later phases.

## Reproduce and validate without opening held-out text

Run from repository root. These commands read development text and held-out IDs
only; neither can accept a held-out question-file argument:

```bash
.venv/bin/python scripts/prepare_phase4c_review_handoff.py validate

# Rebuild into a fresh directory; existing handoff files cannot be overwritten.
.venv/bin/python scripts/prepare_phase4c_review_handoff.py build \
  --directory /tmp/phase4c-review-handoff
```

Validation rebuilds the pool, source/config pins, all 300 blank slots, log headers,
coverage and development screening rather than trusting editable counts. Any
changed field, missing/duplicate/reordered ID, populated review field, stale
source/pool binding or altered report fails exact reconstruction. It validates
preparation integrity, not factual evidence or independent approval. A genuinely
completed private review is a separate artifact; it must never replace the
committed blank draft.

## Future coverage check — human freeze required first

No such command was run on held-out text during Phase 4C. The coordinator must
first resolve the bootstrap, adopt/freeze the protocol, register independent
reviewers and authorize text access. The externally frozen JSON is a separate
copy with this versioned preregistration schema, `status: frozen_preregistered`,
all method/config/pool pins, the full query fingerprint, resolved
`fingerprint_bootstrap_resolution` and actual `bootstrap_resolution_reference`,
and an empty `human_decisions_required` list. Merely editing a status string does
not establish a genuine registration or grant human authorization.

Only after those actions, an authorized operator may use:

```text
.venv/bin/python scripts/prepare_phase4c_review_handoff.py coverage-after-freeze \
  --authorize-heldout-text \
  --frozen-preregistration /secure/path/actual-frozen-registration.json \
  --preregistration-sha256 <independently trusted exact-byte SHA256> \
  --queries /secure/path/authorized-frozen-query-export.json
```

The query export must contain `dataset_revision`, `dataset_split` and `queries`
with exact `query_id`, `question`, `gold_answer`, `gold_doc_ids` in manifest order.
It is not an approval file. The tool checks the external registration pin,
resolved protocol, complete source/config/pool pins and frozen manifest before
opening that file, then verifies all 300 identities and the full content
fingerprint. It prints counts/reasons without question text, candidate choices,
reviewer information or approvals. Keep exports and human-filled worksheets out
of public Git. No status-changing, signing, key-generation, timestamping,
registration-creation or approval-conversion command is provided.

## Human actions required, in order

1. Scientifically assess the strict method using development data. Only 114/300
   development questions pass the mechanical screen, so all-300 held-out coverage
   cannot be assumed. Decide whether to adopt the strict stop rule or validate a
   broader method on development data and version it **before** any held-out
   question access. No change is adopted automatically by this package.
2. Resolve the fingerprint bootstrap: supply an auditable preexisting full
   fingerprint, or explicitly approve the staged-binding amendment described in
   the draft. This is a sequencing change to Phase 4B, not current authorization.
3. Adopt the exact nomination order, first-five bound, supported categories,
   yes/no predicate interpretation, alias/source rubric, maximum two rounds,
   adjudicator agreement rule and all-300 failure policy. Decide whether the
   current single-final-signer runtime plus externally checked adjudication trail
   is sufficient, or develop a multi-signer schema before exposing questions.
4. Verify actual reviewer/adjudicator identities, expertise, conflicts and
   independence; arrange their own real keys and a private verified registry
   outside this task. Do not commit private data.
5. Publish/freeze the registration and any immutable binding supplement through
   a trusted external channel. Resolve every listed human decision and verify
   all pins. Then finalize the real reviewer policy with the actual registration
   hash and verified registry, and externally publish its hash. No tool here can
   perform these human actions or certify their authenticity.
6. Authorize a blinded custodian to distribute the exact frozen query export to
   authorized nominators/reviewers; log actual access. Run the gated coverage
   check once under the frozen procedure. Do not adapt the method from that result.
7. Have humans nominate only fixed ordered candidates, access genuine evidence,
   complete actual independent reviews and at most one clarification/adjudication
   round, preserving all rejects. Stop if any of the 300 remains unsupported.
8. Only in a separately authorized phase, actual reviewers supply their own real
   final decision metadata/signatures and the coordinator freezes the Phase 4B
   assignment release. Validate it with the existing authenticated loader.
9. Separately authorize a real-model smoke, assess semantic-poison quality, and
   only then consider a separate full-matrix authorization. Neither is authorized
   or executed by this preparation package.

## Validation executed

```text
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q \
  tests/test_review_handoff.py tests/test_target_candidates.py \
  tests/test_target_review_audit.py tests/test_verified_development.py --tb=short
62 passed in 1.60s; 0 failed

.venv/bin/python scripts/prepare_phase4c_review_handoff.py validate
valid: true; heldout_ids: 300; heldout_unassessed: 300; independently_approved: 0

.venv/bin/python -m compileall -q src scripts tests
exit 0

git diff --check
exit 0
```

Only the relevant offline suite was executed. No held-out dataset/model tests,
key-generation/signing tests or real post-freeze text audit were run. The
post-freeze code path is tested below a mocked registration boundary with
explicitly synthetic IDs/questions, not a fabricated human approval or an actual
frozen registration. Tests cannot establish the authenticity of future human
registration, reviewer independence, evidence access or factual correctness.
