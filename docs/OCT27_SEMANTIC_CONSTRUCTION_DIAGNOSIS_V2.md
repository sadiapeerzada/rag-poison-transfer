# Semantic construction diagnosis and proposed development pilot

Base: `main` at `6a8468e738f876b11236f1d1b5ceed44a8d2ee37`.
Implementation branch: `development/semantic-construction-diagnostics-v2`.
This is development infrastructure and a pilot proposal, not new experimental results.
No inference, poison regeneration, AI-review census or held-out execution was performed.
This audit authorizes committing and pushing the reviewed development branch only;
merging and model compute remain separate user decisions.

## Evidence examined

- All 152 master attempt records, questions, labels and supplied aliases in
  `/private/tmp/oct26-2wiki-semantic-development-25-v1/semantic_human_review_package.json/master.jsonl`.
- Original frozen protocol, construction records and pinned 300-query train input.
  Protocol SHA-256:
  `00d1600661312ad78bbf5a9d1e54becc080909b913e2124c40705ca9aaced6ca`.
- Current selector, prompt, validator, profile, journal, seal, evaluation and aggregation code;
  previous development reports and regression tests.
- All three existing AI assessment artifacts and their failed pilot-gate report in
  `/private/tmp/oct27-semantic-ai-review-v1/`.
- No held-out question or gold text was inspected. Held-out IDs are used only by the
  existing disjointness checks. No external factual sources were checked in this audit.

The offline per-attempt diagnostic is outside the frozen namespace at
`/private/tmp/semantic-construction-v2-offline-audit.json`; final v6.1 results are at
`/private/tmp/semantic-construction-v2-final-audit.json`.

## Findings and classification

| Finding | Classification | Evidence and consequence |
| --- | --- | --- |
| Country-request source labeled Dutch contaminated the person pool | Previously confirmed defect, already fixed in merged development guard | Four country/person source conflicts in the 300-query train pool. Two frozen destinations used Dutch, affecting 16 attempts. Existing v4 exclusion is reused, not reimplemented. |
| Complete equivalent dates can pass the non-gold exclusion | Newly confirmed implementation defect | Synthetic reproduction: gold `April 14, 1969`, source `14 April 1969`; v4 nominates the latter. v2 candidates and v3 proposals compare text normalization rather than complete calendar dates. This defect was not observed among the 19 actual frozen targets and does not explain their zero acceptance. |
| Pending V2 grammar accepted explicit non-nominal targets in place/nationality slots | Newly confirmed implementation defect, fixed before release | Five deterministic cases accepted years, a full date or yes/no in a place/nationality slot before the fix. The shape guard now runs before both inherited and new positive grammars; validator version is v6.1-development. This is not general named-entity typing. |
| Most cohort predicates are outside the narrow development grammar | Scientific limitation / intentional conservative policy | Full dates, negative Boolean answers, comparisons and kinship are unsupported. Even a correctly formed sentence need not match the exact subject syntax. Unknown support is deliberately refused. |
| Optional articles and role phrases differ between question and generated sentence | Bounded surface-grammar limitation | E.g. `director of film` becomes `director of the film`; the relation and complete title can remain explicit. A new opt-in grammar recognizes only declared complete forms. |
| Existing single-sentence prompt retains historical/institutional framings and omits the validator's 40-character minimum | Prompt/validator interface limitation | These instructions can encourage extraneous context or short outputs. The new prompt removes topic-changing framings and states the existing length floor; it does not lower that floor. Causal improvement requires a future pilot. |
| Competing gold/alias mention screen rejects any complete gold mention | Expected conservative behavior | 43 attempts. Some comparison questions mention both alternatives; these require a separate predicate-aware protocol, not blanket removal of this screen. |
| Target-not-affirmed and short-text failures | Expected behavior / limitations | 20 and 12 attempts respectively. Negative Boolean forms are unsupported; fragments, uncertainty, corrections and missing targets must continue to fail. Short syntactically sound claims can fail the deliberate length floor. |
| AI evaluator produced invalid quotations | Confirmed observed model-output failure; guard worked | Two of three outputs failed the existing passage-quotation checks. They remain unevaluated and do not count as factual review. |
| AI evaluator inferred false nationality from a different person's name | Scientific limitation / unsupported model judgment | The one structurally valid rejection asserts factual falsity from an identity passage. That passage does not itself establish nationality. Exact quotation presence cannot establish relevance or entailment. No AI result is adopted as factual truth. |

### Target compatibility and aliases

The corrected method still mechanically nominates 19/25 queries, with six abstentions:

| Mechanical category | Queries |
| --- | ---: |
| Question-local choice | 5 |
| Boolean | 4 |
| Person / kinship | 2 |
| Full calendar date | 2 |
| Place | 5 |
| Nationality | 1 |
| Target construction failure | 6 |

Both existing source-focus v1 and proposed v2 produce the same 19 targets on this
cohort. Nationality-as-person contamination is excluded by the existing guard, but
person-like names alone do not establish kinship, chronology or identity compatibility.
`America` is a broad geographic label, not verified equivalent precision to a city.
Place typing is not a geographic ontology. Boolean complements can be ambiguous;
choice alternatives need predicate and alias review. None is certified here.

All 25 input questions have no supplied gold aliases. Existing string normalization
excludes known forms but cannot establish complete entity aliases or factual falsity.
New calendar canonicalization only handles the two complete English date formats
already supported, validates the actual calendar date, and excludes equivalents of
gold and supplied aliases. It does not infer numeric locale, partial-date equivalence,
calendar systems, historical identity or unprovided aliases.

## Minimal opt-in changes

1. `src/attacks/development_targets_v5.py`: new selector
   `development-source-focus-guard/v2`, layering complete-date exclusion over untouched
   v4 nominations. Unknown versions and held-out scope fail closed. Descriptor hashes
   bind this implementation and its original source dependencies.
2. `src/attacks/semantic_fluent_development_v2.py`: new profile implementation, with
   prompt `semantic-direct-relation-prompt/v5-development`, validator
   `conservative-text-heuristic/v6.1-development`, and retry policy
   `failure-specific-revision-prompts/v3-development`. It adds exact-subject
   birth-place, complete birth/death date, place-of-death and nationality sentences.
   Only optional articles/paired title quotes are accepted; full qualifiers remain
   mandatory. Existing safe v1 forms are inherited. No kinship, comparative or new
   negative Boolean grammar is introduced. Date-equivalent target assignments are
   also refused at text validation. Explicit scalar/Boolean/full-date answers in
   place/nationality slots are refused before inherited positive rules; this does
   not infer whether arbitrary text is a person, nationality or place.
3. `src/attacks/semantic_profiles.py`: register
   `question-anchored-development/v2` as explicit development-only selection. Existing
   defaults, v1 prompt/validator code, two-attempt ceiling and 150-token cap remain.
4. `scripts/run_week9_protocol_poison_matrix.py` and
   `src/experiments/week9_construction.py`: dispatch the declared target version through
   the existing descriptor, manifest, checkpoint, journal, seal and aggregate checks.
5. `src/experiments/semantic_development_study.py`: permit the new explicit profile
   for the same declared train-only 25-query study; no selection algorithm, IDs,
   intensities, seeds, study descriptor or call ceilings change.
6. `tests/test_semantic_construction_v2.py`: date-equivalence regression, positive and
   adversarial grammar cases, provenance, scope, interruption/replay and end-to-end
   fixture evaluation/aggregation tests. The release audit adds explicit type-mismatch
   regressions, metadata-only preflight, descriptor tampering, journal-fingerprint
   mismatch, per-document intent bindings and actual pending-review CLI export.

The new grammar is a declared development-method extension, not a claim that every
old unverified rejection was a code bug. All original negative screens, competing-gold
checks, known-alias checks, 40-character minimum and fail-closed unknown support remain.
No source text, gold label or factual correction is fed into the generation prompt.

### Retrospective syntax diagnostic, not re-execution

Applying only the proposed validator to saved outputs yields:

| Proposed diagnostic status | Attempts |
| --- | ---: |
| Heuristically supported, still factually unverified | 28 |
| Unverified relation | 49 |
| Does not affirm target | 20 |
| Competing gold / alias | 43 |
| Invalid length | 12 |
| Total | 152 |

The 28 are from six unique questions. They are not 28 independently valid poisons,
new constructed documents, revised historical results or an acceptance-rate estimate
for the changed prompt. No frozen status or artifact is rewritten. The original study
remains 152 attempts and zero accepted documents. Establishing validator false
rejections requires a qualified assessment of the actual subject, relation, aliases,
target compatibility and supporting evidence, with uncertainty retained.

## Verification

Final offline verification after the confirmed shape defect was fixed:
The five new mismatch cases all failed with `DID NOT RAISE` before the fix
(`/private/tmp/semantic-v2-type-reproduction.log`), then passed after the fix.

| Check | Final result |
| --- | --- |
| V2 regression/lifecycle tests | 40 passed, 0 failed, 0 skipped (3.04 seconds) |
| Focused target/semantic/protocol/replay/AI-infrastructure tests | 185 passed, 0 failed, 0 skipped (15.32 seconds) |
| Complete offline suite | 1,212 passed, 0 failed, 0 skipped (138.79 seconds) |
| Python compilation (`src scripts tests`) | PASS |
| Tracked and new-file whitespace checks | PASS |
| Original development study inventory | 499/499 files and exact path set unchanged |
| Original HotpotQA construction/evaluation seals | 17,214 listed files match their hashes |
| Original selector and prompt/validator implementations | v2/v3/v4 selectors and legacy/development-v1 prompt/validator source files unchanged |
| Proposed pilot command syntax | PASS; commands not executed |

Logs: `/private/tmp/semantic-v2-final-new.log`,
`/private/tmp/semantic-v2-final-focused.log`, `/private/tmp/semantic-v2-final-full.log`.
The full suite used offline environment flags and permitted access to existing local
cache locks. No inference/download was initiated; no test failures or skips remain.
The lifecycle fixture covers preflight, freeze/load, target selection, completed
per-document journal replay after a query-checkpoint interruption, construction
validation/sealing, pending-review export, evaluation/resume and aggregation.
It checks descriptor/hash tampering and held-out scope refusal. Review identities,
timestamps and decisions remain blank/pending in exported synthetic fixtures.

Profile registry/runner source bindings intentionally change; old frozen protocols
must be replayed from their original clean source commit, never rehashed to this code.

## Proposed bounded pilot — not executed

This proposal is a **diagnostic rerun influenced by earlier failure analysis**, not
independent confirmation on previously unexamined examples. It uses the same 25
train queries without favorable query resampling. A previously unexamined train
cohort is preferred for subsequent generalization validation; it needs its own
approved cohort descriptor, freeze and budget. This patch deliberately preserves
the existing study's query selection rather than silently changing that protocol.
The deterministic procedure is the first 25 of the pinned train pool sorted by
`SHA256(canonical(["semantic-quality-25/v1", 42, query_id]))`, then query ID.
Dataset: `load_2wikimultihopqa`, published train split, pinned revision
`9823f70484dea525100394220b0ea5184d0eeb7b`. Use both semantic intensities 1/3, seed 42, the same
pinned 300-query train candidate pool and local model snapshot. Freeze the new profile,
method, inputs, output paths, source commit and implementation hashes into a fresh
namespace before any call. No AI evaluator is needed or authorized.

Construction-only maximum: 19 target-bearing queries × (1 + 3) document slots ×
2 attempts = **152 model calls**, at most 150 completion tokens each (22,800 maximum
completion tokens, plus prompt processing). Six target failures per intensity remain
in the 25-query denominator. Expected calls range 76–152 if all calls complete;
interruptions stop without silent regeneration. Actual runtime is unmeasured and
must not be extrapolated from the unrelated three-item AI-review pilot. The study
schema retains its conservative 200-construction/400-total generic ceilings, but
this unchanged frozen cohort/selector has the tighter 152-call construction bound.
Do not proceed if the freeze yields different IDs, more than 19 target-bearing
queries or different assignments; review the discrepancy first.

Intensity 3 still requires exactly three valid documents; partials remain failure.
Report per-query construction coverage, per-slot/per-attempt rejections and manual
validity assessment separately. No conditional denominator removes failed queries.
Export all attempts for blinded review: subject identity, predicate, target assertion,
linguistic form, question constraints, aliases and evidenced factual falsehood. Keep
uncertain or unreviewed cases pending. A heuristic pass is not human approval.

**Preconditions:** review the code and protocol extension, commit the reviewed changes
into a clean checkout, approve the 152-call construction-only budget, then execute the
commands below. Do not bypass the clean-Git guard. The protocol cannot be genuinely
frozen to a final code SHA while these implementation changes remain uncommitted.
The following commands are proposed; none has been run for real construction.

```bash
set -e
cd /private/tmp/rag-semantic-construction-v2
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
SPEC=/private/tmp/oct26-reliable-2026-10-26-v1/twowiki-development/local/replication_inputs.json
SPEC_SHA=8e9467072d97419df69aea0786e28b32c20eaa6fc6342e68ff70b05afe64bba0
PILOT=/private/tmp/oct27-2wiki-semantic-construction-v2-pilot
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
# This must succeed only after the reviewed changes are committed.
test -z "$(git status --porcelain --untracked-files=all)"
test ! -e "$PILOT"
"$PY" scripts/run_week9_protocol_poison_matrix.py preflight \
  --scope development --replication-spec "$SPEC" --replication-spec-sha256 "$SPEC_SHA" \
  --semantic-profile question-anchored-development/v2 \
  --development-study semantic-quality-25/v1 \
  --target-method development-source-focus-guard/v2
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol \
  --scope development --replication-spec "$SPEC" --replication-spec-sha256 "$SPEC_SHA" \
  --semantic-profile question-anchored-development/v2 \
  --development-study semantic-quality-25/v1 \
  --target-method development-source-focus-guard/v2 \
  --model-snapshot "$MODEL" --output "$PILOT/protocol.json"
PROTOCOL_SHA=$(shasum -a 256 "$PILOT/protocol.json" | cut -d ' ' -f 1)
# Check pinned cohort and target count against the proposed 152-call bound before compute.
"$PY" - "$PILOT/protocol.json" "$PROTOCOL_SHA" <<'PY'
import sys
from pathlib import Path
from scripts import run_week9_protocol_poison_matrix as base
old=base.read_pinned(Path('/private/tmp/oct26-2wiki-semantic-development-25-v1/protocol.json'),
    '00d1600661312ad78bbf5a9d1e54becc080909b913e2124c40705ca9aaced6ca')
v,_,_,development=base.load_protocol(Path(sys.argv[1]),sys.argv[2])
assert v['binding']['query_ids']==old['binding']['query_ids']
clean=base.load_clean(v,{})
count=sum(base.protocol.select_target(q,development,42,**base.target_fields(v),scope='development')[0] is not None
    for q in clean['queries'])
assert count==19, count
from src.attacks import development_targets_v4 as previous
for q in clean['queries']:
    current=base.protocol.select_target(q,development,42,**base.target_fields(v),scope='development')[0]
    prior=base.protocol.select_target(q,development,42,target_method=previous.descriptor(),scope='development')[0]
    assert current==prior, q['query_id']
assert v['binding']['scope']=='development' and v['binding']['dataset']['split']=='train'
print('Construction-only maximum calls:', count*4*2)
PY
# Run only after explicit model-compute approval.
"$PY" scripts/run_week9_protocol_poison_matrix.py construct \
  --protocol "$PILOT/protocol.json" --protocol-sha256 "$PROTOCOL_SHA" \
  --construction-dir "$PILOT/execution/construction" --model-snapshot "$MODEL"
SEAL_SHA=$(shasum -a 256 "$PILOT/execution/construction/construction.seal.json" | cut -d ' ' -f 1)
"$PY" scripts/review_semantic_development.py summary \
  --protocol "$PILOT/protocol.json" --protocol-sha256 "$PROTOCOL_SHA" \
  --construction-dir "$PILOT/execution/construction" --construction-seal-sha256 "$SEAL_SHA" \
  --output "$PILOT/construction_quality.json"
"$PY" scripts/review_semantic_development.py export \
  --protocol "$PILOT/protocol.json" --protocol-sha256 "$PROTOCOL_SHA" \
  --construction-dir "$PILOT/execution/construction" --construction-seal-sha256 "$SEAL_SHA" \
  --output "$PILOT/pending_review"
```

A rerun after a clean completed checkpoint resumes under the same pins. An unresolved
intent or error response must stop for incident review; do not create another namespace
to conceal an indeterminate call. The commands do not authorize paired QA. If QA is
later separately approved, its additional upper bound is 19 × 2 intensities ×
2 arms × 2 conditions = 152 calls (304 total), before exact-input cache savings.
No full matrix, held-out profile promotion or AI census is authorized by this proposal.
