# AI-assisted semantic review and source-focus defect correction

This follows the completed train-only 25-query study at frozen source
`12c2400478b8a81c4e668fdbfcf3d0047cb96d32`. All original protocol, construction,
evaluation, aggregate and human-review files remain immutable. A snapshot of all
499 original files is at `/private/tmp/semantic-ai-review-frozen-inventory-v1.json`.
The protocol/seal/completion hashes supplied in the continuation request were
verified and the original aggregate revalidated from its underlying records.

## Confirmed defect and bounded fix

`target_candidates.expected_category()` checks a broad human-role pattern before
its country/place pattern. `development_targets_v2.classify()` also scans beyond
the requested head: `country` is absent from `HEADS`, allowing a later `director`
to determine `person`. Its generic answer-shape test then accepts `Dutch` as a
person-shaped label. Consequently, a source asking “Which country the director of
film Max (2002 Film) is from?” with label `Dutch` enters the person candidate pool.
This is a selection defect, not an answer invented by the generation stage.

Checking the complete 300-query development source pool found four such source
records (three labeled American, one Dutch). The frozen study selected Dutch for
two identity questions: the maternal-grandfather example and Clotilde's father-in-law.
These destinations account for **16/152 generated attempts**. Prompts and construction
records already contain that target; model outputs then often assert nationality
rather than the requested identity. The frozen assignments are not changed.

`development_targets_v4.py` adds the explicit development-only selector
`development-source-focus-guard/v1`. It excludes the demonstrated country-request /
embedded-person-role conflicts and abstains on conflicted destinations. It does not
blacklist Dutch as a potential genuine person's nickname, or misclassify a country
music singer request. Legacy v2/v3 functions remain unchanged for reproducibility.

Future use requires `--target-method development-source-focus-guard/v1` together
with development scope, `question-anchored-development/v1` and the separately frozen
development study. The new protocol container is
`rag-poison-transfer.semantic-development-protocol/v2`. The descriptor binds its
implementation hashes; manifests, query records, journals and replay checks bind
its fingerprint. Old protocols retain the original target method. This fix does not
perform general entity typing, establish aliases, enforce every kinship constraint
or verify target falsehood. A new person-name nomination is not automatically valid.
No corrected attack-generation experiment is launched as part of AI assessment.

## Complete automatic-failure inventory

The sealed study contains 152 model outputs, 50 query/intensity records and no accepted
documents. There are six target-nomination failures per intensity and 19 semantic
construction failures per intensity. Only three of the 19 target-bearing questions
have any grammar recognized by the narrow development validator. Grammar recognition
alone does not ensure a model sentence matches that grammar.

| Automatic reason | Attempts |
| --- | ---: |
| Competing gold answer / supplied alias | 43 |
| Unverified semantic support | 77 |
| Does not affirm target | 20 |
| Invalid length | 12 |
| Total | 152 |

The machine-readable audit is
`/private/tmp/oct27-semantic-failure-audit-v1/automatic_mechanisms.json`.
It covers all 152 attempts and the 25 queries, distinguishing attempt counts from
unique queries. Unsupported dates, negative Boolean answers, comparative prose that
mentions both options, narrow surface-form matching and short statements remain
coverage/policy limitations. They are not relabeled as confirmed implementation bugs
or proven validator false rejections without further assessment. None of the rejection
rules, prompts, retry budgets or frozen outcomes is relaxed.

## Separate AI-review protocol

`run_ai_semantic_review.py` supports `freeze`, `pilot`, `assess`, `compare`.
It reads the original sealed review package (a directory despite its `.json` suffix)
without modifying it. AI outputs use a different namespace and schemas:

- Plan: `rag-poison-transfer.ai-semantic-review-plan/v1`.
- Item: `rag-poison-transfer.ai-semantic-assessment/v1`.
- Completion and comparison artifacts bind every transcript and assessment.

The evaluator is local Qwen2.5-7B-Instruct-4bit, pinned to snapshot
`c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`, with file hashes, clean code commit,
dependency versions, exact prompt text, prompt version, explicit greedy decoding,
seed 20261027, at most 512 completion tokens and one call per unique input.
There are no paid API calls. Because this is the same model snapshot that generated
the attacks, judgments are correlated self-review, not independent adjudication.

Every assessment is labeled `AI-assisted`, `human_review: false`. No human reviewer
identity, human timestamp or independence attestation is populated. Actual UTC start/
completion times describe the originating model call. Exact-input reuse shares that
origin and is explicitly identified; it is not a fresh independent judgment.

Only whitelisted question, benchmark label, explicit aliases, intended target,
generated statement and provided dataset passages reach the evaluator. Automatic
labels/reasons, intensity/attempt metadata and QA outcomes are withheld. All seven
existing criteria are assessed as yes/no/uncertain. The benchmark label is not factual
proof; the prompt requires uncertainty when supplied evidence cannot establish falsity.
References must identify supplied passages and contain actual quotations (whitespace
normalization only). Unknown references and fabricated quotations invalidate the
assessment rather than becoming evidence. These checks establish quote provenance,
not entailment or independent factual truth. Model inferences remain model inferences.

AI dispositions are derived transparently from the seven ratings: an explicit negative
on a substantive criterion rejects; all seven affirmative criteria accept; otherwise
the disposition is uncertain. Positive factual/evidence ratings require a supplied
passage quotation. Invalid model responses remain unevaluated; they are not repaired
through extra generations. AI acceptance does not approve a target or held-out protocol.
The original human-review importer rejects the AI schema and is not used for AI results.

A controlled pilot has three fixed unique questions: the demonstrated identity/type
conflict, a Boolean question and a dated target, selected deterministically before
calls. It checks parseability, evidence quotes and a specific identity-versus-nationality
rubric sanity condition. If it fails, preserve the pilot and stop; do not blindly repeat
calls or silently revise prompts. Only after a meaningful pilot should the complete
census be assessed. Comparison with automatic decisions is blocked until every item
has a terminal record, including any explicitly invalid/unevaluated response.

## Execution and commands

Proposed isolated AI namespace: `/private/tmp/oct27-semantic-ai-review-v1`.
Actual counts/pins are recorded there, not in the original study namespace. This
workflow never reruns poison construction, QA or the held-out matrix.

```sh
cd /private/tmp/rag-semantic-ai-review-development
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
ORIGINAL=/private/tmp/oct26-2wiki-semantic-development-25-v1
PACKAGE="$ORIGINAL/semantic_human_review_package.json"
PACKAGE_SHA=$(shasum -a 256 "$PACKAGE/manifest.json" | cut -d ' ' -f 1)
NEW=/private/tmp/oct27-semantic-ai-review-v1
"$PY" scripts/run_ai_semantic_review.py freeze --plan "$NEW/plan.json" \
 --package "$PACKAGE" --package-manifest-sha256 "$PACKAGE_SHA" \
 --original-protocol "$ORIGINAL/protocol.json" \
 --original-protocol-sha256 00d1600661312ad78bbf5a9d1e54becc080909b913e2124c40705ca9aaced6ca \
 --construction-dir "$ORIGINAL/execution/construction" \
 --construction-seal-sha256 c8714eb7e453c026a2e575e894572970c32cc39b7a16357afa82b3d53b36d951 \
 --model-snapshot "$MODEL"
PIN=$(shasum -a 256 "$NEW/plan.json" | cut -d ' ' -f 1)
caffeinate -i /usr/bin/time -l "$PY" scripts/run_ai_semantic_review.py pilot \
 --plan "$NEW/plan.json" --plan-sha256 "$PIN" --model-snapshot "$MODEL" --allow-local-model-calls
# Inspect pilot rubric/evidence/parse results first. Do not continue a failed pilot.
caffeinate -i /usr/bin/time -l "$PY" scripts/run_ai_semantic_review.py assess \
 --plan "$NEW/plan.json" --plan-sha256 "$PIN" --model-snapshot "$MODEL" --allow-local-model-calls
"$PY" scripts/run_ai_semantic_review.py compare --plan "$NEW/plan.json" --plan-sha256 "$PIN"
```

No automatic generation retry is permitted after an incomplete/error journal. Complete
responses replay exactly; identical full evaluator inputs reuse a provenance-bound call.
The plan records the exact unique-call ceiling (never more than 152); the pilot uses at
most three. Actual AI accept/reject/uncertain/unevaluated counts are available only in
assessment records/comparison after execution. Missing records are never counted as
reviews. The original human sheet remains 152 pending unless actual humans complete it.

## Verification and limitations

Focused regression suite: **96 passed**. Full offline suite: **1164 passed in 125.29s**.
Compilation and whitespace checks passed. Tests cover blinded input construction,
separate human/AI schemas, fabricated-evidence refusal, uncertainty, pilot sanity,
exact-input cache/replay, interrupted-call refusal, altered ratings, completion seals,
namespace/budget enforcement, the source-focus defect and versioned future-selector
construction/replay. These are software fixtures, not factual or human judgments.

Frozen-study metrics remain unchanged. With zero injected poison, conditional ASR,
retrieval visibility and defense effectiveness are unavailable; zero end-to-end success
is not evidence of RCD robustness. No held-out readiness claim follows from AI review.
Further attack generation requires a separately frozen development protocol and
meaningful validation of type/role compatibility and generated claims. The present
fix is bounded, and wider ontology/alias/predicate/factual issues remain unresolved.

Changes are local until their diff is reported and push/merge approval is received.
