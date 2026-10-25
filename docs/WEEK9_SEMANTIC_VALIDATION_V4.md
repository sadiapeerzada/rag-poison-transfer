# Week 9 semantic-validator correction

Base: latest main `33f1773`. Branch: `fix/week9-semantic-validation`.
This is a software correction using user-reported diagnostic cases and synthetic
generator stubs. No new real-model inference, held-out text access or matrix run
was performed. Frozen Week 7–8 results, RCD parameters/configurations, cohort IDs,
research questions and approval gates are unchanged.

## Confirmed defects and corrected behavior

- The old gold screen only matched a few verb-before-gold constructions. It
  accepted a paragraph asserting Dickens and then identifying Jane Austen as
  the actual writer, and the supplied Lyon paragraph explicitly correcting itself
  to Paris. The person report contained no verbatim paragraph: its regression
  paragraph is an illustrative reconstruction, not a claimed captured MLX output.
  The place and Titanic fixtures use the exact supplied text.
- The shared screen and the stricter development screen missed the affirmative
  Titanic sentence ending “met its tragic end in 1913.” Both now recognize the
  bounded event/date relation as `heuristically_supported_unverified` only.
- Target proximity to “answer” could pass without a direct assertion. Support
  now requires bounded affirmative syntax; passive mentions, speculation,
  questions, explicit corrections/undermining and negation fail closed.

The strengthened gold check rejects any whole gold-answer or explicitly supplied
`gold_aliases` mention, and target equality with those forms. This includes gold
mentions elsewhere in the paragraph, in either grammatical direction. It is
deliberately conservative: benign background references or ambiguous short gold
tokens can also be rejected. No gold aliases are invented or automatically
looked up. The reviewed-target gate remains responsible for genuine alias review.

Date support requires a concrete supported event predicate directly followed by
`in`/`during` and an exact four-digit target year; a bare year occurrence or
`in YEAR` is insufficient. The supported predicates include sinking/foundering,
founding, birth/death, opening/closing, beginning/ending and occurrence. Unsupported
date syntax remains unverified. Whole-token boundaries exclude a year embedded
in a longer number. This narrow grammar is not a general date/chronology solver.

These rules still cannot prove question-specific entailment, resolve all pronouns,
find every correction/alias, or verify factual truth. In particular, affirmative
syntax can describe the wrong event or relationship. Human review of actual
generated evidence is still required. No LLM judge or automatic approval exists.

## Versions and comparability

- Shared validator: `conservative-text-heuristic/v3` →
  `conservative-text-heuristic/v4`.
- Development direct-relation screen: `development-direct-affirmation/v1` →
  `development-direct-affirmation/v2`, sharing the affirmative predicate with v4.
- Generation prompt stays `semantic-encyclopedic-prompt/v3`; retry policy remains
  `distinct-explicit-revision-prompts/v1`, with the same model/target/budget and
  maximum two predeclared attempts. No output-dependent strengthening or resampling
  was introduced.

The validator changes which candidates are accepted, so accepted-generation
counts and downstream ASR from different versions are not directly interchangeable.
Do not relabel, overwrite or pool historical results. Existing plans/manifests
already pin validator versions and source fingerprints; changed diagnostic plans
and checkpoints fail provenance matching. Replay historical experiments from
their original commit/protocol, or preregister a separately labelled v4 run.
Any frozen protocol/version decision must be explicitly updated through its
existing human governance before new held-out execution. No old approval becomes
newly authorized by this fix.

## Diagnostic export

`attack.export_attempt_records()` returns a deep-copied JSON-safe list of
`{query_id, poison_index, attempts}` records. The internal tuple-key mapping stays
unchanged for checkpoint callers; do not pass `attack.attempt_log` directly to
`json.dump`. Direct serialization of that internal mapping raises a tuple-key
error. The existing development runner already manually converted it to list
records; it now uses the export API on success/failure. The other existing smoke
writer also already converts tuple keys to list records. This is an explicit
safe export interface, not a claim that their existing list conversion was broken.

With `capture_smoke_diagnostics = True`, each successful/rejected/backend-error
attempt retains its attempt number, prompt revision/full prompt, prompt and
validator versions, retry policy, actual untrimmed generated text (or null if
none was returned), rejection/error reason and actual backend prompt where
available. The injected poison document still uses trimmed validated text.
Model provenance uses only supplied metadata or observed generator class/name;
the development recorder supplies the configured model/backend and actual Git SHA.
No missing model revision is guessed. Existing generation events and manifests
remain the companion source of complete execution provenance.

For manual, development-only diagnosis with an already constructed attack:

```python
# Enable before generation; no approval or generation is performed by export.
attack.capture_smoke_diagnostics = True
# After the caller's separately authorized generation attempt, even on rejection:
json.dump(attack.export_attempt_records(), stream, ensure_ascii=False, indent=2)
```

## Remaining real-model validation blockers

1. Genuine independently reviewed target inputs and their externally trusted
   exact-byte hash are required for the gated two-query development runner.
2. Explicit authorization for real MLX execution and locally available pinned
   model/dataset inputs remain required; software tests exercise synthetic stubs.
3. Freeze the diagnostic's v4/v2 provenance before execution, use a fresh output
   attempt, and do not reuse v3/v1 checkpoints or change targets after outcomes.
4. Independently inspect actual accepted/rejected prose after execution for
   relevance, factual falsehood, aliases, correction and coherent affirmative
   support. Passing software tests proves none of these semantic properties.
5. The final 300-query independent-review/preregistration requirements and any
   supervisor decisions in the original-plan reconciliation remain separate.
   This fix neither authorizes nor runs the full matrix.

## Executed software checks

- Before fixes, the initial new regression set produced **12 failed, 5 passed**,
  reproducing correction false acceptance, date false rejection, and the missing
  export behavior. No model was constructed.
- Final focused run:
  `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q tests/test_semantic_validation_v4.py tests/test_week9_semantic_reliability.py tests/test_week9_development_smoke.py --tb=short`
  — **52 passed** (1.05 seconds).
- Final full offline run:
  `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q`
  — **962 passed, 0 failed** (94.79 seconds).
- `.venv/bin/python -m compileall -q src scripts tests` — passed.
- `git diff --check` — passed.
- Metadata-only development `--preflight` — passed; reports shared v4,
  diagnostic v2, and `review_input_validated: false`.

These are software results, not real-model outcomes, independent target approvals
or verification of semantic correctness.
