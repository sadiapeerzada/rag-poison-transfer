# Task 5 — genuine evidence-dependent two-round poisoned QA versus frozen Dense

**Date:** 9 November 2026  
**Status:** New real experiment workflow *implemented*; the owner's original Mac retrieval, private Qwen generator calls and paired result report must still actually run.  
**Source:** Original sealed 2Wiki frozen run and the already-executed private 480-response 2Wiki RCD ablation prompt plan. **Never alter** original construction, frozen evaluation, protocol or past results.

## Why this is the next real experiment

The repo's two-round retrieval policy already exists in `src/defenses/iterative/retriever.py`. Its round-two query derives an anchor from **first-round retrieved evidence**, not an attacker label, gold answer or query synonym list.

This study uses the 40 valid post-hoc selected original cell/question positions (36 unique original questions) from the existing completed Qwen 2Wiki RCD ablation. It compares **new real iterative retrieval/QA** against the **actual original frozen Dense QA** for identical queries and clean/poisoned corpora. We **reuse original Dense QA only when its source document IDs and entire generator prompt reproduce byte-identically** from an independently reconstructed Dense index; any mismatch aborts with no new Qwen call.

No new inference is necessary to rerun those original 80 clean/poison Dense outcomes. Up to 80 **new iterative-only** Qwen calls are necessary unless the policy explicitly abstains; the real number is reported by `prepare` and frozen in the private plan.

The policy (two rounds, candidate top-10, output top-3, coverage threshold 0.75, weighted RRF) is unchanged; there is no tuning on frozen held-out answers.

## Stage 1: REAL retrieval + parity preflight, no Qwen generation

From the repo root on the original Mac:

```bash
cd "$HOME/Downloads/rag-poison-transfer"
git fetch origin
git switch main
git pull --ff-only origin main

python -m pytest -q tests/test_run_2wiki_iterative_matched_qa.py \
  tests/test_evidence_dependent_iterative_retrieval.py

ROOT="$HOME/Documents/rag-research-results"
RUN="$ROOT/twowiki-300-readiness-20261106/authorized-matrix"
PLAN="$ROOT/nov09-research-gates/task5-iterative-plan-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
df -h "$HOME"

python scripts/run_2wiki_iterative_matched_qa.py prepare \
  --original-run "$RUN" \
  --out "$PLAN"

shasum -a 256 "$PLAN"
```

The plan SHA-256 in the last command must match the `plan_sha256` in `prepare` output. Save both `PLAN` and the digest exactly. This stage builds fresh clean/poison dense indexes per cell using the original pinned BGE model and performs actual iterative retrieval; it **does not load Qwen or generate QA answers**.

Expected prerequisites: the prior private 2Wiki frozen 300-query run, its original local input file and embedding snapshot, the **completed 480-Qwen-ablation private run** and its exact SHA-pinned 480-row retrieval plan. Source locator uses the already merged Task 6 `verify_ablation_sources` helper. If the original local input or prompt plan moved, use `--local-data` or `--private-ablation-plan` pointing to the **authentic hash-matched** original; do not reconstruct or replace missing evidence.

**Stop and send error text** if any of the **80 original Dense prompt/evidence parity checks** fail. Do not force a baseline mismatch through with synthetic data or changed retrieval configuration.

## Stage 2: limited real Qwen model calls with explicit authorization

Stage 2 has real, potentially costly model calls. **Do not start it unless the user has explicitly authorized local inference and the Mac has enough disk, RAM/Metal memory and a recovery/backup plan.** The runner never schedules background work. Once resources are approved:

```bash
ROOT="$HOME/Documents/rag-research-results"
RUN="$ROOT/twowiki-300-readiness-20261106/authorized-matrix"
PIN="$(shasum -a 256 "$PLAN" | awk '{print $1}')"

SNAP="$(python - "$RUN/protocol.json" <<'PY'
import json, sys
from pathlib import Path
p = json.load(open(sys.argv[1], encoding="utf-8"))
repo = p["binding"]["model_identity"]
revision = p["model"]["revision"]
path = Path.home() / ".cache/huggingface/hub" / ("models--" + repo.replace("/", "--")) / "snapshots" / revision
print(path)
PY
)"

RUN_OUT="$ROOT/nov09-research-gates/task5-iterative-real-qwen-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE"

python scripts/run_2wiki_iterative_matched_qa.py run \
  --plan "$PLAN" --plan-sha256 "$PIN" \
  --protocol "$RUN/protocol.json" \
  --model-snapshot "$SNAP" \
  --results-dir "$RUN_OUT" \
  --max-new-requests 4 --execute
```

First physical execution is capped at **4 new requests**. Inspect the receipt for `ITERATIVE_NEW_QWEN_PARTIAL`, `verified_real_qa_observations` and `remaining`. If all 4 newly recorded calls validate and the resource plan permits completion, resume the **same** `PLAN`, `PIN`, `SNAP` and `RUN_OUT` with `--execute` (omit `--max-new-requests`).

If the run stops after writing an intent and before a verified response, **do not delete or automatically retry the intent**. The script raises an unresolved-call error; manually inspect the private journal and clarify whether the model produced a response before deciding a separate recovery protocol.

The source Qwen snapshot is checked against **every pinned original model file hash**, repository and revision. All Qwen responses, original questions, accepted poison passages, prompts and local paths stay private.

## Stage 3: matched QA and question-cluster intervals (no Qwen calls)

Only when the run reports `ITERATIVE_NEW_QWEN_COMPLETE`:

```bash
python scripts/run_2wiki_iterative_matched_qa.py aggregate \
  --plan "$PLAN" --plan-sha256 "$PIN" \
  --results-dir "$RUN_OUT" \
  --out "$ROOT/nov09-research-gates/task5-iterative-summary-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
```

The aggregate requires every actual recorded response, reconciles raw Qwen text with extracted and scored answers, includes abstentions as answer failures, and reports:
- paired *target-match rate* in poisoned inputs, iterative vs **reused exact original Dense**;
- paired clean and poisoned gold correctness, poison exposure and actual one/two-round retrieval operations;
- 2,000-replicate nominal **whole-original-question-cluster** bootstrap CIs preserving repeated query cells.

No Qwen calls are made by `aggregate`; no private source questions, case-level IDs or raw prompts appear in its **console summary**.

## Scientific boundaries

- **Exploratory, not prospective.** Selection is valid-only, post-hoc, and repeated questions can appear in separate poisoning cells. 40 slots are **36 distinct questions**, not 40 independent questions and not 300 new held-out queries.
- **Original dataset risk disclosed.** The original 2Wiki held-out cohort has historical exposure/custody limitations; no fresh blind subject guarantee is claimed.
- **Frozen real controls.** Original Dense outcomes are reused only on exact current evidence-ID and original-prompt parity; if this fails, the study cannot proceed as designed.
- **Real evidence-dependent adaptation.** The first-round evidence changes second-round queries (when triggered), and the trace records one or two actual retrieval calls. This is a deterministic heuristic, **not a learned adaptive controller**.
- **Methodological causality limits.** A target answer alone does not prove poison caused the answer; track clean correctness, poison exposure, and clean-to-poison degradation separately.
- **Resource/timing comparability.** Old Dense QA came from the original run; new and old generation wall-clock speeds cannot be compared as a controlled timing benchmark. New iterative retrieval times are descriptive.
- **Task 5 verdict after actual run:** a valid *bounded exploratory two-round poisoned QA* result can be reported with transparent limits. **Original full multi-dataset, prospective/independently held-out adaptive study still requires stronger experiments.**
- **Do not update primary original construction/QA denominators**, rewrite historical result files, or claim model inference occurred based on synthetic tests or a retrieval plan alone.

The owner's private empirical receipt and signed research scope determine what legitimately closes Task 5; not this PR.
