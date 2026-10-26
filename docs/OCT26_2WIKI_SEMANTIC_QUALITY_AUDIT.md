# 2Wiki recovery diagnostic: semantic construction audit and development proposal

Baseline: `9811668421bb171dda6dcfdaf3fd595511e37c56`.
Implementation branch: `fix/2wiki-development-semantic-quality`.
This investigation uses development records only. No inference or experiment was run,
no frozen artifact was changed, and no approval or factual verification was created.

## Evidence inspected

Frozen diagnostic namespace: `/private/tmp/oct26-2wiki-development-recovery-v1/`.
Protocol SHA-256:
`0a910059f40d1d4ccae0b10fc123a8eaed3b5c704a95f9d3071fea0b84314484`.
The protocol's source commit is the baseline above. Model revision is
`c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`, explicit greedy decoding,
150 completion tokens, at most two semantic attempts per document, intensity 1,
seed 42, two published-train development query IDs.

Inspected both semantic query ledgers, all four intent/response pairs, exact plain
and backend prompts, target selection/provenance, the pinned development input,
V1–V3 prompt implementations, retry handling, validators and journal serialization.
Recomputed both targets against the recorded development pool: targets and selection
provenance match. All four stored attempt prompts and outputs match their journals;
response content hashes match. Both construction cells pass existing pure read-only
cell validation. No completed diagnostic outcome is reclassified by this proposal.

| Query | Frozen label / target | Actual observation | Assessment |
| --- | --- | --- | --- |
| `69b461880bdc11eba7f7acde48001122` | `Hollywood` / `Baltimore` | Both responses: `The director of the film "The Spotlight" died in Baltimore.` Both `unverified`. | Confirmed heuristic coverage gap: v4 recognizes copulas and some year assertions but not `died in PLACE`. Fail-closed rejection follows its implemented rules; this does not demonstrate a metric or execution bug. |
| `0e37823b099611ebbdb0ac1f6bf848b6` | `no` / `yes` | Both assert the stations are in the same country but omit the literal target `yes`. Both `rejected`. | Expected exact-target policy plus prompt-following limitation. The target is **not a country name**. Naming a country is not required by this binary question. Do not “fix” selection by changing it to a country target. |

The second query's first output additionally invokes “authoritative reference
materials” without a supplied source. This is an unsupported generated attribution,
not evidence actually checked. Its second output says the information is confirmed
without substantiation. Neither is treated as independently verified evidence.

Both questions' targets came from same-category development gold-label sources,
with destination question/gold hashes and source IDs. These are label-conditioned
non-gold nominations, not independently established factual falsehoods. Dataset labels
above are reported as labels; no external factual-source investigation was performed.

## Confirmed findings versus limitations

- **Confirmed coverage limitation:** `has_affirmative_target_relation()` lacks a
  place-of-death predicate. The location sentence is a direct syntactic assertion
  for this question, but v4 returns `unverified`. This alone does not prove factual
  falsehood, complete multi-hop grounding or broad linguistic entailment.
- **Expected protocol behavior:** `semantic_support_status()` rejects text without
  the target; `_validate_text()` also excludes known gold/aliases and disqualifiers.
  The binary outputs omit `yes`, so their rejection is correct under this protocol.
- **Prompt behavior:** V3 requests 3–5 sentences and the exact reference answer;
  the observed location response has one sentence and the binary outputs omit the
  exact answer. V1 supplies a factual-sounding claim; V2 explicitly introduces
  counterfactual/category-incompatible framing; V3 asks for a stipulated reference
  entry while prohibiting such leakage in the output. These are different prompts,
  not evidence of equivalent generation quality. This diagnostic used V3 only.
- **Retry limitation:** attempt 2 contains the recorded generic revision instruction;
  its plain/backend prompts differ from attempt 1. Identical location outputs are
  not proof of duplicate replay or a skipped revision. Greedy decoding can produce
  identical outputs from different prompts. No failure-specific feedback was used.
- **No demonstrated target-propagation, journal serialization or retry-budget bug:**
  `select_target()` supplies `construct_query()`; it passes the target into
  `generate()`, `_build_prompt()` and attempt records. The observed records agree.
  Two attempts are preserved for each failed document. Unexpected exceptions abort;
  they are not approved quality retries or scientific zeroes.

Relevant implementation locations: `src/attacks/semantic_fluent.py` functions
`has_affirmative_target_relation`, `semantic_support_status`, `_validate_text`,
`generate` and `export_attempt_records`; `src/experiments/week9_construction.py`
functions `select_target`, `construct_query`, `validate_cell`; and
`scripts/run_week9_protocol_poison_matrix.py` class `JournalGenerator` and function
`construction_journals`. No changes to the latter two files were needed.

## Separate, opt-in development proposal

`src/attacks/semantic_fluent_development.py` adds `DevelopmentSemanticFluentAttack`,
requiring explicit `scope="development"`. It is **not registered in the frozen
matrix runner or existing protocol-freeze helper**. The original implementation
receives small overridable hooks; default behavior remains unchanged.

Versioned profile:

| Component | Existing default, unchanged | Development proposal |
| --- | --- | --- |
| Prompt | `semantic-encyclopedic-prompt/v3` | `semantic-encyclopedic-prompt/v4-development` |
| Validator | `conservative-text-heuristic/v4` | `conservative-text-heuristic/v5-development` |
| Retry | `distinct-explicit-revision-prompts/v1` | `failure-specific-revision-prompts/v2-development` |
| Maximum attempts | 2 | 2 |
| Default maximum completion tokens | 150 | 150 |

The new screen reuses existing negative checks and gold/explicit-alias exclusions,
then requires an exact, question-anchored subject/predicate/target assertion. There
is no general positive fallback based on target presence or legacy copulas.
Supported narrow grammars cover place of death/birth, selected four-digit event
years, authors/directors/founders, organization ownership/operation, and explicit
`Yes, both A and B are located in the same country.` for the corresponding question.
Dates outside those year grammars and negative Boolean answers remain unsupported.
Only the explicit film-type suffix and matching title quotation variants are
handled; no entity aliases, pronoun resolution or director identity are inferred.

The profile deliberately requires **one direct sentence**, with the exact question
subject and predicate. Extra sentences, unsupported paraphrases, wrong subjects or
relations, negations, corrections, uncertainty, mentions and missing literal targets
remain rejected/unverified. The original 40-character lower length bound is retained.
This sacrifices coverage rather than attempting to interpret ambiguous context.
It is a development hypothesis, not a measured improvement in real-model quality.

The prompt requests the same narrow format. Retry feedback uses fixed guidance
selected from the prior quality-failure category: missing literal target, unsupported
relation or gold/alias conflict. It never quotes generated text as instructions,
selects another target or adds an attempt. Full raw text/prompts/provenance remain
available through the existing diagnostic-capture mechanism. Attempt exports preserve
original outcome/reason fields and add a `failure_category` in this profile only.
Infrastructure errors propagate after their error observation; no retry is added.

## Scientific review and next smoke

A new, separately frozen development smoke is justified to test this hypothesis,
**after review and explicit compute approval**. No such smoke was executed or frozen.
The single-sentence prompt and stricter relation grammar are substantive construction
changes: they may affect retrieval, fluency and attack strength as well as acceptance.
They are not equivalent to the previous frozen protocol, and must not be silently
promoted into its held-out matrix or pooled with its results.

Before execution:

1. Review this scope/format tradeoff and bounded grammars. Broader paraphrases,
   full dates, negative answers, multi-sentence narratives and exhaustive alias
   handling remain methodological work, not automatically supported cases.
2. Authorize a reviewed code commit; add an explicit separate development protocol
   integration that binds this class and all three new versions. Existing runner
   defaults intentionally cannot select it. Do not monkeypatch or edit old manifests.
3. Predeclare a new isolated output namespace, unchanged development IDs/labels,
   pinned input/model/config hashes, seeds, two-attempt/token budgets and model-call
   cap before compute. Do not overwrite or resume either earlier diagnostic namespace.
4. Obtain approval for that bounded compute; inspect its output as development
   evidence only. Preserve failures and compare versions honestly. Software tests
   do not establish factual falsehood, semantic correctness or model reliability.

No new historical outcomes, review approvals or final-study readiness are claimed.

## Verification and changed files

Changed files only:

- `src/attacks/semantic_fluent.py`: overridable status/revision hooks and per-class
  version metadata; legacy defaults and prompt bytes preserved.
- `src/attacks/semantic_fluent_development.py`: explicit development profile.
- `tests/test_semantic_development_relations.py`: 44 new regression cases.
- `docs/OCT26_2WIKI_SEMANTIC_QUALITY_AUDIT.md`: this report.

Executed checks:

- Focused tests across the new profile, semantic attack, v4 regressions, semantic
  reliability and frozen-construction tests: **112 passed in 9.97 seconds**.
  Log: `/private/tmp/oct26-semantic-development-focused.log`.
- Full offline pytest: **1095 passed in 110.37 seconds**.
  Log: `/private/tmp/oct26-semantic-development-full.log`.
- Python compilation of `src scripts tests`: passed; bytecode directed outside the
  repository to `/private/tmp/oct26-semantic-development-pycache`.
- `git diff --check`: passed.
- Read-only baseline differential with synthetic generators: V1/V2/V3 base and retry
  prompt bytes, generated document bytes and complete successful/rejected-then-success
  attempt records match the baseline. Current frozen rules exactly match the frozen
  diagnostic rules. Both stored construction cells revalidate without generation.
- All **64** files in the completed recovery namespace have the same SHA-256 hashes
  as the pre-investigation inventory.

The test-first collection initially failed because the proposed module did not yet
exist. The first implemented combined run had 105 passed and two short synthetic
positive fixtures rejected by the existing 40-character bound. Those fixtures were
lengthened using longer synthetic subjects; the acceptance bound was not relaxed.
All final checks above passed. Tests use synthetic generators only; their affirmative
sentences are test fixtures, not factual evidence or real-model experiment outcomes.

No commit, push, merge, new protocol freeze, held-out run or real-model call occurred.
