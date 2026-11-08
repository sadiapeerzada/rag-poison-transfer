# 2Wiki full-run local backup and paired audit: operator PASS checkpoint

**Date:** 9 November 2026 (India time).  
**Evidence:** researcher-supplied Mac Terminal output; tool execution on local original frozen result tree. **This GitHub commit does not itself access the operator's Mac or remotely stored bytes.**

## 1. Full-run archive successfully created and locally verified

Operator ran the `create` mode of [`scripts/backup_2wiki_full_run.py`](../scripts/backup_2wiki_full_run.py) against the unchanged `authorized-matrix` directory, with the archive path outside the run:

```text
PASS: local full-run archive is internally restorable (not yet off-device verified)
Files: 37534 Source bytes: 518755193
Archive: .../com~apple~CloudDocs/rag-research-backups/2wiki-full-run-20261109.tar.gz
Archive SHA-256: faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82
Manifest: .../rag-research-backups/2wiki-full-run-20261109.tar.gz.manifest.json
```

The archive includes **all files under the frozen `authorized-matrix` directory**, including full construction, evaluation, protocol and aggregate, rather than only the construction seal and evaluation. The tool checked the original required pins, inventoried all 37,534 regular files, embedded per-file hashes, and streamed all archive members back through the verifier. Original source bytes total **518,755,193** (~495 MiB). Archive compression size is not inferred from source bytes.

**Important:** this proves only **local content verification**. The file was placed in the *local iCloud sync folder*, but a completed cloud upload, independently retrieved copy, or actual restored tree has **not** been demonstrated. External model weights, cached datasets or other dependencies outside `authorized-matrix` are not included. The operator must retain the original SHA outside the archive and check the remote download.

## 2. Read-only full paired-case census and review packet: PASS

Operator ran [`scripts/audit_2wiki_paired_cases.py`](../scripts/audit_2wiki_paired_cases.py) with `--per-stratum 4` against the frozen original tree. Output:

```text
PASS: read-only 3600 construction-record / paired-arm census
Full paired census: .../2wiki-paired-review-20261109/paired_census.csv
Human review packet: .../2wiki-paired-review-20261109/review_packet.jsonl
Human adjudication template: .../2wiki-paired-review-20261109/human_review_template.csv
Cases selected: 131 Distinct query IDs: 102
No human semantic judgments have been performed or implied.
```

These files were generated **outside** the frozen run directory, and the exporter checked the 12-cell completeness, 300 query IDs per cell, paired arms, construction statuses, and each cell's targeted-ASR numerator against the pinned aggregate. The 131 selected cases represent a deterministic, **post hoc, outcome-visible sample**, **not a blinded, random representative set of 131 independent queries**; there are **102 distinct query IDs**, with some repeated across conditions.

**Not yet completed:** independent human or source-backed factuality judgments, detailed per-case analysis, reviewer disagreement adjudication. Do not interpret the blank `human_review_template.csv` as reviewed evidence. The packet contains raw prompts and retrieved/generated evidence: keep private until licensing/privacy review.

## 3. Already completed

- Frozen 2Wiki inference: 288/288 bounded query-arm batches, 12/12 summaries; separate evaluation hash audit verified 22,446 files.
- Frozen `aggregate.json` wrote successfully, with revalidated matching ASR/counts and paired bootstrap intervals.
- [HotpotQA versus 2Wiki report](HOTPOTQA_VS_2WIKI_PAIRED_COMPARISON_2026-11-09.md) reconciles attempted and conditional ASR, target/semantic construction attrition and protocol differences.
- [2Wiki aggregate error triage](2WIKI_AGGREGATE_ERROR_TRIAGE_2026-11-09.md) identifies paired disagreement and low-clean-EM priorities.

## 4. Remaining evidence required to close the original three tasks

1. **Off-device recoverability — pending:** confirm iCloud web-visible upload; **download** both `2wiki-full-run-20261109.tar.gz` and `.manifest.json` to an independent directory; run the restore verifier on that separate copy against the pinned SHA `faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82`; record PASS and destination. Account separately for model/data caches outside the archive.
2. **Case-level review — pending:** evaluate `review_packet.jsonl` with independent reference sources and reviewer names/dates. Check exact target assertions, gold aliases/constraints, *factual falsehood*, actual generator-visible exposure, clean EM and extraction. Resolve disagreements. No retuning or replacement of held-out examples.
3. **Supervisor handoff — pending:** review both cross-dataset results and completed case-level audit before deciding whether to run a separate source-crafted transfer matrix or narrow paper claims.

These are **local evidence checkpoints**, not a new inference run. The original frozen experiment files and the generated local audit outputs have **not** been uploaded to GitHub.
