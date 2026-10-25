# Phase 3: candidate generation and independent review

The target candidate generator is deliberately **development-only** and does
not use MLX or touch frozen held-out artifacts. It accepts an explicit JSON
list of query records, rather than reading any dataset split implicitly.

Example:
```bash
python scripts/build_target_review_template.py \
  --development-queries /path/to/development_queries.json \
  --output /tmp/development_target_review.json
python -m pytest tests/test_target_candidates.py tests/test_compatible_targets.py -q
```

The output contains conservative category labels, candidate wrong answers
from other development queries in the same category, and SHA256 of exact
question and gold-answer strings. These are *suggestions only*. Category
matches can still be false positives, and missing suggestions are normal.

The review template is intentionally incompatible with the approved target
loader: it uses a different schema and every row has `approved: false`.
A separate, independently reviewed artifact must be created before any
assignment can be used. Reviewers must verify category compatibility,
actual falsehood, grammatical fit, and whether the answer can be asserted
naturally in evidence. Record reviewer identity, evidence, disagreements,
and rejected/ambiguous cases; never automatically approve a suggestion.

This phase does NOT wire the Week 9 matrix runner, generate final poison
manifests, validate semantic quality, or freeze the revised protocol.
The original frozen attack pipeline remains the default.
