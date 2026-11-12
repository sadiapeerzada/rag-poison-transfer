# E2 matched-defense development — actual three-arm reuse, fourth arm incomplete

Recorded 12 November 2026. **This is not a completed four-arm or 25-question E2 pilot.** Real historical Dense/Reranker/RCD observations were matched and analyzed for the frozen five-question exploratory smoke. The fixed-rewrite control is implemented and synthetic-tested, but no new rewrite retrieval or Qwen outcome was produced under the resource stop. No RCD parameters or original experiments were changed.

## Implemented fixed controls

| Arm | Fixed procedure | Generator-visible depth |
|---|---|---:|
| D1 Dense | Original question; pinned BGE dense model | 3 |
| D2 Dense + fixed rewrite | Literal `Background evidence about: {question}`; one dense lookup; final QA asks the original question | 3 |
| D3 Dense + cross-encoder | Original Dense candidate pool 20, pinned MiniLM cross-encoder; stable dense order on ties | 3 |
| D4 frozen RCD | Candidate k=10, rewrite count=3, weights consistency .45 / redundancy .00 / conflict .10 / base-rank .45 | 3 |

The rewrite is deliberately simple and non-generative, with **zero rewrite-model calls**; it is not claimed optimal. The code verifies snapshots and full backend/prompt bindings before inference, preserves immutable private input checkpoints, and uses the shared bounded Qwen runner. Live resource guards cover future retrieval model allocations too. Real D2 model execution remains unverified in this session.

The four arms share the frozen E1 pilot IDs, targets, original M3 poison-document instances, full-300 selected union corpora, Qwen snapshot/configuration and scoring rules. M1/M2 corpora are not silently substituted. Both BM25-selected and Dense-selected corpora are retained as blocks. Generator evidence is the ordered saved top three; deeper diagnostic evidence is kept separate. The five questions were previously examined, including E3 and E1 historical analysis; this is exploratory reuse, not an untouched cohort.

## Executed and verified observations

Native historical reuse supplies **336 logical clean/poisoned QA observations backed by 180 distinct physical responses**, for **168 valid matched defense positions** across D1/D3/D4. These are a subset of the **212** physical responses verified for E1, not an additional independent set of calls.

Across all four arms there are **480 assigned positions** and **224 valid-construction positions**. **56 D2 valid positions remain pending**, and failed constructions have no fabricated QA. All assigned smoke questions/seeds/strata remain represented. [The latest aggregate](E2_MATCHED_DEVELOPMENT_V4_AGGREGATE_20261112.json) contains EM/F1, target matching, exposure, clean-correct→wrong transitions, construction coverage and paired question-cluster intervals, with missing D2 rates explicitly undefined. [The initial blocked analysis](E2_MATCHED_DEVELOPMENT_AGGREGATE_20261112.json) remains preserved separately.

For orientation, averaging descriptively over the two source-selection blocks:

| Family / intensity | D1 target matching | D3 target matching | D4 target matching | Interpretation |
|---|---:|---:|---:|---|
| Lexical / 1 | 0% | 0% | 0% | Real negative historical subset, not a general defense claim |
| Lexical / 3 | 26.67% | 66.67% | 40.00% | Dense has fewer target matches here; RCD is not uniformly best |
| Semantic-fluent / 1 | 0% | 0% | 0% | Only 4/15 valid repeated-question positions per source block |
| Semantic-fluent / 3 | 0% | 0% | 0% | Zero valid constructions; no QA-based efficacy conclusion |

For lexical intensity 3, valid-only poisoned gold EM is **37.50% Dense**, **16.67% Reranker**, **41.67% RCD**, versus **50% clean EM** for all three. Thus lower target matching and higher gold utility do not rank these pipelines identically. The source-specific paired RCD−Dense target-match intervals include zero; the descriptive RCD−Reranker intervals exclude zero in this tiny subset, but they are not multiplicity-adjusted and do not establish general superiority. Repeated seeds/source blocks are not independent questions: bootstrap resamples the five question clusters, preserving repeated conditions. All E2 contrasts are exploratory; no unadjusted interval is treated as a confirmatory test.

## Historical retrieval work and limitations

| Arm | Normal wrapper calls | Normal inner retrieval operations | Diagnostic wrapper / inner operations | Normal retrieval seconds |
|---|---:|---:|---:|---:|
| D1 | 112 | 112 | 56 / 56 | 3.2083 |
| D3 | 112 | 112 | 56 / 56 | 17.2115 |
| D4 | 112 | 448 | 56 / 224 | 5.2468 |

These are real saved trace totals for the matched valid subset. Timings are historical/descriptive, exclude separately counted diagnostics and do not establish paired speedups against a future fresh D2 run. Reranker cross-encoder pair counts were not separately logged in the native measurement accounting: **UNKNOWN**, not inferred as though every wrapper call were one operation. Candidate pool 20 is the fixed implementation setting, not a measured pair-count receipt. D2's architecture uses one rewritten dense search, but no actual D2 retrieval/latency measurement is claimed.

## Resource gate, provenance and continuation

New physical Qwen calls across E1/E2: **0**; failed/retried/indeterminate Qwen calls: **0**. No Qwen initialization occurred. Following the operator's normal-pressure report, E1 v4 was actually attempted, then its live resource guard stopped preparation. The corrected no-model monitoring window still showed actual swap-ins increasing while pressure remained level 1. See [the live resource recheck](E1_RESOURCE_RECHECK_AND_V4_20261112.md). E2 did not bypass the unresolved E1 resource stop or invent its missing desired prompts.

Exact additional D2/Qwen distinct-input budget is **UNKNOWN** until safe retrieval emits and verifies the complete inputs. Fifty-six pending logical pairs are not fifty-six physical calls. The shared authorization remains capped at 200 combined physical attempts, four inference hours, 12 GiB RSS and 10 GiB Metal, with one process and immediate resource stops. Full 100–150-question studies remain unstarted and require separate approval.

Latest private E2 pilot freeze SHA-256: `135f7ba8d103936ac45bcad29bdee9c8922e7e5ff6b12c02129f478748ca2e1b`. Shared native history SHA-256: `5b5729d3750fec98d3dab478984d69186d5423e6593ddbc7c8532c30d9f52298`. Frozen execution-specific source snapshots and previous run versions are retained privately; public files contain no question IDs, prompts, answers or poison documents.

After true swap counters stabilize and the E1 input preparation passes in a new private pilot version, run:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python \
  scripts/run_e2_matched_defense_pilot.py --root "$NEW_PRIVATE_PILOT" \
  --native-root "$PRIVATE_NATIVE_ROOT" --snapshot "$QWEN_SNAPSHOT" \
  --output "$NEW_PRIVATE_E2_PREPARATION_AGGREGATE"

# Only after the E2 input seal and exact call estimate have been checked:
.venv/bin/python scripts/run_bounded_e1_e2_qwen.py \
  --root "$NEW_PRIVATE_PILOT" --snapshot "$QWEN_SNAPSHOT" --experiment E2

# Same frozen code/settings; new output filename; no replacement of checkpoints:
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python \
  scripts/run_e2_matched_defense_pilot.py --root "$NEW_PRIVATE_PILOT" \
  --native-root "$PRIVATE_NATIVE_ROOT" --snapshot "$QWEN_SNAPSHOT" \
  --output "$NEW_PRIVATE_E2_POSTRUN_AGGREGATE"
```

Finish E1 first under its prespecified subcap, then E2 with remaining shared budget. An exhausted budget or unresolved input remains incomplete; do not silently choose conditions based on new outcomes. The E2 protocol document remains a draft; only the run-specific development configuration was frozen.
