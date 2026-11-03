# 2Wiki v4.1 — development-only construction quality audit

This change does **not** claim any 2Wiki poisoning success. It never invokes
a model, creates poisoned corpora, opens the held-out split, or promotes the
frozen Week 9 matrix protocol.

## Inputs and exact provenance

The CLI `scripts/audit_twowiki_v4_1_quality.py` checks:

1. The pinned 300-question **train** dataset (SHA-256
   `58b0342d65addaeab6617ab3a3b8dc759633fc02d11652759b8409dffbe8cb43`).
2. The already completed 25-query clean pilot manifest, whose recorded
   `cohort_manifest_sha256`, query-set fingerprint, and corpus fingerprint
   bind the original frozen development cohort.
3. The external 5-case second-AI review packet (SHA-256
   `467f457a16d1a092e6057f54a91a02de2f9f3c405fe6428876853ba1ff30bbf6`).
4. The raw second-AI review JSON, bound to the exact packet ZIP and inner JSON
   SHA-256 hashes; 3 passage-level decisions per case and source quotations.
5. The v4.1 *versioned* deterministic template statements and typed
   film-director-person source relationship binding.

A missing or mismatched input aborts, rather than silently approving a case.
Rows without a reviewed target count as **abstentions**, not attack failures or
defense successes. The CLI intentionally retains per-case caveats. It expects
5 provisionally reviewed cases and 20 abstentions among the frozen 25.

## Known limitations before any run

- C05 slot 2 in the second-AI review packet is the older *filmmakers behind*
  sentence. The v4.1 repository now uses *directors of ... are of the same
  nationality*. The audit must report this exact-text mismatch.
- The second review has no run ID or timestamp; it cannot pass the current
  two-AI provenance requirement. Even self-reported metadata alone cannot
  cryptographically authenticate an independent reviewer.
- C02's Edward Zwick/Edward M. Zwick and nationality-versus-country
  interpretation require explicit adjudication.
- v4 actual Qwen diagnostic: **0 of 5** heuristic passes. The five source
  compatible deterministic templates must not be reported as Qwen successes.
- All outputs keep construction, factual and injection approval at zero.
- This audit cannot measure a true 25-query real-model semantic construction
  success rate. That requires separate, appropriately logged model
  observations, not interpolation from 5 reviewed templates.
- The code does not access HotpotQA or any 2Wiki test/held-out data.

## Run in a clean Mac worktree containing this branch

Supply the local train dataset, its 25-query cohort manifest, the exact
completed clean pilot manifest, and the two separately downloaded review files:

```bash
python -B scripts/audit_twowiki_v4_1_quality.py \
  --dataset "$HOME/Documents/rag-research-results/twowiki-v2-development-recovery-20261103/development_data.json" \
  --cohort "$HOME/Documents/rag-research-results/twowiki-v3-exploratory-25cohort-20261103/manifest.json" \
  --baseline "$HOME/Documents/rag-research-results/twowiki-clean-dense-rcd-dev25-20261103T145542Z-a6fdbb/manifest.json" \
  --packet "$HOME/Downloads/2wiki_v4_1_independent_review_packet.zip" \
  --review "$HOME/Downloads/2wiki_v4_1_independent_review_results.json" \
  --output "$HOME/Documents/rag-research-results/twowiki-v4-1-quality-audit-20261103.json"
```

The output filename must not already exist. **Do not push the output JSON to
GitHub**: it contains development query identifiers.

Run regression tests with:

```bash
python -m pytest -q tests/test_twowiki_v4_1_quality_audit.py
```

### Downstream experiment gates

1. Re-adjudicate C05's *exact new wording* and the C02 caveats.
2. Obtain legitimately captured reviewer-run metadata and required scientific
   approvals; do not forge a backdated review.
3. Develop a separate reviewed real-model semantic construction audit,
   tracking successes and rejected attempts for intensity 1 and 3.
4. Execute a paired poisoned **development-only** Dense-vs-RCD pilot on
   explicitly eligible source instances only. No mixing deterministic template
   controls with Qwen generation.
5. Review pilot results, freeze a revised protocol and seek authorization
   before the separate 300-query held-out 2Wiki study.
