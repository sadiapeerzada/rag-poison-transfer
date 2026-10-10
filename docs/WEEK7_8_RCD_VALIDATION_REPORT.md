# Week 7–8 RCD Validation Report

## Scope

This report records the current Retrieval-Consistency Defense (RCD) implementation
and the available clean-baseline and poisoned-pilot artifacts. A clean retrieval
baseline measures retrieval and answer performance; it does not, by itself,
establish resistance to poisoning.

## Frozen RCD configuration

The held-out recovery configuration records these values:

| Parameter | Value |
|---|---:|
| Candidate pool size | 10 |
| Maximum additional rewrites | 3 |
| Consistency weight | 0.45 |
| Redundancy weight | 0.00 |
| Conflict weight | 0.10 |
| Base-rank weight | 0.45 |

These are reported as the frozen experiment settings, not as proof that the
defense is effective. Do not tune these settings against the held-out results.

Rewrite generation may return fewer than the configured maximum when unique
rewrites are unavailable. The implementation excludes the original query and
deduplicates rewrites; therefore, describe this as **up to three additional
unique rewrites**, not exactly three.

## Available experiment artifacts

### `exp_028`: incomplete clean run

`results/exp_028_hotpotqa_rcd_v1_mlx_heldout.jsonl` currently contains 17 records
and 17 unique query IDs. It is incomplete relative to the intended 300-query
held-out set and must not be reported as a complete held-out result.

### `exp_028b`: clean held-out recovery baseline

Artifacts:

- `configs/exp_028b_hotpotqa_rcd_v1_mlx_heldout_recovery.yaml`
- `results/exp_028b_hotpotqa_rcd_v1_mlx_heldout_recovery.jsonl`
- `results/exp_028b_hotpotqa_rcd_v1_mlx_heldout_recovery.summary.json`

The JSONL contains 300 records and 300 unique query IDs. The summary reports
300 queries, 2,958 unique retrieved documents, and no poison documents
(`attack_family: none`, `n_poison: 0`, `poison_rate: 0`).

Reported metrics:

| Metric | Value |
|---|---:|
| Exact match (EM) | 0.4133 |
| Answer F1 | 0.5214 |
| Recall@3 | 0.7567 |
| Recall@10 | 0.9433 |
| MRR@10 | 0.9181 |
| nDCG@10 | 0.8562 |

The summary records dataset revision
`1908d6afbbead072334abe2965f91bd2709910ab` and held-out query-ID fingerprint
`76671f6b9a70140578f2b0b6ac405eb3199235bc4d051e62d5896c715454e2df`.
These are clean-baseline results, not poisoning-defense results.

### `exp_029`: exploratory poisoned pilot

`results/exp_029_rcd_poisoned_pilot_n10.json` records a 10-query pilot using
the `semantic_fluent_false_evidence` attack family and RCD.

| Reported field | Value |
|---|---:|
| Query count | 10 |
| Poison documents | 10 |
| Overall ASR | 0.10 (1/10) |
| ASR given retrieved | 0.10 |
| ASR given not retrieved | Undefined (`null`) |
| Poisoned documents retrieved | 10/10 |
| Untargeted degradation rate | 0.00 |

Because every poisoned document was retrieved, the conditional ASR for cases
where poison was not retrieved cannot be estimated from this pilot. The
10-query sample is exploratory and is not held-out confirmation. The reported
zero untargeted degradation must not be generalized beyond this pilot.

## Interpretation and limitations

1. The 300-query `exp_028b` run is the complete clean baseline currently
   available; the 17-record `exp_028` run is incomplete.
2. The clean baseline cannot establish attack success rate or poisoning
   resistance.
3. The poisoned pilot is too small to support a strong efficacy claim.
4. Report attack-specific outcomes separately from clean retrieval metrics.
5. Preserve the frozen configuration for subsequent evaluation and report
   query-set identity, dataset revision, code provenance, and run metadata.
6. For confirmatory evaluation, use a clean, reproducible checkout and record
   both the Git commit and whether the working tree is clean. Do not treat a
   commit SHA alone as complete provenance when uncommitted code changes were
   present during a run.
