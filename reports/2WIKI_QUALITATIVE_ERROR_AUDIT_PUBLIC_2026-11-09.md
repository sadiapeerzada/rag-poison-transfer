# 2WikiMultiHopQA — Preliminary qualitative error audit (public, aggregate-only)

**Recorded:** 9 November 2026  
**Study:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Evidence level:** Exploratory, AI-assisted, post hoc, outcome-revealing review of a deliberately stratified packet. **Not** independent human semantic adjudication, blinded review, or certification of factual falsehood.

**Data protection:** This public summary intentionally omits the held-out questions, case/query IDs, target and gold answers, generated poison text, raw prompts, model responses, and case-level logs. The source-bound original review packet and the 131-row private per-case triage remain outside the public repository pending licensing/privacy review. The companion [aggregate-only machine-readable triage](2wiki_qualitative_triage_aggregate_public_2026-11-09.json) contains counts, not individual cases.

## Scope and interpretation

- Frozen run: 12 cells, **3,600 attempted constructions**, matched Dense and RCD; lexical influential-token and semantic fluent-false-evidence attack families, poison intensities 1/3, seeds 42/43/44; the same 300 question IDs recur across seeds.
- Review export: **131 selected case rows, 102 distinct query IDs**. Of these, **107** had mechanically valid poison constructions and paired answers, **16** had target-nomination failure, and **8** had semantic-construction failure.
- Case selection was deterministic and **outcome-stratified**, not an independent random or blinded estimate. Neither the sample counts nor the heuristic flags below estimate benchmark-wide prevalence.
- The **24 failed-construction cases** lack complete question/gold-answer context in the exported packet; adjudicators must consult the locally preserved original records to examine them fully.
- This analysis does not change any frozen label, poison instance, aggregate result, denominator, or primary study endpoint.

## Entire 3,600-record census: paired targeted-output outcomes

The four outcome bins for a row are mutually exclusive **within mechanically valid constructions**. Construction failures are separate and must not be characterized as defense successes.

| Attack condition | Both target | Dense-only target | RCD-only target | Neither target | Valid | Target failure | Semantic failure |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lexical, intensity 1 | 351 | 31 | 77 | 303 | 762 | 138 | 0 |
| Lexical, intensity 3 | 587 | 65 | 42 | 68 | 762 | 138 | 0 |
| Semantic, intensity 1 | 126 | 8 | 7 | 26 | 167 | 138 | 595 |
| Semantic, intensity 3 | 101 | 3 | 3 | 2 | 109 | 138 | 653 |

In lexical intensity 1, RCD-only successes exceed Dense-only by **46**; at intensity 3, Dense-only exceed RCD-only by **23**. These condition-dependent patterns do not establish a universal protection effect. For the actual inferential analysis, use the frozen query-cluster bootstrap intervals from the [scientific results report](2wiki_300_dense_rcd_scientific_results_2026-11-08.md), not informal significance judgments based on the table alone. Reused query IDs mean query-seed rows are **not independent questions**.

### Clean-answer disagreements in the valid-construction population

| Condition | Dense clean correct, RCD incorrect | RCD clean correct, Dense incorrect |
|---|---:|---:|
| Lexical, intensity 1 | 42 | 15 |
| Lexical, intensity 3 | 42 | 15 |
| Semantic, intensity 1 | 9 | 2 |
| Semantic, intensity 3 | 6 | 1 |

The lexical baseline counts repeat across the same seeded query sets. Lower RCD clean accuracy on some subsets complicates attribution of poisoned-answer differences to adversarial robustness alone.

## Deliberately selected 131-case packet: preliminary diagnostics

Among the **107** mechanically valid selected cases: **45** both-target, **20** Dense-only target, **19** RCD-only target, **23** neither-target. Across the selected valid cases, **30** show a clean exact-match disagreement, and **18** show a mismatch in generator-visible poison exposure between arms. These numbers are **sample counts only**.

The automated triage identified *review flags*, not factual adjudications:

| Review flag | Selected case rows |
|---|---:|
| Person/kinship relation with a likely non-person or nationality target | 19 |
| Country question with a likely city/person target | 5 |
| Grandmother question with an apparently male historical target | 5 |
| Location question with a demonym target | 4 |
| **Unique rows with at least one of these four role/type flags** | **33** |
| Distinct questions in those flagged rows | 28 |
| Flagged and mechanically valid semantic cases | 21 of 51 sampled semantic-valid rows |
| RCD target match with **no generator-visible poison** | 3 (same query across three seeds) |
| Dense target already returned on its clean answer | 6 (3 distinct questions) |
| RCD target already returned on its clean answer | 5 (3 distinct questions) |

**Interpretation boundaries:** (a) the 21/51 count is **not** a semantic invalidity rate; (b) some apparent role/type errors need alias and source-grounded verification; (c) a target match already present in a clean response without visible poison is not evidence of an observed poison-induced answer flip. Keep primary targeted-ASR outcomes frozen; new `clean-to-target-flip` sensitivity analyses, if performed, must be explicitly exploratory.

## Sampled semantic construction rejection diagnostics

The **eight** selected failed semantic cases comprise four intensity-1 and four intensity-3 cases, containing 16 requested document indices and 32 generation attempts. Across those attempts:

| Automated attempt outcome | Count |
|---|---:|
| Unverified relation affirmation | 15 |
| Rejected: competing gold/alias text | 6 |
| Rejected: intended target not affirmed | 6 |
| Mention only; no recognized assertion | 4 |
| Heuristically accepted **partial** document | 1 |
| **Total** | **32** |

The one accepted partial document does **not** turn a failed intensity-3 multi-document construction into a successful intensity-1 construction. Validator rejection also does not itself prove the generated claim false, incoherent, or contradicted; it may reflect limited parsing of the requested relation.

## Scientific failure taxonomy and open adjudication

1. **Construction versus defense:** low semantic construction coverage is a method-feasibility limitation, not evidence that RCD rejected the attack.
2. **Answer-role compatibility:** mechanical target-string affirmation can pass a validator despite a wrong answer type, wrong relation, or impossible role.
3. **Answer-alias ambiguity:** strict exact match may differ for synonyms, transliterations, and historical name variants; no retrospective change to frozen EM is authorized.
4. **Observed poison exposure:** a nominated target may appear without visible poisoned evidence or may already have been generated by a clean model. Neither alone demonstrates poisoning causality.
5. **Generator-versus-retriever attribution:** document IDs alone cannot establish whether rewrite behavior, ranking, selection or final generation caused a paired difference. Original evidence text and scoring traces require private inspection.
6. **Independent factuality:** the review did not independently certify the accuracy or falsehood of all generated statements. No model-written “authoritative reference” may be used as its own source evidence.

### Next scientifically necessary checks

- Independently source-check the **33** flagged cases and resolve aliases, expected answer types, false targets, and ambiguous/incorrect gold labels; separately select a balanced additional sample for the plan's 50–100 representative-error review.
- Recover full original question/gold context from private journals for the **24** failed constructions.
- Use the local blank human-review template; record cited external evidence, review dates, independent reviewer verdicts and adjudicated disagreements. A second reviewer is recommended for uncertain or contested cases.
- Preserve held-out confidentiality and freeze boundaries; only publish redacted, aggregate-level evidence after source/licensing review.
- Report clean utility, construction coverage, exposure and targeted ASR **separately**; do not infer RCD superiority or failure from hand-picked examples.

## Integrity and provenance

| Evidence | SHA-256 |
|---|---|
| Private `review_packet.jsonl` | `dafdfe7f6bbb7abdeb5a002e671e967480c59f6854d0fa22ca54e42a824eb153` |
| Private `audit_summary.json` | `8e869179ee7e17c7d24211f419c138913daec96956b3e4f504148efa1a611d9d` |
| Frozen evaluation aggregate | `721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96` |

These hashes are fingerprints for comparison with independently preserved original files, **not** evidence of independent source validation. The structural/case arithmetic was cross-checked against the supplied packet and private triage; the original frozen study results remain unchanged.

**Status:** public exploratory audit handoff completed; **independent human factuality review and source-level adjudication still pending**.
