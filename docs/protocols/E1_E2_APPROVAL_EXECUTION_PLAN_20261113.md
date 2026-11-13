# E1/E2 approval and execution plan — preparation only

**This document authorizes no execution.** Earlier authorization remains revoked.
The supervisor requires approval before initialization or inference. The frozen
inputs, source-selection rules, historical results and existing guard code are
unchanged. E3/E4/E5 are complete at their stated scopes and are not expanded.

## Exact scope and call reconciliation

The [read-only accounting receipt](../../reports/E1_E2_EXACT_READINESS_BUDGET_20261113.json)
verifies 492 complete, distinct bindings for the existing five-question smoke
prefix: 432 E1 and 60 E2 D2. There is no complete-binding overlap between these
two arrays. The historical export has 392 logical records backed by 212 verified
physical origins, all rechecked against the pinned native completion inventory,
physical response/intent hashes, completed execution flags, actual prompts,
ordered evidence, corpus/config bindings and backend environment. Logical reuse
is not new independent inference.

| Prepared scope | Complete bindings | Reusable physical responses | Missing bindings |
| --- | ---: | ---: | ---: |
| E1, all required source/target controls | 432 | 212 | 220 |
| E2, additional fixed-rewrite D2 | 60 | 0 | 60 |
| Combined, deduplicated by complete frozen binding | 492 | 212 | 280 |

Under the frozen reuse contract and verified export, the prepared scope needs
**at least 280 successful new physical generation calls**, with zero failures
assumed. Against 200 attempts, the deficit is **80**. Every failure, interrupted
or indeterminate attempt also consumes authorization, so 280 attempts supplies
no retry margin. An approved reserve R would require an explicit total 280+R;
this document neither chooses R nor authorizes retries. Prompts or question IDs
alone cannot reduce this budget. Broader equivalence would require a separate
method/provenance review and is not used here.

E1's 220 include 55 missing bindings per pipeline: BM25, Dense, Reranker and
RCD. BM25 is a source-success control for BM25-selected attacks, required by
source success/conditional transfer metrics. The target-comparison grid has
1,080 assigned positions; the logical preparation additionally retains 180
BM25 source-control positions, giving 1,260 logical positions and 588 valid
positions including controls. Dropping those controls to fit a cap is invalid.
The 60 D2 bindings are 4 clean and 56 poisoned, with 112 logical references;
historical Dense/Reranker/RCD records are already included within E1's history,
not additional new calls. No defense condition is discarded.

| Frozen question ordinal | Missing E1 | Missing D2 | Combined | Cumulative prefix |
| --- | ---: | ---: | ---: | ---: |
| 1 | 48 | 13 | 61 | 61 |
| 2 | 56 | 15 | 71 | 132 |
| 3 | 68 | 19 | 87 | 219 |
| 4 | 48 | 13 | 61 | 280 |
| 5 | 0 | 0 | 0 | 280 |

Ordinal 5 has no valid constructions across assigned conditions. It remains in
construction/end-to-end denominators and has no fabricated QA response or
effectiveness evidence. These ordinals preserve the original outcome-blind
question order; no IDs or case-level content are published.

The old cell/question-block round-robin dispatch, under its 160 E1 subcap and
200 combined cap, would fund 156 E1 + 44 D2 attempts. It fully funds ordinals
1 and 2, leaves 20 missing for ordinal 3 and 60 for ordinal 4, and yields zero
construction coverage for ordinal 5. It does not complete the five-question
comparison. Its block seals still match the exact plan/logical inputs; they
are not a complete global-question funding guarantee. This projection is not
permission to execute the revoked plan or to skip ordinals/conditions.

The **intended 25-question development pilot is not covered by 280 calls**.
The remaining 20 questions lack a fully materialized E1/E2 generator-input plan;
their exact new-call requirement is UNKNOWN. Full-300 candidate choices/corpora
are already sealed, but source choices are not final generator bindings. Before
requesting a full-25 budget, prepare/verify the remaining inputs without Qwen,
then rerun exact historical reuse and complete-block accounting. Do not multiply
280 by five, imply the fifth failed smoke question is representative, infer a
main-experiment budget, or call the prepared prefix full experimental completion.

## Conditional dispatch after approval

1. Supervisor selects the scope explicitly: full prepared five-question smoke
   completion as a development checkpoint, or full 25 only after its missing
   bindings are materialized. Keep all frozen questions, methods and failures.
2. Issue a fresh versioned authorization with scope/plan hashes, total attempt
   cap, E1 allocation and D2 allocation, retry policy and wall-time decision.
   The 200-call grant and uncapped grant are superseded. Do not edit or reactivate
   them. Existing pilot freezes embed 200 total/160 E1 and four hours; a reviewed
   operational authorization mechanism must reconcile the new cap without
   overwriting those freezes. No runner change is made in this PR.
   The current runner checks numeric limits/session ledgers but does not read
   the revocation sidecar. Do not invoke it as an authorization check: a reviewed
   fresh-grant check must run before lease acquisition, session creation or model
   loading. This is an execution blocker, not permission to reuse the old grant.
3. Preserve the frozen dispatch order within each experiment: E1 round-robin
   matched question/cell blocks followed by E2 with clean controls first and
   frozen poisoned blocks. Fund the entire 220+60 remaining sequence for the
   prepared prefix; never reschedule by observed answers. A resource stop may
   still leave partial evidence, which must be reported as partial.
4. Verify snapshot/runtime/code/input hashes, complete historical origin
   provenance, all physical-call reservations and session reconciliation.
   Acquire the single-model lease and exclusive process. Start in an approved
   clean environment after resolving the computational feasibility report.
5. Only after explicit authorization, perform one carefully monitored unchanged
   initialization/materialization. Normal idle pressure alone does not permit
   this step. Record phase/RSS/Metal/health/elapsed data. A failure stops the
   attempt; do not repeatedly force another load or proceed into generation.
6. During authorized inference retain pressure level 1, zero new swap-outs
   (swap-ins allowed by existing policy), RSS ≤12 GiB, Metal ≤10 GiB, at least
   5 GiB free disk and thermal stability. Preserve the 0.5-second guard, one
   process and whatever wall budget is explicitly approved. Any guard stop is
   terminal for that session. Review stock MLX-LM automatic wired-limit behavior
   explicitly before proceeding; no OS limit or MLX setting is changed here.
7. Before each physical dispatch, durably reserve an attempt and save the
   complete request intent. Check original prompt/backend-prompt equivalence,
   Qwen snapshot, greedy sampling, seed 42 and 64 output tokens. Save complete
   responses/checksums and validate extraction/scoring. Interrupted/indeterminate
   calls never become successful reuse and never receive automatic retries.
8. Resume only after reconciling every intent/reservation and authorization.
   Reuse only complete verified bindings; keep every original observation ID
   and physical-call identity. Checkpoint directories never reset global caps.

## E1/E2 analysis and output requirements

E1 preserves the same three candidate slots, including failed construction
slots, for M1 first-valid, M2 random-valid and M3 source-selected. M2 retains
the sealed seed rule from the pilot freeze; M3 uses only already verified
source feedback. All full-300 choices were sealed before final-target access.
Never reselect after target results, rebuild candidate pools, or change the
poison union. Preserve both original source pipelines, intensities 1/3 and
seeds 42/43/44. Source controls count toward call and latency accounting.

E2 uses the identical sealed M3 poisoned corpora across Dense, fixed-rewrite
Dense, Reranker and RCD. Matched inputs means the same underlying attack corpus
and question, not forcing identical retrieved evidence across defenses. Keep
the exact recorded ordered evidence separately for each arm. D2 uses the fixed
non-generative template and original final question; D3 retains candidate depth
20, stable ties; D4 retains frozen RCD weights/depth/rewrite settings. No retuning.

Required aggregate outputs are per-condition assigned/valid/failed/pending
counts, construction coverage, valid-conditional and end-to-end target match,
source success/conditional transfer, clean/poison EM/F1 and paired changes,
clean-correct-to-wrong, and generator-depth poison exposure. A target-string
match is not independently established misinformation. Record pipeline build,
retrieval/rewrite/reranking, generator and end-to-end latency separately; retain
wrapper/inner retrieval calls, encoder calls/cache hits, prompt/completion tokens,
physical attempts and reused calls. Historical warm-cache latency is not a
matched cold-run speedup; no synthetic timing replaces it.

Compute paired uncertainty only on complete matched assignments. Cluster by
question, retaining seeds/source conditions inside each cluster. Existing
question-cluster bootstrap is descriptive at four valid/one failed smoke
questions; it cannot supply confirmatory generalization. Report undefined
denominators explicitly. Apply the same pairing to robustness and utility
contrasts, not only separate per-arm intervals. Do not publish complete rates
when any required valid assigned observation is pending. Existing aggregation
entrypoints already suppress incomplete target-match comparisons; verify
coverage for EM/F1/cost contrasts before making those final claims.

Final outputs after future execution must include private checkpoint journals,
raw-result SHA-256 manifests, exact new/reused/failed/indeterminate call counts,
source-only selection provenance, completeness tables, paired robustness/utility
summaries, cost tables with cache/timing caveats, and question-cluster intervals.
Do not fabricate these answer-level outputs during preparation.

Pairing, candidate-budget parity and frozen treatment definitions remain intact;
the comparisons are scientifically interpretable within their development scope
only after completeness checks. E4's ambiguous targets/questions and lack of
independent adjudication remain limitations; do not silently repair labels or
equate target match with verified falsehood. Zero-construction cells provide
coverage evidence, not defense-effectiveness estimates.

## Supervisor approval checklist

- [ ] Decide intended scope: prepared five-question development prefix versus
  full 25 after full input materialization; neither is the main experiment.
- [ ] For the prepared prefix, approve at least 280 total new attempts and
  replace the 160 E1 subcap with capacity for all 220 E1 calls, plus 60 D2.
  Decide explicit failure/retry reserve; 280 successful calls assumes no loss.
- [ ] Decide wall-clock authorization; the prior four-hour cap is not a measured
  completion-time guarantee, and its initialization charges remain preserved.
- [ ] Approve a safe environment and exactly one monitored initialization;
  safe operation on the current Mac is unproved. Review automatic runtime wiring.
- [ ] Approve any operational implementation separately; this PR only adds an
  offline auditor/tests/reports. No lazy-loader or limit change is implemented.
- [ ] Require reverified bindings and all completed approval items before
  dispatch; merging this preparation PR does not grant model-execution approval.

**Stop at this review package. No inference starts automatically.** E1/E2 remain
experimentally incomplete and computationally blocked, with a concrete exact
prepared-scope budget available for approval. E5 deferral and completed E3/E4
results are preserved.
