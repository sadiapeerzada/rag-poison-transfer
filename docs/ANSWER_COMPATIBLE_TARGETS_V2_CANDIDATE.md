# Answer-compatible targets — candidate protocol (NOT frozen)

This branch introduces a **review-gated assignment loader only**. It does not
change `PoisonAttack.pick_cross_query_target_answer`, injection behavior,
held-out IDs, RCD weights, seed policy, existing poison manifests, or results.

## Motivation
The legacy three-way classifier (yes/no, numeric, text) permits category
mismatches such as a virus as the false target for a historical battle.
The 300-query × 3-seed preliminary audit showed 900/900 *coarse-type*
matches, which does **not** demonstrate semantic compatibility.

## Candidate design
- On development data, construct proposed wrong targets of the same expected
  answer category, e.g. battle vs battle, biological genus vs genus.
- Require independent human review, a category label, evidence, and explicit
  approval for each query-target pair.
- Record SHA256 of exact UTF-8 question and gold answer to prevent silently
  applying reviews to changed dataset records.
- `load_reviewed_assignments` and `select_reviewed_target` reject missing,
  duplicate, unapproved, stale, or gold-equal assignments.
- `assignment_fingerprint` produces a deterministic content hash.
- Do not fabricate an approved target for a query when the pool is insufficient.

## Before integration
1. Agree on a review rubric and document provenance; use **development only**
   for designing the rubric, candidate generation, and prompt tuning.
2. Generate independently reviewed candidate assignments; quantify coverage,
   agreement, ambiguity and failure categories.
3. Implement explicit opt-in wiring with a new protocol identifier, a frozen
   manifest and exact provenance. Prove paired attack families use identical
   query targets and Dense/RCD share identical poison documents.
4. Add integration and checkpoint/resume tests; review the effects on RNG
   consumption and reproducibility.
5. Run a development semantic-quality pilot, then a real-model smoke test.
6. Freeze protocol before confirmatory held-out runs.

**Do not claim this branch is a completed fix or run the full matrix.**
The October 13 supervisor report predates smoke-04/05; Week 7–8 RCD remains
closed. Preserve legacy artifacts for reproducibility.
