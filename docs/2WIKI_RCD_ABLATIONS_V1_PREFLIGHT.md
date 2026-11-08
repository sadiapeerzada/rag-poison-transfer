# 2Wiki RCD component-ablation V1 — private original-evidence preflight

**Status: executable metadata/evidence preflight only. Not an ablation inference run.**

This new exploratory study uses the **same private 160-prompt Qwen/Phi selected plan** to choose 40 valid query-stratum positions, then pins all four matching 2Wiki original construction cells and their unchanged clean/poisoned evidence sources. It deliberately does **not** alter, relabel or re-run the original 300-query frozen study. It is a **post-hoc, valid-only** sample, not an untouched confirmatory held-out experiment.

The [preflight utility](../scripts/prepare_2wiki_rcd_ablation_plan.py) is standard-library/read-only for the original stages. It verifies the sealed original protocol (SHA `40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4`), construction seal, completed evaluation, aggregate, original pinned local data, 300-query cohort fingerprints, four selected original construction and QA cells, and by default **every file of both sealed stage inventories**. Its output is a **private** JSON experiment plan with the 40 selected query-stratum positions and six explicit variant definitions, not actual outcomes. All per-case data stays outside public GitHub.

## Six proposed comparisons

| Variant | Rewrites | Scoring | Generator evidence depth |
|---|---:|---|---:|
| `full_k3` | 3 | Frozen 0.45 consistency / 0.10 conflict / 0.45 base | 3 |
| `no_rewrites_k3` | 0 | Frozen score weights, fresh retrieval pool | 3 |
| `no_agreement_k3` | 3 | Recalculate consistency using rank + rewrite stability **without agreement** | 3 |
| `no_conflict_k3` | 3 | Conflict off; renormalize remaining 0.45/0.45 to 0.50/0.50 | 3 |
| `full_k1` | 3 | Frozen score weights | 1 |
| `full_k5` | 3 | Frozen score weights | 5 |

Candidate-retrieval depth remains 10 across variants. The k variants affect the **generator-visible** evidence count, not the candidate pool. The agreement variant must re-evaluate the score features from authentic retriever signals; setting consistency weight to zero would remove rank/rewrite stability too and is **not** equivalent. Similarly, score-only replay does not disable query rewriting.

## First run: no model inference

From the updated repository:

```bash
cd "$HOME/Downloads/rag-poison-transfer"
source .venv/bin/activate
git pull --ff-only origin main
python -m pytest -q tests/test_2wiki_rcd_ablation_preflight.py

ROOT="$HOME/Downloads/2wiki-restored-20261109"
PLAN="$HOME/Documents/rag-research-results/nov09-research-gates/2wiki-second-model-plan-20261108T204440Z_PRIVATE.json"
OUT="$HOME/Documents/rag-research-results/nov09-research-gates/2wiki-rcd-ablation-v1-plan_PRIVATE.json"

# This reads the original protocol's fully pinned local-data path.
# If that absolute original path has moved, pass --local-data with the actual
# restored file whose bytes match the protocol's local_data_sha256.
python scripts/prepare_2wiki_rcd_ablation_plan.py \
  --restored-root "$ROOT" \
  --phi-plan "$PLAN" \
  --phi-plan-sha256 "9c47a64053c2d53bb016a2bad10503d906a9026e0b7092d55ddb0505bd3b199a" \
  --output "$OUT"
```

Expected preflight output: `PRIVATE_ABLATION_PLAN_PREPARED_NO_INFERENCE`, six variants, four condition cells, **40 query-stratum positions**, and at most **480 logical clean/poison generator calls** without reuse/caching. This is a **design ceiling**, not a count of executed calls.

If it fails on missing `local_data`, discover the path from the **pinned original protocol**, not by guessing or repackaging a different dataset:

```bash
python - <<'PY'
import json
from pathlib import Path
p=Path.home()/"Downloads/2wiki-restored-20261109/protocol.json"
v=json.loads(p.read_text(encoding="utf-8"))
print("Original local input path:", v["replication"]["local_data"])
print("Required SHA-256:", v["replication"]["local_data_sha256"])
PY
```

Then pass the existing file as `--local-data "/actual/path/to/original.json"` only if its SHA matches. **Never write a new substitute input under the historical hash.**

## What this preflight does not do

No RCD variant is currently *executed* by this preparation utility. A **separately versioned, actual new-retrieval and new-Qwen-QA runner** must consume this plan and reproduce baseline k3 retrieval IDs before comparing variants. It must save actual clean/poison answers, evidence exposure, paired accuracy and target success, retrieval/generation call counts, latency, source hashes, complete checkpoint provenance and question-cluster uncertainty in fresh private output paths. The experimental corpus for every condition must include the **entire frozen poison union**, not just the 10 selected attacks.

The true ablation study is **pending** until those comparisons run. Never publish invented numeric ablation effects or use a test PASS as a research result.

## Other outstanding research-plan scope

- Phi@64 cap-controlled replay is separately supported by `scripts/nov09_mac_research.sh`, but is only complete when the Mac executes a fresh 160-call output and validates it. The existing Phi@128 results stay untouched.
- Semantic factuality remains AI-assisted/unadjudicated; the 131-case packet cannot establish a population-level false-evidence validity rate.
- Natural Questions single-hop/true iterative or adaptive RAG, intensity 5, unseen attacks and low global poison rate require separately frozen and actually executed experiments; the two multi-hop datasets do not prove those RQs.
- A poison-detection AUROC/F1 claim requires actual per-document ground-truth labels and a score whose direction and threshold are defined before inspection; none has been verified. A final RCD ranking score is not automatically a calibrated classifier.

**The primary project may proceed as a narrower rigorous mixed positive/negative empirical paper without those expansions, if the manuscript states the scope honestly.** No claim of general RCD superiority is supported by the original observed results.
