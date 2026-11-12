# E1/E2 execution paused — 13 November 2026

The latest operator instruction prohibits another initialization, additional
Qwen inference and changes to resource limits. E3 is complete and was not rerun.
E1/E2 are partial development evidence, not completed experiments. E4/E5 work
does not consume or supersede their checkpoints.

The exact v7 private checkpoint is preserved. Its pilot freeze SHA-256 is
`26d055e46a09307f92ddb2e3ba7b14cc2d03abf01bcd82da7a40cbaba16a5e49`;
selection seal is `daa6e6cb42a9d6a11334728ae34953fd3711320be0e65d76609c6c60cb7a4a31`;
E1 plan is `b1c41c4c2ba10b951f28bd3f340e1cb8aa7a41b6376fdead301a8adfff125e84`;
E2 plan is `6a769dc60373ea616e52c04fed4fee1febcd4fea465d9cd08b8a03febf4ef91e`.
All original versions and failed preparation/initialization records remain.

The prepared five-question subset has 432 distinct E1 input bindings: 212
historical physical-response origins are verified reusable, and 220 bindings
lack responses. History has 392 logical records, not 392 physical calls. E2
adds 60 prepared Dense + Rewrite bindings (4 clean, 56 poisoned), representing
112 logical references. Dense, Reranker and RCD historical observations remain
available only where complete bindings match. These 280 missing binding records
are **not** an irreducible physical-call budget. Full 25-question input coverage
and the corresponding new-call budget remain unverified/UNKNOWN. Never reuse
on question ID alone or count historical responses as new inference.

No new Qwen generation calls, failed generation attempts, generation retries or
indeterminate generation intents were recorded. Two earlier model initialization
attempts stopped, without generation. The second stop explicitly recorded
memory pressure level 2: RSS 1.53 GiB, Metal allocation 3.99 GiB, unchanged
swap-outs and no thermal flag. Its preflight had 5.99 GiB available RAM and
22.42 GiB free disk; passing idle checks did not predict a safe model load.
The later no-model readiness check had about 4.98 GiB available RAM. No further
initialization was attempted after the latest pause instruction.

Frozen requirements remain Qwen2.5-7B-Instruct MLX 4-bit snapshot
`c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`, original file hashes, tokenizer/chat
template, generator/scoring code, greedy decoding, seed 42 and 64 output tokens;
MLX 0.32.2 / mlx-lm 0.31.3 in the recorded environment. Preserve all E1 selection
and E2 rewrite/cache/input bindings, including full poisoned-corpus identity,
ordered generator evidence and backend configuration. No RCD redesign or
smaller model/token configuration is authorized to make execution fit.

Resume requires fresh explicit authorization resolving the governing execution
budget, a safely provisioned environment with verified frozen bindings, and
renewed resource validation. Retain one inference process, RSS ≤12 GiB, Metal
≤10 GiB, normal memory pressure, no new swap-outs, thermal stability and disk
headroom. Existing code/guards and the historical 200-call/four-hour plan are
unchanged. The earlier uncapped grant is preserved with a separate private
`SUPERSEDED_DO_NOT_EXECUTE` revocation record; unpublished code for that grant
was stashed and is not part of this correction. Do not use it to resume.

Before any future generation, rehash the checkpoint, audit exact reuse and
remaining prepared bindings, reconcile physical-call ledgers, authorize a
concrete dispatch plan, then checkpoint each completed observation. Full-cohort
missing inputs must first be materialized and verified without changing source
selection or frozen protocols. A safe initialization is a prerequisite, not an
experimental observation or permission to repeatedly retry an unsafe load.
