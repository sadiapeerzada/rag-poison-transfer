#!/usr/bin/env bash
# Research gates: safe local Mac runner; no inference unless model-run is explicitly invoked.
set -euo pipefail
REPO="$HOME/Downloads/rag-poison-transfer"
ROOT="$HOME/Documents/rag-research-results"
TRANSFER="$ROOT/hotpotqa-transfer-20261028/transfer"
TWOWIKI="$ROOT/twowiki-300-readiness-20261106/authorized-matrix"
# When evidence was restored elsewhere, set TWOWIKI_EVAL_DIR to the directory
# containing evaluation.complete.json; never assume the restore tree structure.
TWOWIKI_EVAL_DIR="${TWOWIKI_EVAL_DIR:-$TWOWIKI/evaluation}"
OUT="$ROOT/nov09-research-gates"
PY="$REPO/.venv/bin/python"
# Use a repository-local import path in Mac VS Code shell executions.
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
cmd="${1:-help}"

say() { printf '\n[%s] %s\n' "$cmd" "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 2; }
file() { test -f "$1" || fail "Missing file: $1"; }

cd "$REPO" || fail "Repository missing: $REPO"
file "$PY"

case "$cmd" in
  status)
    git status --short --branch
    git branch -vv | sed -n '1,18p'
    printf '\nHEAD: '; git rev-parse --short HEAD
    printf 'origin/main: '; git rev-parse --short origin/main
    if test -f tests/test_nov09_research_gates.py; then
      say 'Research tests are present in this local checkout.'
    else
      say 'Research tests are missing. Use bootstrap if working tree is clean.'
    fi
    ;;

  bootstrap)
    test -z "$(git status --porcelain)" || fail 'Local changes detected. Save them safely before changing branches; nothing was reset.'
    git fetch origin main
    git switch main
    git pull --ff-only origin main
    file tests/test_nov09_research_gates.py
    "$PY" -m pytest -q tests/test_nov09_research_gates.py
    say 'Source synced and synthetic tests executed. Frozen local datasets untouched.'
    ;;

  transfer-audit)
    file "$TRANSFER/protocol.json"
    file "$TRANSFER/execution/selection/selection.seal.json"
    file "$TRANSFER/execution/evaluation/transfer.complete.json"
    file "$TRANSFER/execution/aggregate.json"
    file paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json
    mkdir -p "$OUT"
    report="$OUT/hotpotqa-transfer-audit-$(date -u +%Y%m%dT%H%M%SZ).json"
    "$PY" scripts/audit_hotpotqa_transfer_raw_offline.py \
      --protocol "$TRANSFER/protocol.json" \
      --selected-dir "$TRANSFER/execution/selection" \
      --evaluation-dir "$TRANSFER/execution/evaluation" \
      --original-aggregate "$TRANSFER/execution/aggregate.json" \
      --public-aggregate paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json \
      --report-out "$report"
    say "Private 240-cell raw audit report: $report"
    ;;

  semantic-status)
    packet="$ROOT/2wiki-paired-review-20261109/review_packet.jsonl"
    summary="$ROOT/2wiki-paired-review-20261109/audit_summary.json"
    file "$packet"; file "$summary"
    "$PY" - "$packet" "$summary" <<'PYTHON'
import hashlib, json, sys
packet, summary = sys.argv[1:]
rows = [json.loads(s) for s in open(packet, encoding='utf-8') if s.strip()]
meta = json.load(open(summary, encoding='utf-8'))
assert len(rows) == 131 and len({r['query_id'] for r in rows}) == 102
assert meta['selected_review_cases'] == 131 and meta['selected_distinct_query_ids'] == 102
counts = {}
for row in rows: counts[row['construction_status']] = counts.get(row['construction_status'], 0) + 1
print(json.dumps({'status': 'AI_ASSISTED_ONLY_NOT_HUMAN_CERTIFIED',
  'selected_case_rows': len(rows), 'distinct_questions': len({r['query_id'] for r in rows}),
  'construction_counts': counts, 'independent_human_review': 'NOT_PERFORMED',
  'source_backed_factuality_of_all_cases': 'NOT_ESTABLISHED',
  'packet_sha256': hashlib.sha256(open(packet, 'rb').read()).hexdigest()}, indent=2))
PYTHON
    ;;

  rcd-ablation)
    : "${DIAGNOSTICS_JSONL:?Set DIAGNOSTICS_JSONL to a real private saved RCD last_diagnostics JSONL file}"
    file "$DIAGNOSTICS_JSONL"
    mkdir -p "$OUT"
    "$PY" scripts/rcd_offline_scoring_ablations.py \
      --diagnostics-jsonl "$DIAGNOSTICS_JSONL" --top-k 3 \
      --output "$OUT/rcd-ranking-only-$(date -u +%Y%m%dT%H%M%SZ).json"
    say 'This is post-hoc ranking-only; no alternate ASR or true no-rewrite experiment.'
    ;;

  model-prepare)
    file "$TWOWIKI_EVAL_DIR/evaluation.complete.json"
    mkdir -p "$OUT"
    "$PY" scripts/second_model_prompt_replay.py prepare \
      --evaluation-dir "$TWOWIKI_EVAL_DIR" --n-per-stratum 10 \
      --output "$OUT/2wiki-second-model-plan-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
    say 'Record output plan path and printed plan SHA-256; do not commit private prompts.'
    ;;

  model-pin)
    : "${MODEL_SNAPSHOT:?Set MODEL_SNAPSHOT to absolute path to a locally cached non-Qwen MLX model snapshot}"
    "$PY" scripts/second_model_prompt_replay.py pin-model --model-snapshot "$MODEL_SNAPSHOT"
    ;;

  model-run)
    : "${MODEL_SNAPSHOT:?MODEL_SNAPSHOT missing}"
    : "${MODEL_PLAN:?MODEL_PLAN missing}"
    : "${MODEL_PLAN_SHA:?MODEL_PLAN_SHA missing}"
    : "${MODEL_SHA:?MODEL_SHA missing}"
    mkdir -p "$OUT"
    "$PY" scripts/second_model_prompt_replay.py run --execute \
      --plan "$MODEL_PLAN" --plan-sha256 "$MODEL_PLAN_SHA" \
      --model-snapshot "$MODEL_SNAPSHOT" --model-sha256 "$MODEL_SHA" \
      --output "$OUT/2wiki-second-model-results_PRIVATE" --max-tokens 128
    ;;

  model-aggregate)
    : "${MODEL_PLAN:?MODEL_PLAN missing}"
    : "${MODEL_PLAN_SHA:?MODEL_PLAN_SHA missing}"
    file "$OUT/2wiki-second-model-results_PRIVATE/run_manifest.json"
    "$PY" scripts/second_model_prompt_replay.py aggregate \
      --plan "$MODEL_PLAN" --plan-sha256 "$MODEL_PLAN_SHA" \
      --results "$OUT/2wiki-second-model-results_PRIVATE" \
      --output "$OUT/2wiki-second-model-aggregate-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
    ;;

  *)
    echo 'Usage: bash scripts/nov09_mac_research.sh [status|bootstrap|transfer-audit|semantic-status|rcd-ablation|model-prepare|model-pin|model-run|model-aggregate]'
    echo 'This script never invents human judgments. No human factuality review is performed.'
    echo 'No full no-rewrite/depth ablations are run; they require separately authorized retrieval + model evaluation.'
    ;;
esac
