#!/bin/sh
# Exact command worksheet. PREPARED ONLY: do not run without full-compute approval.
# Repeating the same command resumes completed checkpoints; exit 75 is a planned pause.
set -eu
: "${OCT26_FULL_RUN_APPROVAL:?After explicit approval choose twowiki or transfer}"
WORK=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$WORK"
PY=${OCT26_PYTHON:-/Users/sadiapeerzada/Downloads/rag-poison-transfer/.venv/bin/python}
MANIFEST=${OCT26_EXECUTION_MANIFEST:-/private/tmp/oct26-reliable-release-2026-10-26-v1/EXECUTION_MANIFEST.json}
MAX_BATCHES=${OCT26_MAX_BATCHES:-12}
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1
field() { "$PY" -c 'import json,sys; x=json.load(open(sys.argv[1]));
for k in sys.argv[2:]: x=x[k]
print(x)' "$MANIFEST" "$@"; }
pin() { "$PY" -c 'import hashlib,sys; f=open(sys.argv[1],"rb"); print(hashlib.file_digest(f,"sha256").hexdigest())' "$1"; }
test "$(git rev-parse HEAD)" = "$(field git_commit_sha)"
test -z "$(GIT_OPTIONAL_LOCKS=0 git status --porcelain --untracked-files=all)"
MODEL=$(field model_snapshot)
case "$OCT26_FULL_RUN_APPROVAL" in
 twowiki|transfer) NAME=$OCT26_FULL_RUN_APPROVAL-heldout ;;
 *) printf '%s\n' 'Choose twowiki or transfer; no other scope is supported.' >&2; exit 2 ;;
esac
P=$(field protocols "$NAME" protocol)
P_SHA=$(field protocols "$NAME" sha256)
test "$(pin "$P")" = "$P_SHA"
if [ "$OCT26_FULL_RUN_APPROVAL" = twowiki ]; then
 C=$(field protocols "$NAME" planned_outputs construction)
 E=$(field protocols "$NAME" planned_outputs evaluation)
 A=$(field protocols "$NAME" planned_outputs aggregate)
 if [ ! -e "$C/construction.seal.json" ]; then
  "$PY" scripts/run_week9_protocol_poison_matrix.py construct --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --construction-dir "$C" --max-batches "$MAX_BATCHES"
 fi
 C_SHA=$(pin "$C/construction.seal.json")
 "$PY" scripts/run_week9_protocol_poison_matrix.py evaluate --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E" --max-batches "$MAX_BATCHES"
 E_SHA=$(pin "$E/evaluation.complete.json")
 "$PY" scripts/run_week9_protocol_poison_matrix.py aggregate --protocol "$P" --protocol-sha256 "$P_SHA" --construction-dir "$C" --construction-seal-sha256 "$C_SHA" --evaluation-dir "$E" --evaluation-completion-sha256 "$E_SHA" --output "$A"
else
 C=$(field protocols "$NAME" planned_outputs candidates)
 S=$(field protocols "$NAME" planned_outputs selection)
 E=$(field protocols "$NAME" planned_outputs evaluation)
 A=$(field protocols "$NAME" planned_outputs aggregate)
 "$PY" scripts/run_source_selection_transfer.py candidates --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --output "$C" --allow-full-compute --max-batches "$MAX_BATCHES"
 C_SHA=$(pin "$C/candidates.complete.json")
 "$PY" scripts/run_source_selection_transfer.py source-select --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --input-dir "$C" --input-sha256 "$C_SHA" --output "$S" --allow-full-compute --max-batches "$MAX_BATCHES"
 S_SHA=$(pin "$S/selection.seal.json")
 "$PY" scripts/run_source_selection_transfer.py evaluate --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --input-dir "$S" --input-sha256 "$S_SHA" --output "$E" --allow-full-compute --max-batches "$MAX_BATCHES"
 E_SHA=$(pin "$E/transfer.complete.json")
 "$PY" scripts/run_source_selection_transfer.py aggregate --protocol "$P" --protocol-sha256 "$P_SHA" --model-snapshot "$MODEL" --input-dir "$E" --input-sha256 "$E_SHA" --selected-dir "$S" --selection-seal-sha256 "$S_SHA" --output "$A"
fi
