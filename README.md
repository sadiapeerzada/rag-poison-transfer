# RAG Poison Transfer

Undergraduate research by Sadia Peerzada on **the transferability of RAG corpus-poisoning attacks across retrieval pipelines and the robustness of Retrieval-Consistency Defense (RCD)**. The study asks whether malicious retrieved documents induce a selected non-gold answer, whether attacks transfer across pipelines, and how the composite RCD defense changes retrieval and answer outcomes.

The repository implements retrieval, attack construction, matched evaluation, transfer-analysis primitives and provenance validation. Implemented software, development diagnostics and completed held-out experiments are different evidence levels; none alone establishes the research hypotheses.

## Current status

**Status update: 25 October 2026, as reported by the researcher.**

- The **two-query development smoke test has completed**. It is diagnostic evidence about execution, not an effectiveness estimate or independent semantic verification.
- **Full 300-query held-out attack construction is underway** in a separate worktree, pinned to commit [`7a24a40c0a25399e1defc02844eb3a1de44b4a19`](https://github.com/sadiapeerzada/rag-poison-transfer/commit/7a24a40c0a25399e1defc02844eb3a1de44b4a19).
- **Held-out poisoned Dense/RCD evaluation and final results are not reported as complete.** No final ASR, defense ranking or significance claim is made here.
- The active worktree is `/private/tmp/rag-week9-frozen-protocol`. Do not edit, reset, clean, switch branches, install dependencies or run additional commands there while the experiment is running. Use another checkout for documentation and development.

This README update does not inspect the running process or its external artifacts. Smoke completion and construction progress above are researcher-reported; counts, timings and outcomes must be established from the eventual sealed artifacts. Status can become stale while a long run proceeds.

## Research architecture

Retrievers share a corpus build/retrieve interface. [`run.py`](run.py) routes configurations to the following implemented components:

| Component | Implementation | Role in the frozen Week 9–10 comparison |
| --- | --- | --- |
| **BM25** | Sparse lexical retrieval using `rank_bm25`; [`bm25.py`](src/retrieval/bm25.py) | Available as a baseline/transfer component and as RCD's sparse signal; not a separate evaluated arm in the 12 cells. |
| **Dense** | Sentence-transformer embeddings, using `BAAI/bge-small-en-v1.5` in the frozen configs; [`dense.py`](src/retrieval/dense.py) | Undefended comparison arm. |
| **Hybrid** | Reciprocal rank fusion of BM25 and Dense rankings, rather than addition of incomparable raw scores; [`hybrid.py`](src/retrieval/hybrid.py) | Implemented baseline/transfer component; not an arm in the 12 cells. |
| **Reranker** | Dense candidates rescored by a cross-encoder; [`reranker.py`](src/retrieval/reranker.py) | Implemented baseline/transfer component; not an arm in the 12 cells. |
| **RCD** | Dense primary retrieval, BM25 agreement, query-rewrite consistency and document scoring; [`retriever.py`](src/defenses/rcd/retriever.py) | One composite defended arm, compared with Dense. |

RCD is not a collection of independently evaluated defenses. Its frozen settings are candidate depth **10**, up to **three additional unique query rewrites**, and:

```text
score = 0.45 × consistency + 0.00 × redundancy
        − 0.10 × conflict + 0.45 × base-rank score
```

Consistency combines document presence across retrieval signals, cross-retriever rank stability and rewrite-rank stability. Redundancy scoring is implemented but has zero weight in this configuration. Conflict scoring is a narrow lexical/temporal year-disagreement heuristic, not a general contradiction or NLI model. The frozen generator receives **three evidence documents**. These settings are defined in the [Dense](configs/exp_030_hotpotqa_dense_heldout_mlx.yaml) and [RCD](configs/exp_031_hotpotqa_rcd_heldout_mlx.yaml) configurations; constructor defaults are not the frozen experiment settings.

The twelve cells measure **matched Dense/RCD comparisons**, not a completed source-to-target transfer matrix. [`run_source_target_asr`](src/attacks/asr.py) and [`transfer.py`](src/pipelines/transfer.py) provide transfer evaluation/statistics infrastructure. The API retains full source/target cohorts and leaves ATR undefined when source successes are zero. Source-aware attack construction and the original broader transfer experiments remain separate research work; naming a source pipeline does not establish source-specific optimization.

## Attack families

The threat model is poisoning the retrieval corpus with documents intended to support a selected non-gold answer, while preserving the original query, gold answer and clean documents.

- **Lexical Influential Token:** repeats question keywords and inserts a direct target-answer statement. [`lexical.py`](src/attacks/lexical.py) uses repeat factor 4 and poison-index templates in the frozen protocol. Construction requires no model generation.
- **Semantic Fluent False Evidence:** asks the generator for encyclopedia-style text affirmatively supporting the intended target. [`semantic_fluent.py`](src/attacks/semantic_fluent.py) uses prompt v3, a 150-token cap and at most two attempts per document under the declared revision policy.

The semantic validator is `conservative-text-heuristic/v4`. It screens for direct support, competing gold answers, corrections, disclaimers and uncertainty. Passing means **`heuristically_supported_unverified`**, not independent factual verification, proof of entailment or guaranteed fluency. See the [validator report](docs/WEEK9_SEMANTIC_VALIDATION_V4.md).

The frozen selection method uses the verified development candidate pool plus declared question-local/scalar/set rules. It excludes normalized gold answers and explicitly supplied aliases, and abstains on unsupported cases. Mechanical type compatibility and non-gold status do not prove factual falsehood or complete alias exclusion. Those limitations remain part of the interpretation of targeted ASR.

## Experimental methodology

### Dataset and population

The Week 9–10 protocol uses HotpotQA's distractor setting, validation split, at dataset revision:

```text
1908d6afbbead072334abe2965f91bd2709910ab
```

Development and held-out populations are separate selections from that split, not the official dataset train/test boundary. The verified **300-query development** artifact is [`exp_025`](results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl). The fixed **300-query held-out** population, order, selection seed **42** and provenance are recorded in [`exp_027_hotpotqa_heldout_manifest.json`](configs/exp_027_hotpotqa_heldout_manifest.json). Development/held-out ID disjointness is checked. Query IDs, original gold labels and gold document IDs are preserved; unsuccessful cases are not dropped, replaced or resampled after outcomes.

The provided HotpotQA contexts form a development-scale distractor corpus; this is not unrestricted retrieval over all of Wikipedia. Loaders for HotpotQA, 2WikiMultiHopQA and NQ-open are implemented in [`loaders.py`](src/data/loaders.py). Their availability is not evidence that every planned dataset experiment has been completed. Held-out 2Wiki replication remains a separate pending milestone.

### Declared matrix

| Dimension | Frozen values |
| --- | --- |
| Attack family | Lexical Influential Token; Semantic Fluent False Evidence |
| Intensity | Exactly 1 or exactly 3 valid poison documents per query |
| Poison seed | 42, 43, 44 |
| Comparison arms | Dense and RCD, sharing the same frozen poison instance |
| Population per cell | All 300 held-out queries, including construction failures |

Two families × two intensities × three seeds produce **12 cells**, each with two matched arms. QA runtime seed is 42. Target selection is deterministic under the versioned seed derivation. The protocol explicitly uses greedy MLX decoding at temperature 0; seeds do not guarantee distinct generated texts or bit-for-bit reproducibility across hardware. Repeated seeds for one question are not independent queries.

### Measurements and failure accounting

General clean-evaluation infrastructure supports gold-document Recall@1/3/5/10, MRR@1/3/5/10, nDCG@10, answer exact match (EM) and token F1. The protocol-based poisoning comparison records poison retrieval, diagnostic ranks and actual generator-visible exposure separately, plus complete QA responses, extracted answers, prompts/hashes, timings and retrieval accounting. Independent diagnostic top-10 and generator-visible top-3 rankings need not be prefixes.

| Protocol outcome | Meaning |
| --- | --- |
| `target_construction_failed` | No compatible target under the frozen rules. |
| `semantic_construction_failed` | The required document count was not achieved within the declared retries. Valid partials are archived but none are injected for that query. |
| `valid_construction` | Exactly the required number of documents passed the mechanical checks; factual or semantic correctness is not independently established. |

Infrastructure errors stop completion rather than being relabeled as scientific construction failures. Results report attempted, valid, failed and actually evaluated counts separately.

| Metric | Denominator and interpretation |
| --- | --- |
| **End-to-end targeted ASR** | Target matches among valid evaluated attacks / **all 300 queries**. Failed constructions contribute zero successes, **not evidence of successful defense**. |
| **Conditional targeted ASR** | Target matches / valid constructions. |
| **Untargeted ASR (degradation definition)** | Clean-correct to poisoned-incorrect transitions / valid constructions; also reported conditional on clean-correct valid cases. It is not arbitrary answer disagreement. |
| **Poison Retrieval Rate (PRR@1/3/5/10)** | Queries retrieving at least one query-specific poison at that diagnostic cutoff / valid constructions. |
| **Generator-visible exposure** | Queries with query-specific poison in actual generation evidence / valid constructions. |
| **ASR given exposure** | Target matches among exposed valid attacks / exposed valid attacks. |
| **EM/F1** | Actual clean and poisoned answer scores over valid constructions. No invented scores for failed constructions. |

Failed cases retain explicit records for both arms with null measurements; they are not silently treated as poisoned evaluations. Zero conditional denominators are null. Conditional valid-construction summaries do not replace the all-300 primary population.

The failure-aware aggregator computes paired Dense-minus-RCD uncertainty using **2,000 query-cluster bootstrap resamples**, seed **20261025**, with percentile 95% intervals. Each sampled query retains all poison seeds and both arms. Conditional denominators are recomputed per replicate, and undefined replicates are counted. The population remains 300 unique questions, not 900 independent observations.

## Research progress

| Stage | Implementation and evidence boundary |
| --- | --- |
| Retrieval and clean baselines | BM25, Dense, Hybrid and cross-encoder reranking implemented; historical baseline artifacts remain under `results/` and `experiments/`. Historical schemas/settings must be checked before comparison. |
| Week 7–8 | Composite RCD implemented and frozen. [`exp_026`](configs/exp_026_hotpotqa_rcd_v1_mlx_frozen_current.yaml) records the corrective development configuration. Development utility and exploratory poisoned pilots do not establish held-out robustness. See the [validation report](docs/WEEK7_8_RCD_VALIDATION_REPORT.md). |
| Week 9–10 implementation | Abbreviation-safe extraction, complete measurement records, zero-source-success transfer handling, semantic validation revisions and a failure-aware construction protocol implemented. |
| Development smoke | Two-query diagnostic completed, as reported by the researcher; no effectiveness conclusion is drawn. |
| Held-out study | All-300 attack construction underway at the pinned commit. No completed held-out poisoned evaluation or final aggregate is claimed. |
| Further research | Broader source-to-target transfer, held-out 2Wiki replication and final scientific interpretation remain separate milestones. |

The README does not reproduce historical numerical result tables as current performance claims. Clean utility results, development findings, recovery runs, exploratory pilots and final poisoning outcomes must remain separately labeled. Earlier reports describe their own historical scope and may predate the current status or protocol clarification.

## Reproducibility and protocol freeze

The active protocol is **`week9-outcome-independent-construction/v1`**, defined by [`week9_construction.py`](src/experiments/week9_construction.py). The [full protocol document](docs/WEEK9_FROZEN_ATTACK_CONSTRUCTION_PROTOCOL.md) specifies its rules, exact commands, schemas and limitations.

Its supervisor-approved design uses a predefined protocol rather than mandatory individually signed false-target assignments for all 300 queries. Existing independent human-review tools remain available for other experiments; the protocol pathway does not fabricate or reinterpret their approvals.

The staged workflow in [`run_week9_protocol_poison_matrix.py`](scripts/run_week9_protocol_poison_matrix.py) is:

1. **`preflight`:** verify metadata, fixed IDs, configs and development provenance without loading held-out question text or models. This is not a scientific-readiness certificate.
2. **`freeze-protocol`:** bind the rules to a clean Git commit, source/configuration hashes, dataset revision and ID fingerprints, exact local model snapshot/file hashes, and Python/package versions.
3. **`construct`:** process every declared query/cell, journal actual generation calls and retain typed failures. Construction cannot consult final Dense/RCD outcomes.
4. **Global construction seal:** freeze every cell ledger, checkpoint/journal, query/corpus fingerprint and file hash before any final Dense/RCD evaluation. Evaluation requires the externally supplied exact-byte seal hash and validates the complete matrix first.
5. **`evaluate`:** replay the frozen matched poison for valid constructions; retain null failure records for both arms. No target regeneration based on outcomes.
6. **`aggregate`:** require the evaluation completion hash, validate sealed/raw artifacts and recompute failure-aware metrics and paired uncertainty.

An interrupted generation intent without a response is not permission for extra retries. Sealed constructions cannot be reopened to select more favorable targets or prose. Any later methodological amendment needs a disclosed new protocol/study version; do not overwrite or pool frozen historical artifacts. Hashes establish content identity and provenance consistency, not factual truth or supervisor signatures.

## Repository structure

| Path | Purpose |
| --- | --- |
| [`run.py`](run.py), [`configs/`](configs/) | Config-driven single-pipeline QA and frozen experiment definitions. |
| [`src/retrieval/`](src/retrieval/) | BM25, Dense, Hybrid and cross-encoder reranking. |
| [`src/defenses/rcd/`](src/defenses/rcd/) | Composite RCD signals, rewrites and scoring. |
| [`src/attacks/`](src/attacks/) | Lexical/semantic attacks, nomination, review and checkpoint infrastructure. |
| [`src/experiments/week9_construction.py`](src/experiments/week9_construction.py) | Protocol rules, failure accounting and paired aggregation primitives. |
| [`src/evaluation/`](src/evaluation/), [`src/pipelines/`](src/pipelines/) | Metrics, lossless QA records, generator backends and transfer statistics. |
| [`src/data/loaders.py`](src/data/loaders.py) | Dataset loading, canonical document IDs and cohort selection. |
| [`scripts/`](scripts/), [`tests/`](tests/) | Workflow entrypoints, audits and regression tests. |
| [`docs/`](docs/) | Protocol definitions, implementation reports and historical review material. |
| [`results/`](results/), [`experiments/`](experiments/) | Tracked historical artifacts; current large run outputs are external and must not be inferred from file names alone. |
| [`data/raw/toy_smoke_dataset.json`](data/raw/toy_smoke_dataset.json) | Small checked-in toy input for mock-generation plumbing checks. |

The older [`run_week9_heldout_poison_matrix.py`](scripts/run_week9_heldout_poison_matrix.py) and [`aggregate_week9_multiseed_results.py`](scripts/aggregate_week9_multiseed_results.py) retain their reviewed-target/legacy workflows. Use the **protocol runner's stages** for the current failure-aware study; do not mix incompatible artifact schemas or run the older matrix command against current artifacts.

## Setup and safe inspection

Use a **separate, inactive development checkout**. Do not perform setup or testing in the running experiment worktree. Python must support the repository's Python 3.10+ annotation syntax; experimental replay must match the frozen runtime rather than merely satisfying that minimum.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

[`requirements.txt`](requirements.txt) is an **unpinned development** dependency list: `rank_bm25`, PyYAML, pytest, sentence-transformers, datasets and NumPy. It is not the frozen experimental environment. On Apple Silicon, the real MLX backend additionally requires:

```bash
.venv/bin/python -m pip install mlx-lm
```

The repository also implements a CUDA Transformers/bitsandbytes backend. [`requirements-kaggle-lock.txt`](requirements-kaggle-lock.txt) records the separate Kaggle environment; it is not the Apple Silicon runtime lock. Dataset/model downloads require appropriate network access during preparation. Offline runs require their actual cached inputs. The frozen Week 9–10 protocol uses `mlx-community/Qwen2.5-7B-Instruct-4bit`, a complete revision-named local model snapshot and explicit greedy sampling.

Read command help or run metadata-only preflight in the inactive checkout:

```bash
.venv/bin/python scripts/run_week9_protocol_poison_matrix.py --help
.venv/bin/python scripts/run_week9_protocol_poison_matrix.py preflight --scope development
.venv/bin/python scripts/run_week9_protocol_poison_matrix.py preflight --scope heldout
```

A separate **toy**, mock-generator QA check is available:

```bash
.venv/bin/python run.py --config configs/exp_000_smoke.yaml
```

That command writes toy run artifacts; it is not the completed real-model development smoke or a held-out experiment. Commands that freeze, construct or evaluate a real run are intentionally kept in the [protocol instructions](docs/WEEK9_FROZEN_ATTACK_CONSTRUCTION_PROTOCOL.md). They require actual trusted hashes and model paths, not copied placeholder values. Do not launch another matrix or alter the active run to try these examples.

## Software verification

From an inactive checkout with dependencies and required local caches available:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts tests

git diff --check
```

For the protocol-specific synthetic regression suite:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  .venv/bin/python -m pytest -q tests/test_week9_frozen_construction_protocol.py
```

The implementation report records 981 full-suite tests passing at the pinned implementation stage. That is historical software verification, not a claim that tests were rerun during this README-only update or that scientific validity follows from passing tests. Synthetic test fixtures are not experimental observations or genuine reviewer decisions.
