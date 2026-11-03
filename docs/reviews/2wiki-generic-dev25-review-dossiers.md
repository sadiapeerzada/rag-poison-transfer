# 2Wiki general train-development review dossiers

## Motivation
The narrow typed-source screener yielded **one** newly source-compatible training question, **outside** the original 25-question clean cohort, while **276** training questions had unsupported question grammar. All 20 originally unreviewed clean-25 questions were excluded by typed matching. This is a **grammar coverage limitation**, not proof that these questions cannot be studied.

The new generic source-packet tool prepares **all 20** remaining original clean-cohort questions for independent fact/target review regardless of the question grammar. It preserves query IDs, exact question, gold answer, aliases, gold-support document IDs, source text and SHA-256. An incomplete source packet is explicitly blocked. It neither guesses target answers nor asserts source-grounding review success.

## Safety and research boundary
- Verifies the frozen 300-train dataset, 25-question clean cohort, baseline and 5-of-25 quality audit with existing pin checks.
- All alternative/poison answers are null; reviewer decisions are blank.
- Gold-support provenance is dataset-derived, not external independent corroboration.
- Two separate, traceable AI model runs must review target feasibility, support chains, gold/aliases, false answer choice, chronology and ambiguities.
- No model calls, poisoning, injection, original run mutations or held-out access. Intensity-3 remains blocked.

## Mac invocation

    (
    set -e
    WT="$HOME/Documents/rag-2wiki-posthoc-screen"
    ROOT="$HOME/Documents/rag-research-results"
    PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
    cd "$WT"
    git fetch origin research/2wiki-v6-posthoc-and-dev-screening
    git checkout --detach origin/research/2wiki-v6-posthoc-and-dev-screening
    "$PY" -B -m pytest -q tests/test_twowiki_generic_dev25_review_dossiers.py
    OUT="$ROOT/twowiki-generic-dev25-review-$(date -u +%Y%m%dT%H%M%SZ).json"
    "$PY" -B -m scripts.prepare_twowiki_generic_dev25_review_dossiers \
      --dataset "$ROOT/twowiki-v2-development-recovery-20261103/development_data.json" \
      --cohort "$ROOT/twowiki-v3-exploratory-25cohort-20261103/manifest.json" \
      --baseline "$ROOT/twowiki-clean-dense-rcd-dev25-20261103T145542Z-a6fdbb/manifest.json" \
      --audit "$ROOT/twowiki-v4-1-quality-20261103T153852Z.json" \
      --output "$OUT"
    echo "GENERIC REVIEW DOSSIERS: $OUT"
    )

The output must contain exactly 20 dossiers, but the number that
are source-complete is an observed quantity rather than guaranteed.
The tool refuses to overwrite an existing report.

## Next gate
Inspect each dataset-backed gold source chain and independently review a
predeclared sample with two AI runs and complete provenance. Record abstentions
and disagreements as results; do not generate false evidence or begin paired
poisoned Dense/RCD until the screening and construction criteria are met.
