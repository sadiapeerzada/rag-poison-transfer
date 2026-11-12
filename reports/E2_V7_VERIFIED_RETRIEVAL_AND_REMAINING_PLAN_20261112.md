# E2 v7 — real fixed-rewrite retrieval verified; generation remains blocked

**EXECUTED:** real local fixed-rewrite Dense retrieval on the frozen five-question exploratory smoke, retaining all assigned families, intensities, seeds and source-selection blocks. **VERIFIED:** all 112 logical clean/poisoned inputs match their exact corpora, targets, original QA questions, ordered top-three evidence and frozen backend/output settings. **INCOMPLETE:** no new D2 Qwen answer was produced, and neither E1 nor E2 is a completed five- or 25-question generation pilot.

The fixed rewrite remains `Background evidence about: {question}`. Final QA retains the original question. Dense/Reranker/frozen RCD baselines use the same original M3 selected union corpora, target assignments and pinned generator. Reranker candidate pool remains 20 and all arms expose three passages; RCD parameters are unchanged. No method was tuned against new target outcomes.

The original E2 preparation repeatedly encoded the same text. Its partial checkpoints and exact source were preserved. The final run uses a frozen per-text cache of the same normalized pinned encoder, preserving document order and dtype; functional equivalence is synthetic-tested. This is an embedding cache, not an answer cache or new attack-selection rule. All resulting real retrieval evidence/prompts were checkpointed before any D2 generation.

## Actual new retrieval work

| Measurement | Observed value |
|---|---:|
| Rewritten Dense searches / wrapper calls | **112 / 112** |
| Distinct complete D2 generator bindings | **60** |
| Distinct clean / poisoned bindings | **4 / 56** |
| Rewrite-model/Qwen calls | **0** |
| Text lookup requests | 344,746 |
| Unique texts encoded | 3,886 |
| Cache hits | 340,860 |
| Encoder method invocations | 23 |
| Build/encoding time sum | 19.61148 seconds |
| Retrieval lookup time sum | 0.18027 seconds |
| Peak preparation RSS | 1,704,034,304 bytes ≈ 1.59 GiB |
| Peak preparation Metal | 1,135,984,640 bytes ≈ 1.06 GiB |

These are real measurements, not synthetic research evidence. They exclude separately performed model initialization, snapshot hashing and statistical aggregation. Warm cached lookup timings are not comparable to uncached historical Dense/Reranker/RCD timing as an unqualified speedup; no such comparison is claimed. Each trace and input checkpoint is private. `new_D2_retrieval_work` describes work in that preparation invocation; a later read-only aggregation pass must not count it as newly repeated work.

[The preparation aggregate](E2_V7_VERIFIED_INPUT_PREPARATION_20261112.json) also retains the real historical three-arm results: 168 complete valid defense positions, backed by 180 historical physical responses (336 logical QA observations), with all 56 D2 valid positions explicitly pending. Those 180 responses are a subset of E1's 212 verified responses and are not new independent inference. The earlier security–utility results remain descriptive historical findings; there is no new four-arm efficacy result.

## Independent input checks and exact budget

[The input-verification receipt](E1_E2_V7_INPUT_VERIFICATION_20261112.json) reconstructed the actual full selected corpora and verified every evidence document ID/text, original question prompt, target assignment, top-k and generator limit. It rechecked pinned plan/history files and exact cross-record-ID reuse. There were **zero UNVERIFIED bindings** in the combined complete-input comparison.

Under the frozen conservative full-binding reuse contract:

- E1: **432 distinct bindings**, **212 reusable historical physical responses**, **220 missing bindings**.
- Additional D2 control: **60 distinct missing bindings**.
- Combined: **492 bindings**, **212 reusable**, **280 missing**; no historical response is counted as new independent inference.

[The model-call budget](E1_E2_V7_MODEL_CALL_BUDGET_20261112.json) is exact for these complete-binding inputs, not an inferred irreducible prompt-only minimum. It is for the five-question smoke, not the full 25-question cohort. The full-smoke 280-input requirement exceeds the authorized 200-call session cap even if resource conditions improve. The prespecified balanced prefix allocates 156 E1 calls and conditionally 44 E2 calls; remaining inputs stay explicitly pending. No conditions are silently removed or resampled based on answers.

Full 25-question input/call requirements remain UNKNOWN until those additional retrieval inputs are prepared. A 100–150-question main experiment is unapproved and unstarted; no cost extrapolation or untouched-cohort claim is made.

## Exact model-load blocker

The operator-authorized single additional Qwen initialization failed the **system memory-pressure gate: observed level 2**. RSS and Metal were below their numeric caps, swap-outs did not increase, and no thermal warning was recorded. See [the exact retry measurements](E1_ONE_AUTHORIZED_RETRY_20261112.md).

**New Qwen generation attempts/responses: 0 / 0.** There were two initialization attempts over the session, both stopped before generation, with conservative total Qwen initialization wall charge 17.45168 seconds. The one additional retry permission is consumed. E2 preparation did not initialize Qwen again or relax any guard/model parameter.

## Pins and handoff

| Artifact | SHA-256 |
|---|---|
| Current pilot | `26d055e46a09307f92ddb2e3ba7b14cc2d03abf01bcd82da7a40cbaba16a5e49` |
| Source-selection seal | `daa6e6cb42a9d6a11334728ae34953fd3711320be0e65d76609c6c60cb7a4a31` |
| E1 complete input plan | `b1c41c4c2ba10b951f28bd3f340e1cb8aa7a41b6376fdead301a8adfff125e84` |
| D2 complete input plan | `6a769dc60373ea616e52c04fed4fee1febcd4fea465d9cd08b8a03febf4ef91e` |
| D2 run-specific freeze | `83c51a7e36c2647f5d7642ed447644b7aa919ab3fb6874134112ba0c707455eb` |
| D2 balanced dispatch | `137e6b3fee8e2ce88ee3a72c88e978f20ebcfcbbaaa909b0a1d62e1754c2cde9` |
| Shared native history | `5b5729d3750fec98d3dab478984d69186d5423e6593ddbc7c8532c30d9f52298` |

The scientific input files are byte-identical across the derived versions; only explicitly recorded diagnostic metadata was revised before the single retry. Copies preserve physical-call identities and do not reset the shared authorization ledger. Raw questions, evidence, prompts, outputs and user-specific paths remain private.

After additional resource headroom **and new explicit initialization approval**, the existing verified private run can continue without regenerating candidates or redoing retrieval. These are future commands, not permission to bypass the consumed retry:

```bash
# Only after the resource/initialization approval prerequisite is satisfied:
.venv/bin/python scripts/run_bounded_e1_e2_qwen.py \
  --root "$VERIFIED_PRIVATE_RUN" --snapshot "$QWEN_SNAPSHOT" --experiment E1

# E2 only with remaining shared call/time allowance and initialization approval:
.venv/bin/python scripts/run_bounded_e1_e2_qwen.py \
  --root "$VERIFIED_PRIVATE_RUN" --snapshot "$QWEN_SNAPSHOT" --experiment E2
```

A failed/indeterminate generation intent halts automatic resume. Completed observations remain immutable. Do not delete attempt markers to obtain more calls or repeated initializations. First review the bounded partial development results once genuine responses exist; a full 25-question pilot then needs a separately validated budget. A main study additionally needs an approved 100–150 cohort/exposure policy and revised resource authorization. Historical questions remain historically exposed.
