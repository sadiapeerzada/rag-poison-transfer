# October 26 execution reliability amendment

This implementation branches from reviewed commit
`8c55b3c1d1b8730c9a24dc5504c931af57fd5aa3`. The completed Week 9–10 worktree,
its results, the previous follow-up protocols and README are untouched. This is
an execution amendment, not a reduced experiment. No full run or model smoke is
authorized by this document. No model inference was performed during implementation.

## Scientific invariants

Keep all 300 frozen IDs, both attack families, intensities 1 and 3, poison seeds
42/43/44, QA seed 42, three transfer candidates, two semantic attempts/document,
the selection rule and all source/target conditions. Keep the complete pooled
poison corpus for a condition when batching its questions. Keep all construction
failures and null unperformed measurements. Neither source failure nor cache
availability permits dropping a target-side observation. RCD remains one composite
defense with its frozen weights and retrieval implementation. Existing human-review
workflows are unchanged. Targets remain label-conditioned, not independently
established falsehoods or AI/human approvals.

The candidate/source-selection barriers and query-cluster bootstrap are unchanged.
RCD is never a source used for candidate selection. All source selections are sealed
before final target QA. 2Wiki evaluation requires the complete construction seal.

## New versions and provenance

- Transfer protocol: `rag-poison-transfer.bounded-source-selection/v2`.
- Transfer source-selection seal: `rag-poison-transfer.selected-source-poison-seal/v2`.
- Local 2Wiki inputs: `rag-poison-transfer.2wiki-replication-inputs/v2`.
- 2Wiki protocol: `rag-poison-transfer.2wiki-frozen-construction-protocol/v2`.
- Execution policy/checkpoint envelope: `atomic-batched-clean-cache/v1`.
- QA execution extension: `qa-execution/v1`; existing QA measurement v2 remains
  readable, with additive cache/replay provenance.

Freeze requires clean committed code and retains code/environment/configuration,
dataset/model hashes and the frozen query order. The new protocols declare exact
output namespaces. They are separate artifacts; old protocol files are never
rewritten. Runtime 2Wiki configs use locally pinned BGE weights rather than a
mutable model name. Input specifications retain the original revision/cohort,
historical-exposure disclosure, parent protocol pin, and hashes of local data,
query set, corpus and both retrieval snapshots. No held-out nomination is performed
by input materialization.

New external root: `/private/tmp/oct26-reliable-2026-10-26-v1/`. Each of
`transfer-development`, `transfer-heldout`, `twowiki-development`, and
`twowiki-heldout` receives its own `protocol.json` and planned `execution/` outputs.
The external execution manifest records actual commit, protocol/config hashes,
input pins and paths after freeze. No new artifact is a completed experiment.

## Checkpoints and interruption policy

Exclusive atomic publication uses a flushed/fsynced temporary file and an
exclusive hard link, then directory fsync. Existing files are never replaced.
An OS lock prevents two writers to one stage; a separate cooperating-process MLX
lease prevents simultaneous model processes across these new runners. Neither
lock interrupts an unrelated or historical process.

Transfer construction checkpoints every query/candidate/cell. Source screening
checkpoints every query/source/candidate. Evaluation checkpoints each clean/poison
query pair and publishes a batch-completion envelope, then the assembled rows.
All bindings include the protocol and exact inputs; checkpoint data hashes are
verified on recovery. Complete stages are idempotently verified, not reopened.
Cache entries and generation journals participate in final inventories. Assembled
measurements are checked against query checkpoints, journals and cache references.

A saved response may be replayed after interruption. **An intent without a saved
response, a recorded backend error, or incomplete atomic publication halts**.
There is no automatic deletion, regeneration, retry-budget extension or conversion
of infrastructure failure into scientific construction failure. Resolving such an
indeterminate call requires an explicit incident decision outside this runner.
This limitation is necessary to avoid silently spending an unknown extra attempt.

`--max-batches N` bounds new batches in a stage invocation. Batch size is frozen
at 25 IDs in their original order. A planned pause returns JSON status `paused`
and exit code **75**; repeat the same stage/protocol/output. Exit zero plus the
expected completion seal means the stage completed. Completed batches are not
charged again. Never advance merely because a subset of rows exists.

An evaluation batch is one target pipeline and up to 25 population queries,
including failed constructions: at most 50 QA calls. Complete clean and poisoned
corpora are retained in the indexes. Dense/RCD or other target arms can run in
separate jobs, but final validation requires exact ID/target/poison pairing.
The jobs are not independent statistical replicates. Aggregation still resamples
query clusters retaining all seeds and arms.

Use larger job allowances, for example 12 batches, to amortize model/index loading.
Every process restart rebuilds required indexes; persistent embedding/index caching
is not implemented. Small jobs trade extra indexing for bounded execution time.

## Exact-input clean-QA caching

Only clean QA is cached. Source screening, semantic construction and poisoned QA
are never served by this cache. Matching includes model/tokenizer snapshot hashes,
source/environment, full clean-corpus fingerprint, retrieval configuration and
snapshot bindings, query ID, ordered evidence IDs/text/scores, plain and effective
chat-formatted prompts, max tokens, decoding settings and QA seed. A mismatch is a
miss, not an opportunity to relax the key. Missing format support disables caching.
The existing chat template is used unchanged. Greedy QA explicitly resets the
already declared seed 42 for an actual call.

Cache hits and journal replay have zero *new backend generation* latency, measured
lookup elapsed time, and explicit `backend_call_executed: false`. Original generated
text, effective prompt, token counts and original timing remain available in origin
provenance. Summary accounting separates logical observations, actual backend calls
and clean-cache hits. Cached/warm execution timing is not a new uncached latency
benchmark and must not be substituted into historical latency claims.

Bounded synthetic tests independently compare complete cached/resumed versus
uncached outputs: answers, EM/F1, targeted success, retrieval/exposure and paired
summaries. In that fixture, final transfer calls fall from 80 to 45 without any
metric change. This is software evidence, not proof of real-model bitwise
repeatability, factual correctness or scientific effectiveness. A separately
approved real-model development smoke remains required before full execution.

## Expected calls and resource limits

Under exact clean-input hits, full transfer's known 135-target-support ceiling
falls from 93,960 to **62,235** backend calls: up to 9,720 semantic construction,
19,440 source screening, 32,400 poisoned QA and 675 distinct clean QA calls.
At measured development-smoke rates this is approximately **57.4 model-hours**,
excluding indexing and restarts. The all-300 mechanical worst-case projection is
138,300 calls with hits, versus the unchanged hard construction/QA budget of
208,800 without cache savings. Exact-key misses remain allowed and can reduce savings.
All 300 IDs remain in denominators; 135 is not an eligible-subset primary study.

For 2Wiki, the all-valid 300-query projection is **15,000** calls with identical
clean hits: 7,200 semantic, 7,200 poisoned QA and 600 distinct clean QA, versus
21,600 without hits. No held-out coverage forecast or semantic-validity claim is
made. The unknown historical 25-query exposure remains unresolved.

Development transfer: up to 220 calls without hits, 150 with all planned clean hits.
Development 2Wiki: up to 20 calls without hits, 16 with hits. Neither new smoke was
run here. Synthetic generator calls in tests are not MLX inference.

Snapshot SHA-256 validation now streams file contents instead of allocating each
multi-GB weight file in RAM. The digest is unchanged and a regression forbids
whole-file `read_bytes()` in that hashing path.

The machine has 16 GB unified memory. Execute one cooperating model job at a time;
release unused allocator buffers between conditions. No peak-RAM validation was
performed, and other applications/legacy processes can still compete for memory.
Checkpoint and batch records increase disk use. Plan at least 30 GiB free local
space, with additional archival capacity; this is an engineering margin rather
than a measured minimum. Existing approximately 8–10 GiB headroom and swap use are
remaining risks. Do not delete, move or clean historical artifacts to obtain space
without separate authorization. Output names are frozen; relocation requires a
new execution freeze, not an edited protocol.

## Commands after implementation commit (no inference in freeze)

Use the existing Python environment and cached snapshots:

```bash
cd /private/tmp/rag-oct26-execution-reliability
PY=/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python
MODEL=/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
EMBEDDER=/Users/sadiapeerzada/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5/snapshots/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
RERANKER=/Users/sadiapeerzada/.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L-6-v2/snapshots/233902d25c440f23af6f7d6e94d2946bac0bee0a
OUT=/private/tmp/oct26-reliable-2026-10-26-v1
export PYTHONDONTWRITEBYTECODE=1

# Freeze a new development transfer protocol; do not overwrite an existing freeze.
"$PY" scripts/run_source_selection_transfer.py freeze --scope development \
  --base-protocol /private/tmp/week9-protocol-heldout/protocol.json \
  --base-protocol-sha256 5eb83f381745addbd102547540362dac6fc099ab7fd1594dcd6e2975ba376025 \
  --model-snapshot "$MODEL" --embedder-snapshot "$EMBEDDER" \
  --reranker-snapshot "$RERANKER" --output "$OUT/transfer-development/protocol.json"

# Freeze 2Wiki using the newly materialized local development specification.
# INPUT_PIN must match the independently recorded materialization receipt.
"$PY" scripts/run_week9_protocol_poison_matrix.py freeze-protocol --scope development \
  --model-snapshot "$MODEL" \
  --replication-spec "$OUT/twowiki-development/local/replication_inputs.json" \
  --replication-spec-sha256 "$INPUT_PIN" --output "$OUT/twowiki-development/protocol.json"
```

Freezes are performed only from the clean new commit. The external manifest carries
actual pins and a separate `SMOKE_COMMANDS.sh` carries exact prepared stage commands.
Those model commands require new approval and were not executed. Transfer stages
remain `candidates`, `source-select`, `evaluate`, `aggregate`; 2Wiki stages remain
`construct`, `evaluate`, `aggregate`. Subsequent stages require the previous complete
artifact's trusted hash. Held-out transfer model stages also require
`--allow-full-compute`, which is not included in development smoke commands.

No intensity/source/seed reduction or new target-review interpretation is introduced.
The explicitly authorized caching changes fresh-call repetition and timing accounting;
if repeated uncached timing is required as an endpoint it needs a separate benchmark,
not a claim that cached timings are comparable. Full compute still requires approval.

## Initial reliability-commit software verification

Final offline full suite: **1,022 passed, zero failed, 105.81 seconds**.
Focused reliability/transfer/replication regressions: **30 passed, 3.01 seconds**.
Compilation of `src scripts tests` and whitespace checks passed. Earlier test runs
and logs are retained; final verification includes the streaming-hash regression.
No real MLX generation, full experiment, push, merge or README update occurred.

## Release continuation verification

The final continuation passed **1,024 offline tests in 110.82 seconds** and
**32 focused regressions in 4.60 seconds**. It corrected existing-aggregate
revalidation and the previously accepted-but-ignored 2Wiki construction batch
limit, without changing scientific selection or metrics. See the
[final execution handoff](OCT26_FINAL_EXECUTION_HANDOFF.md) for the release
namespace and commands. Earlier freezes remain intact and bind their own commits.
