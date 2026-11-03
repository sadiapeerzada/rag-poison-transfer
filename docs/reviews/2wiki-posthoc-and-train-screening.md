# 2Wiki next development gates: v6 post-hoc screen + wider train pool

This research branch deliberately adds **read-only analysis**. It does not
alter the v4, v5 or v6 generation code, old manifests, previous tests,
reviewer records, clean baseline, poisoned evaluation or held-out split.

## Why

Frozen actual outcomes:
- v4 strict surface grammar: **0/30** accepted model responses.
- v5 single-sentence surface triage: **30/30** nominated for review,
  **0/5** cases with three distinct slots.
- v6 two-sentence source-anchored surface triage: **0/30** accepted,
  **0/5** cases with three distinct slots. Its original validator
  checks the second sentence as if it contained all standalone referents;
  this is not a valid *passage-level* test.

A qualitative post-hoc inspection found **four** potentially reviewable
two-sentence passages in v6 (C09 slot 1, C11 slot 1 and C13 slots 0/1),
but **zero independently factually approved constructions**. The new
script recomputes a bounded syntactic passage-level screen; it never
converts previous v6 results into accepted experimental observations.

## Gate A: inspect saved v6 ZIP (no Qwen calls)

The bundle is expected at \`~/Downloads/twowiki_v6_review_bundle.zip\` as
previously created on the user's Mac. The script confirms five exact
train case IDs, the original review-packet SHA-256, all 30 response
SHA-256s, no poisoning or held-out access, and all original rejected
outcomes. It screens **15 unique slots**, preserving duplicate attempts.

It checks source anchor in first sentence, the explicit target relation
in the *second*, named director, film identity **across the passage**,
negative/contradictory claims, and known false side-claims. Exact
Wikipedia title suffix variants remain **review caveats**, never approval.
Surface matches DO NOT verify semantic truth or supporting context.
All positive outputs are \`needs_independent_content_review\`.

## Gate B: screen development questions for two-AI review

Uses the exact already-pinned 300-question **train** dataset, the
25-question clean baseline manifest and its review audit. It prioritizes
20 originally-unreviewed members of the clean 25, then considers other
train questions. It binds the existing four narrow, typed
film/director/person question templates with hashes computed from the
dataset. These are **not independent external source pins** or
corroboration. Other question types abstain and must be reviewed through
separately versioned methods rather than forced into this grammar.

The screening packet contains *review candidates*, not approved
answers. If a Boolean question is grounded, its opposite is only a
mechanical **unapproved suggestion**, never the accepted target. Place
questions deliberately provide no auto-selected alternative location.
Every claim requires independent, traceable **two-AI** review of both
proposed target and source evidence. C05 stale slot-2 wording and
second-reviewer provenance still require resolution.

**Do not silently reuse the original 25-query clean baseline** for any
newly shortlisted train question outside that 25: freeze and run a new
clean baseline protocol before comparing on those cases.

## Mac commands

\`\`\`bash
(
set -e
BASE="$HOME/Documents/rag-2wiki-v3-development"
WT="$HOME/Documents/rag-2wiki-posthoc-screen"
ROOT="$HOME/Documents/rag-research-results"
PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"

cd "$BASE"
git fetch origin research/2wiki-v6-posthoc-and-dev-screening
if [ ! -d "$WT" ]; then
  git worktree add --detach "$WT" FETCH_HEAD
fi
cd "$WT"
git checkout --detach origin/research/2wiki-v6-posthoc-and-dev-screening

"$PY" -B -m pytest -q \
  tests/test_twowiki_v6_posthoc_passages.py \
  tests/test_twowiki_additional_train_screening.py

"$PY" -B -m scripts.audit_twowiki_v6_posthoc_passages \
  --bundle "$HOME/Downloads/twowiki_v6_review_bundle.zip" \
  --output "$ROOT/twowiki-v6-passage-screen-$(date -u +%Y%m%dT%H%M%SZ).json"

"$PY" -B -m scripts.screen_twowiki_additional_train_targets \
  --dataset "$ROOT/twowiki-v2-development-recovery-20261103/development_data.json" \
  --cohort "$ROOT/twowiki-v3-exploratory-25cohort-20261103/manifest.json" \
  --baseline "$ROOT/twowiki-clean-dense-rcd-dev25-20261103T145542Z-a6fdbb/manifest.json" \
  --audit "$ROOT/twowiki-v4-1-quality-20261103T153852Z.json" \
  --max-new 25 \
  --output "$ROOT/twowiki-additional-train-review-$(date -u +%Y%m%dT%H%M%SZ).json"
)
\`\`\`

If a test or a pin fails, leave the old experiment untouched and fix the
new read-only adapter. Avoid repeated generation on the same five cases.

## What is still not authorized

No paired poisoned Dense/RCD test, no injection, no independent factual
approval, no automatic reviewer-provenance repair, and no full
300-query held-out matrix until the new cohort/claims are independently
reviewed and a revised protocol is frozen.
