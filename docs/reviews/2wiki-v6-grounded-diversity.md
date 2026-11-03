# 2Wiki v6: source-grounded passage-diversity development test

## Motivation / historical record

v4: **0/30** strict validator passes.
v5: **30/30** surface review candidates, but **0/5** cases with three
distinct passages, on **five repeatedly tuned development queries**. Each
two-attempt pair duplicated the same greedy generation. Neither finding
demonstrates an independently validated or injectable false document.

**v6 changes the construction method, not the original results.**

## Key v6 controls

- Same five previously screened development queries, pinned source-review
  packet, local MLX Qwen model revision, 15 slots and two attempts per slot.
- Every slot has a different, **source-literal** contextual anchor: a film
  year, named cast member, award/submission or studio named in the supplied
  supporting documents. Each anchor binds to its source ID/SHA-256, and the
  exact source text is checked before a model call.
- Output instruction is **two complete sentences**: (1) a true contextual
  film/person fact supported by the selected source excerpt; (2) the explicit
  intentionally false target relation preserving exact film titles and named
  directors. No invented peripheral facts are permitted.
- Checks reject wrong directors, incomplete titles, extra/absent anchors,
  conflicting location claims, yes/no markers used for place questions,
  failure to affirm the target, and duplicate surface passages. It requires
  all three requested anchor contexts, not merely different seeds.
- All candidates remain **unverified**. The validators cannot establish
  global factual truth, entailment, credible supporting details, source
  independence, or certified reviewer identity. Each candidate needs
  *manual/independent factual-content review* before any poison injection.
- The v6 test is exploratory on previously observed cases, **not a new
  generalization claim**, and should not be used to tune against held-out
  questions or to alter the frozen HotpotQA matrix.
- 150 tokens max per generation, up to 30 calls total, with the same local
  Qwen snapshot and per-attempt seed derivation as v5.
- Each call writes an intent before generation and a response/error file.
  Interrupted/indeterminate calls must not be replayed casually or counted
  as completed.

## Local Mac reproduction

```bash
(
set -e
BASE="$HOME/Documents/rag-2wiki-v3-development"
WT="$HOME/Documents/rag-2wiki-v6-diagnostic"
PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
ROOT="$HOME/Documents/rag-research-results"

cd "$BASE"
git fetch origin research/2wiki-v6-grounded-diversity-diagnostic
if [ ! -d "$WT" ]; then
  git worktree add --detach "$WT" FETCH_HEAD
fi
cd "$WT"
git checkout --detach origin/research/2wiki-v6-grounded-diversity-diagnostic

"$PY" -B -m pytest -q \
  tests/test_semantic_fluent_development_v6.py \
  tests/test_twowiki_v6_grounded_diversity.py

PACKET="$HOME/Downloads/twowiki_v4_1_audit_inputs/2wiki_v4_1_independent_review_packet.zip"
V5="$ROOT/twowiki-qwen-v5-20261103T160252Z"
MODEL="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
OUT="$ROOT/twowiki-qwen-v6-$(date -u +%Y%m%dT%H%M%SZ)"

"$PY" -B -m scripts.run_twowiki_v6_grounded_diversity \
  --repo "$WT" --packet "$PACKET" \
  --v5-summary "$V5/summary.json" --v5-manifest "$V5/manifest.json" \
  --model-snapshot "$MODEL" --output "$OUT" --preflight

caffeinate -i "$PY" -B -m scripts.run_twowiki_v6_grounded_diversity \
  --repo "$WT" --packet "$PACKET" \
  --v5-summary "$V5/summary.json" --v5-manifest "$V5/manifest.json" \
  --model-snapshot "$MODEL" --output "$OUT"

echo "RESULTS: $OUT/summary.json"
)
```

Do not run the actual generator if tests or preflight fail. Reruns use
distinct output directories and should never overwrite a previous attempt.

## Decision gate following v6

- Evaluate `surface_review_candidates`, `three_context_candidate_cases`,
  per-case rejection reasons and actual saved raw response content.
- If three diverse passages genuinely emerge, independently review every
  factual side claim and the exact false relation. Three different context
  anchors are **not necessarily independent sources**.
- If v6 still produces one or two usable passages per case, stop tuning
  only the same five records. Consider small controlled non-LLM source
  templates **as a distinct control condition** rather than relabeling them
  semantic-fluent; broaden reviewed development cases under a separate
  proposal/review protocol.
- Outstanding blockers: C05 slot-2 revised wording, source-identity
  caveats, independent reviewer metadata, and 20 currently abstained
  queries in the 25-question development cohort.
- Run the matched poisoned Dense/RCD development comparison **only** once
  reviewed, construction-eligible documents exist. Freeze the revised
  design before any 300-query held-out study.
