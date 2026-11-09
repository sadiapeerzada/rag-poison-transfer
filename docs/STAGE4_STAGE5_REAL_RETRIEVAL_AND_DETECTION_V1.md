# Stages 4–5: actual implementations and the empirical gates

Date: 2026-11-09. Scope: explicitly versioned follow-ups. **Neither stage is complete merely because code or synthetic tests pass.**

## Stage 4: genuine evidence-dependent second retrieval

New module: src/defenses/iterative/retriever.py

The controller performs a real initial retrieval, checks a fixed 0.75 lexical question-term coverage proxy, and either answers, abstains on absent evidence, or derives an anchor from *first-round retrieved document text* and actually performs a second retrieval. It fuses the real candidates with a fixed reciprocal-rank policy and records JSON-serializable round queries, document IDs, action decisions and call counts. At most two retrieval calls. It does not read any gold answer, adversarial label, or poison target.

This is an **uncalibrated exploratory rule**, not learned Adaptive-RAG, calibrated answer confidence or secure reasoning. First-round poison can influence the anchor; that is precisely a mechanism requiring measurement.

After Stage 3 NQ cohort freeze, run a **clean real-retrieval development smoke**:

~~~bash
cd "$HOME/Downloads/rag-poison-transfer"
git pull --ff-only origin main
source .venv/bin/activate
python -m pytest -q tests/test_evidence_dependent_iterative_retrieval.py tests/test_stages45_private_runners.py

python scripts/nq_iterative_retrieval_v1.py \
  --cohort-dir "$HOME/Documents/rag-research-results/nq-singlehop-v1-private" \
  --manifest-sha256 "PASTE_REAL_NQ_COHORT_SHA" \
  --cohort dev \
  --max-queries 20 \
  --output "$HOME/Documents/rag-research-results/nq-iterative-dev-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
~~~

This runs real Dense retrieval and records whether each query triggers a genuinely different evidence-dependent second-round query, with gold-document visibility and latency. **It does not run Qwen, poison the corpus or establish RQ3.** Full Stage 4 requires actual same-corpus matched clean/poison conditions on NQ and a multi-hop benchmark, real generation, fixed baseline under equal retrieval/token budgets, repeated question-level uncertainty and an independently versioned pre-test policy; reuse the original frozen results only as historical context. Pin real embedding weights and mark all dev-only policy tuning.

## Stage 5: detection AUROC/AUPRC/F1 with real injection identity

New library: src/evaluation/poison_detection.py  
New private evaluator CLI: scripts/evaluate_poison_detection_v1.py

The explicitly predeclared score is:

    suspicion = 0.7 * (1 - mean(agreement, rank_stability, rewrite_stability)) + 0.3 * temporal_year_conflict

Higher = more suspicious. It is a heuristic derived from **actual RCD last_diagnostics**, not a learned classifier, not general NLI fact-checking and not an assumption that an RCD ranking score is an anomaly probability.

Labels must come from the *actual known, globally injected poison document ID set for the entire sealed corpus*. A document being injected does not certify its factual falsity. Only candidates present in RCD scorer diagnostics can be scored. Report missing-positive retrieval/candidate exposure separately.

Prepare TWO private input JSON files with schema rag-poison-transfer.rcd-poison-identity-diagnostic-cohort/v1 and a records list. Every record must contain question query_id, condition="poisoned", known_global_poison_doc_ids containing IDs for the whole corpus, plus authentic per-question RCD last_diagnostics with consistency_signals, conflict_scores, scores. Inputs must be derived from true pinned corpus/diagnostics and must NOT be fabricated. Dev/test question IDs must be disjoint. By default document IDs must also be disjoint; disabling this is explicitly exploratory due to leakage.

When verified genuine inputs exist:

~~~bash
python -m pytest -q tests/test_poison_detection_v1.py tests/test_stages45_private_runners.py

python scripts/evaluate_poison_detection_v1.py \
  --dev "$HOME/Documents/rag-research-results/detection-dev-authentic_PRIVATE.json" \
  --test "$HOME/Documents/rag-research-results/detection-test-authentic_PRIVATE.json" \
  --out "$HOME/Documents/rag-research-results/detection-aggregate-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
~~~

It calculates tie-aware ROC AUC, average precision, dev-only threshold, held-out F1, precision, recall, false-positive rate and positive prevalence. It emits aggregate-only metrics and source SHA-256; no per-question data is written to public GitHub.

For a publishable result, further add query/document clustered uncertainty, real provenance and false-positive/false-negative error analysis. **The input cohorts have not been supplied; no real detection result is established yet.**

## Still required for full Stage 5

The real earlier HotpotQA N=25 intensity-5 and 30%-poison-rate sweeps are development-retrieval evidence only. Full matched Qwen answer-level testing at intensity 5, low global poison rate, an unseen attack family, and predeclared reranker/rewrite variants remains unexecuted. Freeze these as separate experimental protocols. Do not modify frozen HotpotQA/2Wiki outcomes or count failed construction as a defended success.
