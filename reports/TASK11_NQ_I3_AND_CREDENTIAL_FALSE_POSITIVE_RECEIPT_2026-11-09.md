# Task 11 targeted diagnostic receipt — NQ I3 hash and credential false positive

**Recorded:** 9 November 2026. **Scope:** One local operator Mac receipt plus checked public GitHub source lines. **Status:** Current NQ I3 plan provenance reconciled; code-secret-pattern alert confirmed false positive; tracked raw-result rights still require review.

## 1. NQ intensity-3 SHA status

The first local run of `audit_nov09_release_evidence_offline.py` reported `HASH_MISMATCH` for `nq-stage3-lexical-I3-qa-plan-v1_PRIVATE.json`. A second explicit read-only shell diagnostic printed these values:

| Source | SHA-256 |
|---|---|
| Frozen expected I3 plan | `53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2b8f46d968a2e7b5` |
| Actual file at second check | `53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2b8f46d968a2e7b5` |
| Source aggregate's recorded `plan_sha256` | `53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2b8f46d968a2e7b5` |
| Source run manifest's recorded `plan_sha256` | `53aebbb47648727a664eeb012b591ed28cb33c65aad59f8a2b8f46d968a2e7b5` |

The operator's original file modification timestamp was 9 November 2026, 14:32:42 local time. **The observed mismatch is not present at the subsequent explicit check**, but the reason for the two readings is unknown. No file was regenerated or overwritten in this PR; repeat the read-only full NQ paired analysis with the current pinned evidence before updating the audit to a durable PASS. Do not silently erase the earlier mismatch receipt.

The same initial local report found `MATCH` for I1 source plan, I1 source aggregate, I3 source aggregate, the 8 public evidence blobs, and the pinned full 2Wiki tar SHA-256.

## 2. False credential pattern: scientifically verified code text

The read-only local scanner returned an `openai_looking_key: 1` **file-count** warning, and a safe diagnostic identified **two matched substrings on lines 19 and 133** of `scripts/prepare_twowiki_300_matrix_preflight.py`.

Verified GitHub line content:
- Line 19: `SCHEMA = "twowiki-300-risk-disclosed-matrix-preflight/v1"`
- Line 133: `"scope": "historically-risk-disclosed-existing-frozen-2wiki-300"`

These are **not API credentials**. The old `sk-` pattern matched the substring of the word **risk-disclosed**. This patch requires a non-word/non-token boundary before `sk-`, and adds tests to reject both literal strings while still recognizing a structurally valid `sk-proj-...`-shaped dummy key. No key value was printed, published, or rotated.

**Scope caveat:** Clearing this alert does **not** prove the entire repository contains zero secrets; this is a heuristic regex scan, not a full external secrets audit.

## 3. Tracked-result data rights remain open

The local release scan counted **57 Git-tracked `results/` .json/.jsonl/.csv/.txt files** requiring dataset redistribution and privacy review. The GitHub tree contains 28 JSONL, 22 JSON, and 7 CSV entries in this group. Inspection of **sampled** public JSONL shapes (`results/exp_001_real_generator.jsonl`, `results/exp_003_hotpotqa_pilot.jsonl` and `results/exp_009_hotpotqa_retrieval_eval_smoke.jsonl`) confirms keys such as **`question`**, **`gold_answer`**, **`prompt`**, **`generated_text`**, plus query IDs and document IDs. No raw content is repeated in this report.

This is a **rights/privacy review requirement**, not a finding that publication is unlawful or that private held-out evidence leaked. The code/doc change in this PR **does not remove data**. Before a public release, separately classify allowed public benchmark examples, copyrighted source passages, user/private data, and sealed held-out evidence; keep restricted raw material outside public Git while retaining scientific reproducibility privately.

## Next local steps

1. Merge this **false-positive fix** after tests pass, then fast-forward `main`. Do **not** change the original experiment data.
2. Re-run the already merged `scripts/nq_paired_statistics_offline.py` **without `--output`**. It validates both pinned NQ source plans, aggregates, all 2,400 saved QA response fingerprints and paired statistics without model inference or creating a new private JSON.
3. Re-run the release checker with a **new private output filename**. The false-key scan should no longer flag the two `risk-disclosed` lines. Any remaining credential-like warnings must be inspected without printing values.
4. Review redistribution/privacy rights for tracked raw `results/` files; record action (retain with verified rights, redact/remove only by explicit researcher-approved change, or restrict) before claiming complete Task 11.
5. Complete off-device model/data asset custody, semantic source validation and final CI/supervisor decision separately.

**Task 11 verdict: PARTIAL.** The targeted mechanical alerts are explainable, but the broader scientific and release-readiness gates are not yet certified. Completion count remains **5/12**.
