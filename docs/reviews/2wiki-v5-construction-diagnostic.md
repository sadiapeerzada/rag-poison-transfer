# 2Wiki v5 — matched real-Qwen development construction diagnostic

The previous 2Wiki train/development-only v4.1 diagnostic completed 30 model
calls and produced **0/30 strict grammar passes**. Its post-hoc triage classified
six replies, all from C05, as *needing independent content review*. The other
24 replies had referent and/or polarity failures. The rejection-reason counts
overlap, and zero injected documents or construction approvals exist.

This branch **does not replace, alter or retroactively correct** v4 outcomes.

## Changed method and limitations

- v5 explicitly includes *entire film titles*, including leading words
  such as **Yes, Giorgio** and disambiguators such as **(1933 Film)**.
- The target relation is stated with Boolean/place-specific polarity.
- Three document slots use distinct prompts, but a slot's output is not
  accepted as independent just because its prompt differs.
- The v5 surface triage is less literal than exact v4 templates. It still
  fails closed for unsupported question types, absent exact referents,
  negated place claims, wrong relations, malformed text and held-out scope.
- The triage output is **never an approval**; a positive only means
  `needs_independent_content_review`. Its syntactic patterns cannot prove
  factual falsehood, semantic entailment, independent corroboration, model
  provenance authenticity or evidence quality. Ambiguous outputs abstain.
- Intensity 3 needs all three distinct candidate responses and separate
  independent semantic review; normalized surface diversity is not
  independent evidence.

## Matched v4 versus v5 comparison

v5 uses exactly the same fixed five case IDs, pinned train review packet,
local MLX Qwen model revision, independent per-slot/attempt seeds,
`max_tokens=150`, and two attempted completions per slot as the completed
v4.1 run. It changes the versioned prompt and triage only. Results are in
new timestamped *local* folders; there is no corpus injection or access to
held-out data. Per-call intent is written before generation, so interrupted
calls remain **indeterminate**, not "failed with no model call".

## Running on your Mac

Use a **new clean worktree** for this stacked branch so the original study
and `research/2wiki-v4-1-development-quality-audit` worktree are unchanged.

```bash
cd "$HOME/Documents/rag-2wiki-v3-development"
git fetch origin research/2wiki-v5-construction-diagnostic
git worktree add --detach "$HOME/Documents/rag-2wiki-v5-diagnostic" FETCH_HEAD
cd "$HOME/Documents/rag-2wiki-v5-diagnostic"
PY="$HOME/Downloads/rag-poison-transfer/.venv/bin/python"
"$PY" -B -m pytest -q tests/test_semantic_fluent_development_v5.py tests/test_twowiki_v5_construction_diagnostic.py

ROOT="$HOME/Documents/rag-research-results"
PACKET="$HOME/Downloads/twowiki_v4_1_audit_inputs/2wiki_v4_1_independent_review_packet.zip"
AUDIT="$ROOT/twowiki-v4-1-quality-20261103T153852Z.json"
MODEL="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
OUT="$ROOT/twowiki-qwen-v5-$(date -u +%Y%m%dT%H%M%SZ)"

"$PY" -B -m scripts.run_twowiki_v5_construction_diagnostic \
  --repo "$PWD" --packet "$PACKET" --audit "$AUDIT" \
  --model-snapshot "$MODEL" --output "$OUT" --preflight

caffeinate -i "$PY" -B -m scripts.run_twowiki_v5_construction_diagnostic \
  --repo "$PWD" --packet "$PACKET" --audit "$AUDIT" \
  --model-snapshot "$MODEL" --output "$OUT"
```

**Do not run the real-model command if preflight, test results or worktree
integrity checks fail.** A second invocation must use a new output folder;
do not reissue indeterminate calls without an explicit audited policy.

## Next gates (unchanged)

1. Inspect v5 per-case raw outputs, failure causes and distinctness. Do not
   collapse generation success, surface triage and factually approved evidence.
2. Independently review candidate claims against source documents. Re-review
   the changed C05 slot-2 sentence, resolve the C02 referent/nationality
   caveats, and record genuine reviewer run metadata (not fabricated).
3. Expand compatible train/development targets beyond the original five
   under an explicit versioned review protocol. No automatic approval of the
   20 abstained questions.
4. Only then run a small paired poisoned Dense-vs-RCD **development** pilot
   on eligible, fixed poison instances; preserve clean/poison identity pairs.
5. Freeze the revised replication protocol and obtain held-out authorization
   before any 300-query test/matrix study.
