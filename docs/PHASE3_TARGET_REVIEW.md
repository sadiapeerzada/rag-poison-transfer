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

## Development-only coverage audit

Once you have an **independent development-split** JSON list of
`{query_id, question, gold_answer}` records, run:

```bash
python scripts/build_target_review_template.py \
  --development-queries /path/to/dev_queries.json \
  --output /tmp/dev_target_review.json
python scripts/audit_target_review_template.py \
  --development-queries /path/to/dev_queries.json \
  --template /tmp/dev_target_review.json \
  --output /tmp/dev_target_audit.json
python -m pytest tests/test_target_review_audit.py tests/test_target_candidates.py tests/test_compatible_targets.py -q
```

The audit reports total queries, unknown categories, number with and without
suggestions, and total candidate suggestions. It checks exact question/gold
fingerprints, coverage, duplicate IDs, and that suggestions differ from gold.
It **does not** measure semantic correctness, independent review acceptance,
or false-evidence quality; all approval counts remain zero. Do not feed the
held-out 300-query matrix split to this development-only workflow. No
development data was included in the repository change, and no real-dataset
coverage result is claimed.
