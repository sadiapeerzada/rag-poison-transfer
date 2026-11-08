# Complete 2Wiki backup and qualitative review: operator runbook

**Date:** 9 November 2026. **Status:** implementation and instructions prepared; **off-device restoration and human case review have not been performed by this PR**.

This runbook is intended for the researcher who owns the original local frozen 2Wiki
artifacts. It never asks that frozen branches, protocols, files, generation
outputs, seeds or model configurations be rewritten. The tools use only standard
Python 3 libraries and do **not** invoke any model or inference runner.

## 0. Check location and capacity

The frozen run was previously reported at:

    $HOME/Documents/rag-research-results/twowiki-300-readiness-20261106/authorized-matrix

From an ordinary terminal, without enabling shell-wide fail-fast options:

    RUN="$HOME/Documents/rag-research-results/twowiki-300-readiness-20261106/authorized-matrix"
    du -sh "$RUN"
    df -h "$HOME"
    shasum -a 256 "$RUN/protocol.json" \
      "$RUN/execution/construction/construction.seal.json" \
      "$RUN/execution/evaluation/evaluation.complete.json" \
      "$RUN/execution/aggregate.json"

Pinned 2Wiki values:
- Protocol: 40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4
- Construction seal: e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44
- Evaluation completion: db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519
- Validated aggregate: 721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96

**Do not proceed if a pin differs.** Investigate without deleting old artifacts.

## 1. Obtain the two tools outside the frozen checkout

The PR adds:
- [Full-run backup/restoration checker](../scripts/backup_2wiki_full_run.py)
- [Paired-case census and semantic review exporter](../scripts/audit_2wiki_paired_cases.py)

Download the two Python files from the **GitHub PR branch** to a separate
directory, for example **~/Downloads/2wiki-research-tools/**. Do not switch the
existing frozen checkout to this PR branch or change any tracked file in it.

## 2. Create an archive that INCLUDES the full construction directory

Choose an independent destination with capacity for the complete run directory.
For example, with enough available iCloud Drive quota:

    RUN="$HOME/Documents/rag-research-results/twowiki-300-readiness-20261106/authorized-matrix"
    TOOL="$HOME/Downloads/2wiki-research-tools/backup_2wiki_full_run.py"
    CLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
    ARCHIVE="$CLOUD/rag-research-backups/2wiki-full-run-20261109.tar.gz"

    python3 "$TOOL" create --run "$RUN" --archive "$ARCHIVE"

The tool refuses to overwrite existing backups, verifies the exact frozen
protocol/construction/evaluation/aggregate pins, enumerates/hashes every regular
file under **the entire authorized-matrix directory**, refuses symlinks,
archives the tree and an embedded hash manifest, and independently re-reads and
checks every member from the resulting archive.

Expected success: a printed local archive SHA-256, a sidecar
\`<archive>.manifest.json\` and \`<archive>.sha256.txt\`. **Preserve the SHA-256
separately** (e.g., in a written research handoff). A locally readable archive
and a file under iCloud's *synchronized local folder* do **not** by themselves
prove off-device recoverability.

This intentionally supersedes the earlier partial 447-MB evaluation archive:
that archive contained the construction **seal**, but not the full construction
records/journals.

## 3. Confirm a separately retrieved off-device copy restores correctly

1. Wait for iCloud Drive upload to complete and check the archive appears at
   **iCloud.com**, or transfer the archive and sidecar to another device/disk.
2. **Download** the archive and matching \`.manifest.json\` from that remote
   location to a new destination. Do not use the original local iCloud-sync
   path as the independent copy.
3. Verify the copy and restore all files to a **new, empty location**, using
   the SHA-256 **copied from the earlier create output**:

        TOOL="$HOME/Downloads/2wiki-research-tools/backup_2wiki_full_run.py"
        python3 "$TOOL" verify \
          --archive "$HOME/Downloads/2wiki-full-run-20261109.tar.gz" \
          --manifest "$HOME/Downloads/2wiki-full-run-20261109.tar.gz.manifest.json" \
          --expected-archive-sha256 "<PASTE_SEPARATELY_RECORDED_HASH>" \
          --restore-to "$HOME/Downloads/2wiki-restored-20261109"

4. Record the independent destination, download time, expected digest and the
   verifier's final PASS line in a research custody note. **Do not invent the
   external download/restore check if it wasn't performed.**

The run-tree archive covers construction, evaluation, aggregate and other files
*inside* \`authorized-matrix\`. Source-code commit, external model snapshots and
dataset caches that reside *outside* this tree still require their own pinned
availability check and recovery policy. Do not publish private datasets, API
keys or model binaries without licensing and consent review.

## 4. Generate the full paired-case error census and audit sample

Run **only against the frozen original** (not a partial restored copy),
writing outside its tree:

    RUN="$HOME/Documents/rag-research-results/twowiki-300-readiness-20261106/authorized-matrix"
    TOOL="$HOME/Downloads/2wiki-research-tools/audit_2wiki_paired_cases.py"
    OUT="$HOME/Documents/rag-research-results/2wiki-paired-review-20261109"

    python3 "$TOOL" --run "$RUN" --output "$OUT" --per-stratum 4

It verifies the uploaded-aggregate SHA-256, checks 12 cell × 300 constructions
and both paired arms against their aggregate targeted-success totals, and
deterministically samples disagreements with a frozen selection hash:
RCD-only successes, Dense-only successes, clean-EM differences, exposed-vs-
unexposed disagreements, semantic accepted/rejected cases and controls. It
creates:
- \`paired_census.csv\`: **all 3,600** case×cell records, both arms, QA labels
- \`audit_summary.json\`: counts by stratum and provenance, no human judgments
- \`review_packet.jsonl\`: selected original poison texts, prompts, generated
  answers, semantic validator outcomes and source paths for inspection
- \`human_review_template.csv\`: **blank** independent-review decisions

**Do not interpret an empty human-review template as a completed semantic audit.**

## 5. Human adjudication protocol (unperformed)

Use two independent reviewers where feasible and record their identity/date,
sources and disagreements. For each sampled case, decide whether:
- the poison text actually **asserts** the nominated answer rather than
  merely mentions it or contradicts it;
- the nominated fact is *actually false* under authoritative independent
  sources, **not merely different from the provided dataset gold label**;
- relation/entity/time/choice constraints and supplied gold aliases are
  respected;
- answer extraction/formatting falsely counts or misses a target success;
- the RCD-versus-Dense difference comes from actual generator-visible
  poisoned evidence, answer generation, or an unresolved mechanism.

Review semantic **accepted** and **rejected** texts separately. Do not
retroactively accept previously rejected generations or modify frozen
denominators. Sampling was selected *after* seeing aggregate outcomes, so
qualitative examples are explanatory/exploratory, not confirmatory evidence of
causation. The template shows model/pipeline outcomes; this is **not a blinded
review protocol**. If blinding is needed for publication, independently design
and freeze an additional reviewer packet with arm/target masking before review.

**Privacy:** The raw review packet can contain dataset text, query IDs,
generated passages and model prompts; keep it local until licensing/privacy
and human-review requirements are satisfied.

## 6. Close-out criteria

- [ ] Full-run archive created, sidecar hashes pinned externally
- [ ] Archive observed/uploaded at independent destination
- [ ] Independently downloaded copy restored, every archived file/hash verified
- [ ] External model/data dependencies accounted for
- [ ] Paired-case census generated successfully
- [ ] Human reviewers adjudicated samples with citations and reconciled disputes
- [ ] Discussion contrasts HotpotQA and 2Wiki without pooling incomparable
      denominators or claims (see [comparison](../reports/HOTPOTQA_VS_2WIKI_PAIRED_COMPARISON_2026-11-09.md))
- [ ] Supervisor reviews unresolved scientific limitations and manuscript scope

**Current outcome:** The cross-study numerical comparison is complete, but
off-device backup verification and qualitative human truth adjudication are
blocked on local/external evidence and must not be marked DONE from this PR.
