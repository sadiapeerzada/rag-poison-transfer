# Task 11: 57-file raw-result content and redistribution-rights review

**Date:** 9 November 2026  
**Scope:** Read-only file-structure triage of the **57 results files already publicly Git-tracked**. This work does not revise frozen experiment values, rewrite Git history or approve redistribution.

## Verified source inventory

The merged [57-file pinned inventory](../paper/release/nov09_tracked_result_rights_inventory.json) records **28 JSONL + 22 JSON + 7 CSV = 57** files, with **37,543,064** original tracked bytes, exact paths and Git blob identities. The repository's tracked tree currently contains **no top-level LICENSE/NOTICE file** identified by the latest repository tree query, so upstream scientific data licenses and repository code licensing must be documented separately rather than inferred from public access.

The first local audit already passed (four NQ SHA pins, eight public evidence blobs, 2Wiki full-run archive SHA) and did not flag credentials after two fixed scanner false positives. That result is an **integrity check**, not source-license/privacy/legal certification.

## Primary-source license pointers (not a blanket rights clearance)

| Source corpus | Upstream published notice | Primary upstream link | What still needs review |
|---|---|---|---|
| HotpotQA | CC BY-SA 4.0, including the processed Wikipedia corpus as described on official site | https://hotpotqa.github.io/index.html | Attribution/license notices, share-alike implications for reproduced/modified passages, prompts, and generated derivatives; identify exact source version |
| 2WikiMultiHopQA | Official upstream GitHub repository displays **Apache-2.0** license | https://github.com/Alab-NII/2wikimultihop | Exact dataset source variant and copied texts; distinction between repository notice and underlying Wikipedia content, model-generated modifications, privacy |
| Google Natural Questions | Google's **official download page states Creative Commons Share-Alike 3.0** | https://ai.google.com/research/NaturalQuestions/download | NQ HTML/Wikipedia extracts, question text, any additional third-party content, source version and attribution/redistribution requirements |

**Important:** A dataset's upstream license does not necessarily clear all third-party text, generated responses, model checkpoints or hidden-test data. This document is a research-source checklist, not legal advice or a license grant.

## New local source-content audit

The [read-only full-file scanner](../scripts/audit_57_result_contents_offline.py) reads each of the 57 tracked files **under an 8-MiB/file cap**. It verifies every path, byte size and Git blob SHA-1 against the merged pinned inventory. It fully parses JSONL/JSON/CSV, records the presence and aggregate counts of raw question, prompt, response, document/text and answer field **names**, plus possible email patterns and high-confidence credential-pattern *classes*. No source text, emails, matches, raw answer contents or credentials are copied into the report.

Each file receives a preliminary status:
- `RAW_OR_MIXED_TEXT_REVIEW_REQUIRED` when known raw-text fields occur.
- `NO_NAMED_RAW_FIELDS_REVIEW_STILL_REQUIRED` otherwise (not a clean privacy or license clearance).

The scanner also reports dataset **filename hints**, rather than asserting that a file was derived from a specific licensed upstream dataset. All 57 remain `publication_rights_cleared: false` and `human_privacy_review_completed: false` unless a responsible person verifies and documents their rights.

### One Mac command (after merging the PR when its tests pass)

```bash
cd "$HOME/Downloads/rag-poison-transfer"
git fetch origin
git switch main
git pull --ff-only origin main
python -m pytest -q tests/test_audit_57_result_contents_offline.py
python scripts/audit_57_result_contents_offline.py --out "$HOME/Documents/rag-research-results/nov09-research-gates/task11-57file-content-audit-$(date -u +%Y%m%dT%H%M%SZ)_PRIVATE.json"
```

Share **only the command's aggregate terminal summary** for review. The complete report has filenames and aggregate flags, not snippets, but should still be retained privately until owner review.

## Human scientific and rights decision sheet

For each file flagged raw/mixed, the responsible author/data-rights reviewer must determine:

1. **Provenance** — dataset name, exact split and revision, original text/response origin; whether any content came from a hidden or access-restricted test source.
2. **Rights** — which license or permission applies to source passages, benchmark question/answer strings, model output and attack-generated modifications; required notices, attribution and share-alike obligations.
3. **Privacy** — whether any person-identifying, third-party or confidential information occurs in raw questions, prompts, retrieved documents or output; decide whether existing public copies/history need restriction/redaction. A lexical email flag alone neither proves nor disproves a privacy issue.
4. **Release action** — approve continued publication as-is with documented justification, publish aggregate-only replacements while preserving private originals, or quarantine/restrict content using an authorized Git-history/privacy process. **Do not automatically delete or rewrite raw research evidence.**
5. **Traceability** — record responsible reviewer, review date, decision and source supporting evidence for every reviewed path.

Public release **GO cannot be auto-generated** from a regex or heuristic file scan.

## Remaining independent reproducibility gates

- **External archive custody:** Local 2Wiki archive SHA `faecd723105465d80ff4de8c48795cbb983560ddaa06943840b3971d59deac82` and same-Mac restore are already checked, but there is no verified off-device restore receipt/source chain.
- **Model/data dependency restoration:** The tar did not establish independent recovery of original Qwen/tokenizer, embedding snapshots and input caches. Preserve their exact pinned manifests and check backup on a genuinely distinct device/storage medium before claiming this.
- **Historical exposure:** The original 2Wiki cohort's prior exposure risk and the prospective v3 NO-GO cannot be mechanically reversed.
- **Scientific source adjudication:** Task 4/9 factuality remains an independent source-review requirement; do not label matched targets as verified misinformation from an integrity audit.
- **Current CI and rights reviewer sign-off:** CI and artifact correctness are necessary but insufficient for rights/custody certification.

**Task 11 status after this PR and Mac run:** the **57-file automated structural/privacy triage** can be completed, while **global independent rights, custody, exposure and scientific validity sign-offs remain open**. This is tangible, source-grounded progress without wasting Qwen calls.
