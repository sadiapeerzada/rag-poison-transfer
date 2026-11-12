# E1 bounded development — partial historical reuse; new inference resource-blocked

Recorded 12 November 2026. **The E1 pilot is not complete. No new Qwen inference was performed.** The authorized Mac environment is present and its GPU is accessible outside the sandbox, but repeated live checks reported macOS memory-pressure level 2 (warning), with roughly 0.6 GiB swap in use. The user's hard stop prohibits starting Qwen under this condition. The preparation process stopped before allocating new retrieval models or initializing Qwen. It did not weaken model settings or ignore the warning.

## Implemented and executed

Implemented and tested a read-only native adapter, outcome-independent cohort/selection freeze, private retrieval-input preparation, a separately guarded inference runner, immutable per-call journals, and failure-aware aggregation with paired question-cluster uncertainty. The inference runner is synthetic-tested but **has not been exercised on real Qwen in this session**.

Executed the native adapter against actual private HotpotQA records and verified model snapshot bytes, historical code fingerprint from Git objects, critical retrieval/generation/scoring implementation hashes, native stage inventories, request/response hashes and QA extraction. Clean-cache entries must resolve to a real completed physical journal with matching full effective backend input, not just an identical answer. The adapter preserves native record IDs, scores and original physical origins. Diagnostic retrieval may retain ten documents; reuse uses the ordered three generator-visible documents and checks their texts against journal evidence.

The private 25-question manifest is deterministic: sort original historical IDs by SHA-256 of canonical JSON `E1-dev25-v1:` plus ID and take 25; the active smoke is the first five, without outcome or construction filtering. These questions have prior historical exposure, including E3 analysis; they are not untouched or confirmatory. Every family, intensity {1,3}, seed {42,43,44}, source {BM25,Dense} and M1/M2/M3 policy remains in the assignment. No conditions were silently dropped to fit the budget.

All 300-query policy selections were sealed before new pilot target-input access, preserving original candidate opportunities (three slots, including failures) and full-union corpus scope. M1 uses first-valid; M2 uses the recorded deterministic per-query draw; M3 uses verified source-only candidate-band screening and first-success/fallback logic. No final-target outcome is fed into selection. Final source success is measured separately on the final selected union corpus.

## Verified results and limitations

- Native export: **392 logical QA observations**, backed by **212 distinct verified historical physical responses**. These are not new independent inferences.
- Historical source-screening provenance: **4,588 physical calls** across the retained full-300 candidate/source selection design; recorded summed screening latency **17,418.44 seconds**. This is historical whole-corpus work, not the incremental cost of a standalone five-question pilot. New screening calls: **0**.
- Five-question smoke: **1,080 assigned source/policy/stratum/target positions**, **504 valid-construction target positions** and **171 completed valid target positions** through exact historical input matching. All **168 M3** valid positions resolve; **3 M1** positions resolve; M1 has **165** pending and M2 **168** pending. Positions repeat the five underlying questions, seeds and pipelines.
- All remaining valid outcomes are **pending**, not construction failures or defense successes. Construction failures stay in full-population end-to-end denominators and have no fabricated QA.
- Twelve paired policy contrasts have zero construction coverage for both policies; their zero population difference is a construction-only result, not Qwen evidence. The other policy comparisons remain incomplete. No M3 superiority or new-pilot efficacy conclusion is supported.
- New physical Qwen calls, failures, retries and interruptions: **0**. Full 25-question pilot: **NOT EXECUTED**. Exact additional distinct Qwen-input budget: **UNKNOWN**, because resource policy stopped new retrieval/input preparation. Counts of pending logical positions are not call counts.

[Aggregate metrics and paired intervals](E1_BOUNDED_DEVELOPMENT_AGGREGATE_20261112.json) retain all assignments, explicit missingness and undefined denominators. The observed M3 outcomes are real historical observations, not new model outputs; small five-question intervals are descriptive and cannot establish generalization. No RCD parameters, original protocols or original evidence changed. Earlier failed preparation versions were preserved privately; the adapter fixes are covered by synthetic score-projection and diagnostic-depth regression tests.

## Pins and execution limits

| Artifact | SHA-256 |
|---|---|
| Frozen exploratory pilot | `56a0aee2e1d42e07ac3e3119204dc7e4a563d07d6aad5739d9c4f9c97ab618d3` |
| Source-selection seal | `712f59595efd6fe79271e4fb5cec03c640acd077073e1155a0ae470acbcfa001` |
| Verified private native export | `5b5729d3750fec98d3dab478984d69186d5423e6593ddbc7c8532c30d9f52298` |

Session authorization: at most **200 combined new physical Qwen attempts**, including failures/retries; **4 inference hours including model initialization**; **12 GiB RSS / 10 GiB Metal**, one cooperating inference process; stop on warning pressure, active swap/page-outs, thermal throttling or less than 5 GiB free disk. A 160-attempt E1 subcap reserves 40 for E2. This is a compute allocation, not a change to experimental settings. Inference stays greedy, seed 42, max_tokens 64 on the exact frozen Qwen snapshot. No construction inference is requested because the candidate library already exists.

The guarded runner monitors memory, swap, disk and thermal state, checkpoints intent before every physical invocation, and checkpoints each completed response. Missing/failed responses halt automatic continuation, and attempts consume budget. Cleanly completed sessions can resume without repeating completed inputs; unresolved sessions require explicit provenance reconciliation. The cap and inference wall-clock ledger cover E1/E2 together across versioned pilot directories under the same private research parent; starting a new pilot version does not reset them. Do not relocate that shared authorization ledger or treat a new directory as a new authorization. This code has not been validated by an actual real-model run while resource-blocked.

## Local continuation after the resource warning clears

Do not close other applications automatically. Once the operator frees memory and `sysctl -n kern.memorystatus_vm_pressure_level` returns **1**, use a **new** private version directory (preserve the failed/blocked versions). Set `PRIVATE_NATIVE_ROOT` to the original transfer directory containing protocol.json/execution; `QWEN_SNAPSHOT` to its verified local snapshot; `NEW_PRIVATE_PILOT` to an unused private directory outside this repository.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  .venv/bin/python scripts/prepare_e1_native_pilot.py \
  --native-root "$PRIVATE_NATIVE_ROOT" --snapshot "$QWEN_SNAPSHOT" \
  --output "$NEW_PRIVATE_PILOT"

# Only after prepare.complete.json exists and its exact call estimate is verified:
.venv/bin/python scripts/run_bounded_e1_e2_qwen.py \
  --root "$NEW_PRIVATE_PILOT" --snapshot "$QWEN_SNAPSHOT" --experiment E1

python3 scripts/aggregate_e1_bounded_pilot.py --root "$NEW_PRIVATE_PILOT" \
  --output "$NEW_PRIVATE_AGGREGATE_FILE"
```

The existing five-question resource-blocked artifacts cannot be represented as a finished preparation plan. Do not invoke the inference runner on them. Full 100–150-question experiments remain unauthorized and unstarted; they require a separate cohort/exposure review and revised compute approval.
