# E1 resource recheck and private v4 attempt

After the operator reported normal pressure, actual local preflight checks passed: pressure level 1, 0.033 GiB preflight RSS, 0 GiB Metal allocation, accessible GPU, 20.38 GiB free disk and no reported thermal warning. A new separately versioned private v4 preparation was executed under a live resource guard. The frozen model, candidate opportunities, five-question smoke prefix and full experimental dimensions were unchanged.

The process completed native verification/export and one real retrieval checkpoint, then stopped with exit 75 before completing generator-input preparation or initializing Qwen. Recorded peak RSS was **889,929,728 bytes (0.829 GiB)** and Metal use **1,523,712 bytes (0.00142 GiB)**. New Qwen physical attempts, failed Qwen attempts, retries and indeterminate Qwen calls were all **zero**. This is not a newly executed Qwen pilot.

The first guard conservatively conflated general page-outs with swapping. That implementation issue was corrected and regression-tested: the current guard monitors actual **Swapins + Swapouts** counters; general page-outs alone cannot trigger a swapping stop. Apple's [native VM statistics definitions](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/mach/vm_statistics.h) distinguish these counters. The original stop receipt remains unchanged; its reason string must not be interpreted as proving which component increased.

A subsequent immutable 25-second no-model stability window using the corrected counters still **failed**: pressure stayed level 1, Swapouts stayed 349,996, but Swapins increased **76,801 → 77,095**. Thus normal pressure did not establish the no-active-swapping condition required by the operator. No Qwen initialization was attempted, and no resource restriction was weakened.

| Artifact | SHA-256 |
|---|---|
| v4 frozen exploratory pilot | `e234916143b64f41994c7201b4242b7b9894dbc5c2a3980bc52cbba486158d62` |
| v4 source-selection seal | `7415537b8141244861f058339e4c4a9cec622683ba45a67fc5d92e6523373839` |
| Verified native history | `5b5729d3750fec98d3dab478984d69186d5423e6593ddbc7c8532c30d9f52298` |
| Post-stop no-model stability receipt | `9ca069f34668c3a72ea559bf8f94454ad4f1b43e3997fa8e00079c569c8ec104` |

[The v4 aggregate](E1_BOUNDED_DEVELOPMENT_V4_AGGREGATE_20261112.json) retains the same genuine historical subset: 212 verified historical physical responses, 171 completed valid target positions out of 504 valid positions, with incomplete M1/M2 comparisons explicitly missing. The 25-question pilot is incomplete. Additional distinct Qwen input requirements remain **UNKNOWN**, because the resource stop prevented the required new retrieval/prompt preparation. Pending logical positions are not physical-call estimates.

The updated preparer verifies the actual retrieval-model snapshot bytes, uses the shared one-model lease, guards real retrieval allocations, checkpoints completed retrieval observations and pins the resource-guard implementation for future pilot versions. Existing blocked versions and their historical code hashes remain recoverable; no original evidence was overwritten.

Continuation uses the commands in [the initial execution report](E1_BOUNDED_DEVELOPMENT_EXECUTION_20261112.md), with a new private version directory after real swap-in/out counters stabilize and pressure is level 1. `prepare.complete.json` and a verified distinct-input estimate must exist before the bounded Qwen runner is invoked. The same authorization still permits at most 200 combined new Qwen attempts and four inference hours; none of those attempts has been consumed. This does not authorize the 100–150-question main studies.
