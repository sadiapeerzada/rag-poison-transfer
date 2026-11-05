# 2Wiki: fast path to the **existing** 300-query matrix

This is **not** the prospective V3 25-query construction pilot. The repo already
contains a separate, frozen **300 train-development + 300 dev-heldout** cohort
manifest at `docs/protocols/oct26_2wiki/cohort_manifest.json`. Its held-out
population is historically **risk-disclosed, not independently pristine**. The
older Week 5–6 25-query sweep IDs and complete custodian inventory are missing.
Do **not** claim new fresh IDs or merge the study into V3 prospective evidence.

## What this PR does

Provides a standard-library-only, no-network **metadata preflight**. It
recomputes and verifies both 300-query cohort fingerprints, dataset revision,
the policy byte hash embedded in the manifest, zero train/dev ID overlap,
then-known historical exclusions, the current 900-ID registry and its external
SHA-256 pin, and the unchanged matrix dimensions from the actual source AST.

For the existing protocol, 2 attacks × 2 intensities × 3 seeds = **12 cells**.
Each cell has 300 frozen dev queries, giving **3,600 query-cell experiments**
and up to **7,200 paired Dense/RCD poisoned-observation records**. Semantic
construction has a protocol upper bound of **7,200 backend attempts** before
the separate QA inference cost; actual calls vary with failures/replays.
These are workload counts, not completed results or guaranteed physical calls.

The report does not inspect any held-out question/gold text. It does not
select or replace queries, load a model, freeze an inference protocol, change
the 509 preserved artifacts or claim approved target falsehoods. Output is
write-once; repeated execution at the same output path fails.

## Run in a clean checked-out PR worktree

```bash
python -m pytest -q tests/test_twowiki_300_matrix_preflight.py \
  tests/test_twowiki_v3_census_handoff.py \
  tests/test_twowiki_v3_train_pool.py

python scripts/prepare_twowiki_300_matrix_preflight.py \
  --registry-sha256 799c87aa83f6cb8ded2a16d0cbf110f35d1512b359d725dd27fa342422a68e65 \
  --output "$HOME/Documents/rag-research-results/twowiki-300-matrix-preflight-20261105.json"
```

Review the packet. This reports `frozen_cohort_metadata_preflight: PASS`
and `matrix_execution_go: false` until actual missing prerequisites are
addressed; it is not an experiment executor.

## What to verify next on the user's Mac

1. Find the previously created **2Wiki replication spec** and its exact
   pinned local data for the frozen 300 dev cohort, along with model snapshot
   and retrieval embedder/reranker snapshots. These aren't included in this PR.
   The existing runner requires those paths and hashes. Run metadata-only
   `preflight` with `scripts/run_week9_protocol_poison_matrix.py`,
   `--scope heldout`, and the actual `--replication-spec` /
   `--replication-spec-sha256`. No guesses or placeholder files.
2. Validate the installed MLX environment, resource budget and the complete
   12-cell construction/evaluation schedule. **Do not** use
   `pilot_prep/twowiki_semantic_v3/forms/authorization.blank.json` for this
   distinct existing protocol or set `allow_model_calls` without the
   responsible human's actual approval.
3. Document any supervisor authorization and interpretations for running
   an **historically risk-disclosed non-prospective 300-query replication**
   without independently proven nonexposure. This is not a license to claim
   fresh held-out evaluation, independently verified false targets, or
   full RAG transfer beyond the implemented Dense/RCD comparisons.
4. Only when the input spec, model snapshots, protocol freeze and actual
   authority are established, use the existing runner stages in order:
   `preflight`, `freeze-protocol`, `construct`,
   externally pin completed construction seal, `evaluate`, `aggregate`.
   Do not issue these calls simply to force an experiment GO flag.

## Scientific boundary

The V3 25-case pilot remains separate and NO-GO. Missing 25-ID sweep
provenance, original deleted/remote execution logs, complete historical
custody and independent review cannot be reconstructed or certified by this
preflight. This PR **does** verify the preexisting risk-disclosed 300 matrix
population and dimensions; it **does not** finish the matrix or fake approvals.
