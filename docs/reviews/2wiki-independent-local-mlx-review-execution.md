# Two independent local MLX reviews: real model execution

## What is already frozen

Six first-in-cohort train-only questions, two separately blinded
prompt sets, exact 20-dossier source text, prior 15/15 review-ledger
regression tests. The question/answer and source packet must **not**
be modified. This runner does not generate counterfactual passages or
touch poisoned/held-out experiment outputs.

## Run criteria

Use two *different, actually installed* local MLX Instruct models.
Examples of model families: Qwen2.5 for Reviewer A; an independent
Phi model for Reviewer B **if already installed and compatible**.
Never relabel two seeds/snapshots of the same model as two reviewers.

This runner refuses to download models implicitly: each --model-path
must be an existing, local snapshot with config.json and
tokenizer_config.json. It does not claim authenticated model identity.
It records actual local run UUIDs, immutable raw UTF-8 responses and
per-response timestamps/seed/config/prompt hashes. These are
**local identifiers**, NOT authenticated external provider IDs.

Each reviewer is run in a separate invocation so only one model is
held in memory on the Mac. Reviewer B won't start until A has six
complete recorded responses. A and B must have different supplied
IDs **and different resolved model snapshot directories**.

## Verify tests and available models on Mac

    (
    set -e
    BASE="$HOME/Documents/rag-2wiki-two-ai-review-ledger"
    WT="$HOME/Documents/rag-2wiki-mlx-review-execution"
    PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
    cd "$BASE"
    git fetch origin research/2wiki-independent-mlx-review-execution
    if [ ! -d "$WT" ]; then
      git worktree add --detach "$WT" FETCH_HEAD
    fi
    cd "$WT"
    git checkout --detach origin/research/2wiki-independent-mlx-review-execution
    "$PY" -B -m pytest -q tests/test_twowiki_independent_mlx_reviewer.py
    )

Find *installed* model snapshots without downloading anything:

    find "$HOME/.cache/huggingface/hub" -type f -name config.json -path '*/snapshots/*' -print

If only one compatible independent Instruct model is installed,
**do not pretend** to have two-model review. Use a genuinely
different external provider/model with its actual captured response
and provenance, or install a distinct MLX model under a documented
budget and revision-control protocol.

## Execute Reviewer A (example local Qwen snapshot)

In the same terminal set:

    WT="$HOME/Documents/rag-2wiki-mlx-review-execution"
    ROOT="$HOME/Documents/rag-research-results"
    PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
    BATCH="$ROOT/twowiki-two-ai-blinded-first6-20261103T171532Z"
    DOSSIERS="$ROOT/twowiki-generic-dev25-review-20261103T170934Z.json"
    RESP="$ROOT/twowiki-two-ai-review-raw"

    MODEL_A="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"

    cd "$WT"
    "$PY" -B -m scripts.run_twowiki_independent_mlx_reviewer \
      --batch-dir "$BATCH" --dossiers-path "$DOSSIERS" \
      --responses-dir "$RESP" \
      --reviewer-slot A --model-path "$MODEL_A" \
      --model-id "mlx-community/Qwen2.5-7B-Instruct-4bit@c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed" \
      --preflight

Once the no-model preflight passes, repeat the same command
**without --preflight** to perform exactly six model calls.
Do **not** rerun completed/indeterminate calls automatically.

## Execute Reviewer B

Pick a separately installed, compatible local model, with a different
resolved snapshot path and honest distinct actual identifier:

    MODEL_B="/absolute/path/to/OTHER_INSTALLED_MLX_MODEL_SNAPSHOT"
    MODEL_B_ID="REAL_OTHER_MLX_MODEL_ID_AND_REVISION"

    "$PY" -B -m scripts.run_twowiki_independent_mlx_reviewer \
      --batch-dir "$BATCH" --dossiers-path "$DOSSIERS" \
      --responses-dir "$RESP" \
      --reviewer-slot B --model-path "$MODEL_B" \
      --model-id "$MODEL_B_ID" --preflight

After a successful preflight, rerun without --preflight.

## Analyze saved responses without changing them

    "$PY" -B -m scripts.audit_twowiki_two_ai_review_responses \
      --batch-dir "$BATCH" --dossiers "$DOSSIERS" \
      --responses-dir "$RESP" \
      --output "$ROOT/twowiki-two-ai-real-review-audit-$(date -u +%Y%m%dT%H%M%SZ).json"

The model may return malformed JSON, incomplete citations or
unsupported targets. Those outcomes MUST be counted as actual
review failures/uncertainties rather than fixed silently.
No inference about factual truth may be drawn from lexical citation
matches alone.

## Resume/review of failed calls

The runner writes a .intent.json **before each call** and
an .error.json if an exception is caught. It refuses to overwrite
either. After a failure, preserve the record, classify whether a
physical generation may have occurred, and make a separately versioned
retry protocol if needed. Never simply repeat the complete batch.

## Research boundary

This stage generates REVIEW JUDGMENTS on train-only documents, not
poisoned evidence. No construction approval, injection, held-out
query, 300-query matrix or claim of independent factual verification
is authorized by this tool or its audit labels.
