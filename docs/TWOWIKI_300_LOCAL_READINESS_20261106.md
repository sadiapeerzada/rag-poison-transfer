# Existing 300-query 2Wiki replication: local readiness, 6 November 2026

Decision: **NO-GO for execution today**. Frozen population and local input checks
pass. Scientific model-call authorization, an approved resource budget and a
reviewed local-v2 execution freeze are still absent. No model inference,
construction or held-out evaluation was performed by this audit.

Remote fetch verified `origin/main = fcebb1e0a8f0` and merged PRs #110–112.
Work was isolated from the user's six staged files. No frozen protocol,
cohort, historical result, checkpoint or approval form was edited.

## Verified inputs

The existing adapter, runner, materializer, construction rules, execution
reliability implementation and base configurations have no changes between
historical source `b1466db04c4f8f0314c7e537d8e7ec390c8c3b29` and fetched main.
This PR adds diagnostics; it does not alter those implementations.

| Artifact | Verified value |
| --- | --- |
| Cohort manifest SHA-256 | `3f51077946601cc0f58c0866716bf6c4650306dfd497cb98ed2973a466ca2cd4` |
| Dataset | Salesforce/ContextualBench, 2WikiMultihopQA |
| Dataset revision | `9823f70484dea525100394220b0ea5184d0eeb7b` |
| Original v1 replication spec SHA-256 | `30e46a5876b1c089a52dd47ae88f9ccc8b6483b0ea89f0cee10f4e4bd2f06856` |
| Historical parent protocol SHA-256 | `47c164fd7461153f68e6b0df3e5dc31ca9b0a70b84fe379e1ada4a68f0f7a035` |
| Parent code fingerprint | `f43df684a62d96beaa9c06a149142af4baf12a186c570835af6c80d52f66becb` |
| Local train data SHA-256 | `58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43` |
| Newly materialized dev data SHA-256 | `24954162808913da007eead81be3d42a1762aabab0eca3d9cfc203c3e8759287` |
| Dev query fingerprint | `1265f174e7e1b641277b7bb1a968501998273a91e7a512355ef801d47519f341` |
| Dev corpus fingerprint | `c2fb58345f83ef06ccdaeb8d63493ca018bd97bee8c19df09a77ba0c98788a74` |
| Durable local v2 spec SHA-256 | `e30904a1c7cd255c5fe5acec13f19c65e7579e84c5a3aefc341576db2228fa48` |

The v1 spec lives at
`~/Documents/rag-research-results/twowiki-v2-development-recovery-20261103/replication_inputs.json`.
Its manifest path points to `~/Documents/rag-2wiki-v2-clean/docs/protocols/oct26_2wiki/`;
those manifest bytes match this repository. Its training data contains all
300 frozen train records; question hashes and ordering verify.

The previously available v2 spec in `twowiki-v2-binding-20261103/local-v2/`
is **development scoped**, with train data; it cannot satisfy held-out execution.
The existing `scripts/materialize_2wiki_execution_inputs.py` successfully fetched
only the selected dev cohort from the pinned revision: **300 queries, 2,163
corpus documents**. All question hashes and ID ordering verify. This is data
preparation and does read the selected held-out data; the metadata-only cohort
preflight does not. No question, answer or prompt text is included here.

New evidence and durable v2 inputs live in
`~/Documents/rag-research-results/twowiki-300-readiness-20261106/`.
`materialization-original/` retains the first spec and dataset byte-for-byte;
`replication_inputs.json` changes only the local data path to its durable copy.
The original materialization's `/private/tmp` path is provenance, not the path
to use for future execution. No replacement cohort was selected.

Generator `mlx-community/Qwen2.5-7B-Instruct-4bit` snapshot
`c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed` matches **every file hash** in the
historical parent. Embedder `BAAI/bge-small-en-v1.5` at
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` and cross-encoder
`cross-encoder/ms-marco-MiniLM-L-6-v2` at
`233902d25c440f23af6f7d6e94d2946bac0bee0a` match the historical local v2 bindings.
The cross-encoder is pinned by existing materialization, but Dense/RCD execution
uses the embedder plus RCD's sparse retrieval/rank scoring; it does not add a
cross-encoder arm.

The inherited settings remain top-k 3, QA max tokens 64, greedy decoding,
RCD candidate-k 10/rewrite count 3 and weights consistency .45, redundancy 0,
conflict .10, base rank .45. Semantic construction uses max tokens 150,
two attempts per document, no profile override, and the original nomination,
validation, failure accounting and complete-corpus evaluation mechanics.

## Runtime and evidence boundaries

Python 3.13.7; mlx 0.32.2; mlx-lm 0.31.3; transformers 5.16.1;
sentence-transformers 6.0.0; datasets 5.0.1; numpy 2.5.2; torch 2.13.0.
These versions, including the exact Python version string, match the parent.
pyarrow 25.0.1 and huggingface-hub 1.29.0 were available for materialization.
Imports of torch, sentence-transformers, datasets and pyarrow passed.
Metal and mlx-lm imports passed outside the sandbox without loading weights.
The sandbox itself cannot access Metal; inference must use a GPU-capable session.

Apple M4, 16 GiB physical RAM, Metal recommended working set 12,713,115,648
bytes; free disk approximately 8.7 GiB at audit time. This is not a measured
full-matrix memory/disk/time estimate or an approved budget. The original
Hotpot transfer evidence alone occupies about 3.2 GiB; retain it.

The cohort metadata preflight passes and the runner metadata preflight passes
with the local held-out v2 spec. Historical rules equal current rules. However,
the parent binding's configuration fingerprints include `_config_path`, which
changes across checkouts. The current worktree therefore does **not** match
that parent binding/source. The original clean checkout **does** remain at
`~/Documents/rag-2wiki-v2-clean`, exactly at historical commit
`b1466db04c4f8f0314c7e537d8e7ec390c8c3b29`: both its full source fingerprint
and original parent binding verify exactly. Use that checkout for execution,
preserving the source revision. Its metadata preflight with the durable local-v2
inputs also passes. Do not rewrite the parent or relax checks. A separately
recorded local-v2 execution freeze must retain this same source, current matching
environment and pinned local inputs, with the historical parent retained.
Review/authorize that local-input execution freeze before inference; the
population and scientific construction rules stay unchanged.

## Local construction and checkpoint census

The initial census hashed **246,349 pre-existing files**, including copied code,
Hotpot evidence and every local 2Wiki artifact under `rag-research-results`.
Its inventory fingerprint is
`83badf10e163391ed462dcdaeac2b687480bf6db82499c17faf617da54026758`.
The final census also includes the new preparation packets; the inventories
are observations of local bytes, not a complete custodian/external execution log.

Only one discovered protocol is the 300-query 2Wiki held-out protocol, with pin
`47c164fd…f7a035`. **No construction/evaluation execution plan references it**;
no completed matrix cell or held-out evaluation for that protocol was found.
This establishes no locally recorded start, not proof that no external call
has ever happened. The 12 held-out cells remain outstanding.

The two existing 25-query development protocols each have two semantic cells,
50 validated query checkpoints and 148 completed construction responses. These
are development evidence and supply zero completed cells to this matrix.
Their directories are `twowiki-v2-construction-pilot-20261103` and
`twowiki-semantic-quality-25-v2-20261104`. The former construction seal's file
manifest matches. The latter construction seal and evaluation completion each
have **one additional `.DS_Store`, no missing or changed sealed payloads**;
strict resume must reject the extra files. All 509 artifacts remain preserved.
No historical seal was rewritten to legitimize the difference.

All six stores with execution plans pass the existing `validate_store`
checkpoint/journal checks. Outside those stores,
`recovery-evidence/unresolved-call-20261029T135409Z/01.intent.json` has no
response. This archived call's execution is indeterminate; no automatic replay
is permitted. It is not evidence that this 2Wiki held-out matrix started.
Review and exploratory scripts use separate intent/output formats; their
files are inventoried and explicitly reported as requiring their own validators,
not falsely treated as native missing `.response.json` files.

Seven reviewer-output files fail JSON parsing: reviewer B cases 02/03 under
`twowiki-three-candidate-gate-20261104-v1/responses/`, and cases 01–05 under
`twowiki-two-ai-review-raw/`. This is a syntax finding, not a claim about review
validity, authenticity or matrix-checkpoint corruption. Their bytes are retained.

The reusable census emits hashes and metadata only and cannot authorize calls.
To reproduce it, choose a fresh output outside both trees:

```bash
/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python \
  scripts/audit_twowiki_300_local_readiness.py \
  --results-root "$HOME/Documents/rag-research-results" \
  --output /private/tmp/twowiki-300-local-census-new.json
```

## Execution commands, only after authorization and budget confirmation

Use the verified original clean checkout for execution. This PR supplies the
audit and commands; it does not replace the historical execution source.
Do not move the original checkout or change dependencies after freezing. The existing runner enforces source, environment, snapshot,
input and output namespace pins. These commands do not supply scientific
approval. The responsible researcher must separately record approval for the
historically risk-disclosed 300-query replication and the local-v2 input binding under the original frozen source.
Do not use the separate V3 pilot authorization form.

```bash
cd "$HOME/Documents/rag-2wiki-v2-clean"
test "$(git rev-parse HEAD)" = b1466db04c4f8f0314c7e537d8e7ec390c8c3b29
test -z "$(git status --porcelain --untracked-files=all)"
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
E="$HOME/Documents/rag-research-results/twowiki-300-readiness-20261106"
SPEC_PIN=e30904a1c7cd255c5fe5acec13f19c65e7579e84c5a3aefc341576db2228fa48
MODEL="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
RUN="$E/authorized-matrix"  # Fresh namespace; preserve it for every resume.

"$PY" scripts/run_week9_protocol_poison_matrix.py preflight --scope heldout \
  --replication-spec "$E/replication_inputs.json" --replication-spec-sha256 "$SPEC_PIN"

# After the required execution approval and budget confirmation:
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope heldout \
  --replication-spec "$E/replication_inputs.json" --replication-spec-sha256 "$SPEC_PIN" \
  --model-snapshot "$MODEL" --output "$RUN/protocol.json"
shasum -a 256 "$RUN/protocol.json"
# Record/review that digest externally, then set PROTOCOL_PIN to that exact digest.
# Do not regenerate or overwrite the protocol on resume.

"$PY" scripts/run_week9_protocol_poison_matrix.py construct \
  --protocol "$RUN/protocol.json" --protocol-sha256 "$PROTOCOL_PIN" \
  --construction-dir "$RUN/execution/construction" --model-snapshot "$MODEL" --max-batches 1
# Exit 75 is a planned pause. Repeat this exact construct command while unsealed.
# A sealed construction rejects further construct calls; proceed to seal review.
# Any unresolved intent, error response, corruption or temp debris requires
# explicit investigation; never delete a journal or automatically replay it.
shasum -a 256 "$RUN/execution/construction/construction.seal.json"
# Only once all 12 cells are sealed, independently record/review that digest
# and set SEAL_PIN to it. Inspect the seal with the existing runner validators.

"$PY" scripts/run_week9_protocol_poison_matrix.py evaluate \
  --protocol "$RUN/protocol.json" --protocol-sha256 "$PROTOCOL_PIN" \
  --construction-dir "$RUN/execution/construction" --construction-seal-sha256 "$SEAL_PIN" \
  --evaluation-dir "$RUN/execution/evaluation" --model-snapshot "$MODEL" --max-batches 1
# Repeat the exact evaluate command after planned pauses. It validates and reuses
# completed checkpoints; an already completed evaluation returns its completion pin.
shasum -a 256 "$RUN/execution/evaluation/evaluation.complete.json"
# Record/review that digest externally, then set EVALUATION_PIN to it.

"$PY" scripts/run_week9_protocol_poison_matrix.py aggregate \
  --protocol "$RUN/protocol.json" --protocol-sha256 "$PROTOCOL_PIN" \
  --construction-dir "$RUN/execution/construction" --construction-seal-sha256 "$SEAL_PIN" \
  --evaluation-dir "$RUN/execution/evaluation" --evaluation-completion-sha256 "$EVALUATION_PIN" \
  --output "$RUN/execution/aggregate.json"
```

`--max-batches 1` limits new 25-query batches per invocation, **not** backend
calls, elapsed time or total budget. It does not authorize calls. All 12 cells
remain required: two families × intensities 1/3 × seeds 42/43/44. Construction
has a ceiling of 7,200 semantic backend attempts. QA has up to 14,400 logical
clean/poisoned observations; exact-input clean caching can reduce physical calls
(up to 7,800 under unchanged deterministic clean inputs). Budget conservatively
for the uncached ceiling; actual calls and failures must come from journals.
There are up to 7,200 poisoned Dense/RCD observations, not 7,200 guaranteed successes.

## Reporting requirements

Historical nonexposure remains unproven, including missing Week 5–6 25-query IDs
and complete custodian history. Targets are mechanically label-conditioned
non-gold/type-compatible nominations, not independently adjudicated falsehoods.
Report these limits, construction failures in all 3,600 denominators, paired
Dense/RCD results, and frozen query-cluster uncertainty. No pristine prospective
claim, independent-review claim, replacement cohort, or V3 pilot result is implied.
Actual completed construction, sealed evaluation, validated aggregate and an
explicitly approved interpretation are still needed before reporting results.

## Verification delivered with this change

The combined offline regression run passed **296 tests in 93.58 seconds**:
cohort preflight, replication adapter, frozen protocol, failure-aware held-out
matrix, checkpoint reliability, paired evaluation/aggregation, reliable 2Wiki
and workflow resume, semantic reliability, V3 census and train-pool regressions.
After adding one further intent-format regression, all three census tests passed
again (**297 distinct tests verified** across the runs). Test stdout is retained
with the audit evidence and in the PR. Both runbooks' Bash blocks pass `bash -n`;
`git diff --check` passes. No test used a real model backend.

Re-run the combined regression selection from the clean checkout:

```bash
/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python -m pytest -q \
  tests/test_twowiki_300_matrix_preflight.py tests/test_twowiki_replication_adapter.py \
  tests/test_week9_frozen_construction_protocol.py tests/test_execution_reliability.py \
  tests/test_week9_heldout_poison_matrix.py tests/test_twowiki_300_local_readiness.py \
  tests/test_reliable_2wiki.py tests/test_reliable_workflows.py \
  tests/test_week9_semantic_reliability.py tests/test_twowiki_v3_census_handoff.py \
  tests/test_twowiki_v3_train_pool.py
```
