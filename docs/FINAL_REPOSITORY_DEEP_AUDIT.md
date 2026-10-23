# Addendum: validator missing-field hardening (on candidate `ac5da6c`)

**AUDIT-037 (Medium, confirmed, fixed).** `validate_completed_cell()` read `generation_evidence_doc_ids`, `retrieved_doc_ids`, `poison_rank`, `poison_retrieved` and `prr_at_k` with `.get()` defaults or conditional skips, so a row missing them could pass: a missing `generation_evidence_doc_ids` skipped the evidence and `poison_retrieved` checks; a missing `retrieved_doc_ids` became `[]`; a missing `poison_rank` skipped the rank check; a non-dict `prr_at_k` raised `AttributeError`; `True` passed as `1.0`; extra PRR cutoffs were accepted; clean rows were not checked; missing `answer`/`gold_answer` defaulted to `""`. Fix: `_validate_retrieval_record()` requires all five fields on every row (absent key is an error, stored `null` rank is valid), validates types and exact cutoffs, and re-derives every value; `answer`/`gold_answer` must be strings. 54 regression tests added: **46 failed and 8 passed against the unpatched validator** (the 8 are the valid-cell baseline, two legitimate-null acceptance cases and four checks the old code already made); **54 passed after the fix**. Schema source: `run_week9_matched_poison_comparison.py` writes all five fields for both conditions; clean rows are fixed to `poison_retrieved=False`, `poison_rank=None`, PRR all `0.0`.

---

# Re-audit addendum (2026-10-23, HEAD `ac5da6c5253aaa47625de6522a6d55a311e3d31a`)

**Checkout:** fresh anonymous clone of the public repo (no credential was used), branch `audit/week9-bug-fixes` (the clone started on `main` = `a635945`, a merge of this branch; I switched to the audit branch, so this audit and its edits are on that branch only). `origin/main` = `a63594526b2b…`, `origin/audit/week9-bug-fixes` = `ac5da6c5253a…`, `origin/week7-8-rcd` = `0b8051dfbd07…` (the three differ). **The author's local working tree, uncommitted files and external result directories were not available.** GitHub Actions results were not accessible. Python 3.12.3; no MLX, no `sentence-transformers`, no Hugging Face access. Nothing was committed, pushed or staged.

**Not run:** the Week 9 matrix, any model inference, poison generation, API calls, dataset/model downloads. `tests/test_corpus_construction.py` was excluded (real-loader/network, see AUDIT-023) and not run.

| ID | Status now | Evidence / change |
|---|---|---|
| **A. Incomplete-cell recovery** (new **AUDIT-036**) | **Confirmed at HEAD, now fixed (opt-in)** | `run_matrix` still did `continue` for any existing cell dir without summary, so one failed cell blocked the matrix forever. Added `--resume --recover-incomplete` (`recover_incomplete=True`): the incomplete dir is **moved intact** (`os.rename`, no copy, never deleted/overwritten) to `_recovery_archive/<cell>/attempt_NNN` with a sidecar record and file SHA-256s in `plan.json["recoveries"]`; a poison manifest is reused only if it passes `verify_cell_provenance`, its recomputed poison fingerprint matches, it was written at the current commit, and all candidate manifests are the same instance, else recovery is **refused** and nothing is modified; results are always regenerated (partial or unsummarised results are never trusted); the fresh cell must pass `validate_completed_cell` before it counts as complete. If no manifest was ever written, poison is generated normally (no instance existed to preserve). A crash between archive and re-creation reuses the archived manifest. **Default resume is unchanged** (still preserves and skips). Cells whose *summary exists but fails validation* are deliberately **not** recoverable (possible tampering; operator decision). 11 new tests (evaluation failure, pre-manifest failure, results-without-summary, repeated interruptions, corrupt manifest, failed verification, wrong commit, crash mid-archive, untouched completed cells, flag misuse, default-resume unchanged); a mutation that disabled manifest reuse failed 3 of them. **Protocol impact:** none to design, seeds, IDs or metrics, but re-evaluating a recovered cell re-runs generation (seeded; MLX determinism unverified, U-2). Supervisor should confirm that a recovered cell may replace the failed attempt in the matrix. |
| **AUDIT-021** git cwd in `run.py` guard | **Confirmed, fixed** | Reproduced: from a foreign dirty repo `_git_dirty()` returned `True` and `_git_commit_sha()` returned the foreign SHA (`93dbf534`). Both now run `git -C <repo root>` (`repo_root=` override). Tests that relied on `chdir` now pass `repo_root`; 3 new tests fail on the old code (7 failures) and pass now. |
| **AUDIT-022** `test_smoke.py` dirties tracked `results/` | **Confirmed, fixed** | Test now writes to `tmp_path`; the full suite left `git status` showing only intended edits. |
| **AUDIT-032** CI skips `scripts/` | **Fixed** | `compileall` now covers `scripts`; CI also runs on `audit/**` pushes. `python -m compileall -q run.py src scripts tests` passes. CI is still not run on a runner here; optional-dependency tests (below) still make it red unless `sentence-transformers` is available and network tests are mocked/marked. |
| **AUDIT-020** `q[7:]` vs `"which "` | **Reproduced, intentionally NOT changed (supervisor gate)** | `"Which city hosts the Eiffel Tower?"` → `"what ity hosts…"`; `"Which film…"` → `"what ilm…"`. Committed raw rows: **41/300** dev questions (exp_022–026; the earlier audit said 43, I could not reproduce 43) and **47/300** held-out (exp_028b) begin with "Which". Minimal fix is `q[6:]`; the strict-xfail test in `tests/test_audit_regressions.py` records it. Fixing changes RCD rewrite scores for ~14–16% of queries, so exp_026/exp_028b/the matrix would no longer be the frozen method and would need re-running; freezing it means the method description must say rewrites are partly garbled. Decision required. (Also noted: the `who` rewrite uses a case-sensitive `"Who "` replace, so a lowercase "who" yields a duplicate rewrite.) |
| AUDIT-001…013 | **Not re-derived in full**; the 97 focused tests passed unchanged in the matrix and matched-comparison suites, and the recovery change did not alter their behaviour (62 pre-existing matrix tests passed after the change). | |
| AUDIT-023 non-hermetic tests | **Still open** | 8 tests need `sentence-transformers`, 2 need Hub access; identical at the unmodified HEAD (see ledger). |
| AUDIT-024/025/026/027/028/029/030/031/033/034/035 | **Still open / unverified, unchanged** | Not modified: each needs a protocol decision, new experiment component, or evidence I do not have. |

**Open items I did not fix, and why:** AUDIT-028 (missing RCD keys fall back to non-frozen weights) and AUDIT-027 (`revision=None`) would reject or alter older configs and need a decision on which legacy configs must keep loading; AUDIT-031 changes tie ordering; AUDIT-030 changes the poison acceptance protocol. I did not hunt exhaustively for new bugs in `bm25.py`, `hybrid.py`, `reranker.py`, `transfer.py`, `conflict.py`, `redundancy.py`, `scoring.py`, 2Wiki/NQ loaders or `metrics.py` beyond the targeted checks above; this re-audit **does not** supersede the "not read in depth" list in §1.

**Test ledger (this re-audit, offline, `HF_*_OFFLINE=1`):**

| Command | Result |
|---|---|
| `pytest -q tests/test_week9_heldout_poison_matrix.py` (before recovery tests) | 62 passed |
| same, with 11 new recovery tests | 73 passed in the full run (a `-k` filter selected 10 of the 11; all 11 pass in the full run) |
| `pytest -q tests/test_git_dirty.py tests/test_metric_wiring.py tests/test_env_metadata.py tests/test_heldout_metadata.py` | 39 passed, 4 failed (all `sentence-transformers` ImportError) |
| `pytest -q --ignore=tests/test_corpus_construction.py` (full) | **415 passed, 10 failed, 1 xfailed** |
| same 10 failing tests at unmodified HEAD | the same 10 fail (8 `sentence-transformers` ImportError, 2 Hub `OfflineModeIsEnabled`) |
| `python -m compileall -q run.py src scripts tests` | ok |

**Files changed:** `.github/workflows/tests.yml`, `scripts/run_week9_heldout_poison_matrix.py`, `src/utils/env_info.py`, `tests/test_git_dirty.py`, `tests/test_smoke.py`, `tests/test_week9_heldout_poison_matrix.py`, this document.

**Readiness (separate):** *Code correctness:* improved, not complete (10 environment-blocked tests unexecuted; several modules not audited in depth). *Reproducibility:* a fresh preflight is reasonable to attempt; the full matrix should wait for AUDIT-020 decision and AUDIT-034 baselines. *Scientific validity:* **not ready**.

---

## Previous audit (history preserved, dated at its own HEAD `1da874c`)

# Final Repository Deep Audit — `rag-poison-transfer` (Week 9–10 readiness)

**Audit date:** 2026-10-23
**Checkout audited:** a fresh anonymous clone of `github.com/sadiapeerzada/rag-poison-transfer`, branch `main`, HEAD `1da874c` (189 tracked files).
**Not audited:** the author's local working tree. Uncommitted edits, untracked files, backups and any results kept outside Git (for example `../rag-rcd-week9-final-results/`) were **not available** to this audit. Findings about them are marked Unverified.

> Passing unit tests establishes code correctness only. It does not establish that any experiment ran, that results are valid, or that the study is publication-ready.

---

## 1. Executive summary

* **What was inspected (actually read):** the Week 9 matrix runner, matched-comparison runner, multiseed runner/aggregator, held-out aggregator, `protocol.py`, `metrics.py`, `injection.py`, `base.py`, `lexical.py`, `semantic_fluent.py`, `generator.py`, `dense.py`, the RCD retriever and `rewrites.py`, `run.py` (retriever/generator/prompt/final-run guard), `env_info.py`, the frozen configs and `exp_027` manifest, the committed `exp_026`/`exp_028b` artifacts, CI config, the README and Week 7–8 report. **Not read in depth:** BM25/Hybrid/Reranker, `transfer.py` internals, 2Wiki and NQ loaders, RCD `core/conflict/redundancy/scoring`, `bootstrap`/McNemar internals beyond signatures.
* **Findings:** 29 numbered (**13 fixed** with regression tests, **15 open**, **1 unverified**) plus 3 further unverified items (U-1 to U-3); see §3.
* **Tests actually executed (scratch clone):** focused suites 23 → **97 passed**; full offline suite 318 passed / 10 failed → **401 passed / 10 failed / 1 xfailed**. All 10 failures are environmental (8 need `sentence-transformers`, 2 need Hugging Face access) and are identical before and after. `git diff --check` clean. A mutation check broke six key behaviours in a scratch copy and the tests caught all six.
* **Readiness:** **Technically** the Week 9 runner is substantially safer than before. **Scientifically: not ready.** One confirmed defect in frozen RCD behaviour (AUDIT-020) affects roughly 14–16% of queries and needs a supervisor decision before held-out or poisoned RCD results are treated as final. The clean held-out baselines, transfer study, 2Wiki protocol and paired statistics are not established.

## 2. Execution statement and deviations (read this)

* **No full matrix, no real model inference, no poison generation (LLM), no API call, no token use.** A GitHub token was pasted into the chat; it was used **once** to list repositories and locate the public repo, then not again (the clone itself was anonymous). **That token should be revoked.**
* `preflight()` was run on the committed configs: it reads local files only (no model, dataset or network).
* **Deviation to disclose:** my full-suite runs included `tests/test_smoke.py`, which re-runs the repo's **`exp_000` mock smoke scaffolding** (Mock generator; no inference, no API). It deleted and regenerated tracked `results/exp_000_smoke_test.*` **in my scratch clone only**. The Week 9 `run_smoke_test` workflow was not run. The effect is recorded as AUDIT-022.
* All changes were made in a scratch clone. **Nothing was staged, committed, reset, stashed or pushed, and your local repository was not touched.** The patch is delivered separately for you to review and apply.

## 3. Findings register

Legend — Status: **Fixed** / **Open** / **Unverified**. Tests are in `tests/test_week9_heldout_poison_matrix.py` (H), `tests/test_week9_matched_poison_comparison.py` (M), `tests/test_audit_regressions.py` (A).

### Fixed

| ID | Sev | Category | Where | Finding → fix | Test |
|---|---|---|---|---|---|
| AUDIT-001 | High | metric/runtime | `run_week9_heldout_poison_matrix.py::preflight` | `retrieval_calls` was `cells×queries×4` = **14,400**, omitting the 7,200 diagnostic retrievals (true total **21,600**). Now `estimate_workload()` derives normal/diagnostic/total from `top_k`, the diagnostic cutoff and the pipeline/condition lists; invalid input raises. Runtime counts are compared with the estimate per cell and a mismatch aborts the cell. | H: `test_preflight_counts_*`, `test_estimate_*`, `test_observed_*`, `test_workload_mismatch_*` |
| AUDIT-002 | High | reproducibility | `run_matrix` | `plan.json` stayed `running` forever; no counts, no failure info. Now `complete`/`partial`/`failed` with expected/completed/failed IDs and counts, UTC timestamps, attempts, failure summaries, atomic writes, and an explicit non-final scientific status. Interrupts are recorded and **re-raised**. | H: lifecycle tests |
| AUDIT-003 | High | data integrity | aggregator `validate_completed_cell` | Cells were accepted if summary, manifest and rows agreed with *each other*; nothing checked them against frozen inputs or even that the 300 IDs equal `exp_027`. Now independent verification (§7). Integrated into aggregation, resume and fresh-cell validation. | H: provenance tests |
| AUDIT-004 | Medium | portability | `run_week9_matched_poison_comparison.py` | `DEFAULT_SOURCE_MANIFEST` hardcoded `/Users/sadiapeerzada/...`. Removed; explicit `--source-manifest` or `RAG_POISON_SOURCE_MANIFEST`, resolved at call time, validated, fails before creating outputs. | M: Fix D tests |
| AUDIT-005 | Medium | scientific validity | `evaluate_cell` | The 300-query runner never validated Dense/RCD shared settings (only implicit via hash pins) and used **Dense's** `top_k`/`max_tokens` for both pipelines. Now one `validate_shared_pipeline_settings` (single source of truth), each pipeline gets its own config; intentional differences (`retriever`, `experiment_id`, `rcd_*`) remain allowed. | H, M |
| AUDIT-006 | High | provenance | `_require_clean_relevant_inputs`, `git_commit_sha` | Git ran in the **caller's cwd**. Reproduced: from another Git repo the guard passed vacuously in smoke mode and `git_commit_sha()` recorded the *other* repo's commit. Now pinned to `REPOSITORY_ROOT` (opt-in `repo_root=` for `git_commit_sha`). | H: `test_guard_inspects_the_repository_*` |
| AUDIT-007 | High | provenance | `RELEVANT_TRACKED_PATHS` | Guard covered 12 files and **excluded the retrievers, RCD, prompts/answer extraction, metrics and data loader**; relevant-but-untracked files were invisible to `--untracked-files=no`. Now 27 paths, and final runs require every one to be tracked. | H: guard tests, `test_every_guarded_path_*` |
| AUDIT-008 | Medium | metric | `metrics.py::attack_transfer_rate` | Truthiness: the string `"False"` counted as success (reproduced: ATR 0.5). Present non-bool values now raise. | A |
| AUDIT-009 | Medium | testing | `test_aggregate_rejects_bad_raw_cell` | After Fix C this test would pass for the wrong reason (missing-inputs error). Fixtures updated to exercise the real branches. | H |
| AUDIT-010 | Medium | documentation | `README.md`, `Week_7-8_Report.md` | Said the `exp_026` raw log/summary are **absent**. They are present (commit `e3e9e85`; 300 rows, 300 unique IDs, `git_dirty=false`, validation split). README corrected narrowly; the dated report gets an addendum (history preserved). | docs |
| AUDIT-011 | Medium | reproducibility | `run_matrix` | No commit recorded in the plan; HEAD or inputs could change mid-run and mix code versions. Plan records the SHA; each cell re-checks the guard and HEAD; resume at a different commit is refused. | H |
| AUDIT-012 | Low | data completeness | `evaluate_pipeline` | Required "retrieval-call overhead" was not preserved; RCD's inner retrieval count (query-dependent) was discarded. Now `retrieval_call_accounting` is added to every raw record (additive). | H |
| AUDIT-013 | Medium | metric integrity | validator | PRR@k (diagnostic retrieval) and ASR/`poison_retrieved` (normal retrieval) were never checked to describe the same ranking. Validator now requires generation evidence to be a prefix of the diagnostic ranking and re-derives `poison_retrieved`, rank and PRR@k. **Unverified on real hardware** — see §6. | H |

### Open — confirmed

| ID | Sev | Category | Where | Finding | Next action |
|---|---|---|---|---|---|
| **AUDIT-020** | **High** | **scientific validity** | `src/defenses/rcd/rewrites.py::_generic_rewrites` | `"which "` is 6 chars but the code uses `q[7:]`, so **"Which city…" → "what ity…"**. Reproduced. 43/300 dev and 47/300 held-out questions start with "Which". The garbled rewrite feeds RCD's rewrite-consistency signal for ~14–16% of queries in `exp_022`–`exp_031`. **Frozen behaviour — not changed.** | Supervisor decision: fix and re-run dev/held-out, or document as part of the frozen method. `xfail(strict)` test records the expected behaviour. |
| AUDIT-021 | Medium | provenance | `run.py::_ensure_clean_final_run`, `env_info._git_dirty` | Same cwd dependence as AUDIT-006, in the **clean-baseline final-run guard** (Stage 3). Not fixed: tests monkeypatch `run._git_dirty` with zero-arg lambdas, so the fix needs a deliberate test update. | Run final baselines from the repo root until fixed; then add `repo_root` and update tests. |
| AUDIT-022 | Medium | testing/reproducibility | `tests/test_smoke.py` | Deletes and rewrites tracked `results/exp_000_smoke_test.*`. Running `pytest` **dirties the tree**, which blocks `final_run` guards. | Write to a temp results dir; do not run the suite between freezing and a final run. |
| AUDIT-023 | Medium | testing | `test_corpus_construction.py` etc. | Tests call the real loader (network, unpinned revision) with no marker; 8 more need `sentence-transformers` and a model download. Not hermetic. | Add markers/skip-or-mock. |
| AUDIT-024 | Medium | scientific validity | Week 9 runners, `run_week9_poison_pilot.py` | Matrix covers **Dense vs RCD only**; the pilot hardcodes `source_pipeline="rcd"`. No runner for BM25/Hybrid/Reranker sources or targets (Stage 7). `TransferMatrix` exists but is untied to Week 9. | New experiment component; report separately. |
| AUDIT-025 | Medium | scientific validity | repo | No disjoint 2Wiki dev/held-out manifest (Stage 8); only baselines `exp_017–020`. | Create/freeze protocol; no RCD retuning. |
| AUDIT-026 | Medium | metric completeness | Week 9 evaluate/aggregate | **F1 is not computed** (EM only), so EM/F1 retention needs post-hoc F1 from raw `answer`/`gold_answer` (preserved). `paired_mcnemar_counts` exists but is unused; no effect sizes. Bootstrap CI is sound (query-cluster resampling, paired). | Add F1 + McNemar/effect sizes at analysis time. |
| AUDIT-030 | Medium | scientific validity | `semantic_fluent.py` | Quality gate requires the target answer in the text but **never checks the gold answer is absent**; semantic poison cannot be regenerated offline, so it is verified by replay and ID hashes only. Poison and answers use the same LLM. | Add gold-answer-absence check **only as a protocol decision**; note in methods. |
| AUDIT-027 | Low | reproducibility | `loaders.py` | `revision=None` default leaves datasets unpinned for non-frozen configs (frozen Week 9 configs pin it). | Require revision for final runs. |
| AUDIT-028 | Low | configuration | `run.py::build_retriever` | Missing RCD keys silently fall back to non-frozen weights (0.55/0.05/0.20/0.20 vs frozen 0.45/0.00/0.10/0.45). Week 9 configs are explicit. | Fail on missing keys. |
| AUDIT-029 | Low | comparability | `generator.py` | `MLXGenerator` passes the raw prompt (no chat template; `TransformersGenerator` applies one); token counts are word counts; `time.time()` used for latency. Kaggle-era and MLX-era results are not directly comparable. | Document; do not pool. |
| AUDIT-031 | Low | reproducibility | `dense.py` | `np.argsort` is not stable; exact ties break implementation-defined. | `kind="stable"` (changes tie order → treat as protocol-adjacent). |
| AUDIT-032 | Low | CI | `.github/workflows/tests.yml` | `compileall` skips `scripts/`. | Add. |
| AUDIT-033 | Info | validation | `validate_poisoned_dataset` | 5% poison-rate tolerance; mitigated because replay requires every query to carry the family. | — |
| AUDIT-035 | Info | provenance | `run_matrix` | Cell manifests set `git_dirty=False` after the guard; untracked files outside the 27 paths are ignored by design. | Document. |

### Unverified

| ID | Why unverifiable here |
|---|---|
| AUDIT-034 | README states `exp_030`/`exp_031` are **complete**, with results archived outside the repo. Not present in this checkout; completion, `final_run` and `git_dirty=false` are unverified. The baselines remain a publication gate. `exp_028b` rows record `git_dirty: null` and are correctly an exploratory/recovery run. |
| (U-1) | The 10 environment-failing tests (sentence-transformers / Hugging Face) were not run to success. |
| (U-2) | Real-hardware determinism of Dense normal vs diagnostic retrieval (AUDIT-013's strict prefix check could reject a cell on float-tie noise); needs a real run on MLX hardware. |
| (U-3) | Anything depending on local uncommitted files, or on MLX behaviour. |

## 4. Fix summary (files changed in the scratch clone)

* `scripts/run_week9_heldout_poison_matrix.py` — workload estimate/preflight, per-pipeline evaluation and runtime-vs-estimate check, atomic plan writes, plan lifecycle, resume validation, repo-pinned Git guard with 27 paths, `FrozenMatrixInputs`, `verify_cell_provenance`, shared `validate_completed_cell`.
* `scripts/aggregate_week9_heldout_poison_matrix.py` — requires frozen inputs, loads them once, reuses the shared validator, new `--heldout-manifest/--dense-config/--rcd-config`.
* `scripts/run_week9_matched_poison_comparison.py` — source-manifest resolver, `SHARED_MATCHED_KEYS`, `validate_shared_pipeline_settings`, `diagnostic_retrieval_required`, per-record call accounting.
* `src/experiments/protocol.py` — `git_commit_sha(repo_root=...)`.
* `src/evaluation/metrics.py` — ATR rejects non-bool `attack_success`.
* Tests: `tests/test_week9_heldout_poison_matrix.py` (23 → 62), `tests/test_week9_matched_poison_comparison.py` (→ 35), new `tests/test_audit_regressions.py`.
* Docs: `README.md` (narrow), `Week_7-8_Report.md` (addendum), this report.
* **Side effect, not a deliverable:** `results/exp_000_smoke_test.summary.json` was rewritten by `tests/test_smoke.py` (AUDIT-022). Exclude it from any patch.

## 5. Behaviour you should know about

* **Preflight (committed configs, `top_k=3`, diagnostic k=10):** 12 cells × 300 queries → generations **14,400**; normal retrievals **14,400**; diagnostic **7,200**; total `retrieval_calls` **21,600**. RCD inner operations are reported as bounds (21,600–54,000) because the rewrite count is query-dependent. These hold *only* under these configs (hash-pinned); they recompute if configs change, and diagnostics drop to 0 when `top_k ≥ 10`.
* **Plan statuses:** `complete` (all expected cells completed **and** independently validated), `partial`, `failed`. `running` at rest means the process was killed without recording. Legacy plans resume and are upgraded (`legacy_plan_upgraded_fields`) but never promoted to `complete` unless cells validate. Corrupt or incomplete cell directories are preserved, never retried or deleted.
* **Source manifest:** `--source-manifest PATH`, else `RAG_POISON_SOURCE_MANIFEST`, else an actionable error. No home-relative default, because the pilot manifest is one specific experiment's artifact and guessing could select the wrong one.

## 6. How the aggregator verifies provenance independently

For every cell, against the frozen inputs loaded once from the repository's own validated loaders: dataset name/config/revision/split, held-out fingerprint, **exact `exp_027` query IDs and order**, config SHA-256s, retriever and generator settings, attack configuration, seed ∈ predeclared seeds, cell ID; each poison ID must equal its canonical `poison::family::query::index::sha1(text)`; the manifest is **replayed** over the frozen clean data and the poison-instance fingerprint is recomputed, then compared with the manifest, the summary and every raw row; raw rows must carry the replayed poison IDs and target; lexical cells are additionally **regenerated deterministically** and compared (catches a manifest forged consistently). Missing frozen inputs raise; no saved fingerprint is ever trusted.
**Limit:** semantic-fluent poison text comes from an LLM and cannot be regenerated offline.

## 7. Research-validity risks and missing evidence

Confirmed AUDIT-020 (rewrite defect); clean held-out baselines unverified (AUDIT-034); matched poison comparison, transfer (AUDIT-024), 2Wiki (AUDIT-025) and paired statistics (AUDIT-026) not yet run or built; semantic poison may contain the gold answer (AUDIT-030). Verified positives: held-out IDs are disjoint from `exp_026` dev IDs; the manifest reports 0 overlap with `exp_025`; the Dense/RCD configs differ only in `retriever`, `experiment_id` and RCD parameters; pinned hashes match the committed files; the fingerprint is canonical (sorted, no volatile fields); bootstrap resampling respects pairing.

## 8. Test coverage

Now covered: workload arithmetic and edge cases, plan lifecycle (complete/partial/failed/interrupted/resume/legacy/corrupt/pre-loop), atomic writes, Git guard (cwd, tracking, fail-closed), provenance tampering, source-manifest resolution, ATR strictness. **Still missing:** `run_matrix` against real retrievers (integration), RCD `core/conflict/redundancy/scoring` edge cases, transfer-matrix wiring to Week 9, hermetic loader tests, semantic-cell end-to-end replay, aggregation across all 12 real cells.

## 9. Week 9–10 readiness

| # | Stage | Status |
|---|---|---|
| 1 | Documentation cleanup | **Done in clone** (README/report); apply and review |
| 2 | Freeze code under commit/tag | **Not started** — steps below |
| 3 | Matched clean held-out Dense/RCD baselines | **Blocked/unverified** (AUDIT-034); needs `final_run`, `git_dirty=false` from actual files; AUDIT-021 |
| 4 | Final-run provenance | **Implemented, not executed** |
| 5 | Immutable matched poison instances | **Implemented, not executed** |
| 6 | Primary HotpotQA matrix (12 cells) | **Implemented, not executed** |
| 7 | Required metrics preserved | **Mostly** — F1 missing (AUDIT-026) |
| 8 | Source-to-target transfer | **Not started** (AUDIT-024) |
| 9 | 2Wiki disjoint protocol | **Not started** (AUDIT-025) |
| 10 | Paired statistics | **Partial** — bootstrap exists; McNemar/effect sizes not wired |

**Freeze steps (not performed):** apply and review the patch → decide AUDIT-020 → fix AUDIT-021/022 → commit → confirm `git status` clean for tracked files → tag (for example `week9-eval-freeze`) → run the focused tests **before** committing (the suite dirties `results/`).

**Must be resolved before:** *clean baselines* — AUDIT-020, -021, -022, -034; *primary matrix* — the above plus a successful dry check of AUDIT-013 on real hardware (U-2) and AUDIT-030 decision; *transfer study* — AUDIT-024, -026; *2Wiki* — AUDIT-025 and no retuning.

## 10. Test ledger

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_week9_heldout_poison_matrix.py tests/test_week9_matched_poison_comparison.py` (baseline, before changes) | 23 passed |
| same (after changes) | **97 passed** |
| `pytest -q --ignore=tests/test_corpus_construction.py` with `HF_*_OFFLINE=1` (baseline) | 318 passed, 10 failed |
| same (after changes) | 401 passed, 10 failed, 1 xfailed |
| `git diff --check` | clean |
| `tests/test_corpus_construction.py` | **not run to completion** (network hang) |

Environment: Python 3.12, no `sentence-transformers`, no MLX, no Hugging Face access. The project's own virtualenv and documented test command were not available to me.
