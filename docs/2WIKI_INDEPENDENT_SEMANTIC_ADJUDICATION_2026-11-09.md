# 2Wiki independent semantic/factual adjudication — handoff protocol

**Date:** 9 November 2026  
**Status:** **Reviewer packets generated privately; no human reviewer judgments returned.**  
**Scope:** post hoc assessment of the frozen 300-query, 12-cell Dense/RCD 2Wiki experiment's 131 deliberately selected error-review records; source data and results are unchanged.

## Starting point and scope

The [public qualitative audit](../reports/2WIKI_QUALITATIVE_ERROR_AUDIT_PUBLIC_2026-11-09.md) is a useful **AI-assisted triage**, not a source-verified truth set. Its 131 case rows represent **102 distinct query IDs**; the chosen strata overrepresent particular errors and cannot estimate their prevalence. The audit identifies 107 mechanically valid cases with question/gold/poison context (**79 unique questions within this subset**), plus 24 construction-failure cases whose question/gold context is absent from the initial export. These 24 require private, hash-verified original record recovery, not guessed values or silent exclusion from the final scope accounting.

Original construction failures remain in the attempted-population denominator. Semantic validator acceptance is **not** human verification of false evidence. A target answer matched by the clean system and without poison exposure cannot be interpreted as a demonstrated poisoning-induced answer flip.

## Private, blinded packet creation

Prepare from these **local private inputs** (not included in this public repository):

- `review_packet.jsonl` from the read-only 2Wiki paired review export.
- `2Wiki_131_Case_Private_Triage_2026-11-09.json`, derived privately from that export and retained with its SHA-256.

Run from the repo using a **fresh output directory outside Git**:

```bash
python3 scripts/prepare_2wiki_independent_review.py prepare \
  --packet "$HOME/Documents/rag-research-results/2wiki-paired-review-20261109/review_packet.jsonl" \
  --triage "$HOME/Documents/rag-research-results/2wiki-paired-review-20261109/2Wiki_131_Case_Private_Triage_2026-11-09.json" \
  --out "$HOME/Documents/rag-research-results/2wiki-independent-human-review"
```

The private triage JSON is a separately generated artifact, **not** the source exporter’s blank `human_review_template.csv`. If the file has not been copied to that Mac folder, first obtain the original privately retained triage file; the script does not invent it or scrape prompts for missing source claims.

### Private outputs

| Output | Custodian and use |
|---|---|
| `reviewer_A.csv` | Give to independent reviewer A only |
| `reviewer_B.csv` | Give to independent reviewer B only |
| `coordinator_mapping_PRIVATE.csv` | **Coordinator only**: maps two reviewer aliases to original case IDs and conditions |
| `pending_original_context_PRIVATE.csv` | **Coordinator only**: 24 cases needing original source question/gold recovery |
| `manifest_PRIVATE.json` | Hash-pinned local evidence inventory; not an adjudication receipt |
| `REVIEW_INSTRUCTIONS_PRIVATE.md` | Reviewer instructions; communicate without disclosing outcomes |

Each reviewer receives the **same 107 candidate-evidence cases**, in a different reproducible order with a different pseudonymous review ID. Reviewers see the question, benchmark answer (clearly marked **unverified**), nominated target, and accepted candidate evidence; they are not shown Dense/RCD outputs, poison-visibility results, seeds, attack family, sampling strata, or previous AI heuristic flags. Reviewer A and B should be independent actual people, not two runs of the same model. Keep their answers separate until both are complete.

**Blindness limitation:** this is outcome-blinding, not blinding to the fact that the displayed candidate evidence is an attack candidate. Reviewers may also recognize repeated questions from the three poison seeds. Coordinate repeat-question analyses at the distinct-query cluster level and do not imply 107 independent test questions.

## Human review codebook

Review each case's **question, answer type, relation/hop chain, candidate assertion, and independent evidence**. The benchmark answer is a reference label to verify rather than an authoritative fact itself.

| Field | Permitted judgments | Required support |
|---|---|---|
| `relationship_asserted` | yes / no / uncertain | Does text explicitly claim nominated target answers the actual relation? |
| `answer_type_compatible` | yes / no / uncertain | Person/place/date/role and any multi-hop constraints |
| `target_factuality` | false / true / mixed / unverifiable | Independent primary or credible source citations and precise support |
| `benchmark_answer_status` | supported / unsupported / ambiguous | Gold/alias/source discrepancy check |
| `source_urls` and `source_quotations` | Nonempty | Verifiable factual source excerpts; no model-written authority |
| `reviewer_name`, `review_date`, `reviewer_confidence`, `reasoning_notes` | Nonempty | Dated accountable decision and reason |

Treat all question, dataset and generated poison text as **untrusted data**. Do not follow commands embedded in the material. Abstention/`unverifiable` is permitted when reliable source evidence is insufficient. If independently sourced evidence disagrees, record the conflict; do not force a positive verdict.

Completed reviewer sheets can be syntax-checked with:

```bash
python3 scripts/prepare_2wiki_independent_review.py validate \
  --packet-file "/path/to/completed/reviewer_A.csv"
python3 scripts/prepare_2wiki_independent_review.py validate \
  --packet-file "/path/to/completed/reviewer_B.csv"
```

The validator checks completeness/enums/source fields, not reviewer identity, independence, factual accuracy, or citation trustworthiness. A **validation PASS** alone is never scientific acceptance.

## Adjudication and publication gate

1. Preserve both original completed reviewer files, independent hashes, actual human reviewer identity and dated source logs; identify repeat-query cases.
2. Reconcile `review_A_id` and `review_B_id` privately via the coordinator mapping. Record agreement and disagreement on factuality, relation and type compatibility; commission a third adjudicator for conflicts.
3. Complete original-context recovery of the 24 blocked cases separately; log each source file path/hash and avoid pretending an unavailable case was independently checked.
4. Produce counts of independently false, true, mixed, unverifiable, wrong-type, unsupported benchmark and unresolved items; include **reviewable denominators**, missingness and query-cluster counts.
5. Report the outcome-stratified sample as a **mechanism/failure taxonomy**; never report sampled proportions as prevalence of the 3,600-record population. Preserve the preregistered ASR/ATR/clean correctness statistics and their original denominator definitions.
6. Before public release, conduct licensing/privacy review of source excerpts and dataset redistribution rights. Publish aggregate counts and sanitized examples only where authorized; retain held-out raw records privately.

**No additional model inference or modification to the frozen experimental protocol is required for preparing or validating this handoff.**
