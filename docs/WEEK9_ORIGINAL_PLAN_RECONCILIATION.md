# Week 9 reconciliation with the original research plan

**Decision:** continue the original targeted-poisoning/transfer study, with all
300 frozen queries and the frozen composite RCD. Do not adopt the Phase 4E
target-free proposal or an eligible-subset primary study. The all-300 **evaluation**
requirement is binding; an all-300 **independently signed pre-run target approval**
requirement is an additional later constraint. It must not be silently removed.
This report recommends corrections and clarifications; it authorizes no execution.

## Authority and scope

Both named originals were read from the user's Downloads directory; the full
private documents are not copied into Git:

| Binding source | Relevant requirements | Exact file SHA-256 |
| --- | --- | --- |
| `Sadia_Peerzada_RAG_Research_Experiment_Plan.docx` | §§1–7: targeted poisoning, source × target transfer, RCD and metrics; §§9/12: frozen evaluation, logs, statistics and 50–100 representative error inspections; §13: honest negative results | `ee361dfca338c532a8811e0d9847d77bbde42b2684c2173eb188f17c1c5c68eb` |
| `Sadia_Current_GitHub_and_Week9_Readiness_Review_2026-10-13.pdf` | pp. 1–3, §§8–11: RCD is one composite defended target; matched Dense/RCD first, then source-to-target transfer and 2Wiki | `53b63a883dcd7e0bf4c5423b3d560e3930028b34aa428927063dff0478ca9477` |

The duplicate experiment-plan DOCX has identical bytes. Neither original
prescribes per-query independent signatures, an SSH reviewer registry, a separate
published preregistration, a development-gold-only target pool, five candidates,
two review rounds, or a direct-fact-only taxonomy. The plan's representative
error analysis is not a requirement to obtain 300 signed approvals before a smoke.
The October review explicitly closes Week 7–8; it does not ask for RCD retuning.

Code inspection is against main `4f1b98bb2f086cca6fa07da1caec86ae66255d80`.
Phase 4E's unmerged development report was separately inspected at
`88821d22316fb006e548c08a0ec07ec83480f2cd` (177/300 mechanical nominations,
123 blocked, no independent semantic verification). This branch starts from main
so its change is **this report only**, not the unmerged Phase 4E implementation.
No held-out question records or raw result logs were opened for reconciliation.

## What is necessary, and what was added

**Scientific necessities:** a prespecified attack objective; a defensible incorrect
answer for any attack counted as targeted; question-compatible, coherent false
evidence for the semantic family; exclusion of gold-equivalent targets; unchanged
labels/cohort/RCD; immutable per-condition poison reused across compared systems;
source-conditioned construction/selection and unchanged target replay; complete
records, correct denominators, quality/error analysis and honest negative results.
A substring heuristic or a signature alone proves none of factual falsehood,
semantic compatibility or poison quality. Dataset labels and logical constructions
can support an operational validity argument, but ambiguous/co-correct cases must
be identified rather than asserted false.

**Additional safeguards/restrictions:** Phase 4A added nomination taxonomy and
formal review rows; Phase 4B added the later requested per-target independent-approval gate,
including exact 300 coverage; its implementation chose SSH signatures and a pinned
reviewer registry to authenticate decisions;
Phase 4C added the fixed development pool/order, five-candidate/two-round limits
and preregistration bootstrap; Phases 4D/E developed alternative nomination
methods without integrating them into the runtime. These were deliberate later
choices, not requirements found in the two originals. Authentication, hashes and
traceability are useful; their particular signing ceremony, universal pre-review
count and narrow nomination source/rule limits are not scientific laws.

Keep data/poison/config fingerprints and fail-closed integrity checks. Discuss
changing the **review workflow**, not dispensing with target validity. A mechanical
abstention is not proof that a query has no defensible false target. Conversely,
177 mechanical nominations do not establish 177 scientifically validated attacks.

## Focused blocker/fix table

Types: **D** confirmed code/reporting defect; **U** unfinished original experiment
or instrumentation; **R** additional later restriction; **H** supervisor decision.
Code anchors below refer to the inspected main revision.

| Type | Confirmed blocker or gap | Smallest correction preserving the research |
| --- | --- | --- |
| **D** | `src/attacks/asr.py::_extract_answer` splits at `. `; synthetic correct answer `A. B. Example` becomes `A` and scores EM=0. Matched `_generate` uses it and returns no full raw response. | Fix abbreviation-safe extraction; log raw response, extracted answer, prompt/version and extractor version. Add synthetic regressions. Preserve old results; assess rescoring/rerun needs rather than overwrite history or infer lost text. |
| **D** | `run_source_target_asr` raises when source successes are zero, before evaluating the other targets; its message suggests trying stronger attacks/intensities. | Preserve a valid negative result: all source/target records, source ASR=0 and ATR=`null` with denominator 0. Never strengthen a frozen attack after seeing test outcomes. Regression-test this path. |
| **U** | The primary twelve cells contain only attack × intensity × seed and evaluate Dense/RCD. No source-pipeline axis or source-aware attack construction is implemented there. | Retain this legitimate matched-defense experiment. Add the original, separate source-to-target orchestration using existing evaluation/transfer primitives; do not rename the twelve cells a transfer matrix. |
| **U** | For nonzero source success, the transfer API already evaluates every attacked target query, but filters both sides for statistics and exports no full target-side result list. | Persist full aligned source/target rows and full-cohort metrics. Reuse `compute_transfer_statistics` on full aligned inputs: it already computes transfers conditional on source success and leaves ATR undefined at zero. Keep conditional summaries explicitly labelled. |
| **U** | Attack `generate` methods receive question/target/index, not a source retriever or source feedback. A source label alone is not source-specific crafting. | Declare and implement the source-only construction/selection rule and budget for each existing family, then freeze/replay identical poison on all targets. Distinguish source-validated selection from source optimization; do not claim an optimizer that does not exist. |
| **U** | Matched `summarize_pipeline` supplies exact-match accuracy, targeted ASR, PRR and retrieval-conditional ASR, but no F1/faithfulness outcome. | Add existing `f1_score` to the matched raw/summary/validator path; summarize stored ranks with a stated miss convention. Specify the planned faithfulness assessment. These are measurement gaps, not reasons to alter RCD. |
| **R/H** | `_load_run_targets` demands five artifact/policy/preregistration inputs; `load_heldout_targets` requires all 300 signed rows. `run_smoke_test` uses this same gate before selecting two held-out IDs. | Keep the final gate unchanged pending a written clarification. Separately authorize a development-only diagnostic smoke with real quality checks and a distinct non-final manifest; do not add a hidden skip-review flag to the final runner. |
| **R/H** | `validate_assignment` rejects non-`direct_fact` questions, categories outside its old classifier and unsupported date/count shapes, even if a human could substantiate a target. The five-candidate/development-only pool rules further restrict the method. | Approve a versioned validity/adjudication specification allowing justified question-local, constructed or genuinely sourced targets and manual resolution of parser abstentions. Retain exact question/gold bindings, aliases, evidence and rejection reasons. Do not automatically accept v3 proposals. |
| **R/H** | Fixed reviewed targets remove the lexical generator's only seeded randomness; lexical `generate` ignores `rng`. Semantic prompts also do not consume the poison seed, while runtime seed is fixed. | Verify actual variation before claiming seed robustness. Declare source-only seeded construction variation, or obtain clarification for deterministic repeats. Matched poison must be identical **within** a condition; the originals do not require identical targets across all seeds. Do not change frozen defense/config files or count duplicate realizations as independent evidence. |
| **R/H** | Phase 4C demands a full question/gold fingerprint before text access, but the ID-only manifest lacks that fingerprint. | Authorize deterministic materialization/hash computation after the method and existing manifest/revision are frozen, before generation; prohibit tuning/selection from test outcomes. No held-out loading is authorized by this report. |

The original selector (`PoisonAttack.pick_cross_query_target_answer`) is also not
a valid shortcut: its coarse numeric/text buckets and fallback can nominate
incompatible or alias-equivalent answers. Do not simply revert to it or remove
semantic rejection checks. The existing semantic validator explicitly labels its
acceptance heuristic as unverified; previous fixed false-acceptance examples are
not proof that current outputs are valid or that every new output is defective.

## Does the twelve-cell runner implement transfer?

**It implements matched Dense/RCD comparison, not the original full transfer
experiment.** `matrix_cells` = two families × intensities 1/3 × seeds 42/43/44;
`evaluate_cell` builds Dense and RCD against the same snapshot and reports paired
differences. Cell IDs, manifests and aggregation lack an attack-source axis;
there is no call to `run_source_target_asr`. This matches the October review's
§9 step 5, but does not complete step 7.

`src/attacks/asr.py::run_source_target_asr` and
`src/pipelines/transfer.py::compute_transfer_statistics` provide reusable transfer
infrastructure. Source-success conditioning is a legitimate **ATR denominator**,
not permission to evaluate only eligible/source-successful queries. Subject to
the zero-success defect, targets are already evaluated on all attacked queries;
it is their full records/metrics that must be retained. Keep source construction
and selection source-only; never optimize poison on target outcomes.

The original transfer sources are BM25, Dense, Hybrid and Reranker, with RCD as
an additional **single composite defended target** (October review §8). Do not
create four RCD wrappers or change its dense backbone, BM25 signal or weights.
Full transfer adds source/target axes beyond the twelve matched conditions.
2Wiki replication, ablations/model checks and statistical conclusions remain
original unfinished work, not prerequisites for a tiny diagnostic smoke and not
reasons to redesign the threat model.

## All-300 gate and honest failure accounting

**Recommendation: obtain an explicit supervisor-approved clarification; do not
leave the added signing workflow mistaken for an original scientific requirement.
Until then, the current gate remains in force.** Record separately:

1. Whether every final target needs an independently signed individual decision,
   or a documented, versioned construction/validity protocol plus actual human
   quality/error review is sufficient. The originals do not decide the ceremony.
   Do not fabricate identities/signatures or treat an audit sample as proof about
   every unreviewed pair. If all-300 signed decisions are retained, complete them.
2. Whether “all 300 evaluated” also requires 300 valid poison constructions.
   Under that interpretation, unresolved validity/construction failures halt the
   primary experiment. If an attempt-level failure policy is approved instead,
   prespecify its estimand and per-query status accounting; it is not ordinary
   valid-poison ASR and cannot silently replace it. No such policy is adopted here.
3. The semantic prompt/validator version, retry budget, actual seed variation,
   source-crafting rule, quality rubric and permitted fixed-test access. New prompt
   variants require an attack-protocol freeze, not an RCD retune or pooled old/new
   results. Phase 4E's target-free fallback is outside the binding research.

For a complete valid attack cohort, source/target ASR and PRR use **N=300**.
For source successes `S`, ATR is `transferred/S`; if `S=0`, it is undefined,
while unconditional ASR and all 300 outcome rows remain reportable. Likewise,
ASR given generator-visible poison uses the exposure count, with an explicit
zero-denominator status. Neither conditional metric changes the primary cohort.
Keep construction invalidity, generation exhaustion, missing infrastructure
outputs, poison not retrieved, model resistance, targeted success and unrelated
wrong answers distinct. Missing targets/outputs are not evidence of RCD resistance;
negative source success is not an excuse to resample attacks or omit queries.

## Exact route to the first valid real-model smoke

1. **Human decision:** record the gate/smoke-scope clarification above. The
   shortest safe route is a separately authorized **development-only** smoke,
   leaving the final all-300 gate intact. The unmodified current CLI cannot do
   that: its two-query smoke still requires the full signed held-out artifact.
2. **Narrow engineering:** repair answer extraction and preserve full raw QA
   responses/prompts. Add a small development-smoke adapter reusing existing
   injection, retriever and matched-evaluation functions, with a distinct
   development manifest that final-cell aggregation rejects. Validate pinned
   development membership and held-out-ID disjointness. No final-run bypass.
3. **Real quality checks:** predeclare two verified development diagnostic IDs,
   intended incorrect answers and evidence/alias/compatibility checks under the
   agreed smoke policy. Actual people supply any required judgments. Phase 4A's
   preparer recommendations and v3's constructions are not approvals. Freeze
   the two cases before viewing model outputs; never replace a failure quietly.
4. **Freeze plumbing:** commit/tag the adapter and prompt/validator/retry versions;
   require clean tracked inputs. Read, do not edit, frozen configs: Qwen2.5-7B
   MLX model, generation `top_k=3`, diagnostic depth 10, runtime seed 42,
   `rcd_candidate_k=10`, up to three additional rewrites, weights
   `0.45/0.00/0.10/0.45`. Pass frozen parameters explicitly rather than the
   transfer API's default `top_k=5`. Verify replay/checkpoint rejection on stale
   fingerprints using synthetic tests; this is not a real-model run.
5. **Separate execution authorization:** run lexical then semantic-fluent,
   intensity 1/seed 42, on those same development IDs. Within each family reuse
   identical poison documents/targets across Dense and RCD. Use isolated,
   append-only, non-final outputs; log every actual generation attempt, raw
   response, target, document/rank/evidence window and failure. This report does
   not issue that authorization or run either command.
6. **Accept the smoke for instrumentation/quality only:** verify unchanged gold,
   complete paired records, identical fingerprints, generator-visible exposure,
   correct scoring and coherent target-supporting semantic text. A valid attack
   with ASR=0 is an honest result. Invalid prose or exhausted generation is an
   attack-construction failure, not defense success or a licence to weaken checks.
   A small smoke is not a publication subset or an effectiveness estimate.
7. **Then validate transfer on development data:** retain full source/target rows,
   handle zero-source success, exercise declared source crafting/selection and
   diagonal/ATR accounting with unchanged poison. This follows the first matched
   smoke; completing the whole cross-pipeline study is not a prerequisite for it.
8. **Only afterward approach held-out execution:** settle the final target-validity
   policy, freeze code/method, authorize fixed-cohort loading and complete the
   required all-300 artifacts. Confirm publication clean-baseline provenance/code
   compatibility without reopening Week 7–8 tuning. Follow the October sequence:
   matched poisoning, source-to-target transfer, then 2Wiki/statistics. No matrix
   launch, subgroup substitution or experimental-config change is authorized here.

## Checks performed for this report

The abbreviation defect and zero-source early exit were reproduced with isolated
synthetic inputs/stub evaluators, without model calls or real query records.
The stub used non-strict metadata only in memory to demonstrate control flow;
production metadata checks must remain strict. Existing focused tests:

```text
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q \
  tests/test_transfer_framework.py tests/test_asr_evaluation.py \
  tests/test_reviewed_target_integration.py -k 'not signature_primitive'
110 passed, 1 deselected in 0.62s
```

These passing tests do not negate the demonstrated untested edge cases. Signature
creation was deliberately excluded. This change is documentation only; no gate,
attack, model, RCD parameter, frozen dataset/config or historical result was
modified. No approvals, held-out question inspection, real-model execution,
target-free experiment or eligible-subset primary study was performed.
