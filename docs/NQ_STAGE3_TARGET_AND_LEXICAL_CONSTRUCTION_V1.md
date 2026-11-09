# Natural Questions Stage 3: versioned target and lexical poison construction

Date: 9 November 2026. **Code and synthetic tests prepared; no real 300-question NQ construction was run here.** This is a new exploratory extension; it does not modify frozen HotpotQA/2Wiki data.

The script scripts/nq_stage3_lexical_construction_v1.py provides three separately checked actions: prepare-targets, construct-lexical, verify-lexical. It requires the exact SHA-pinned NQ cohort from PR #138, selects one deterministic non-gold attack target per evaluation question from the 50 development gold answers, freezes all 300 assignments for use by both attack intensities, and constructs immutable lexical poison documents (intensity 1 or 3). It validates original corpus/gold label integrity and reconstructs the sealed injected-document fingerprint.

**Critical limitations:** These are answer-type-approximate non-gold targets, not independently verified factually false claims. The NQ corpus comprises pooled long-answer candidates rather than the standard open-domain Wikipedia index. No full QA, semantic false-evidence attack, retrieval matrix or scientific attack result is produced by this action.

## Run only after an actual successful frozen NQ receipt

~~~bash
cd "$HOME/Downloads/rag-poison-transfer"
git pull --ff-only origin main
source .venv/bin/activate
python -m pytest -q tests/test_nq_stage3_lexical_construction_v1.py

COHORT_DIR="$HOME/Documents/rag-research-results/nq-singlehop-v1-private"
COHORT_SHA="$(shasum -a 256 "$COHORT_DIR/cohort_manifest.json" | awk '{print $1}')"

python scripts/nq_singlehop_v1_freeze.py verify \
  --out-dir "$COHORT_DIR" --manifest-sha256 "$COHORT_SHA"

OUTPUT_ROOT="$HOME/Documents/rag-research-results"
TARGET_FILE="$OUTPUT_ROOT/nq-stage3-targets-v1_PRIVATE.json"

python scripts/nq_stage3_lexical_construction_v1.py prepare-targets \
  --cohort-dir "$COHORT_DIR" --cohort-sha256 "$COHORT_SHA" \
  --output "$TARGET_FILE"

TARGET_SHA="$(shasum -a 256 "$TARGET_FILE" | awk '{print $1}')"

for INTENSITY in 1 3; do
  FILE="$OUTPUT_ROOT/nq-stage3-lexical-intensity-$INTENSITY-v1_PRIVATE.json"
  python scripts/nq_stage3_lexical_construction_v1.py construct-lexical \
    --cohort-dir "$COHORT_DIR" --cohort-sha256 "$COHORT_SHA" \
    --targets "$TARGET_FILE" --targets-sha256 "$TARGET_SHA" \
    --intensity "$INTENSITY" --output "$FILE"
  CONSTRUCTION_SHA="$(shasum -a 256 "$FILE" | awk '{print $1}')"
  python scripts/nq_stage3_lexical_construction_v1.py verify-lexical \
    --cohort-dir "$COHORT_DIR" --cohort-sha256 "$COHORT_SHA" \
    --targets "$TARGET_FILE" --targets-sha256 "$TARGET_SHA" \
    --construction "$FILE" --construction-sha256 "$CONSTRUCTION_SHA"
done
~~~

Never overwrite or delete private artifacts to repeat an outcome. Retain source/target/poison file pins. The semantic attack, matched Dense/RCD retrieval and up to 4,800 Qwen logical QA observations still need separate implementation and genuine execution, followed by attempted-population and valid-only statistical analysis. Code tests are not a substitute for real experiments.
