# HotpotQA cross-pipeline transfer — verified aggregate-only results

This release contains **only aggregate statistics** from the frozen held-out evaluation.
It excludes all query-level IDs, questions, answers, model prompts and responses,
poison documents, checkpoint records, and locally stored held-out data.

## Design and provenance

- Dataset: HotpotQA; 300 fixed evaluation questions; poison seeds: 42, 43, 44.
- Attacks: lexical influential token and semantic fluent false evidence, intensities 1 and 3.
- Sources: BM25, Dense, Hybrid, Reranker. Targets: those four plus RCD.
- Candidate generation preceded source-only screening of at most three fixed choices.
- Selected poison for each source condition was sealed before target evaluation.
- The same selected instance is evaluated across all five target pipelines.
- Unsuccessful constructions remain failures in full-population rates.
- ATR is measured from **final** source/target evaluations, not screening outcomes.
- 240 source × target × attack × intensity × seed condition cells.
- 2000 query-cluster bootstrap replicates retaining poison seeds; no multiplicity adjustment.

## Execution accounting

- `actual_backend_calls`: **21,175**
- `clean_cache_hits`: **19,825**
- `logical_generation_observations`: **41,000**

## Pooled-seed descriptive matrices

Each row pools three seed conditions, i.e. 900 query-seed positions; repeated seeds are
not independent samples. The bootstrap clusters by query across all seeds.
ASR = target successes / 900; ATR = transferred / final source successes.
An undefined ATR or confidence interval is denoted by —.

### lexical_influential_token, intensity 1

| Source → target | Valid / 900 | Target ASR | ATR | ATR 95% CI |
|---|---:|---:|---:|---:|
| bm25 → bm25 | 405/900 | 23.9% | 100.0% | [100.0%, 100.0%] |
| bm25 → dense | 405/900 | 17.9% | 66.0% | [55.7%, 75.3%] |
| bm25 → hybrid | 405/900 | 20.8% | 82.8% | [74.2%, 90.0%] |
| bm25 → reranker | 405/900 | 17.3% | 67.0% | [56.2%, 77.4%] |
| bm25 → rcd | 405/900 | 19.1% | 72.1% | [62.3%, 80.9%] |
| dense → bm25 | 405/900 | 22.3% | 85.6% | [76.8%, 93.4%] |
| dense → dense | 405/900 | 20.0% | 100.0% | [100.0%, 100.0%] |
| dense → hybrid | 405/900 | 20.3% | 82.8% | [73.3%, 91.6%] |
| dense → reranker | 405/900 | 17.3% | 76.1% | [65.4%, 86.0%] |
| dense → rcd | 405/900 | 20.8% | 93.9% | [87.7%, 98.5%] |
| hybrid → bm25 | 405/900 | 22.7% | 92.4% | [85.9%, 97.9%] |
| hybrid → dense | 405/900 | 18.0% | 73.6% | [63.7%, 83.1%] |
| hybrid → hybrid | 405/900 | 21.9% | 100.0% | [100.0%, 100.0%] |
| hybrid → reranker | 405/900 | 17.2% | 72.6% | [62.4%, 82.7%] |
| hybrid → rcd | 405/900 | 19.4% | 79.7% | [70.2%, 88.2%] |
| reranker → bm25 | 405/900 | 22.7% | 90.0% | [81.9%, 96.8%] |
| reranker → dense | 405/900 | 18.6% | 81.8% | [72.0%, 90.5%] |
| reranker → hybrid | 405/900 | 20.4% | 84.1% | [74.7%, 92.3%] |
| reranker → reranker | 405/900 | 18.9% | 100.0% | [100.0%, 100.0%] |
| reranker → rcd | 405/900 | 19.7% | 85.3% | [76.6%, 93.4%] |

### lexical_influential_token, intensity 3

| Source → target | Valid / 900 | Target ASR | ATR | ATR 95% CI |
|---|---:|---:|---:|---:|
| bm25 → bm25 | 405/900 | 42.2% | 100.0% | [100.0%, 100.0%] |
| bm25 → dense | 405/900 | 36.6% | 85.8% | [80.0%, 90.9%] |
| bm25 → hybrid | 405/900 | 37.9% | 88.9% | [83.0%, 93.9%] |
| bm25 → reranker | 405/900 | 41.8% | 97.4% | [94.6%, 99.5%] |
| bm25 → rcd | 405/900 | 34.9% | 81.3% | [75.1%, 87.3%] |
| dense → bm25 | 405/900 | 41.8% | 98.9% | [96.9%, 100.0%] |
| dense → dense | 405/900 | 39.2% | 100.0% | [100.0%, 100.0%] |
| dense → hybrid | 405/900 | 38.1% | 93.5% | [88.7%, 97.5%] |
| dense → reranker | 405/900 | 41.9% | 98.3% | [96.0%, 100.0%] |
| dense → rcd | 405/900 | 36.6% | 92.1% | [87.4%, 96.3%] |
| hybrid → bm25 | 405/900 | 41.7% | 98.6% | [96.4%, 100.0%] |
| hybrid → dense | 405/900 | 37.0% | 89.2% | [83.9%, 93.7%] |
| hybrid → hybrid | 405/900 | 40.0% | 100.0% | [100.0%, 100.0%] |
| hybrid → reranker | 405/900 | 41.6% | 97.5% | [94.8%, 99.5%] |
| hybrid → rcd | 405/900 | 34.8% | 83.6% | [77.5%, 89.4%] |
| reranker → bm25 | 405/900 | 41.9% | 97.6% | [94.9%, 99.7%] |
| reranker → dense | 405/900 | 36.7% | 85.8% | [80.0%, 90.9%] |
| reranker → hybrid | 405/900 | 37.9% | 89.2% | [83.6%, 94.3%] |
| reranker → reranker | 405/900 | 42.1% | 100.0% | [100.0%, 100.0%] |
| reranker → rcd | 405/900 | 35.0% | 81.8% | [75.7%, 87.5%] |

### semantic_fluent_false_evidence, intensity 1

| Source → target | Valid / 900 | Target ASR | ATR | ATR 95% CI |
|---|---:|---:|---:|---:|
| bm25 → bm25 | 140/900 | 12.6% | 100.0% | [100.0%, 100.0%] |
| bm25 → dense | 140/900 | 9.2% | 70.8% | [55.9%, 84.2%] |
| bm25 → hybrid | 140/900 | 10.8% | 82.3% | [69.5%, 93.7%] |
| bm25 → reranker | 140/900 | 9.9% | 75.2% | [62.2%, 87.6%] |
| bm25 → rcd | 140/900 | 10.2% | 77.0% | [63.4%, 89.0%] |
| dense → bm25 | 140/900 | 12.2% | 93.5% | [84.1%, 100.0%] |
| dense → dense | 140/900 | 10.2% | 100.0% | [100.0%, 100.0%] |
| dense → hybrid | 140/900 | 10.8% | 91.3% | [81.4%, 98.9%] |
| dense → reranker | 140/900 | 10.6% | 91.3% | [81.4%, 98.8%] |
| dense → rcd | 140/900 | 10.4% | 94.6% | [87.5%, 100.0%] |
| hybrid → bm25 | 140/900 | 12.3% | 94.1% | [85.0%, 100.0%] |
| hybrid → dense | 140/900 | 9.6% | 80.2% | [65.4%, 92.0%] |
| hybrid → hybrid | 140/900 | 11.2% | 100.0% | [100.0%, 100.0%] |
| hybrid → reranker | 140/900 | 10.1% | 81.2% | [68.2%, 92.6%] |
| hybrid → rcd | 140/900 | 10.6% | 89.1% | [78.4%, 97.6%] |
| reranker → bm25 | 140/900 | 12.3% | 93.8% | [85.0%, 100.0%] |
| reranker → dense | 140/900 | 10.0% | 85.4% | [72.4%, 96.1%] |
| reranker → hybrid | 140/900 | 10.8% | 87.5% | [75.6%, 97.5%] |
| reranker → reranker | 140/900 | 10.7% | 100.0% | [100.0%, 100.0%] |
| reranker → rcd | 140/900 | 10.6% | 91.7% | [83.1%, 98.6%] |

### semantic_fluent_false_evidence, intensity 3

| Source → target | Valid / 900 | Target ASR | ATR | ATR 95% CI |
|---|---:|---:|---:|---:|
| bm25 → bm25 | 75/900 | 7.9% | 100.0% | [100.0%, 100.0%] |
| bm25 → dense | 75/900 | 7.9% | 98.6% | [95.0%, 100.0%] |
| bm25 → hybrid | 75/900 | 7.9% | 100.0% | [100.0%, 100.0%] |
| bm25 → reranker | 75/900 | 8.0% | 100.0% | [100.0%, 100.0%] |
| bm25 → rcd | 75/900 | 7.9% | 98.6% | [95.0%, 100.0%] |
| dense → bm25 | 75/900 | 7.9% | 98.6% | [94.7%, 100.0%] |
| dense → dense | 75/900 | 7.9% | 100.0% | [100.0%, 100.0%] |
| dense → hybrid | 75/900 | 7.9% | 98.6% | [94.7%, 100.0%] |
| dense → reranker | 75/900 | 8.0% | 100.0% | [100.0%, 100.0%] |
| dense → rcd | 75/900 | 7.9% | 100.0% | [100.0%, 100.0%] |
| hybrid → bm25 | 75/900 | 7.9% | 100.0% | [100.0%, 100.0%] |
| hybrid → dense | 75/900 | 7.9% | 98.6% | [95.0%, 100.0%] |
| hybrid → hybrid | 75/900 | 7.9% | 100.0% | [100.0%, 100.0%] |
| hybrid → reranker | 75/900 | 8.0% | 100.0% | [100.0%, 100.0%] |
| hybrid → rcd | 75/900 | 7.9% | 98.6% | [95.0%, 100.0%] |
| reranker → bm25 | 75/900 | 7.9% | 98.6% | [94.7%, 100.0%] |
| reranker → dense | 75/900 | 7.9% | 98.6% | [95.1%, 100.0%] |
| reranker → hybrid | 75/900 | 7.9% | 98.6% | [94.7%, 100.0%] |
| reranker → reranker | 75/900 | 8.0% | 100.0% | [100.0%, 100.0%] |
| reranker → rcd | 75/900 | 7.9% | 98.6% | [95.1%, 100.0%] |

## Scientific caveats

- Aggregate arithmetic and provenance have been checked by the built-in runner and
  a separate aggregate-schema audit. Independent content/factual review is NOT automated.
- Semantic-construction acceptance does not establish factual truth or falsehood.
- The original seed-42 interrupted model call remains indeterminate; the separate
  verified replacement must not be represented as reconstructing that original call.
- Confidence intervals are not multiplicity-adjusted and do not automatically prove
  RCD superiority or generalization to a different dataset/model.
- Keep raw evidentiary files and the original execution environment offline and backed up.
- This publication contains no held-out examples, only aggregated held-out results.

`aggregate_public.json` supplies all 240 grouped-condition records, 80 clustered
confidence intervals, backend-call accounting, and non-reversible provenance hashes.
