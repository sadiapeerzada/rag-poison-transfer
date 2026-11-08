# 2Wiki full-run restoration verification receipt — 9 November 2026

**Evidence type:** operator-supplied local Mac Terminal transcript. **Status:** downloaded/separately supplied archive verification and full extraction **PASS**. Origin of downloaded bytes remains an operator assertion, not independently attested by the verifier.

## PASS output

The researcher executed the already merged [full-run backup verifier](../scripts/backup_2wiki_full_run.py) with the archive and manifest in `~/Downloads/`, the following independently recorded creation-time digest, and an empty restore path outside the frozen original:

```text
python3 .../backup_2wiki_full_run.py verify \
  --archive ~/Downloads/2wiki-full-run-20261109.tar.gz \
  --manifest ~/Downloads/2wiki-full-run-20261109.tar.gz.manifest.json \
  --expected-archive-sha256 faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82 \
  --restore-to ~/Downloads/2wiki-restored-20261109

PASS: separately supplied archive matches pinned hash, embedded manifest and 37534 restored file hashes
Restored to: /Users/sadiapeerzada/Downloads/2wiki-restored-20261109
Remote independence must be confirmed by operator (e.g. actual web download to different location/device).
```

### Validated integrity

- Archived inventory: **37,534** files, **518,755,193** original source bytes (as recorded in the [creation checkpoint](2WIKI_LOCAL_RECOVERY_AND_AUDIT_CHECKPOINT_2026-11-09.md)).
- Archive SHA-256: `faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82` matched the separately retained pinned digest.
- Archive embedded manifest, external manifest and each extracted file hash matched; a **new restore directory** was created outside the original run.
- The original frozen run and experiment are unchanged; no model inference or regeneration.
- The preceding attempted verification with missing `~/Downloads/2wiki-full-run-20261109.tar.gz` failed with `FileNotFoundError` before creating a restoration directory. After obtaining the missing archive in Downloads, the rerun passed.

### Evidence limits

The transcript shows that the archive existed separately in Downloads and restored correctly. **The tool cannot attest where the archive's bytes originated.** If the operator indeed downloaded the two inputs from the **iCloud.com web interface**, rather than copied the local sync file, this demonstrates independent cloud retrieval. Retain the browser download confirmation or dated custody note to establish that external origin in the paper's reproducibility package. Do not claim a restore on a second physical device; this was an independent directory on the same Mac.

The run archive covers the `authorized-matrix` tree, not model weights and dataset caches located elsewhere. Those external dependencies require a separate pinned preservation plan.

### Remaining work

1. **Human/source-backed review** of 131 sampled cases representing 102 distinct query IDs. Read-only paired-case census already passed 3,600 records; no human semantic adjudication was performed by the exporter.
2. **External model and dataset-cache recovery plan** if full bitwise rerun/reproducibility is required.
3. **Researcher/supervisor assessment** of the two-dataset results and remaining limitations before publication.

For complete prior results, see the [HotpotQA versus 2Wiki comparison](HOTPOTQA_VS_2WIKI_PAIRED_COMPARISON_2026-11-09.md) and [2Wiki qualitative triage](2WIKI_AGGREGATE_ERROR_TRIAGE_2026-11-09.md).
