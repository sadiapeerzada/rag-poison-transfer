# 2Wiki 300-query paired Dense/RCD evaluation: execution-completion checkpoint

> **Later checkpoint (8 November 2026):** The 22,446-file integrity audit passed and the frozen aggregator returned `validated_aggregate_written`. The statistical findings are published separately in the [2Wiki Dense/RCD scientific results report](2wiki_300_dense_rcd_scientific_results_2026-11-08.md). The remaining audit/aggregate tasks below document the **original execution handoff**, not their current status. Full off-device backup restoration, semantic validity, and source-crafted transfer are still pending.

**Recorded:** 8 November 2026 (Asia/Kolkata).  
**Evidence status:** Author-supplied local terminal/supervisor log; **post-run independent evaluation-artifact audit and scientific aggregation remain pending**.  
**Experiment:** Historically risk-disclosed 2WikiMultiHopQA replication. Do not represent this cohort as independently certified untouched or prospectively unexposed.

## Verified from the supplied terminal output (not from uploaded raw result files)

| Item | Reported completion |
| --- | --- |
| Bounded query-arm evaluation batches | **288/288** |
| Paired Dense/RCD cell summaries | **12/12** |
| Native evaluation completion manifest | **Present**; supervisor reported `status: complete` |
| Evaluation completion manifest SHA-256 | `db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519` |
| Construction cells already frozen | 12/12; 3,600 attempted construction records |
| Frozen source commit used by local run | `b1466db04c4f8f0314c7e537d8e7ec390c8c3b29` |
| Frozen protocol SHA-256 | `40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4` |
| Construction seal SHA-256 | `e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44` |

The local supervisor emitted `evaluation_completion_sha256` with the value above, followed by a `shasum -a 256` line for `evaluation.complete.json` reporting the same digest. The supervisor's final text says **"EVALUATION COMPLETED. Native completion manifest present."** and **"Independently pin and audit the completion SHA-256 BEFORE running aggregate."**

**Subsequent operator verification (same Mac, separate shell command):** after the supervisor finished, the operator ran `shasum -a 256 "$RUN/execution/evaluation/evaluation.complete.json"` and obtained exactly `db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519`. A subsequent `bash ~/Downloads/2wiki_evaluate_supervisor.sh --status` again showed 288/288, 12/12 and the same manifest digest; unlike the previous supervisor output, this status did not print a supervisor-lock warning. This confirms a separate file-digest check but **does not verify every file enumerated by the manifest**, establish whether any specific process is active, or substitute for the independent frozen-runner audit.

The last visible resource readings were approximately **34 GiB available disk** (supervisor minimum 30 GiB), with bounded resumptions returning their expected `Batch budget reached` status. The terminal also noted that a supervisor lock still existed; a lock file alone is not evidence of a running process.

This GitHub documentation checkpoint **does not independently hash or inspect the local evaluation artifact tree**. It does not establish scientific completeness, correctness of generated answers, semantic falsity of poisoned statements, or backed-up recovery of evaluation outputs. Raw evaluation checkpoints have not been committed here.

## Subsequent complete file-integrity audit — PASS (8 November 2026)

After the separate file SHA-256 confirmation, the operator ran the read-only
manifest traversal and comparison using the completed local evaluation directory.
The supplied Terminal output reported:

```text
PASS: Evaluation manifest and all listed files verified
Files checked: 22446
Paired cell row files checked: 12
Completion SHA-256: db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519
```

The check matched every path and SHA-256 in `evaluation.complete.json`,
rejected missing/symlinked listed files, checked that no extra regular files
were present, and independently checked the 12 declared cell `rows.json`
digests. This evidence was supplied as the local operator's Terminal output;
it is **not** a repository-hosted copy of the full raw artifact tree, nor a
substitute for the frozen runner's semantic/provenance validation during
`aggregate`. As of this checkpoint, **evaluation backup, final aggregation,
statistical interpretation and full transfer experiment remain pending**.

## Validated aggregation checkpoint — PASS (8 November 2026)

The operator ran the pinned `aggregate` stage from the frozen local checkout after
re-verifying all three hashes. The supplied terminal output reported:

```text
protocol.json: OK
construction.seal.json: OK
evaluation.complete.json: OK
PASS: Frozen aggregate destination verified
{"scope":"heldout","status":"validated_aggregate_written"}
```

This means the frozen aggregator wrote `execution/aggregate.json` successfully.
The stage rechecks construction-seal and evaluation-manifest file integrity,
provenance and paired row schemas, journals/measurement linking, stored summary
consistency, and builds paired query-cluster uncertainty estimates. **The aggregate
numbers have not been inspected or independently interpreted here**; no
effectiveness, attack success or statistical conclusion is claimed.

### Local evaluation archive created (off-device restore pending)

The operator created `2wiki-evaluation-20261108.tar.gz` under iCloud Drive's
`rag-research-backups/` folder, successfully listed it with `tar -tzf`,
and recorded its local SHA-256:

```text
197435fc1345d0adfbd3bfb9ef409d8700b79e064e3b077789de3117462098d4
```

**Backup limitations:** the archive contains `protocol.json`, the
`execution/construction/construction.seal.json` file, and the complete
`execution/evaluation` tree. It does **not** include the remaining frozen
construction data and is not a standalone full-run backup. iCloud sync
completion and a separate downloaded-copy hash/restoration have not yet been
verified. A full experiment-recovery copy should additionally preserve the
construction tree and relevant local input/model provenance without publishing
large/private assets to GitHub.

**Next:** independently inspect `aggregate.json` and record denominator-aware
ASR, PRR, clean utility, paired effects/CIs, and the construction-failure split;
check for aggregate output consistency; close the backup restoration gap.
Full source-crafted cross-pipeline transfer remains separate/pending.

## Construction coverage and interpretation

The previously independently checked frozen construction had **3,600 attempted records**, comprising **1,524 valid lexical constructions** and **276 valid semantic constructions** (1,800 mechanically valid overall), **552 target-construction failures**, and **1,248 semantic-construction failures**. These are *construction* outcomes, not attack success or defense efficacy. Failed construction must remain in attempted-population denominators as specified by the protocol, and must not be labeled a successful defense. Mechanically accepted semantic constructions do not imply independent factual verification.

## Immediate handoff: audit before analysis

1. In the frozen local checkout, confirm the supervisor has exited, and check its lock *read-only* before doing anything to it. Preserve all artifacts and checkpoints.
2. Independently compute the SHA-256 of `evaluation.complete.json` and compare it to the pinned value above. Audit all files referenced in the evaluation completion manifest, the per-batch checkpoint/journal integrity, the 12/12 paired summaries, and query/corpus/model/source/protocol binding.
3. Create a recoverable, separately verified backup of the **completed evaluation** (not merely the construction). Preserve paths and checksums in a non-sensitive archival handoff.
4. Only after independent evaluation validation, use the versioned **aggregate** stage with the exact frozen protocol and completion pin. Recompute paired clean/poisoned Dense/RCD ASR, exposure/PRR, EM/F1, construction coverage and paired uncertainty with correct denominators.
5. Compare HotpotQA and 2Wiki results; inspect semantic construction failures and representative errors; explicitly address historical exposure uncertainty and lack of independent semantic validation.
6. Take the completed evidence to the supervisor to decide whether a *separate* source-crafted BM25/Dense/Hybrid/Reranker → five-target transfer experiment is required, or whether to narrow the manuscript's research claims.

## Important boundaries

- **Not yet claimed:** an attack-success rate, RCD robustness advantage, statistically significant effect, semantic-poison factual correctness, or a validated final 2Wiki research result.
- **Not completed by this 2Wiki run:** source-only selected, cross-pipeline source→target attack transfer among BM25, Dense, Hybrid and Reranker (with RCD as an additional target).
- **Still separately NO-GO without its own approvals:** prospective 2Wiki semantic-quality V3 cohort work with unresolved historical exposure/custody and independent human-review gates.
- **Safe GitHub scope:** metadata and documentation only. Do **not** modify or pull a documentation branch into the frozen local running/evaluation checkout, retune weights, regenerate attacks, rerun construction, or upload private/raw local experiment artifacts as part of this milestone.

This document records a completed **computational execution milestone** and an explicit verification handoff. Formal scientific conclusions await validated aggregate outputs.
