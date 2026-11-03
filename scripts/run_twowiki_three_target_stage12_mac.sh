#!/usr/bin/env bash
# Explicit user-run real inference on Mac: three frozen targets, two distinct
# independent AI reviewers, then one exploratory legacy-semantic construction.
# No held-out inputs are read; no completed reviewer call is retried.
set -euo pipefail

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${RAG_PYTHON:-$HOME/Downloads/rag-poison-transfer/.venv/bin/python}"
ROOT="${RAG_RESULTS:-$HOME/Documents/rag-research-results}"
DEV="$ROOT/twowiki-v2-development-recovery-20261103/development_data.json"
DOS="$ROOT/twowiki-generic-dev25-review-20261103T170934Z.json"
OLD="$ROOT/twowiki-two-ai-real-review-audit-20261103T174042Z.json"
QWEN="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
PHI="$HOME/.cache/huggingface/hub/models--mlx-community--Phi-4-mini-instruct-4bit/snapshots/ac1c269cb4222a4e136a3d09edad301056c1f36a"
QWEN_ID='mlx-community/Qwen2.5-7B-Instruct-4bit@c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed'
PHI_ID='mlx-community/Phi-4-mini-instruct-4bit@ac1c269cb4222a4e136a3d09edad301056c1f36a'
RUN_ID="${RAG_REVIEW_RUN_ID:-twowiki-three-candidate-gate-20261104-v1}"
BATCH="$ROOT/$RUN_ID"
AUDIT="$ROOT/$RUN_ID-audit.json"
SEMANTIC="$ROOT/$RUN_ID-semantic"

cd "$WT"
# An interrupted batch is forensic evidence. Never begin a fresh run to bypass it.
if [[ -e "$BATCH" || -e "$AUDIT" || -e "$SEMANTIC" ]]; then
  echo "Existing run artifacts detected; inspect them and do not rerun the batch: $BATCH" >&2
  exit 1
fi
for path in "$PY" "$DEV" "$DOS" "$OLD" "$QWEN/config.json" "$PHI/config.json"; do
  if [[ ! -f "$path" ]]; then printf 'Missing input: %s\n' "$path" >&2; exit 1; fi
done
if [[ -n "$(git status --porcelain)" ]]; then echo 'Dirty worktree; aborting before inference' >&2; exit 1; fi
if command -v caffeinate >/dev/null 2>&1; then
  RUN=(caffeinate -i)
else
  RUN=()
fi
base=(--batch "$BATCH" --dossiers "$DOS" --development "$DEV" --previous-audit "$OLD")
gate() { local stage="$1"; shift; "$PY" -B -m scripts.twowiki_three_case_candidate_gate "$stage" "${base[@]}" "$@"; }

echo '=== TEST: synthetic only; no model calls ==='
"$PY" -B -m pytest -q tests/test_twowiki_three_case_candidate_gate.py

echo '=== FREEZE: immutable separate post-hoc candidate-specific review ==='
gate freeze

echo '=== REVIEWER A: Qwen preflight, then three real calls ==='
gate review --slot A --model-snapshot "$QWEN" --model-id "$QWEN_ID" --preflight
"${RUN[@]}" "$PY" -B -m scripts.twowiki_three_case_candidate_gate review "${base[@]}" --slot A --model-snapshot "$QWEN" --model-id "$QWEN_ID"

echo '=== REVIEWER B: Phi-4 preflight, then three real calls ==='
gate review --slot B --model-snapshot "$PHI" --model-id "$PHI_ID" --preflight
"${RUN[@]}" "$PY" -B -m scripts.twowiki_three_case_candidate_gate review "${base[@]}" --slot B --model-snapshot "$PHI" --model-id "$PHI_ID"

echo '=== AUDIT: immutable read-only decisions; no automatic factual approvals ==='
gate audit --output "$AUDIT"

echo '=== SEMANTIC: one train-only target using held-out-compatible legacy syntax ==='
gate semantic --model-snapshot "$QWEN" --model-id "$QWEN_ID" --output "$SEMANTIC" --semantic-profile heldout-compatible-legacy --preflight
"${RUN[@]}" "$PY" -B -m scripts.twowiki_three_case_candidate_gate semantic "${base[@]}" --model-snapshot "$QWEN" --model-id "$QWEN_ID" --output "$SEMANTIC" --semantic-profile heldout-compatible-legacy

echo '=== FINAL REPORT (does not authorize held-out execution) ==='
"$PY" - "$AUDIT" "$SEMANTIC/result.json" "$BATCH" <<'PY'
import json,sys
from pathlib import Path
review=json.loads(Path(sys.argv[1]).read_text())
semantic=json.loads(Path(sys.argv[2]).read_text())
print('Frozen review:', sys.argv[3])
print('Independent AI review audit:', sys.argv[1])
print('Candidate review statuses:', [r['status'] for r in review['rows']])
print('AI agreement count:',review['concordant_provisional_ai_cases'])
print('Independent factual approvals:',review['factual_approvals'])
print('Semantic attempt result:',semantic['status'])
print('Semantic generation calls:',semantic['model_calls'])
print('Semantic output:',sys.argv[2])
print('Held-out matrix remains NOT STARTED; manual scientific acceptance required.')
PY