# HotpotQA cross-pipeline transfer — local raw-artifact verification receipt

**Recorded:** 9 November 2026 (India local date)  
**Evidence type:** operator-supplied Mac terminal output from the existing read-only verifier.  
**Reported status:** **PASS_RAW_TRANSFER_AUDIT**.  
**Scope:** frozen 300-query, 12 condition-cell source-crafted HotpotQA cross-pipeline transfer experiment; 4 source pipelines × 5 target pipelines = **240 final source-target cells**.

## Operator-reported verification result

The operator first updated their local checkout to the merged raw-audit verifier at commit `34dce108a6528a1c9dee2e74b9a23c7b145f2a9e`, then ran:

```bash
python -m pytest -q tests/test_nov09_research_gates.py
# 10 passed in 0.12s

bash scripts/nov09_mac_research.sh transfer-audit
# status: PASS_RAW_TRANSFER_AUDIT
```

The verifier reported:

| Field | Value |
|---|---:|
| Verified source-to-target cells | **240** |
| Frozen unique query IDs per condition | **300** |
| Seeded attack-family/intensity condition cells | **12** |
| Original source-target paired QA comparisons checked | **20,500** |
| Selection-stage inventory files hash-checked | **61,601** |
| Evaluation-stage inventory files hash-checked | **158,037** |
| Optional candidate-library inventory files checked | **Not checked (null)** |
| Original/public aggregate conditions compared | **240** |
| Original/public cell-value comparison | **Exact match after keying by condition** |
| Public aggregate list order differs from original | **Yes (permutation only)** |

The public [transfer aggregate](../paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json) contains the same 240 keyed records, with identical counts, rates, 80 query-cluster bootstrap groups, and execution accounting. The two arrays are presented in different condition order; list-order equality is **not** part of scientific identity.

The verifier confirmed the original selection and evaluation stage inventories match their recorded file SHA-256s. It checked generation-record extraction and exact-match metrics against the matched source/target raw observations, including construction-failure accounting. It did **not** invoke the generator, rerun retrieval, regenerate attack documents, or modify the original frozen data.

## Immutable provenance pins (publicly non-reversible)

| Bound artifact | SHA-256 |
|---|---|
| Frozen transfer protocol | `94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa` |
| Source-selection seal | `3f9217c83a7c1309763468be1cf2e57ebcd0ecd726a44c57b4eaa4d61ab3b750` |
| Transfer evaluation completion | `72343b04134f8d6f24815d731af52c644d517dba042754236f9e7f089316c191` |
| Original aggregate | `43f3f652460ac365fefdf2e516d227c66aae9fb124df8ca028874327e9335adc` |

## Verification boundaries

- This is a **reproducible operator-reported local receipt**, not an independent third-party audit of the operator's machine or source provenance. The assistant received the displayed terminal output, **not the original raw tree itself**.
- The optional candidate library was **not** inspected by the invocation recorded here; `candidate_inventory_files_checked` was `null`. The source-selection and final-evaluation inventories **were** checked.
- Hash matching proves consistency with the recorded manifests, not dataset licensing, independent target factuality, truthfulness of synthetic semantic evidence, hidden prior model behavior, or external model-weight custody.
- There are repeated query IDs across seeds and repeated evaluations across pipeline targets. **20,500 paired comparisons are not 20,500 independent questions.**
- The existing seed-42 interrupted-call provenance caveat remains documented in the original [transfer results README](../paper/results/hotpotqa_transfer_43f3f652460a/README.md). This receipt does not reconstruct the indeterminate call or alter the separate replacement provenance.
- No query-level IDs, gold/target answers, attack text, private filesystem paths, prompts, checkpoints, or model outputs appear in this report.

**Conclusion:** The HotpotQA transfer final-evaluation raw-artifact integrity and its aggregate/public numerical consistency gate is **complete as an operator-reported local verification**. The optional candidate-library and external factuality/custody checks remain distinct and unclaimed.
