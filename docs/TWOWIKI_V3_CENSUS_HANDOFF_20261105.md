# 2Wiki V3 — verified train-census handoff (5 November 2026)

**Outcome: train-ID capacity GO; prospective V3 and held-out replication NO-GO.**
This is a new evidence addendum. Do not edit the original historical exposure
register, 509 frozen artifacts, V3 profile, RCD constants or old run seals.

## Verified, independently user-produced artifacts

- Same-revision `Salesforce/ContextualBench`, `2WikiMultihopQA`, train,
  revision `9823f70484dea525100394220b0ea5184d0eeb7b`.
- Exact uploaded train export SHA-256:
  `d03fbec1e4bce53de1c3dae095c810b180bdf53efd9512e547ee49bb37f983c2`.
- Reconciled exclusion registry SHA-256:
  `799c87aa83f6cb8ded2a16d0cbf110f35d1512b359d725dd27fa342422a68e65`.
- User-produced scientific review report SHA-256:
  `f9488c3a18720c04546a290e2e40b01148a74178342df27475a1cbdec57bfa83`.
- 167,454 unique train IDs; 900 known exclusions; 300 overlapping train IDs;
  167,154 train IDs outside **known** exclusions.
- The reconciled registry lists **3 historical gap categories**; the independent
  historical issue register lists **six issues**, one of which (`FRESH-POOL`)
  predates this new larger-pool evidence. Do **not** rewrite historical entries:
  this addendum supersedes *only* the pool-cardinality finding.

The enumerated 167,154 are *not independently certified unexposed IDs*.
Exact Week 5–6 25-ID sweep provenance, remote/deleted record inventory, custody,
human review and inference authorization are not supplied by those counts.

## One terminal command — create a write-once handoff

From a checkout containing this PR:

```bash
python scripts/prepare_twowiki_v3_census_handoff.py \\
  --train-ids "$HOME/Documents/rag-research-results/twowiki-v3-census-20261105/twowiki-full-train-ids.json" \\
  --train-sha256 d03fbec1e4bce53de1c3dae095c810b180bdf53efd9512e547ee49bb37f983c2 \\
  --registry reports/twowiki_v3_exposure_reconciliation/reconciled_registry.json \\
  --registry-sha256 799c87aa83f6cb8ded2a16d0cbf110f35d1512b359d725dd27fa342422a68e65 \\
  --review-report "$HOME/Documents/rag-research-results/twowiki-v3-census-20261105/SCIENTIFIC_GO_REVIEW.json" \\
  --review-sha256 f9488c3a18720c04546a290e2e40b01148a74178342df27475a1cbdec57bfa83 \\
  --output-directory "$HOME/Documents/rag-research-results/twowiki-v3-handoff-20261105"
```

Outputs in the *new*, immutable-name directory:
`all_train_pool.ids.json` (all original training IDs, sorted, never selected)
and `READINESS_HANDOFF.json` (aggregate-only decisions and SHA bindings).
If the output directory exists, the command fails rather than overwriting it.

**Do not commit the 167,454-ID export** to GitHub. Store it in the external
results directory. The original 300-ID development cohort is still excluded.
The handoff's all-train IDs can become a future `--pool-ids` input **only once**
the certified registry and all prospective handoffs exist. It does not authorize
`prepare_semantic_v3_pilot.py select` while the registry contains historical
gaps, and it never calls the model or opens held-out records.

## Real remaining gates (not solved by code)

1. Reconcile or explicitly account for the original 25-query sweep exact IDs,
   executed revision, deleted/remote exposures and runtime receipts.
2. Obtain evidence-based custodian certification bound to a new *separately
   pinned* complete registry. An unsigned or self-declared flag is not proof.
3. Obtain independent protocol review, freeze a genuinely uninspected
   development cohort **before** any content access, complete target evidence
   and independent human approval.
4. Freeze runtime/model/tokenizer and corpus pins, construction-only budget,
   immutable journal/output namespace, and an external authorizer's explicit
   approval before any V3 construction inference.
5. Only after separate validation and authorization may a later paired Dense/RCD
   or held-out replication be considered.

A separate, explicitly **non-prospective** construction-only protocol can use
exposed development examples after its own real approval and artifact freeze.
It can establish engineering construction quality, not prospective attack or
defense effectiveness. Neither an offline passing test nor this handoff can
legitimately turn the full experiment's NO-GO into GO.
