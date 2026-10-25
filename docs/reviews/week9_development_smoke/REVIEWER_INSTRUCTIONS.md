# Independent development-smoke target review

These two cases are diagnostic development examples, not held-out approvals.
No valid independently completed review file has been supplied. The installed
MLX packages and a successful software preflight do not authorize execution.

## Prepare a private candidate worksheet

From the repository root:

```bash
.venv/bin/python scripts/prepare_week9_development_review.py prepare \
  --output /private/tmp/week9-candidate-review.json
```

Use a fresh writable destination. The helper never overwrites an existing file
or the committed pending template. Keep completed reviewer data in an appropriately
protected location outside Git; `/private/tmp` above is a preparation example.
The draft preserves exact development IDs, question/gold text, document IDs,
hashes and provenance. The original actor question's wording is intentionally
preserved rather than corrected to a paraphrase.

`candidate_suggestion.answer` contains the user's unverified Alfonso Ribeiro and
1804 suggestions. `target_answer` stays blank. The helper has accessed no factual
sources and verified neither suggestion. Reviewers may reject or replace them;
there is no automatic promotion or completion command.

## Genuine independent human actions

1. Establish who actually nominated the target and choose a genuinely independent
   reviewer. Record their real identities in the private file only. An operator
   must verify independence outside the software; different strings do not prove it.
2. Access reliable sources and establish the correct answer, relevant aliases,
   the precise question constraints, and why the proposed alternative is false.
   Record actual references with the precise supported `claim` and `limitations`.
   No source in this sheet is presented as evidence. For the university question,
   resolve Tokarev's professorship institution, founding versus reorganisation
   dates, calendar interpretation and any competing institution interpretation.
   Do not approve 1804 if its falsehood is ambiguous under the intended reading.
3. Decide whether the false answer has the required answer type and satisfies the
   question's constraints, and whether coherent affirmative false evidence could
   support it. Explain these conclusions and alias exclusions in `review_evidence`
   and optionally `candidate_review_notes`. Fill `gold_aliases` with all known
   relevant aliases, including the exact stored gold answer. Include at least one
   genuine evidence object with `reference`, `claim`, and `limitations`; state
   real limitations even if no further issue was found. Placeholder URLs are invalid.
4. If unresolved, falsehood is unverified, or the candidate is unsuitable, leave
   approval pending (or record rejection) and stop. Both cases must be genuinely
   approved before smoke execution. Never force acceptance to complete the file.
5. Only after a real positive decision, the human records the chosen `target_answer`,
   actual nominator/reviewer, actual timezone-qualified `reviewed_at` decision
   timestamp, `review_status: "approved"`, `approved: true`,
   `semantic_compatible: true`, `factually_false: true`,
   `coherent_false_evidence: true`, `alias_check_complete: true`,
   `ambiguity_status: "resolved"`, and `evidence_status: "independently_verified"`.
   Compute `reviewed_target_sha256` from the exact UTF-8 target string, with no
   trailing newline. Keep all original question/gold/document/provenance fields
   unchanged. After both actual approvals, the human sets header
   `status: "reviewed_diagnostic_only"`. This is a manual decision, not a tool output.
6. The trusted handoff custodian supplies the exact-byte SHA-256 over the final
   immutable file through a separately trusted channel. Hashing a file proves
   content identity, not approval. Any edit invalidates the old hash and requires
   a new handoff; a changed target requires renewed human review. Do not commit
   private identities, evidence notes or completed review files.

This development schema does not create signatures. It does not replace the
separate final held-out signed approval protocol or relax its 300-query gate.

## Validate without model execution

Set `WEEK9_DEV_REVIEW_FILE` to the actual completed private file and
`WEEK9_DEV_REVIEW_SHA256` to its externally trusted lowercase 64-hex hash:

```bash
.venv/bin/python scripts/prepare_week9_development_review.py validate \
  --targets "$WEEK9_DEV_REVIEW_FILE" \
  --targets-sha256 "$WEEK9_DEV_REVIEW_SHA256"
```

Exit 0 means structural validation passed. Exit 2 reports missing or invalid
field locations without printing review contents. This command does not load
datasets or models, run inference, sign, or modify the input. The authoritative
runner loader is reused. No software check can prove that a source was actually
read, factual claims are true, or identities are independent. Obvious unfinished
placeholders are rejected; convincing fabrication cannot be excluded mechanically.

Then the original metadata-only preflight can validate the same immutable input:

```bash
.venv/bin/python scripts/run_week9_development_smoke.py --preflight \
  --targets "$WEEK9_DEV_REVIEW_FILE" \
  --targets-sha256 "$WEEK9_DEV_REVIEW_SHA256"
```

The original failure with `/secure/path/...` and an unset hash was an expected
missing-input rejection. Those strings were examples, not supplied review inputs.
The workflow improvements add explicit missing-input messages, field-level reports,
draft preparation and obvious placeholder checks; they do not fix or bypass the gate.

After valid genuine reviews exist, execution still requires explicit authorization
for MLX inference and cached weights/data. See the
[execution instructions](../../WEEK9_DEVELOPMENT_SMOKE_IMPLEMENTATION.md).
Actual generated semantic evidence still requires post-run human inspection.
No inference or full matrix is authorized or run by this review workflow.
