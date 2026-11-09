# Continuation of the original research plan — Stages 3–5

**Date:** 9 November 2026  
**Status:** Stage 3 private NQ cohort freezing implemented, subject to local tests and execution. **No new NQ full-scale QA, adaptive-RAG, robustness, or poison-detection results are claimed.**

## Stage 3 — Natural Questions single-hop

The original real 25-query NQ retrieval sweep already exists in results/week5_6_nq_sweep.csv and the NQ loader is tested (src/data/loaders.py, docs/WEEK5_6_BENCHMARK_VALIDATION_REPORT.md §10). Its corpus pools NQ long-answer candidate passages. It is **not** full open-domain Wikipedia retrieval and must never be called a standard open-domain NQ benchmark.

### New versioned study

| Component | Predeclared initial design |
| --- | --- |
| Dataset | google-research-datasets/natural_questions, default configuration, revision e8103d566bef4154c2c12b17c6095ec5275840cc |
| Sampling | Existing streaming loader, shuffle buffer 10,000; not a uniform sample |
| Development | 50 training-split queries, seed 20261109 |
| Evaluation | 300 validation-split queries, seed 20261110 |
| Corpus | Pooled candidate passages from each complete selected cohort; not target-only indexing |
| Attacks | Lexical influential-token and semantically fluent false-evidence, intensity 1 and 3 |
| Generator | New Qwen2.5-7B-Instruct-4bit real inference, pinned snapshot, greedy 64-token QA |
| QA arms | Matched Dense and one composite Dense-primary/BM25-auxiliary RCD, frozen historical weights |
| PRR baselines | BM25, Dense, Hybrid and Dense+CrossEncoder; same sealed poisoned corpus |
| Planned calls | 2 attack families × 2 intensities × 300 questions × 2 QA arms × 2 conditions = **2,400 logical QA observations** if all constructions valid |
| Scientific status | New follow-up/exploratory unless all historical exposure and prospective design are independently certified before outcomes |

The new standalone script scripts/nq_singlehop_v1_freeze.py downloads the exact pinned dataset via the existing NQ loader, verifies nonempty questions and gold labels, verifies gold candidate IDs against the pooled corpus, rejects duplicate IDs, compares train/validation query IDs, records exact source-data SHA-256 seals, git revision, cohort/corpus fingerprints, and writes private source JSON. It **does not run an attack, retrieval or a generator**. Fail-closed on dirty Git working tree. A JSON list of prior exposed IDs may be supplied by --exposure-exclusions; absence of that list **does not certify an uninspected cohort**.

Run after the PR is merged:

~~~bash
cd "$HOME/Downloads/rag-poison-transfer"
git pull --ff-only origin main
source .venv/bin/activate
python -m pytest -q tests/test_nq_singlehop_v1_freeze.py tests/test_natural_questions_loader.py

OUT="$HOME/Documents/rag-research-results/nq-singlehop-v1-private"
python scripts/nq_singlehop_v1_freeze.py freeze --out-dir "$OUT"
~~~

Record the returned new **manifest SHA-256**, then independently verify:

~~~bash
python scripts/nq_singlehop_v1_freeze.py verify \
  --out-dir "$HOME/Documents/rag-research-results/nq-singlehop-v1-private" \
  --manifest-sha256 "PASTE_FROZEN_MANIFEST_SHA256"
~~~

Expected: NQ_COHORT_FROZEN_NO_RETRIEVAL_OR_INFERENCE and PASS_PRIVATE_NQ_COHORT_INTEGRITY_ONLY. **This only prepares the cohort, not the matched QA experiment.** Do not rerun/overwrite an existing private output tree; use a fresh directory for any intentional study version.

### Gates before the new 2,400-call evaluation

1. Resolve NQ annotation disagreement (first short-answer annotated, possible aliases and yes/no) and disclose cohort sampling/candidate-corpus limitation. Exclude historically exposed IDs if recoverable; do not silently call cohort prospective.
2. Seal immutable poison corpora for each family/intensity; full poisoned union is available to both pipelines, with same target and documents. Track attempted constructions, mechanically valid cases, semantic failures and ambiguous targets separately.
3. Run clean and poisoned BM25/Dense/Hybrid/Reranker retrieval-only baselines and matched Dense/RCD output depths, recording PRR@1/3/5/10, gold-document recall, actual call counts and latency.
4. Pin local Qwen file-by-file model hashes, prompts, 64-token cap and output-extraction policy. Use crash-safe request intent + response journals; do not make repeated calls automatically after an unresolved intent.
5. Produce clean and poisoned EM/F1, poisoned target matches, clean-correct→poison-wrong flips, evidence exposure, attempted and valid denominators, question-cluster CIs, multiplicity policy and compute costs. Never count failed poison construction as defense success.
6. Publish **only aggregate statistics**, raw-file digests, and caveats. All per-question prompts, labels and model responses remain private.

## Stage 4 — Genuine adaptive and iterative retrieval

The current RCD rewrite set is **not** an adaptive multi-round controller. A qualifying new study requires a separately versioned development-frozen policy with a first retrieval, evidence-based action choice {answer, retrieve again, abstain}, and a **new retrieval** based on evidence seen in a previous round. Record new query, selected evidence, doc ranks and score changes for each round. Do not inspect gold/target answer in decisions. Cap to e.g. two rounds, predeclare thresholds on development data and compare against fixed-top-k/RCD under equal call/token budgets. Evaluate single-hop NQ and multi-hop HotpotQA/2Wiki with matched clean/poisoned corpora. **New controller implementation and actual new evaluation remain pending.**

## Stage 5 — Robustness and real detection metrics

Existing N=25 HotpotQA intensity-5 and 30%-poison-rate sweeps (eight attacked IDs) are real *development-scale retrieval* checks, not full end-to-end robust conclusions. Add separately frozen test cells for intensity 5, low global poison rate, a truly unseen attack family and additional rewrite-count/reranker-use variants when pursuing the full Section 8 plan.

For poison detection, define **document identity** as the known injected-poison ground-truth label (not "factually false") and a separately meaningful continuous per-document *suspicion* score whose direction is fixed in advance. Freeze classifier threshold on development only; evaluate AUROC, AUPRC, F1/precision/recall, FPR, positive prevalence, document/question repeatedness and clustered uncertainty on test. A final RCD ranking score is **not automatically a detector**. If authentic signals/labels are missing, the proposed metric is unsupported, not zero or invented. Independent semantic factuality remains unverified if no human/source adjudication occurs.

## Evidence checklist

| Phase | Code prepared? | Actual results? |
| --- | --- | --- |
| NQ private 50/300 cohort freeze | Yes, new script + offline synthetic tests | **Not run on Mac** |
| NQ actual poison/retrieval/2,400-call QA | No new runner in this PR | **Pending** |
| Adaptive multi-round controller | No | **Pending** |
| Robustness intensity5/low-rate/unseen | Historical small-N retrieval only | **Full validation pending** |
| Labeled document poison detection | No verified classifier study | **Pending** |
| Publication package | Professor handles manuscript | **Not part of this PR** |

The original frozen HotpotQA and 2Wiki outcomes are not modified by this work.
