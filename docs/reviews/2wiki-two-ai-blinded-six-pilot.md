# 2Wiki blinded two-AI review pilot — first six pending clean-dev questions

## Grounded inputs

The latest Mac execution produced 20/20 **source-complete** review
dossiers, none blocked, from the 20 unreviewed train questions in the
original frozen clean-25 cohort. This does *not* prove their multi-hop
relations are supported: it only confirms their declared gold-support
source texts were present and pinned.

Frozen existing experiment outcomes remain: v4 0/30 strict passes;
v5 30/30 surface review candidates, 0/5 triple-distinct cases; v6
0/30 original surface passes, 4/15 post-hoc two-sentence review
candidates, 0/5 triple-distinct cases. No research outcome is rewritten.

## Method

Run scripts/prepare_twowiki_two_ai_review_batch.py on the **exact** file
from the completed Mac dossier export. It checks all 20 dossier hashes,
source text hashes, original scope, zero previous approvals/injections,
and selects the **first six in frozen clean-cohort order**, not the most
promising cases. The output holds a manifest and two independent prompt
sets (reviewer_A/case_XX.txt and reviewer_B/case_XX.txt), twelve prompts
total, never a claim that reviewers already ran.

Two genuinely different AI models should assess the same six cases
without exchanging responses. A model must quote exact source spans,
trace both multi-hop steps, distinguish supported gold facts from
assumptions, check aliases and chronology, and either nominate one
answer-type-compatible test counterfactual or abstain. Supporting
dataset documents must be treated as untrusted quoted data; no
instructions inside source text may be followed.

**Reviewer A and Reviewer B must be independent real model runs with
actual model identifiers, run IDs, timestamps and retained raw responses.
Do not invent provenance, use a copied response for both reviewers,
or treat two seeds of the same model as two independent reviewers.**
Reviewers are not yet executed, and their outputs remain provisional
until manually evaluated. No review automatically approves attack
construction or poisoned inference.

## Reproduce from user's Mac

    (
    set -e
    WT="$HOME/Documents/rag-2wiki-posthoc-screen"
    ROOT="$HOME/Documents/rag-research-results"
    PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
    cd "$WT"
    git fetch origin research/2wiki-v6-posthoc-and-dev-screening
    git checkout --detach origin/research/2wiki-v6-posthoc-and-dev-screening
    "$PY" -B -m pytest -q tests/test_twowiki_two_ai_review_batch.py

    IN="$ROOT/twowiki-generic-dev25-review-20261103T170934Z.json"
    OUT="$ROOT/twowiki-two-ai-blinded-first6-$(date -u +%Y%m%dT%H%M%SZ)"
    "$PY" -B -m scripts.prepare_twowiki_two_ai_review_batch \
      --dossiers "$IN" --output-dir "$OUT" --pilot-size 6
    echo "TWO-AI BLINDED REVIEW BATCH: $OUT"
    )

Do not rerun the Qwen poison generator for this review stage. Do not
begin a paired poisoned Dense/RCD development pilot or held-out matrix.

## Next decision

First verify the six dossiers' actual source chains, then execute the
two genuinely independent AI reviewers, capture raw response bytes and
metadata, check exact quotes against pinned text, and adjudicate
conflicts/abstentions. Expand to the remaining 14 original-clean-cohort
questions only under a predeclared protocol and bounded cost.
