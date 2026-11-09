# Task 6 — Real saved RCD poison detection: one offline run, no new Qwen inference

**9 November 2026 · Status: Implementation ready for owner's original private Mac artifacts. Empirical metrics NOT claimed until the saved-data command succeeds.**

## What was discovered (read-only repository source audit)

The publicly tracked `results/exp_021_hotpotqa_rcd_v1_mlx_smoke4.jsonl` records actual RCD candidate signal and score dictionaries, but **has no injected corpus-wide poison label set**. The small `results/exp_029_rcd_poisoned_pilot_n10.json` contains query-local injected poison IDs and target outcomes but **not candidate-level RCD score/conflict/consistency dictionaries**. Joining unrelated runs is invalid.

More promisingly, the original already executed [2Wiki 480-Qwen-observation ablation](../reports/2wiki_rcd_ablation_v1_question_cluster_audit_2026-11-09.md) has a **private, SHA-pinned 480-entry retrieval plan**. In the source [retrieval-preparation code](../scripts/prepare_2wiki_rcd_ablation_prompts.py), every entry explicitly stores:
- `cell_id`, `variant`, `condition`, original `query_id` and `poison_doc_ids`;
- `candidate_consistency_features` = actual `retriever.last_diagnostics["consistency_signals"]`;
- `candidate_scores` = actual `retriever.last_diagnostics["scores"]`, including the original raw `conflict` component.

The original source construction sealed all **300 original questions per cell**. Rebuilding the **union of injected IDs in all mechanically valid records per cell** is essential: simply using one selected question's `poison_doc_ids` would incorrectly label poison belonging to other queries as clean.

## New offline analysis

Run `scripts/evaluate_saved_2wiki_rcd_poison_detection.py` against the original 480 plan and the restored original 2Wiki run. It:

1. Verifies the frozen original 480-Qwen aggregate SHA-256, run manifest and SHA-256-bound retrieval plan. **No model is invoked.**
2. Verifies the original 2Wiki frozen protocol, construction seal and evaluation completion plus pinned local query/corpus input.
3. Reconstructs **global injected poison IDs** from all original valid 300-query construction records in each of the four ablation source cells. Failed or partial documents are not counted as inserted, following the source replay behavior.
4. Checks candidate IDs belong to the source clean corpus or injected union. Reuses recorded actual RCD consistency, conflict and score dictionaries.
5. Restricts to **full_k3 poisoned** records. The 40 post-hoc selected cell positions contain **36 distinct original question IDs**, so it uses a single deterministic cell per question to prevent duplicate-question leakage. A SHA-256-derived 18-question development / 18-question test split is used.
6. Uses the predeclared actual document-suspicion heuristic and picks F1 threshold on development only. On test, reports candidate-level **AUROC, AUPRC, precision/recall/F1, clean false-positive rate, prevalence**, and **question-cluster 2,000-replicate nominal confidence intervals**. Does **not** claim labels represent source-proven false factual assertions.
7. Writes **one private aggregate-only JSON receipt with exclusive file creation**; prints aggregate numbers only. Never publishes case-level scores, question IDs, original prompts, poison strings or unreviewed dataset excerpts.

## Run on your Mac

These lines contain **no zsh comment lines** (previous terminal pasted lines beginning with `#` as commands):

```bash
cd "$HOME/Downloads/rag-poison-transfer"
git fetch origin
git switch --track origin/research/task6-real-2wiki-detector-offline
python -m pytest -q tests/test_evaluate_saved_2wiki_rcd_poison_detection.py tests/test_poison_detection_v1.py
python scripts/evaluate_saved_2wiki_rcd_poison_detection.py --allow-shared-document-ids --out "$HOME/Documents/rag-research-results/nov09-research-gates/task6-real-detector-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
```

`--allow-shared-document-ids` is explicit because same-corpus development and test candidate identities can overlap. The tool **reports the overlap**; it is not a genuinely independent-document generalization test. Remove this flag if you require fail-closed document-disjoint evaluation, understanding it may reject the selected 36-question cohort.

If the original sealed full-run folder cannot be auto-located under `~/Documents/rag-research-results` or `~/Downloads`, pass `--restored-root "/path/to/verified-original-full-2wiki-run"`. The directory must contain **`protocol.json`**, **`execution/construction/construction.seal.json`** and **`execution/evaluation/evaluation.complete.json`**. If the model prompt plan was moved, pass `--plan PATH` to its **exact SHA-pinned original 480-row file**; the script never accepts an alternate plan by filename alone. If the original pinned corpus snapshot path moved, pass `--local-data PATH`; its SHA-256 is checked against the original sealed protocol.

**Do not** copy the private plan, any case-level results, prompts, document texts or corpus files to public GitHub. The console receipt is aggregate-only and can be shared for review.

## Scientific limits

- This is a retrospective **valid-only and outcome-selected** subset, **36 unique questions**, not the full 300-question, independently blinded detection population.
- The same set of original retrieval model weights, dataset family and frequent candidate documents can appear across development/test. Even with query-disjoint split, this is not proof of generalization to unseen document families.
- The true label is **known injected document identity** under verified original construction, **not independently proved factual falsehood**. Candidate-level metrics exclude injected documents never retrieved or scored.
- The source RCD score's `conflict` field is directly the raw value from [`score_documents`](../src/defenses/rcd/scoring.py), **not a fitted likelihood**. The heuristic policy and score direction are fixed before this offline analysis.
- Bootstrap intervals are nominal, with very few question clusters, unadjusted for repeated metric comparisons and not suitable as a strong held-out guarantee.
- A successful run would make **Task 6 exploratory candidate-level evaluation empirically available** without new Qwen calls; it would not by itself justify a fully validated detector for the original broad protocol.

**If the command errors:** Do not edit, rename, modify, rebuild, or reseal source files. Share only the full text of the error (avoid raw excerpts); we can diagnose paths, missing score fields and corpus provenance without touching the frozen originals.
