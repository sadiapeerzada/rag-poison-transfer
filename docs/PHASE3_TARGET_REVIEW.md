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

The output contains conservative category labels, candidate answers
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

## Verified extraction and schema migration (2026-10-25)

Use the original results file, including its `gold_doc_ids` for verification:

```bash
.venv/bin/python scripts/extract_verified_development_queries.py \
  --artifact results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl \
  --manifest configs/exp_027_hotpotqa_heldout_manifest.json \
  --output /tmp/hotpotqa_dev300_verified.json \
  --provenance /tmp/hotpotqa_dev300_provenance.json
```

The historical query-set hash uses `src.experiments.protocol.query_set_fingerprint`
(includes gold document IDs). The development ID hash uses sorted, newline-joined
IDs; the held-out hash preserves manifest order, as in `run._load_heldout_manifest`.
Both development hashes reproduce the frozen manifest. The original manifest
creation script was not located in available Git history; this reconstruction
uses existing historical protocol code and exact digest equality, not a new
hash compared to an unrelated historical digest. Extraction writes only query
ID, question, and gold answer, with separate input/output provenance hashes.
It rejects malformed records, duplicate IDs, wrong count/revision/split,
fingerprint mismatches, and overlap before writing outputs.

Regenerate old templates: `review-template-v2` adds `suggestion_sources`, mapping
each exact candidate string to its development source query IDs. The audit
reconstructs the complete deterministic default top-five suggestion list and
sources, rejecting injected, omitted, reordered, cross-category, or stale
suggestions. Normalized duplicate strings are collapsed before the limit.
Normalization cannot resolve all semantic aliases; reviewers must check these.
Explicit alternatives and comparative questions abstain for manual review.
Classifier rules are heuristic and intentionally sacrifice coverage.

Approved files now require `protocol_version: answer-compatible-targets/v3-reviewed`.
Old v2 candidate approvals must be independently re-reviewed, never mechanically
upgraded. Every row requires the existing exact question/gold fingerprints,
query ID, target, category, reviewer and evidence, plus:

- `approved: true` and `review_status: approved`;
- `semantic_compatible: true`, `factually_false: true`, and
  `coherent_false_evidence: true`;
- `reviewed_at`: an ISO8601 timestamp with timezone, not in the future;
- `reviewed_target_sha256`: SHA256 of the exact target string reviewed.

These are attestations, not authentication of a human reviewer or independent
verification of evidence. Store factual sources and rationale in `review_evidence`.
No age-based expiry is imposed: staleness means changed question, gold or target,
not simply an old review. Direct in-memory assignments undergo the same checks.
Never use test fixture identities/timestamps as real review evidence.

Injection records protocol and assignment fingerprints and fixes the target
across poison seeds/intensities. Reviewed checkpoint use additionally requires
an identical `target_assignment_fingerprint` in checkpoint provenance before any
lookup or generation. The existing checkpoint validator also checks target,
source/config/model provenance, document identity and heuristic support.

**Integration blocker:** the frozen Week 9 runner still invokes `inject_poisons`
without reviewed assignments. It has no reviewed-file CLI/config loader, and its
cell association serialization/replay does not preserve review protocol and
assignment fingerprints. The existing poison-instance hash covers targets and
texts but not review provenance. A separately versioned runner/manifest protocol
must carry and verify those fields throughout replay and paired Dense/RCD
metadata before a reviewed real-model smoke test. Do not pass revised artifacts
to frozen legacy replay or silently switch the existing matrix protocol.
Semantic generation uses explicit targets and bounded retries, but its text
screen is syntactic support only; it cannot prove question-specific entailment,
compatibility, falsehood, or transfer success. The full matrix remains paused.
