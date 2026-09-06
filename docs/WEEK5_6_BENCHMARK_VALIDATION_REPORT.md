# Benchmark Validation Report — Weeks 5–6

**Deliverable for:** Weeks 5–6, "Implement stress/attack/shift benchmark and validate labels/conditions" (research plan, Section 14)
**Repo state:** builds on `clean-baseline-v1` (Weeks 3–4 deliverable)

## 1. Summary

This report validates the knowledge-poisoning attack benchmark built in
`src/attacks/`: two attack content families, configurable intensity
(number of poison documents per query) and global poison rate, a
structural validator, and a cross-pipeline retrieval-evaluation harness.
Per the research plan's Section 6 requirement ("construct the controlled
stress/attack/shift conditions without changing the ground-truth answer
or test labels"), every condition below was validated for label
integrity before any result was reported.

## 2. What Was Built

| Component | File | Purpose |
|---|---|---|
| `PoisonAttack` base class | `src/attacks/base.py` | Shared interface; canonical query-scoped poison doc IDs; cross-query target-answer selection with answer-type matching |
| Lexical / influential-token attack | `src/attacks/lexical.py` | Surface term-repetition attack, exploits lexical retrievers |
| Semantic-fluent false-evidence attack | `src/attacks/semantic_fluent.py` | Uses the real generator to write fluent, encyclopedic false "evidence" |
| Injection engine | `src/attacks/injection.py` | `inject_poisons()` (intensity + global rate support) and `validate_poisoned_dataset()` |
| Cross-pipeline evaluation | `src/attacks/evaluate.py` | `evaluate_poison_across_retrievers()` — same poisoned corpus tested against all 4 retrievers |
| Systematic sweep | `src/attacks/sweep.py` | `run_attack_intensity_sweep()` — runs attack × intensity × retriever combinations under one validated protocol |

All components are unit-tested (68 new tests across `test_poison_injection.py`,
`test_semantic_fluent_attack.py`, `test_cross_pipeline_evaluation.py`,
`test_sweep.py`), on top of the 153 tests already passing at the
`clean-baseline-v1` tag. Full suite: 203 tests passing as of this report.

## 3. Label-Integrity Validation

Per `validate_poisoned_dataset()`, every poisoned dataset generated during
this phase was checked against 7 criteria before any downstream result
was reported:

1. Same query set as the clean source (no queries added/dropped)
2. `gold_answer` byte-identical to the clean source for every query
3. `gold_doc_ids` byte-identical to the clean source for every query
4. Every clean corpus document preserved unmodified in the poisoned corpus
5. No poison document ID collides with a clean document ID
6. No duplicate poison document IDs
7. Poison count per attacked query matches the requested intensity; global attack rate matches the requested rate

**Result: `VALID: True` on every condition tested** (exploratory N=30 lexical run,
real cross-pipeline N=30 test, and all 8 conditions of the systematic
N=25 sweep). No condition was reported without passing this gate.

## 4. Attack Intensity & Rate Coverage

| Setting | Status |
|---|---|
| Single-document poison (intensity=1) | Tested, both attack families |
| Multi-document poison (intensity=3) | Tested, both attack families, coordinated (same false target answer across documents, verified distinct phrasing per document) |
| Multi-document poison (intensity=5) | Implemented and unit-tested; not yet run at scale due to GPU time constraints (semantic-fluent attack requires one real generation call per poison document) |
| Low global poison rate (<1.0) | Implemented and unit-tested (`poison_rate` parameter); not yet run at scale in this phase |
| Full poison rate (1.0, i.e. every query attacked) | Tested, both attack families |

Intensity=5 and low-rate sweeps are recommended as a follow-up run once
GPU time allows — the mechanism is proven and tested, only the large-N
execution remains.

## 5. Real Cross-Pipeline Retrieval Results

N=25 real HotpotQA validation queries (pinned revision
`1908d6afbbead072334abe2965f91bd2709910ab`), `poison_rate=1.0`,
`top_k=10`, real `Qwen/Qwen2.5-7B-Instruct` generator for the
semantic-fluent attack's content. Full data: `results/week5_attack_intensity_sweep.csv`.

| Attack | Intensity | Retriever | PRR@1 | PRR@3 | PRR@5 | PRR@10 |
|---|---|---|---|---|---|---|
| Lexical | 1 | BM25 | 1.00 | 1.00 | 1.00 | 1.00 |
| Lexical | 1 | Dense | 0.52 | 0.96 | 1.00 | 1.00 |
| Lexical | 1 | Hybrid | 0.96 | 1.00 | 1.00 | 1.00 |
| Lexical | 1 | Reranker | 0.96 | 1.00 | 1.00 | 1.00 |
| Lexical | 3 | BM25 | 1.00 | 1.00 | 1.00 | 1.00 |
| Lexical | 3 | Dense | 0.60 | 1.00 | 1.00 | 1.00 |
| Lexical | 3 | Hybrid | 1.00 | 1.00 | 1.00 | 1.00 |
| Lexical | 3 | Reranker | 1.00 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | 1 | BM25 | 0.44 | 0.84 | 0.88 | 0.96 |
| Semantic-fluent | 1 | Dense | 0.68 | 0.92 | 0.96 | 1.00 |
| Semantic-fluent | 1 | Hybrid | 0.56 | 0.92 | 0.96 | 0.96 |
| Semantic-fluent | 1 | Reranker | 0.88 | 0.96 | 1.00 | 1.00 |
| Semantic-fluent | 3 | BM25 | 0.80 | 0.92 | 0.92 | 0.96 |
| Semantic-fluent | 3 | Dense | 0.76 | 0.96 | 1.00 | 1.00 |
| Semantic-fluent | 3 | Hybrid | 0.76 | 0.92 | 0.96 | 1.00 |
| Semantic-fluent | 3 | Reranker | 0.92 | 1.00 | 1.00 | 1.00 |

### Discussion

The result pattern is directionally consistent with the research plan's
Section 4 hypothesis (lexical attacks favor lexical retrievers;
semantically fluent attacks favor semantic retrievers):

- **Lexical attack**: near-perfect against BM25 at PRR@1 even at
  intensity 1 (1.00), but visibly weaker against Dense (0.52-0.60) --
  the term-stuffing signal that dominates lexical scoring is partially
  filtered out by a semantic embedding model.
- **Semantic-fluent attack**: the reverse pattern -- weakest against
  BM25 (0.44-0.80) and strongest against Reranker (0.88-0.92) --
  consistent with a cross-encoder responding to fluent, coherent content
  rather than raw term overlap.
- Both attacks strengthen with intensity (1 -> 3 poison documents), as
  expected -- more coordinated documents increase the chance at least
  one is retrieved.

An earlier exploratory run (N=30, lexical only, intensity=3,
`repeat_factor=4`) showed the lexical attack transferring near-perfectly
to *all* retrievers including Dense and Reranker (PRR@10=1.0
everywhere), which appeared to contradict the hypothesis. The N=25
systematic sweep above shows a clearer, hypothesis-consistent gap. This
discrepancy is noted rather than hidden: it may reflect small-sample
variance, corpus-size effects (a smaller/easier corpus gives retrievers
less competition to filter poison out), or aggressive term-repetition
producing incidental semantic signal. **This is flagged as an open
question for a larger-N confirmatory run, not resolved by this report.**

## 5b. Additional Conditions: Intensity=5, Low Poison-Rate, and 2Wiki (added post-initial-report)

### Intensity=5 (HotpotQA, N=25, same pinned revision as Section 5)

| Attack | Retriever | PRR@1 | PRR@3 | PRR@5 | PRR@10 |
|---|---|---|---|---|---|
| Lexical | BM25 | 1.00 | 1.00 | 1.00 | 1.00 |
| Lexical | Dense | 0.68 | 1.00 | 1.00 | 1.00 |
| Lexical | Hybrid | 1.00 | 1.00 | 1.00 | 1.00 |
| Lexical | Reranker | 1.00 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | BM25 | 0.72 | 0.92 | 0.96 | 1.00 |
| Semantic-fluent | Dense | 0.80 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | Hybrid | 0.84 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | Reranker | 1.00 | 1.00 | 1.00 | 1.00 |

Lexical-vs-Dense continues strengthening with intensity (0.52 at n=1 -> 0.60 at n=3 -> 0.68 at n=5), consistent with the "more coordinated documents increase retrieval chance" expectation. Semantic-fluent-vs-BM25 dipped from 0.80 (n=3) to 0.72 (n=5) -- noted rather than smoothed over; at 25 attacked queries this is a small enough sample that a single-query swing moves the mean by 0.04, so this is not treated as evidence against the hypothesis.

### Low global poison-rate (HotpotQA, N=25, intensity=1, poison_rate=0.3 -> 8 queries actually attacked)

| Attack | Retriever | PRR@1 | PRR@3 | PRR@5 | PRR@10 |
|---|---|---|---|---|---|
| Lexical | BM25 | 1.000 | 1.0 | 1.0 | 1.0 |
| Lexical | Dense | 0.750 | 1.0 | 1.0 | 1.0 |
| Lexical | Hybrid | 1.000 | 1.0 | 1.0 | 1.0 |
| Lexical | Reranker | 1.000 | 1.0 | 1.0 | 1.0 |
| Semantic-fluent | BM25 | 0.750 | 1.0 | 1.0 | 1.0 |
| Semantic-fluent | Dense | 0.750 | 1.0 | 1.0 | 1.0 |
| Semantic-fluent | Hybrid | 0.625 | 1.0 | 1.0 | 1.0 |
| Semantic-fluent | Reranker | 0.875 | 1.0 | 1.0 | 1.0 |

**Caveat, stated plainly:** with only 8 attacked queries, PRR@3-and-above saturating to 1.0 everywhere is a small-N ceiling effect, not a finding that low poison-rate defeats all retrievers equally at higher k. This condition demonstrates the injection/validation mechanism works correctly at a reduced rate; it should not be cited as a statistically comparable result to the N=25-attacked-query conditions elsewhere in this report.

### 2Wiki (N=25, intensity 1 and 3, both attacks, all 4 retrievers)

| Attack | Intensity | Retriever | PRR@1 | PRR@3 | PRR@5 | PRR@10 |
|---|---|---|---|---|---|---|
| Lexical | 1 | BM25 | 0.96 | 0.96 | 0.96 | 0.96 |
| Lexical | 1 | Dense | 0.64 | 1.00 | 1.00 | 1.00 |
| Lexical | 1 | Hybrid | 0.96 | 0.96 | 1.00 | 1.00 |
| Lexical | 1 | Reranker | 0.88 | 1.00 | 1.00 | 1.00 |
| Lexical | 3 | BM25 | 0.96 | 0.96 | 0.96 | 0.96 |
| Lexical | 3 | Dense | 0.68 | 0.96 | 1.00 | 1.00 |
| Lexical | 3 | Hybrid | 0.96 | 1.00 | 1.00 | 1.00 |
| Lexical | 3 | Reranker | 0.88 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | 1 | BM25 | 0.76 | 0.80 | 0.88 | 0.88 |
| Semantic-fluent | 1 | Dense | 0.84 | 0.96 | 1.00 | 1.00 |
| Semantic-fluent | 1 | Hybrid | 0.84 | 0.88 | 0.96 | 1.00 |
| Semantic-fluent | 1 | Reranker | 0.84 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | 3 | BM25 | 0.84 | 0.88 | 0.96 | 1.00 |
| Semantic-fluent | 3 | Dense | 0.96 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | 3 | Hybrid | 0.84 | 1.00 | 1.00 | 1.00 |
| Semantic-fluent | 3 | Reranker | 0.96 | 1.00 | 1.00 | 1.00 |

The lexical-weaker-against-Dense pattern replicates on 2Wiki (0.64-0.68 vs. 0.88-0.96 on other retrievers), consistent with HotpotQA. The semantic-fluent pattern is less clean here than on HotpotQA: Reranker is not consistently the strongest target (Dense and Hybrid tie or exceed it in several rows), and BM25's resistance (0.76-0.84) is notably higher than on HotpotQA (0.44-0.80 depending on intensity). The 2Wiki corpus built by this loader is much smaller (218 documents for 25 queries, vs. HotpotQA's larger pooled corpus) -- less competition for a poisoned document to out-rank likely compresses cross-retriever differences. This is a plausible explanation, not a confirmed one, and is flagged here rather than asserted as fact.

## 6. Bugs Found and Fixed During This Phase

Documented in full in the repo's commit history and README; summarized here:

1. **Cross-query target-answer type mismatch**: a "what year" question
   could be assigned a person's name as its false target answer,
   producing incoherent generated poison content. Fixed by preferring
   same-type (numeric vs. text) candidates.
2. **Multi-document poison coordination bug**: target answer was
   originally selected independently per poison document, so a
   "coordinated" 3-document attack could argue for 3 different random
   false answers. Fixed by selecting the target answer once per query.
3. **Multi-document duplication (both attack families)**: under greedy
   decoding, multiple poison documents for the same query were
   byte-identical (same prompt/template in, same output out every
   time). Fixed by varying phrasing/framing per document index in both
   `lexical.py` and `semantic_fluent.py`.
4. **Shallow corpus copy**: `inject_poisons()` originally copied the
   corpus list but not its dictionaries, so mutating a "poisoned"
   document could silently corrupt the "clean" reference data. Fixed
   with a proper per-dict copy; caught by a dedicated corruption-detection test.
5. **Sweep script had no progress output**: a real, long-running sweep
   (up to hundreds of real generation calls) was indistinguishable from
   a frozen kernel. Fixed by adding per-condition progress printing.
6. **2Wiki dataset loader used a dead Hugging Face mirror**: `load_2wikimultihopqa()` pointed at `xanhho/2WikiMultihopQA`, which ships a Python loading script; current `datasets` (v4+) refuses to execute dataset loading scripts at all, so any real attempt to load 2Wiki failed outright with `RuntimeError: Dataset scripts are no longer supported`. This is why 2Wiki was marked "not yet run for real" in the original version of this report -- the revision hash had been pinned but never actually validated against a live load. Fixed by switching to `Salesforce/ContextualBench` (a parquet-native mirror of the same data, commit `9823f70484dea525100394220b0ea5184d0eeb7b`), which also required mapping the "validation" split name to that mirror's "dev" split and updating the row-parsing code since its `context`/`supporting_facts` fields are native nested structures rather than JSON-encoded strings. All four 2Wiki configs' `dataset_revision` field was updated from the old (dead) hash to the new one.

## 7. Readiness Assessment

- [x] Poisoning does not corrupt ground-truth labels (validated, 7-point check, 100% pass rate across all conditions run)
- [x] Both required attack content families implemented and tested
- [x] Intensity levels 1 and 3 validated with real data and real generation
- [x] Intensity level 5 -- run at scale (N=25, HotpotQA, both attack families, all 4 retrievers). Both attacks strengthen further at intensity 5 vs. 3 for lexical-vs-Dense (0.52 -> 0.60 -> 0.68 PRR@1); semantic-fluent-vs-BM25 dipped slightly at intensity 5 (0.72) vs. intensity 3 (0.80), within expected noise at N=25 attacked queries -- not treated as a reversal of the hypothesis.
- [x] Low global poison-rate condition (poison_rate=0.3) -- run at scale, HotpotQA, intensity=1. Only 8 of 25 queries were attacked at this rate, so PRR@3 and above saturating to 1.0 across all retrievers reflects small-N ceiling effects rather than a strong finding -- reported as an existence proof that the mechanism functions correctly at low rate, not as a statistically weighted comparison point.
- [x] Cross-pipeline transferability mechanism built and producing real, hypothesis-relevant results
- [x] 2Wiki dataset -- run for real (N=25, intensity 1 and 3, both attack families, all 4 retrievers). See Section 5b and Section 6 (new bug #6) for details, including a real dataset-loading bug found and fixed during this run.

**Overall: the benchmark itself is built, tested, and validated as required for Weeks 5-6, and all previously-deferred conditions (intensity=5, low poison-rate, 2Wiki) have now been run at scale.** One item remains open by design, not oversight: the N=30-vs-N=25 discrepancy in Section 5's discussion (lexical attack transferring near-perfectly to all retrievers in an early exploratory run, vs. a cleaner hypothesis-consistent gap in the systematic N=25 sweep) is still unresolved and is explicitly deferred to Weeks 9-10, where a larger-N confirmatory run and a repeat_factor ablation are the planned next steps. Attack Success Rate (ASR) -- comparing generated answers against true vs. targeted false answers -- remains scoped for Weeks 9-10 per the roadmap, once the RCD defense (Weeks 7-8) exists to compare against.
