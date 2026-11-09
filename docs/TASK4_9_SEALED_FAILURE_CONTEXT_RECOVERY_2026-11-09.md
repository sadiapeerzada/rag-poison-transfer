# Tasks 4 + 9 — Recovered review context and source-adjudication handoff

**Date:** 9 November 2026.  
**State:** Original private 131-case packet checksum verified by operator; 131-row private factuality ledger template created with **0 source adjudications**. New **24-failure context recovery code prepared; not yet executed on the owner's original Mac evidence**.

## Authentic starting point

Original private review packet: `2wiki-paired-review-20261109/review_packet.jsonl`  
Original pinned SHA-256: `dafdfe7f6bbb7abdeb5a002e671e967480c59f6854d0fa22ca54e42a824eb153`.  
Operator's recorded successful template generation: **131 selected cases, 102 distinct questions, 0 verdicts**. Of those selected cases: 107 mechanically valid, 16 target nomination failures, 8 semantic construction failures. These are not a new unbiased benchmark sample.

The 24 construction failures lack complete clean original **question and gold answer** context in the 131-case packet because frozen evaluation observations were correctly absent for unsuccessful constructions.

## New read-only context recovery

[Script](../scripts/recover_2wiki_review_case_context.py) verifies the exact private packet SHA and the original pinned `protocol.json`, `construction.seal.json`, `evaluation.complete.json`, original 300-question input snapshot and original query/corpus fingerprints. It then verifies source-cell SHA-256 and each of all 131 selected case IDs, status, construction path and target/gold provenance. It writes a **new private 24-row JSONL** with complete original clean question/gold and available target context for the failed-construction cases only.

- Do **not** mark a target-nomination failure as having a successfully nominated false answer. Target may correctly be `null`.
- Do **not** count a partial document in a failed intensity-3 construction as a valid intensity-1 poison.
- Do **not** convert previously rejected semantic constructions into successes or alter the sealed 3,600 attempted-case denominators.
- Do **not** claim recovered context is a verified true answer, a verified false target, or independent semantic adjudication.

### Run on the original Mac (after CI passes and PR merges)

```bash
cd "$HOME/Downloads/rag-poison-transfer"
git fetch origin
git switch main
git pull --ff-only origin main
python -m pytest -q tests/test_recover_2wiki_review_case_context.py tests/test_audit_2wiki_source_factuality_ledger.py

python scripts/recover_2wiki_review_case_context.py \
  --packet "$HOME/Documents/rag-research-results/2wiki-paired-review-20261109/review_packet.jsonl" \
  --run "$HOME/Documents/rag-research-results/twowiki-300-readiness-20261106/authorized-matrix" \
  --out "$HOME/Documents/rag-research-results/nov09-research-gates/task4-9-failed-context-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.jsonl"
```

**Expected successful source-backed receipt:** `selected_packet_rows_verified=131`, `failed_case_contexts_recovered=24`, `target_nomination_failures=16`, `semantic_construction_failures=8`, `factuality_verdicts_performed=0`. If a SHA, original input location, cell, question ordering, status or target differs, the script stops rather than inventing replacement information. If the original pinned `local_data` path moved, use `--local-data PATH` with the exact original SHA-matching local data snapshot.

Keep the output JSONL and full original packet **outside public GitHub**. Share only the aggregate CLI receipt; the output contains selected held-out questions and answers requiring rights/privacy review.

## Once 24 contexts are recovered

All 131 selected cases will then have accessible source question context (107 valid cases from the existing private packet plus original clean contexts for 24 failures). **Source truth remains unreviewed.**

The original 131-case private factuality ledger is preserved; do not create or overwrite another template unless intentionally creating a separately versioned review. For each valid semantic assertion, distinguish:

1. **Factual truth:** whether independent, dated, cited sources support or contradict the *specific relation/entity/time assertion*, not just the dataset gold string.
2. **Answer role:** whether the target has the correct person/place/kinship/date type and meets the question's constraints.
3. **Poison assertion and exposure:** whether the inserted passage states the nominated false relation and was actually generator-visible; whether a clean generator already returned the target.
4. **Ambiguity:** aliases, translations, contested/dated facts, irrelevant target nomination and no independent reference should be recorded as uncertain/unverifiable rather than forced yes/no.

The [existing private ledger schema](../scripts/audit_2wiki_source_factuality_ledger.py) requires citations with URLs, access dates and short real source quotes. **That program verifies syntax only**, not that the URL really proves a claim. Avoid model-generated quotations and self-citation to poisoned passages. Distinguish AI-assisted researcher review from independent human adjudication.

**Scientific scope:** 131 cases were deliberately selected after observing outcomes and include repeated question IDs; neither a fraction of them nor the 24-failure subset establishes benchmark-wide causal validity.

**Task verdict:** Context recovery *implementation prepared*; source adjudication and broader semantic poisoning evaluation still incomplete until actual private-data execution and independent source research.
