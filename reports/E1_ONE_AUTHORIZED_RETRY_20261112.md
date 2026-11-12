# Single authorized Qwen initialization retry — exact resource outcome

**Result: initialization did not pass the resource gate. No generation call started, and no new Qwen response was produced. No further retry was attempted.**

The operator permitted one additional carefully monitored initialization, keeping the frozen model, sampler, output-token limit, methodology and resource caps unchanged. Before this attempt, all five-question E1 scientific inputs were copied byte-identically from the verified preparation; only diagnostic metadata/checksums were revised. The guard's resource predicates and thresholds were not weakened. The earlier stop's generic pressure/thermal message cannot identify its precise past disjunct; it remains recorded as such.

The new initialization recorded the precise failing predicate: **`memory_pressure_level != 1`, observed level 2**. Both independent live monitors captured the same event. This was one initialization, not two attempts.

| Measurement | Actual value |
|---|---:|
| Idle pressure samples | 1, 1, 1 |
| Available RAM after idle check | 6,435,962,880 bytes ≈ 5.99 GiB |
| Free disk before attempt | 24,069,664,768 bytes ≈ 22.42 GiB |
| Initial Metal policy headroom | 10 GiB |
| Peak process RSS | 1,643,085,824 bytes ≈ 1.53 GiB |
| Peak Metal allocation | 4,287,507,464 bytes ≈ 3.99 GiB |
| Pressure at termination | **2** |
| New swap-outs | **0** (1,231,704 before and at termination) |
| Thermal warning | **False**; no CPU speed/scheduler limit recorded |
| Generation intents / responses | **0 / 0** |

Thus neither the 12 GiB RSS cap nor 10 GiB Metal cap was breached. Idle normal pressure and available RAM did not establish that the full model load would remain at normal system pressure. The model weights were being loaded when the warning appeared; there is no resource-cleared `model.initialized.json` record. Per-process memory below its cap does not override the separate system-pressure stop.

There were two initialization attempts over this execution session: the earlier resource stop plus this one specifically authorized retry. Both stopped before generation. Their conservative combined Qwen initialization wall-time charge is **17.45168 seconds**, including one-second safety margins, against the four-hour cap. Physical generation calls, failed/retried generation calls and indeterminate generations are all **zero**. Both sessions were reconciled only after verifying no generation intents or shared call reservations; no missing answer was reconstructed.

[The machine-readable retry receipt](E1_ONE_AUTHORIZED_RETRY_20261112.json) contains exact measurements and checksums. Retry stop SHA-256: `d31fa0630f7bd698dda128a80b170c5c3d4fc6e959e516208f90863297849fbb`. Native history remains `5b5729d3750fec98d3dab478984d69186d5423e6593ddbc7c8532c30d9f52298`. Original raw checkpoints, failed stages and executed source versions remain private and immutable.

The exact E1 smoke requirement remains 220 new complete bindings, with 212 historical physical responses verified reusable; the balanced planned prefix funds 156 calls under its subcap. These are prepared inputs, not completed inference. The full 25-question pilot remains incomplete. E3 analysis is complete and the smaller E2 retrieval stage is separately executable under the same guards, without loading Qwen again.

Further generation requires enough headroom to keep pressure normal **during the actual frozen-model load**, plus new explicit initialization authorization because the one-retry permission has been consumed. Do not bypass the pressure stop, reduce model/output settings, label reused answers as new inference, or start the 100–150-question main studies. No new model initialization is performed by this report or its verification commands.
