# Phase 4B: reviewed held-out target integration

Status: implementation for review; no held-out targets approved. No experiment
execution is authorized by this document. Phase 4A's 24 nominations remain
**development examples**, including recommendations awaiting independent review.
They cannot be imported as held-out approvals.

## Integration points

| Existing component | Integration |
| --- | --- |
| `compatible_targets.py` | Reuse v3 decision, exact question/gold/target hash and timestamp validation. Its standalone mapping loader is insufficient for held-out execution. |
| `target_candidates.py`, `development_review_package.py` | Reuse conservative category and answer-shape checks; unknown categories abstain. |
| `reviewed_target_artifact.py` | New externally pinned, signed, complete 300-query artifact and policy loader; verification only, no approval/signing helper. |
| `injection.py` | Same reviewed target across seeds, attacks and intensities; validate before checkpoint lookup or generation. |
| `protocol.py` | Include reviewed provenance in poison-instance fingerprints; preserve historical hashes when absent. |
| Matrix runner | Require authenticated assignments before loading a generator or creating output; v2 cells, raw results, summaries and resumable plans bind exact pins. |
| `checkpoint.py` | Reuse complete provenance equality for current and archived recovery; runner includes assignment and artifact fingerprints in that provenance. |
| Matrix replay and aggregate | Require externally authenticated context for v2; compare every query target, summary and raw row; all 12 cells share the artifact. |
| Matched comparison | Shared Dense/RCD evaluation and flattened records preserve review metadata; paired comparisons reject differing pins/targets. Historical pilot replay rejects reviewed cells rather than stripping metadata. |

Historical v1 cell replay/aggregation remains available for auditing historical
results, without converting them into reviewed experiments. New execution has no
legacy fallback. Passing a development v3 mapping to the injection library alone
does not authorize the held-out runner. The frozen manifest, RCD weights, dataset
revision and historical results are unchanged.

## Leakage-safe, nonadaptive procedure — must be preregistered first

1. Complete method validation on development data only. Freeze nomination rules,
   supported categories, candidate source pool, aliases policy, source standards,
   reviewer rubric, disagreement handling and the failure/abstention rule. Record
   hashes of the development pool and nomination protocol. Do not inspect held-out
   text to tune these rules. The current conservative classifier can abstain on
   many held-out questions; coverage of 300 is **not established**.
2. An accountable coordinator preregisters the procedure, the existing 300 IDs,
   dataset revision and full query-set fingerprint, candidate ordering and a
   bounded number of permitted review rounds, before opening held-out questions.
   Freeze a reviewer policy with verified public keys, independent identities and
   a timezone-aware registration timestamp. Publish its hash and the
   preregistration hash through a trusted channel outside the assignment file.
   Establish reviewer independence externally; different strings or signatures
   alone do not establish it. The coordinator must not accept nominator-owned
   keys as independent reviewers. Keep private identities and keys out of Git.
3. Designated nominators may then inspect each frozen question solely to apply
   the preregistered rules. This access exposes test text and gold labels: it is
   a test-set leakage risk, even though target construction precedes execution.
   Record access, every nomination/rejection, candidate ordering and source
   provenance. Do not tune retrieval, defenses, prompts or category rules using
   these questions. Reviewers must be blind to model outputs, Dense/RCD outcomes,
   attack success, poison seeds and comparative results.
4. Independent reviewers check gold correctness, target falsehood, all known
   gold aliases, entity identity, question-specific type/role/constraints and
   whether coherent false evidence could support the target. Access reliable
   sources and record precise supported claims and limitations. Pending,
   ambiguous, unsupported or disputed cases cannot be approved automatically.
   The current schema supports direct factual questions only; comparison and
   chronology substitutions require further development validation and a new
   preregistered protocol, not a held-out-specific override.
5. Apply only the preregistered adjudication/replacement rule. If any of the 300
   IDs cannot receive a valid independent approval, **stop**. Do not drop that
   query, substitute another question, select favorable targets, inspect model
   outcomes, or enlarge the candidate search adaptively. A protocol amendment
   requires independent scientific review before execution; preserve the frozen
   held-out selection and disclose any test access. No assignment package has
   been produced in Phase 4B.
6. Freeze the exact header and complete rows. Each independent reviewer signs
   the exact decision message described below with their own private key.
   Editing any signed decision or header requires renewed independent review
   and signatures. Publish an immutable release and externally record its byte
   SHA-256; retain the nomination/decision audit trail under appropriate access
   control. A new release never overwrites an old one.
7. A separately authorized smoke run uses the first N manifest IDs, never a
   favorable subset, after authenticating all 300 assignments. Then inspect
   execution and semantic poison quality before separately authorizing the
   12-cell matrix. Targets remain identical across all three predeclared seeds,
   both attacks, both intensities and both matched pipelines. Runtime heuristic
   semantic support checks do not prove entailment or scientific validity.

## Artifact and authentication contract

Artifact schema: `rag-poison-transfer.reviewed-heldout-targets/v1`.
Policy schema: `rag-poison-transfer.target-review-policy/v1`.
Executable artifacts must be JSON objects with unique keys; their **exact bytes**
are pinned with external SHA-256 values, including whitespace and signatures.
Do not obtain the trusted pin solely from the file being checked.

The artifact header (all top-level fields except `assignments`) contains:

- `schema`, `scope: "heldout"`, `status: "frozen_independently_reviewed"`;
- immutable nonempty `release_id` and `review_policy_sha256`;
- `dataset`: exact `name`, `config`, `revision`, `split`,
  `heldout_manifest_fingerprint`, `heldout_manifest_sha256`,
  `query_set_fingerprint` (existing fingerprint over IDs, questions, gold answers
  and gold document IDs).

`assignments` contains exactly one independently reviewed row for every frozen
ID, with no extras. Each row retains all v3 fields:
`query_id`, `target_answer`, `answer_category`, `reviewer`, `review_evidence`,
`approved`, `review_status`, `semantic_compatible`, `factually_false`,
`coherent_false_evidence`, `question_sha256`, `gold_answer_sha256`,
`reviewed_target_sha256`, `reviewed_at`. Only actual independent decisions may
supply approval values and identity/time. Rows also require:

- exact `gold_answer`, complete nonempty `gold_aliases` including gold,
  `alias_check_complete`, `question_form: "direct_fact"`, and `nominator`;
- `candidate_provenance`: `nomination_protocol_sha256`,
  `development_pool_fingerprint`, nonempty `source_reference`;
- nonempty `evidence_references`, each with `reference`, precise `claim`, and
  explicit `limitations` (write an honest statement even if none are known);
- `decision_provenance`: `review_policy_sha256`, `nomination_protocol_sha256`,
  unique nonempty `decision_id`;
- `signature`: ASCII OpenSSH SSHSIG armor from the registered independent key.

The policy contains the same exact dataset binding, `scope: "heldout"`,
`status: "frozen_preregistered"`, `registered_at`, `preregistration_sha256`,
`nomination_protocol_sha256`, `development_pool_fingerprint`, `allowed_categories`,
and `reviewers`: a mapping of independently verified reviewer identifiers to
`{role: "independent_reviewer", public_key: "ssh-ed25519 <base64>"}`. No signing
keys, example approvals, or real reviewer records are provided in this change.
Policy registration must precede each review; future timestamps are invalid.

Allowed categories reuse the development vocabulary: `yes_no`,
`instrument_family`, `animal`, `language`, `sports_venue`, `date`, `quantity`,
`relationship`, `battle`, `person`, `company`, `brewery`, `magazine`, `empire`,
`river`, `comic_series`, `film`, `transport_place`, `biological_taxon`, `place`.
The existing classifier must agree with the category. Shape screening currently
accepts four-digit years and integer counts; other dates/counts require a
method revision rather than a per-query exception. Screening cannot discover
all semantic aliases or certify a named entity's type; independent signed
review is essential.

The exact signed message is UTF-8 JSON:
`{"header": <all artifact fields except assignments>, "assignment": <row except signature>}`.
Serialization uses sorted keys, no ASCII escaping, comma/colon separators,
no NaN/Infinity and **no trailing newline** (`decision_message` implements it).
Reviewers use their own signing environment and the SSHSIG namespace
`rag-poison-transfer.reviewed-targets.v1`. Verification requires OpenSSH with
`ssh-keygen -Y verify` and supports Ed25519 public keys. No dependency installation
or paid service is needed. Signatures authenticate exact recorded decisions;
they cannot prove factual correctness, evidence access or personal independence.
No test fixture creates a signed approval record.

The immutable in-memory context holds serialized bytes and returns copies.
Artifact byte SHA, policy SHA, preregistration SHA, full query fingerprint and
canonical assignment fingerprint travel together as `target_review` in v2 cells,
associations, raw results, summaries, checkpoints and aggregates. The mapping
fingerprint includes identities, timestamps, evidence, provenance and signatures;
changing any of them invalidates recovery and replay. Historical v1 cells cannot
be downgraded from v2 by retaining review markers. Externally supplied v2 context
also rejects legacy cells even if their markers are removed.

## Execution interface (blocked until genuine inputs exist)

The matrix runner and aggregate CLI accept:

```text
--target-assignments /secure/path/frozen-targets.json
--target-assignments-sha256 <externally trusted exact-byte SHA256>
--reviewer-policy /secure/path/frozen-policy.json
--reviewer-policy-sha256 <externally trusted exact-byte SHA256>
--preregistration-sha256 <externally trusted preregistration SHA256>
```

All five are mandatory for new matrix or smoke execution; a missing/partial set
fails before output directories or generators are created. `--preflight` is a
read-only structural check and does **not** certify approvals or authorize a run.
Use the existing manifest/config defaults and a fresh experiment ID. Smoke uses
`--smoke-test --smoke-query-count 2`; no smoke or matrix was launched here.
Aggregation of reviewed cells requires these same external pins, plus the
existing independently trusted commit/source pins where available. Historical
v1 aggregation retains its existing interface and historical status.

## Verification and remaining blockers

Regression tests cover mandatory approval gating, real development-package
rejection, missing/duplicate IDs, dataset/query/policy pins, pending decisions,
alias/type/chronology/provenance checks, signature verification/tampering,
three-seed target determinism, v2 replay/downgrade rejection, raw and summary
provenance, whole-matrix consistency and checkpoint provenance rejection.
Tests isolate the post-authentication boundary using pending nomination doubles;
they do not constitute a successfully independently approved 300-query release.
Existing lifecycle tests explicitly mock that boundary to continue exercising
legacy recovery and model-free execution behavior. An end-to-end genuine signed
release remains blocked on actual independent decisions and trusted policy pins.

Scientific blockers: preregistration and independent governance; genuine review
of all 300 frozen IDs; unknown category/abstention coverage; evidence and alias
adjudication; review of generated semantic poison quality; separately authorized
real-model smoke test and full experiment. Technical tests cannot remove these
blockers. The full 12-cell matrix is **not authorized**.

## Phase 4B implementation validation

From main `b8151adb24b086a860b80c98888ba6fa21b93077`, on branch
`experiment/week9-reviewed-target-integration`:

```text
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q
755 passed in 93.10s; 0 failed

.venv/bin/python -m compileall -q src scripts tests
exit 0

git diff --check
exit 0
```

The 39 new integration tests use pending records and isolated context doubles,
not artificial approvals. No real-model smoke, paid call or matrix was run.

Exact changed files:

```text
docs/PHASE4B_REVIEWED_TARGET_PROTOCOL.md
scripts/aggregate_week9_heldout_poison_matrix.py
scripts/run_week9_heldout_poison_matrix.py
scripts/run_week9_matched_poison_comparison.py
src/attacks/injection.py
src/attacks/review_provenance.py
src/attacks/reviewed_target_artifact.py
src/experiments/protocol.py
tests/test_reviewed_target_integration.py
tests/test_week9_heldout_poison_matrix.py
tests/test_week9_semantic_reliability.py
```
