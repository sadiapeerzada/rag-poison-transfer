# Week 9 semantic generation reliability revision (experimental branch)

This branch starts from frozen commit
`06f91c393e7056a5d7ea39507b60d96a2e370a70` and does not
change the old `week9-10-evaluation-freeze-v1` tag. Do not pool
results produced by the old and revised generator implementations.

## Backend revision

MLX wraps each unformatted task prompt in the tokenizer's Qwen chat
template (user role, assistant generation prefix) before generation.
Token accounting uses tokenizer tokens. The original frozen prompt
content, Qwen model identifier, evaluation token budgets, dataset
revisions, frozen held-out IDs and seed schedule are unchanged, but
the model input format has changed, so a new freeze is required.

## Semantic poisoning and validation

The attack retains the same cross-query false-answer selection and
framing prompts. It uses a versioned, **conservative syntactic screen**
(`conservative-text-heuristic/v1`) that checks length, leakage, target
presence, nonidentity with the gold answer, and whether the text
contains a direct affirmative target relation versus an obvious denial.
This is **not** an NLI/entailment validator. Heuristic passes carry the
status `heuristically_supported_unverified`: they remain subject to
independent blinded human review. Inconclusive texts are *not* accepted.
No performance or transfer-efficacy claims follow from a heuristic pass.

Rejected texts trigger at most one distinct, deterministic, explicitly
versioned prompt revision
(`distinct-explicit-revision-prompts/v1`).
`max_attempts=2` means original prompt plus one revision;
generator transport/runtime failures are recorded and fail immediately.
All attempts are recorded for successful checkpoints. Exhaustion
fails the cell rather than replacing the attack or target.
No sampling parameters or model identifiers are changed.

## Crash recovery

`poison.checkpoints/<query_id>.<poison_index>.json` is written
atomically after **each validated semantic document**. Files record
the canonical poison document ID, original text and SHA256, target,
query/index, validation state, generation attempts, and provenance
covering the commit, source fingerprint, frozen config hashes, held-out
fingerprint, seed, model/backend and policy versions.

On explicit `--resume --recover-incomplete`, checkpoints are loaded
from the existing incomplete cell and immutable attempt archives.
Every record is checked before moving the incomplete cell into an
archive. Any corruption, incompatible provenance, conflicting or
incorrect target, or invalid document refuses recovery. Reused
documents are independently checked against the actual clean query
and its gold answer, and new attempt checkpoints are re-persisted.
Incomplete checkpoints are *not* finished cell manifests. Final
poison snapshots retain their previous immutable replay design.
A normal `--resume` never automatically recovers incomplete cells.

## Review protocol before a new experimental freeze

1. Run the complete Python test suite and inspect the diff.
2. On Apple Silicon, run one real MLX semantic smoke test on a
   reduced held-out subset; ensure model formatting and output gates
   work and checkpoints survive deliberate interruption.
3. Conduct a blinded review of a prespecified random sample of
   generated semantic documents, recording query, intended false
   target, whether the text positively asserts it, ambiguity, and
   reviewer disagreement. Predeclare acceptance threshold and
   adjudication rules, and archive the review alongside output.
4. Decide whether the new prompt revision, semantic filter and retry
   budget represent a protocol amendment. Document differences from
   prior experiments. **Only then create a new code freeze.**
5. Never treat a syntactic screen as a guarantee of entailment.
   Failure counts, retry counts and sampling exclusions must be
   transparently reported, not silently omitted.

Do not execute the full matrix while the revised protocol remains
unvalidated. This branch must not be merged into main until reviewed.


## Proposed semantic prompt v2 amendment (not frozen)

Prompt versions are `semantic-encyclopedic-prompt/v1` (the original,
selectable for reproduction) and `semantic-encyclopedic-prompt/v2`
(the current candidate). The latter frames the task as a synthetic
counterfactual encyclopedia entry, explicitly asks for the exact assigned
cross-query target, and requires an affirmative relation to the question,
even when the target is categorically unrelated. The source question,
false-target selection, seeds, held-out IDs, model, token limits, two-attempt
retry policy, conservative validator, and evaluation metrics are unchanged.

This is a substantive attack-prompt amendment, **not** a mere bug fix.
The selected prompt version is recorded in the semantic attack configuration,
smoke review metadata, per-document checkpoint and its provenance, and
failure diagnostics. Checkpoint recovery rejects a different prompt version.
The old freeze tag is not modified; do not combine v1 and v2 observations.
The v2 generator may still fail to assert nonsensical targets; record failures
without weakening the validator or selecting replacement targets. Full-matrix
execution remains blocked pending real MLX smoke tests, interruption/recovery
validation, independent blinded semantic review, and an explicit new freeze.


## Candidate v3 amendment following real MLX smoke-03 (2026-10-25)

Smoke-03 completed 2/2 queries and 8/8 evaluation records with v2. Its two generated paragraphs were independently inspected in an initial, unblinded diagnostic review; both were rejected as self-discrediting. The first explicitly said the target Flavivirus was unrelated to the battle question and invoked a counterfactual knowledge base. The second acknowledged that Second Battle of Bull Run was not a biological genus. Both had passed the v1 syntactic screen. This review is diagnostic, **not** a blinded independent adjudication or a population quality estimate.

Candidate changes: prompt v3 requests a direct reference-style paragraph without meta-commentary; syntactic screen v2 additionally rejects obvious self-discrediting/meta-counterfactual phrases. The cross-query target assignment, held-out queries, model, token budget, two-attempt retry cap, retrieval and evaluation metrics remain unchanged. The stronger screen is still **not** entailment verification and can both miss contradictions and reject acceptable prose. Do not silently resample targets or omit failed documents. Archive per-attempt counts, exclusions, and any generation failures. Prompt v1/v2/v3 outcomes must not be pooled without explicit stratification and justification.

**Pre-freeze gates:** full CI; real MLX v3 smoke; interruption/checkpoint recovery; prespecified blinded human review with at least two independent reviewers, recorded disagreements and adjudication; explicit acceptance threshold and sampling rule; documented retry/failure denominators. No new freeze, no full matrix, and no merge until these are satisfied.
