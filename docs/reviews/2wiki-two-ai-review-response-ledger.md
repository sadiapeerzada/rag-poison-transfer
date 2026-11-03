# 2Wiki first-six independent AI review: capture and read-only adjudication

## Starting point

The Mac run has already succeeded: 12/12 batch-preparation tests;
6 development cases; 12 prompts saved in:

    ~/Documents/rag-research-results/twowiki-two-ai-blinded-first6-20261103T171532Z

The original 20 source-complete dossiers remain pinned:

    ~/Documents/rag-research-results/twowiki-generic-dev25-review-20261103T170934Z.json

The generation models v4–v6, post-hoc screening, clean baseline,
held-out matrix and source documents remain frozen and unmodified.

## Reviewer procedure

Run Reviewer A and Reviewer B in genuinely separate model/provider
environments. Use exactly the corresponding frozen .txt prompt for each
case, not a shortened paraphrase. Do not show Reviewer B the responses
from A. Do not use the same model under different seeds as independent
reviewers. Save the exact raw model JSON output, including its original
newlines, to a temporary file.

Capture real model identifiers, actual run or response IDs and the
correct timezone-aware review timestamp. If run metadata cannot be
verified from provider records, document the limitation explicitly.
**No model identity can be authenticated merely by a locally supplied
string.** Never fabricate metadata or copy one response as two reviews.

## Example: capture ONE actual response

    WT="$HOME/Documents/rag-2wiki-two-ai-review-ledger"
    ROOT="$HOME/Documents/rag-research-results"
    PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
    BATCH="$ROOT/twowiki-two-ai-blinded-first6-20261103T171532Z"
    DOSSIERS="$ROOT/twowiki-generic-dev25-review-20261103T170934Z.json"
    RESP="$ROOT/twowiki-two-ai-review-raw"

    cd "$WT"
    "$PY" -B -m scripts.record_twowiki_two_ai_review_response \
      --batch-dir "$BATCH" --dossiers "$DOSSIERS" \
      --responses-dir "$RESP" \
      --case-index 1 --reviewer-slot A \
      --raw-response-file "/path/to/real/model_response.json" \
      --model-id "ACTUAL_PROVIDER_MODEL_ID" \
      --review-run-id "ACTUAL_PROVIDER_RUN_OR_RESPONSE_ID" \
      --reviewed-at "ACTUAL_TIMESTAMP_WITH_UTC_OFFSET"

Use *actual* values, not the uppercase placeholders above. Repeat
with reviewer B and the other five cases. The program computes and
records raw response and prompt hashes, stores the original response
unmodified and refuses to overwrite previous captures.

## Run the ledger audit (also safe before reviews arrive)

    "$PY" -B -m scripts.audit_twowiki_two_ai_review_responses \
      --batch-dir "$BATCH" --dossiers "$DOSSIERS" \
      --responses-dir "$RESP" \
      --output "$ROOT/twowiki-two-ai-review-audit-$(date -u +%Y%m%dT%H%M%SZ).json"

The auditor reconstructs and byte-checks the batch; checks each
prompt and source SHA, exact source-document quotes, all required
structured fields, gold/alias distinctness, model and run IDs,
timezone-aware timestamps, and stored raw-response hashes. Cases can
be pending, invalid, uncertain/rejected, independent-review provenance
inadequate, two target proposals in disagreement, or **concordant
provisional AI only**.

Literal exact quotes do not prove source entailment. Reviewer metadata
is operator-supplied, not independently authenticated. The ledger
always sets factual_approvals, construction_approvals,
injection_approvals and poison_injections to zero.

## Repository verification

    (
    set -e
    BASE="$HOME/Documents/rag-2wiki-two-ai-review"
    WT="$HOME/Documents/rag-2wiki-two-ai-review-ledger"
    PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
    cd "$BASE"
    git fetch origin research/2wiki-two-ai-review-ledger-validation
    if [ ! -d "$WT" ]; then
      git worktree add --detach "$WT" FETCH_HEAD
    fi
    cd "$WT"
    git checkout --detach origin/research/2wiki-two-ai-review-ledger-validation

    "$PY" -B -m pytest -q \
      tests/test_twowiki_two_ai_review_response_audit.py \
      tests/test_twowiki_two_ai_review_capture.py

    "$PY" -B -m scripts.audit_twowiki_two_ai_review_responses \
      --batch-dir "$HOME/Documents/rag-research-results/twowiki-two-ai-blinded-first6-20261103T171532Z" \
      --dossiers "$HOME/Documents/rag-research-results/twowiki-generic-dev25-review-20261103T170934Z.json" \
      --responses-dir "$HOME/Documents/rag-research-results/twowiki-two-ai-review-raw" \
      --output "$HOME/Documents/rag-research-results/twowiki-two-ai-review-pending-$(date -u +%Y%m%dT%H%M%SZ).json"
    )

Before the two real reviewer runs, the expected result is six pending,
zero approvals. Do not misrepresent the pending audit as completed
reviews. Frozen outcomes for v4/v5/v6 and the original research
matrices must remain unchanged.

## Gate

Proceed to a separate, preregistered train-only construction pilot
only after target types/source chains are independently examined and
provenance concerns adjudicated. No retrieval attack or 300-query
held-out test is authorized by this review ledger.
