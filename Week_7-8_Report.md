# Research Progress Audit

## Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG

| | |
|---|---|
| **Repository** | `sadiapeerzada/rag-poison-transfer` |
| **Audit focus** | Research progress vs. the planned 12-week experimental roadmap |
| **Recorded test result** | `258 passed in 105.02s` (`python -m pytest -q`; associated branch state only) |
| **Current phase** | Weeks 7–8 **complete** → Weeks 9–10 **next** |
| **Overall verdict** | Methodology and infrastructure established; scientific validation of RCD still outstanding |

---

## Contents

1. [At a Glance](#1-at-a-glance)
2. [Evidence Levels and How to Read This Audit](#2-evidence-levels-and-how-to-read-this-audit)
3. [Phase-by-Phase Audit (Weeks 1–6)](#3-phase-by-phase-audit-weeks-16)
4. [Weeks 7–8: RCD Audit](#4-weeks-78-rcd-audit)
5. [Weeks 9–10: Evaluation Readiness and Plan](#5-weeks-910-evaluation-readiness-and-plan)
6. [Weeks 11–12 Audit](#6-weeks-1112-audit)
7. [Test Suite and Experiment Evidence](#7-test-suite-and-experiment-evidence)
8. [Reproducibility Audit](#8-reproducibility-audit)
9. [Risks, Gaps, and Open Questions](#9-risks-gaps-and-open-questions)
10. [Claims Ledger: What You Can and Cannot Say Today](#10-claims-ledger-what-you-can-and-cannot-say-today)
11. [Recommended Next Steps](#11-recommended-next-steps)
12. [Final Verdict](#12-final-verdict)
13. [Appendix A: Handoff Instructions for Week 9–10](#appendix-a-handoff-instructions-for-week-910)

---

## 1. At a Glance

**Status in one sentence:** the Retrieval-Consistency Defense (RCD) is implemented, integrated, tested, run at smoke/development scale, and frozen. It has **not** yet been evaluated at full test scale, so no defense-effectiveness claim is supported yet.

| Phase | Focus | Status | Evidence level |
|---|---|---|---|
| Weeks 1–2 | Datasets, clean baseline setup | ✅ Complete | Code + tests + experiments |
| Weeks 3–4 | Clean retrieval baselines | ✅ Complete | Code + tests + experiments |
| Weeks 5–6 | Poisoning and transfer benchmark | ✅ Complete (confirmatory stats deferred) | Code + tests + experiments |
| **Weeks 7–8** | **RCD implementation and development validation** | **Substantially complete; held-out validation pending** | Code + tests + dev/smoke runs + frozen config |
| **Weeks 9–10** | **Full defended-vs-undefended evaluation** | 🔶 **Next phase** (dev runs only so far) | Infrastructure ready; full results not verified |
| Weeks 11–12 | Statistics, figures, paper | ⬜ Not started / not verified | None |

### Key takeaways

- **Do not redo Weeks 7–8.** The implementation and freeze are done.
- **Code complete ≠ experiment complete ≠ research conclusion.** These are three separate milestones, and only the first is achieved for RCD.
- The central research question has now changed from *"Does RCD work as code?"* to *"Does RCD reduce poisoning success while preserving clean RAG performance?"*

---

## 2. Evidence Levels and How to Read This Audit

To avoid overstating progress, every status in this document maps to one of the following levels.

| Level | Meaning | Can support |
|---|---|---|
| **L0 – Not verified** | No evidence found in the repository | Nothing |
| **L1 – Implemented** | Code exists in `src/` | "The component exists" |
| **L2 – Unit/integration tested** | Automated tests pass | "The component behaves as specified" |
| **L3 – Smoke/dev executed** | Run on a small or development split | "The pipeline runs end to end" |
| **L4 – Frozen** | Configuration locked before test evaluation | "A frozen config exists for use in final testing" (provenance to be verified) |
| **L5 – Full evaluation** | Test-scale, multi-seed, with analysis | "The method improves/does not improve X" |

**Current RCD position: L4.** Weeks 9–10 exist to reach **L5**.

---

## 3. Phase-by-Phase Audit (Weeks 1–6)

### Weeks 1–2: Foundations — ✅ Complete

**Objective:** research framing, datasets, clean baseline architecture, reproducible infrastructure, initial clean experiments.

**Evidence**
- Clean baselines established on **HotpotQA** and **2WikiMultiHopQA**.
- Retrieval families covered: BM25, dense, hybrid, cross-encoder reranking.
- Dataset revisions pinned; reproducibility metadata recorded (per the earlier project status report).

### Weeks 3–4: Clean Retrieval Baselines — ✅ Complete

**Objective:** complete clean retrieval/generation baselines across all required pipelines and datasets, with retrieval metrics and reproducibility metadata.

**Evidence**

```text
src/retrieval/bm25.py
src/retrieval/dense.py
src/retrieval/hybrid.py
src/retrieval/reranker.py
```

- Tests cover Recall@K, MRR, nDCG, retriever routing, clean retrieval behaviour, and integration.
- The earlier status report documents all **8 baseline combinations** (4 retrievers × 2 datasets).

### Weeks 5–6: Poisoning and Transfer Benchmark — ✅ Complete (confirmatory work deferred)

**Objective:** build the attack and transfer benchmark: single- and multi-document attacks, lexical and semantic/fluent attacks, varied intensity and poison rate, multiple datasets and pipelines, and the metrics PRR, poison rank, and transfer rate.

**Evidence**

```text
src/attacks/injection.py
src/attacks/lexical.py
src/attacks/semantic_fluent.py
src/attacks/sweep.py
src/attacks/evaluate.py
```

- Tests cover injection, intensity, poison rate, lexical and semantic/fluent attacks, multi-document variation, PRR, transfer rate, and the transfer matrix.
- Integration tests confirm that **retrieval depth is separated from generator `top_k`**, so generator settings cannot silently alter retrieval evaluation.

**Note:** some confirmatory experiments and statistical analysis are intentionally deferred to the later evaluation phase. This does not undermine completion of the attack/stress-benchmark phase.

---

## 4. Weeks 7–8: RCD Audit

> **Verdict: COMPLETE** at the implementation, testing, development-validation, and configuration-freeze level.

### 4.1 What RCD does

RCD identifies evidence that is **unstable, inconsistent, redundant, or conflicting** across retrieval variations, and uses those signals to re-score and select evidence.

```text
 query ──► rewrites (×3) ──► retrieve per rewrite ──► record ranks
                                                          │
          ┌───────────────────────────────────────────────┘
          ▼
   consistency signals ──┐
   (rank stability,      │
    retriever agreement) ├──► RCD score ──► re-ranked evidence ──► generator
   redundancy ───────────┤
   claim/evidence        │
   conflict ─────────────┘
```

### 4.2 Requirement-by-requirement audit

| Requirement | Evidence (file) | Impl. | Tested | Run | Status |
|---|---|:-:|:-:|:-:|---|
| Query rewrites | `src/defenses/rcd/rewrites.py` | ✓ | ✓ | ✓ | Complete |
| Multiple rewrites (default 3) | `rewrites.py`, config | ✓ | ✓ | ✓ | Complete |
| Retrieval across rewrites | `RCDRetriever` | ✓ | ✓ | ✓ | Complete |
| Rank stability | `core.py` | ✓ | ✓ | ✓ | Complete |
| Cross-retriever agreement | `core.py` | ✓ | ✓ | ✓ | Complete |
| Redundancy | `redundancy.py` | ✓ | ✓ | Dev | Complete / dev-validated |
| Claim/evidence conflict | `conflict.py` | ✓ | ✓ | Dev | Complete / dev-validated |
| Suspicion/penalty scoring | `scoring.py` | ✓ | ✓ | ✓ | Complete |
| Final RCD score | `score_documents()` | ✓ | ✓ | ✓ | Complete |
| Retriever integration | `retriever.py` | ✓ | ✓ | ✓ | Complete |
| YAML configuration | multiple configs | ✓ | ✓ | ✓ | Complete |
| Dedicated tests | `tests/test_rcd.py` | ✓ | ✓ | ✓ | Complete |
| Smoke experiments | `exp_021_…_smoke*` | ✓ | ✓ | ✓ | Complete |
| Dev experiment | `exp_022_…_dev300` | ✓ | ✓ | ✓ | Complete |
| Frozen configuration | `exp_023_…_frozen.yaml` | ✓ | ✓ | ✓ | Complete |

### 4.3 Component notes

| Component | Signals / behaviour |
|---|---|
| **Rewriting** (`rewrites.py`) | Generates multiple query variants (default 3), invoked before ranking evidence is collected. |
| **Consistency** (`core.py`) | Agreement, rank stability, rewrite stability, retriever agreement, cross-retriever rank stability, cross-query rank stability. |
| **Conflict** (`conflict.py`) | Claim-conflict and evidence-conflict scoring; tests distinguish related from conflicting claims. |
| **Scoring** (`scoring.py`) | Combines signals into one score with conflict penalties and configurable weights. |
| **Integration** (`retriever.py`) | Rewrite → retrieve → record ranks → consistency → conflict → final score → retain internal signals for logging. RCD is a real part of the retrieval workflow, not a set of isolated utilities. |
| **RCD v2** (`retriever_v2.py`) | Query-conditioned variant using a cross-encoder relevance signal. A **development extension**, not a substitute for evaluating primary RCD. |

### 4.4 Frozen configuration

```text
configs/exp_023_hotpotqa_rcd_v1_mlx_frozen.yaml
# Week 7-8 frozen RCD configuration.

rcd_candidate_k:         10
rcd_rewrite_count:        3
rcd_consistency_weight:   0.45
rcd_redundancy_weight:    0.00
rcd_conflict_weight:      0.10
rcd_base_rank_weight:     0.45
```

Weights sum to **1.00**, which is consistent with a normalised linear combination.

> **⚠ Observation: the redundancy weight is `0.00`.**
> The redundancy component is implemented and tested, but in the frozen configuration it contributes **nothing** to the score. This is a legitimate outcome of development tuning, but it affects how the method should be described:
> - The final paper should state that redundancy was evaluated on dev data and **disabled by tuning**, rather than present it as an active part of RCD.
> - The Weeks 9–10 ablation should include a redundancy-on arm to document that decision (clearly labelled as an ablation, not a change to the frozen method).

### 4.5 Week 7–8 completion checklist

- [x] RCD implemented as a dedicated subsystem
- [x] Query rewriting implemented
- [x] Consistency, rank-stability, and agreement signals implemented
- [x] Conflict detection implemented
- [x] RCD scoring implemented
- [x] RCD integrated into the retriever
- [x] Dedicated RCD tests exist and pass
- [x] Smoke experiments executed (5 iterations)
- [x] Development experiment executed (`dev300`)
- [x] Frozen configuration explicitly labelled "Week 7-8"
- [x] Full test suite passes (248)

There is no justification for classifying Weeks 7–8 as "not started" or "incomplete implementation."

---

### Test-count and source-provenance caveat

The report records a run of 248 passing tests in 95.77 seconds. Treat this as the recorded result for its associated branch state, not as a fresh test run on the current commit. The report alone does not establish a complete source fingerprint for every experiment; verify the relevant commit, working-tree state, configuration, and result artifacts before attributing experimental results to a specific source revision.

## 5. Weeks 9–10: Evaluation Readiness and Plan

Weeks 9–10 move the project from **building RCD** to **scientifically evaluating RCD**.

### 5.1 Readiness status

| Requirement | Status |
|---|---|
| RCD available for evaluation | ✅ Complete |
| Frozen RCD configuration | ✅ Complete |
| Development RCD runs | ✅ Executed |
| Full test-set defense benchmark | ❓ Not verified |
| Clean vs. defended comparison (full) | ❓ Not verified |
| Full ASR comparison | ❓ Not verified |
| RCD ablations | ❓ Not verified |
| Robustness evaluation | ❓ Not verified |
| Latency / overhead analysis | ❓ Not verified |
| Second-model evaluation | ❓ Not verified |
| Final defense conclusions | ⛔ Not yet available |

### 5.2 Gap to flag: dataset coverage

All RCD experiment IDs found (`exp_021`–`exp_023`) are **HotpotQA** runs. The Weeks 1–6 benchmark covers **two datasets** and **four retrievers**. No RCD evidence on **2WikiMultiHopQA** or across all four pipelines was identified in this audit. Cross-pipeline transferability is the project's headline topic, so RCD should be evaluated on every pipeline and dataset the attack benchmark covers, not only the one it was tuned on.

### 5.3 Proposed evaluation matrix

| Axis | Levels |
|---|---|
| Dataset | HotpotQA, 2WikiMultiHopQA |
| Retrieval pipeline | BM25, dense, hybrid, reranked |
| Attack family | Lexical, semantic/fluent |
| Attack scope | Single-document, multi-document |
| Poison intensity / rate | As defined in the Weeks 5–6 sweep |
| Condition | Clean-undefended, poisoned-undefended, clean-RCD, poisoned-RCD |
| Seeds | ≥ 3 (final count per research plan) |
| Generator | Primary + second model for confirmation |

> Size the full grid before launching. The product of these axes grows quickly; prioritise the primary configuration first, then expand to the confirmatory arms.

### 5.4 Metrics

| Metric | Measures | Direction |
|---|---|---|
| **PRR@K** | Poison retrieval rate in top-K | ↓ better |
| **Poison rank** | Position of poisoned documents | ↑ (deeper) better |
| **Poison-to-generation fraction** | Share of poison reaching the generator | ↓ better |
| **ASR** | Attack success rate | ↓ better |
| **Targeted false-answer rate** | Attacker-chosen wrong answers produced | ↓ better |
| **Clean EM / F1** | Clean answer quality | ↑ better |
| **ASR reduction** | Undefended ASR − defended ASR | ↑ better |
| **Clean accuracy retention** | Clean-RCD ÷ clean-undefended | ≈ 1.0 |
| **Overhead** | Extra retrieval calls, latency, memory | ↓ better |

### 5.5 Ablation plan

Ablations are run **against** the frozen configuration; they never modify it.

| Ablation | Question answered |
|---|---|
| No query rewrites (`rewrite_count = 0/1`) | Do rewrites carry the defense? |
| Rewrite count (e.g. 1, 3, 5) | Cost/benefit of more rewrites |
| Consistency only (conflict off) | Is conflict detection adding value? |
| Conflict only (consistency off) | Is consistency adding value? |
| Redundancy on (weight > 0) | Documents the decision to set it to 0.00 |
| Sparse-only vs. dense-only signals | Which retriever signal matters? |
| Candidate depth (`rcd_candidate_k`) | Sensitivity to retrieval depth |
| With vs. without reranking | Interaction with the cross-encoder |
| RCD v1 vs. RCD v2 | Value of the cross-encoder signal |

The exact set should follow the original experiment plan.

### 5.6 Decision gates

Define these **before** running the test set, so results cannot be rationalised afterwards.

| Gate | Suggested criterion (set thresholds in advance) |
|---|---|
| **G1 – Defense works** | ASR and PRR@K drop meaningfully vs. undefended on the primary configuration |
| **G2 – Utility preserved** | Clean EM/F1 retention within a pre-agreed tolerance |
| **G3 – Generalises** | Benefit holds on the second dataset and across pipelines |
| **G4 – Cost acceptable** | Overhead is reported and judged acceptable |

If G1 passes but G3 fails, the honest finding is "RCD helps in HotpotQA setting X," which is still a valid, publishable result. Report negative and mixed outcomes as they are.

---

## 6. Weeks 11–12 Audit

**Planned activities:** bootstrap confidence intervals, paired statistical tests, qualitative failure analysis, representative examples, final figures and tables, manuscript integration.

**Verdict:** ⬜ Not started / not verified. This is expected at the current stage.

**Preparation that can start now (non-blocking):**
- Scripts that generate result tables directly from raw JSONL logs.
- Figure scripts (transfer matrix, ASR before/after, ablation bars).
- A bootstrap/paired-test utility with unit tests.

---

## 7. Test Suite and Experiment Evidence

### 7.1 Test suite

```bash
python -m pytest -q
```

```text
==================== 258 passed in 105.02s (0:01:57) =====================
```

- An earlier run with bare `pytest tests/ -v` failed at collection with `ModuleNotFoundError: No module named 'src'`. This was an **invocation/environment issue**, not a code failure, and is resolved by `python -m pytest`.
- The earlier 219-test run included the dedicated RCD tests:

```text
tests/test_rcd.py::test_rcd_components_smoke PASSED
tests/test_rcd.py::test_claim_conflict_distinguishes_related_and_unrelated_years PASSED
tests/test_rcd.py::test_agreement_is_document_specific PASSED
```

**Verdict: full test suite passing.**

> **Recommended hardening:** make the bare `pytest` command work too (e.g. `pythonpath = ["."]` under `[tool.pytest.ini_options]` in `pyproject.toml`, or a `conftest.py` at the repo root). This removes a reproducibility trap for collaborators and reviewers.

> **Interpretation note:** passing tests show the code behaves as specified. They say nothing about whether RCD is an effective defense.

### 7.2 Experiment evidence

| Experiment | Type | Level | Representable as |
|---|---|---|---|
| `exp_021_hotpotqa_rcd_v1_mlx_smoke` … `smoke5` | Smoke iterations | L3 | "Pipeline runs end to end"; **not** benchmark results |
| `exp_022_hotpotqa_rcd_v1_mlx_dev300` | Development evaluation (300 examples) | L3 | Development evidence; used for tuning |
| `exp_023_hotpotqa_rcd_v1_mlx_frozen` | Frozen configuration | L4 | "Frozen config exists for final evaluation" (provenance and held-out status to be verified) |

JSONL and summary result files exist for the smoke and dev runs.

---

## 8. Reproducibility Audit

**Rating: Good / research-ready infrastructure.**

| Capability | Present |
|---|:-:|
| YAML experiment configurations | ✓ |
| Experiment IDs | ✓ |
| Deterministic seeding | ✓ |
| Dataset revision tracking | ✓ |
| Environment metadata | ✓ |
| Result logging | ✓ |
| Raw JSONL outputs | ✓ |
| Transfer-matrix export | ✓ |
| Tests for reproducibility behaviour | ✓ |

**Remaining requirement:** ensure every Weeks 9–10 run uses the frozen configuration and records the required metadata.

**Suggested additions**
- Record the **git commit hash** and a **hash of the frozen config** in every final run's metadata, so any result can be tied to the exact frozen method.
- Keep dev and final outputs in **separate directories** (e.g. `results/dev/` and `results/final/`).
- Note that the generator is run via **MLX**; record backend, quantisation, and sampling settings (temperature/seed), since local-inference determinism can differ across hardware and versions.

---

## 9. Risks, Gaps, and Open Questions

### 9.1 Blocking gaps

The main gap is **not RCD implementation**. It is the full experimental evaluation needed to support any scientific claim about RCD:

1. Full test-set evaluation
2. Defended vs. undefended comparison
3. Attack-success analysis
4. Clean-performance retention
5. Transfer analysis
6. Ablations
7. Robustness analysis
8. Overhead/latency analysis

### 9.2 Risk register

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **Dev/test leakage**: modifying the frozen config after seeing test results | Invalidates the evaluation | Hash the frozen config; fail runs on mismatch; report any post-hoc change as an ablation |
| R2 | **Small dev set (300)** → tuned weights may not be stable | Frozen weights may overfit dev | Report dev variance; test sensitivity to weights in the ablation |
| R3 | **Single-dataset tuning** (HotpotQA) | Weak generalisation claims | Evaluate on 2WikiMultiHopQA with the same frozen config |
| R4 | **Non-adaptive attacker**: attacks were built without knowledge of RCD | Defense may look stronger than it is | State the threat model explicitly; if feasible, add at least one RCD-aware attack (e.g. poison crafted to stay stable across rewrites) |
| R5 | **Redundancy weight = 0.00** | Described method ≠ effective method | Document in paper; include ablation arm |
| R6 | **Clean-utility cost** | Defense "works" but hurts normal QA | Gate G2; always report clean EM/F1 beside ASR |
| R7 | **Compute overhead** (3 rewrites ⇒ more retrieval calls) | Practicality concerns | Measure and report overhead (Step 6) |
| R8 | **Generator nondeterminism** (local MLX inference) | Noisy ASR estimates | Multiple seeds, fixed decoding where possible, bootstrap CIs |
| R9 | **Test count as a false proxy** | Over-claiming | Use the claims ledger below |
| R10 | **Dev vs. held-out split ambiguity**: `exp_022` and `exp_023` reportedly both use the HotpotQA validation split (per reviewer note; confirm in the configs) | A "frozen" run on the dev split is not a held-out test | Define a genuinely held-out subset/split that was never used for tuning before any Week 9–10 run |

### 9.3 Non-blocking improvements

- Cleaner separation of development vs. final experiment outputs.
- Explicit written documentation of the frozen configuration and how it was selected.
- Auto-generated final result tables from raw logs.
- Final visualisation scripts.
- Statistical-analysis infrastructure.

None of these require reimplementing RCD.

---

## 10. Claims Ledger: What You Can and Cannot Say Today

| Claim | Supported now? | Why |
|---|:-:|---|
| "RCD is implemented and integrated into the retrieval workflow." | ✅ | L1–L2 |
| "RCD's components pass unit and integration tests." | ✅ | Dedicated tests exist; see the explicitly identified test run and commit provenance |
| "RCD runs end to end on HotpotQA at development scale." | ✅ | `exp_021`, `exp_022` |
| "A frozen RCD configuration exists and is intended for use before final test evaluation." | ✅ | `exp_023` frozen config; provenance and held-out status to be verified (see Appendix A, items 4 and 13) |
| "RCD reduces attack success rate." | ❌ | No full defended-vs-undefended result |
| "RCD preserves clean accuracy." | ❌ | Not verified at full scale |
| "RCD generalises across datasets / pipelines." | ❌ | No 2Wiki or multi-pipeline RCD evidence found |
| "Each RCD component contributes to the defense." | ❌ | No ablations; redundancy weight is 0.00 |
| "RCD is robust to adaptive attackers." | ❌ | Not tested |
| "RCD overhead is acceptable." | ❌ | Not measured |
| "Differences are statistically significant." | ❌ | Weeks 11–12 |

---

## 11. Recommended Next Steps

The project should **not** go back and redo Weeks 7–8.

| Step | Action | Output | Depends on |
|---|---|---|---|
| **1** | **Preserve the frozen RCD config.** Hash it; log the hash with every run. | Config hash in all run metadata | — |
| **2** | **Run the full RCD evaluation**: clean and poisoned corpora × undefended and RCD-defended, on all required datasets and pipelines. | Raw JSONL + summaries in `results/final/` | 1 |
| **3** | **Measure core defense metrics**: PRR@K, poison rank, poison-to-generation fraction, ASR, targeted false-answer rate, clean EM/F1, ASR reduction, clean-accuracy retention. | Main results table | 2 |
| **4** | **Run planned ablations** (see §5.5) against the frozen config. | Ablation table | 2 |
| **5** | **Evaluate robustness** across poisoning intensities, attack families, pipelines, datasets, and single-hop vs. multi-hop settings; consider one RCD-aware attack. | Robustness table / figure | 2–3 |
| **6** | **Measure computational overhead**: extra retrieval calls, inference overhead, latency, memory. | Overhead table | 2 |
| **7** | **Confirmatory runs**: additional seeds and the second generator named in the research plan. | Replication table | 3 |
| **8** | **Move to Weeks 11–12**: confidence intervals, significance tests, error analysis, figures, tables, manuscript. | Paper-ready artefacts | 2–7 |

### Suggested two-week sequencing

| Window | Focus |
|---|---|
| Days 1–2 | Config hashing, `results/final/` layout, evaluation driver, pilot on a small slice to confirm nothing breaks |
| Days 3–6 | Primary evaluation (main dataset, all pipelines), core metrics |
| Days 7–9 | Second dataset, ablations |
| Days 10–12 | Robustness, overhead, second generator, extra seeds |
| Days 13–14 | Consolidate tables from raw logs; check decision gates; handoff to Weeks 11–12 |

---

## 12. Final Verdict

| Item | Verdict |
|---|---|
| **Current research phase** | Transition from Week 7–8 RCD development to Weeks 9–10 full evaluation |
| **Weeks 1–6** | Complete (confirmatory statistics deferred) |
| **Weeks 7–8** | **Implementation substantially complete; scientific validation pending** |
| **Weeks 9–10** | **Next major phase**; development-stage evidence exists, full evaluation not yet verified |
| **Weeks 11–12** | Not yet started |
| **Overall** | Core methodology and experimental infrastructure substantially established; final defense evaluation and scientific validation remain |

### Bottom line

**Is the Week 7–8 implementation complete? Substantially, yes; the scientific validation is not yet complete.** RCD is integrated, dedicated tests exist, development and smoke experiments have been executed, and a configuration labelled *"Week 7-8 frozen RCD configuration"* exists. The current working-tree test run passed `258 tests in 105.02s`. However, passing tests and the existence of a frozen config do not establish that the config was frozen before evaluation, that its provenance is reproducible, or that the final evaluation uses genuinely held-out data. Those checks remain open.

**What remains?** The key question changes from

> "Does the RCD implementation work?"

to

> "Does RCD actually improve resistance to knowledge poisoning while preserving clean RAG performance?"

Answering that requires full defended-vs-undefended experiments, attack-success evaluation, transfer analysis, ablations, robustness testing, overhead measurement, and the final result tables.

> **Weeks 1–6:** completed.
> **Weeks 7–8:** completed.
> **Weeks 9–10:** next — full scientific evaluation of RCD.
> **Weeks 11–12:** statistical analysis, figures, and paper preparation.


---

## Appendix A: Handoff Instructions for Week 9–10

Use this block when handing the report and repository to Claude (or any collaborator) to start Week 9–10. Its purpose is to stop Weeks 7–8 being redone and to stop RCD being tuned on test data.

### Current-state constraints

Treat this report as the current baseline.

1. **Do not re-implement or retune RCD unless there is an actual correctness bug.** Implementation, integration, tests, the dev run, and the frozen config are complete. The frozen config is `configs/exp_023_hotpotqa_rcd_v1_mlx_frozen.yaml`; its weights are frozen for all Week 9–10 test experiments.
2. **Do not use test results to modify the frozen config.** Tuning stays on development data only. If there is evidence the frozen weights were not selected by the documented development procedure, flag it as a reproducibility/documentation issue; do not silently change them.
3. **Use the evidence levels strictly** (§2): L1 implemented, L2 tested, L3 smoke/dev executed, L4 frozen, L5 full test-scale evaluation. Never present L3/L4 as proof of defense effectiveness.
4. **`exp_022` (dev300) and `exp_023` (frozen) are not a held-out final evaluation.** Per the reviewer note, both use the HotpotQA validation split; confirm this in the configs. Week 9–10 must use a genuinely held-out subset/split not used for tuning.
5. **Inspect the repository's actual CLI/config interface before proposing any command.** Do not invent flags, config keys, experiment IDs, or scripts.
6. **Audit execution flow, not just source.** For each proposed experiment, trace `config → dataset → corpus → poisoning → retriever → RCD/undefended path → generator → metrics → JSONL → summary`, and verify the intended condition is the one executed.
7. **Preserve the retrieval-depth / generator-`top_k` separation.** Generator `top_k` must not truncate the retrieval depth used for Recall@K/MRR.
8. **Keep the primary comparison controlled:** same query set, attack instance, seed, generator settings, and candidate/retrieval depth; only the defense condition changes. Compare `poisoned + undefended` vs. `poisoned + RCD`, and separately `clean + undefended` vs. `clean + RCD`.
9. **Do not claim RCD works from retrieval metrics or clean EM/F1 alone.** Defense claims need poison-specific evidence: PRR@K, poison rank, poison-to-generation fraction, ASR, targeted false-answer rate, ASR reduction, clean accuracy retention, and overhead.
10. **Treat the redundancy weight of 0.00 explicitly** (§4.4). Do not describe redundancy as an active component of frozen RCD. Include a redundancy-on ablation if the experiment interface supports it.
11. **Do not silently expand or shrink the research plan.** If a roadmap experiment cannot be run, report what is missing, where the gap is, whether it blocks, and the smallest legitimate fix.
12. **Do not manufacture results.** Anything not executed is labelled "not executed". Do not infer ASR reduction, generalisation, robustness, significance, or effectiveness from dev/smoke results.
13. **Inspect Git history before changing anything.** Check the current branch, recent Week 7–8 commits, and the commit containing the frozen configuration/results. Use Git history to establish provenance where possible; do not assume the current working tree tells the complete story.
14. **Perform a small preflight run before any expensive evaluation.** The preflight must verify dataset selection, poisoning, defense condition, retrieval depth, generator settings, metrics, output location, and reproducibility metadata. A successful preflight is not a scientific result.
15. **Do not make architectural changes automatically.** If the existing experiment runner cannot support the required Week 9–10 comparison, first explain the exact limitation and propose the smallest code/configuration change. Do not modify the repository until the required change is clearly justified, and stop and ask before proceeding.
16. **Keep the primary evaluation reproducible and comparable.** For defended-vs-undefended comparisons, use the same query IDs and the same generated poison instances wherever the experiment design permits. Do not regenerate attacks independently between conditions if that would make the comparison statistically uncontrolled.
17. **Preserve raw evidence.** Never overwrite existing development/smoke results. New Week 9–10 runs must have unique experiment IDs and separate output locations.
18. **Before declaring Week 9–10 complete, produce an evidence table** showing, for every required experiment: config, dataset/split, retriever, attack, defense condition, seed, query count, generator, metrics, raw output, summary output, and commit/config provenance.

### Immediate task

Do **not** modify RCD first. Inspect the repository and determine:

1. the exact experiment runner and CLI;
2. how clean vs. poisoned experiments are configured;
3. how undefended vs. RCD conditions are configured;
4. how poison-specific metrics are computed;
5. whether the existing pipeline can run the defended-vs-undefended comparison without code changes;
6. which dataset/split is the held-out evaluation set;
7. the exact first Week 9–10 command to run.

Only after this audit should changes be proposed or made.

### Required output

| Item | Verified status | Evidence | Action |
|---|---|---|---|

Then give the **single safest first Week 9–10 experiment command** based on the repository's actual interface. No hypothetical commands.
