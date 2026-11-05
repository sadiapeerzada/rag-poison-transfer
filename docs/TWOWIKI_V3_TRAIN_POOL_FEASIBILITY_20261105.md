# 2Wiki V3: metadata-only broader-train feasibility gate (5 Nov 2026)

This is **not** a repair of missing scientific evidence. The original prospective
pilot stays **NO-GO**. The original 25 sweep IDs and runtime revision binding
remain unresolved, the existing 300-ID train sample has 0 eligible IDs after
the recorded 900-ID exclusions, and no independent custody certification exists.

## New read-only tool

`scripts/audit_twowiki_v3_train_pool.py` accepts an **independently obtained**
IDs-only, pinned-revision JSON export (example shape shown below) and the existing
reconciled registry, each with an independently obtained SHA-256 value:

```json
{
  "dataset": "Salesforce/ContextualBench",
  "config": "2WikiMultihopQA",
  "revision": "9823f70484dea525100394220b0ea5184d0eeb7b",
  "split": "train",
  "query_ids": ["EXAMPLE_DEVELOPMENT_ID"]
}
```

The input must contain **only** these five fields. Do not add or fetch questions,
answers, gold labels, corpus text, held-out or validation rows. This tool does
not download dataset files, infer metadata from filenames, or export query IDs.
The dataset revision matches `src/experiments/twowiki_replication.py:REVISION`;
verify the actual upstream revision and legality of the export before running.

```bash
python -B scripts/audit_twowiki_v3_train_pool.py \\
  --train-ids /absolute/path/to/full-train-ids-only.json \\
  --train-sha256 EXTERNALLY_RECORDED_64_HEX_SHA256 \\
  --registry /absolute/path/to/reconciled_registry.json \\
  --registry-sha256 EXTERNALLY_RECORDED_64_HEX_SHA256
```

Output contains aggregate counts and a permanent `prospective_go: false`.
At least 25 IDs outside the recorded exclusions is **necessary but not
sufficient**. This script does not choose 25 IDs, attest historical nonexposure,
certify a custodian, verify human review, or unlock model calls. If the exact
revision is not accessible, report that as **not assessed**, not zero eligible.

## Separate option for exposed development material

If history cannot be certified, a *separately versioned, explicitly
non-prospective* construction-only diagnostic may be proposed using previously
exposed training examples, after independent scientific approval and a distinct
frozen protocol. It may measure V3 heuristic coverage, relation correctness,
target-evidence quality, duplicates, abstentions and logging. It **must not**
claim unbiased gains, a novel fresh cohort, held-out effectiveness, RCD superiority
or successful full 2Wiki replication. Do not feed the current V3 draft to the
held-out runner or modify old seals/configurations.

## Remaining external blockers

1. Recover or account for historical sweep IDs, runtime revision and all exposures.
2. Obtain independently certified custody and pinned same-revision source metadata.
3. Freeze the new protocol/cohort *before* development content inspection.
4. Obtain evidence-backed target nominations and independent human review.
5. Pin model/tokenizer/environment, raw corpus, manifests, driver and output namespace.
6. Obtain a separately bound construction-only model-call authorization.
7. Run and independently review the real-model pilot before proposing QA.

This PR intentionally creates **no model execution path and no approvals**.
