# E1/E2 reuse inventory — preparation review, 12 November 2026

The revised E1/E2 direction supersedes the previous expansion plan. This milestone ran no Qwen/Phi inference, final experiment or retrieval replay. Original results, checkpoints, manifests and protocols were preserved. New protocols remain drafts. No real E1/E2 response reuse is certified yet; this does not imply that no historical calls will ultimately qualify.

## Evidence inspected

Reviewed the source-selection runner, offline HotpotQA raw verifier, matched Week9 evaluator, QA record validation, Dense/RCD configs, reranker implementation, existing transfer tests, frozen construction documentation and published transfer/Week9 receipts. Located the authorized local private HotpotQA transfer tree. No private paths, queries, IDs, evidence, prompts or answers are reproduced here.

Read-only SHA-256 inventory verification found exact membership and content matches, with symlinks rejected:

| Stage | Files checked | Manifest SHA-256 |
|---|---:|---|
| Candidate library | 24,546 | `97960932066b24f172fc566dd29808dc191cb85aa08cf995ffbd04c91d809f23` |
| Source selection | 61,601 | `3f9217c83a7c1309763468be1cf2e57ebcd0ecd726a44c57b4eaa4d61ab3b750` |
| Final evaluation | 158,037 | `72343b04134f8d6f24815d731af52c644d517dba042754236f9e7f089316c191` |

The latter two match the published November 9 receipt. The candidate pin is newly recorded here: it proves consistency with the available manifest, not independent external custody. Native selected/evaluation inventories are not new response counts. This milestone does not repeat the full scientific/aggregate validation performed by the existing raw verifier.

Native candidate records contain ordered bands, original/partial documents, attempt records, target selections, status and query fingerprints. Selected records contain source feedback. Screening checkpoints bind candidate, query, source and library pin. Sampled valid evaluation records contain clean/poisoned ordered evidence and IDs, full generator/backend prompts, raw/extracted responses, hashes, execution metadata and timing/operation accounting. The protocol records model file hashes, revision and runtime package versions. These are availability/structure findings, not an assertion that every record has complete backend provenance.

## Required-observation classifications

| Required evidence | E1 | E2 | Reason / remaining action |
|---|---|---|---|
| Existing aggregate and historical verification receipts as descriptive context | REUSABLE | REUSABLE | Already published; cannot reconstruct individual matches |
| Candidate library and selected poison archive integrity | REUSABLE | REUSABLE | Hash inventories verified; frozen protocol/candidate/selection linkage must still accompany normalized export |
| M1/M2 query-level selected union corpora and final QA | MISSING | MISSING if used | New selection/corpus identities must first be determined; identical selections may later qualify |
| M3 source-only screening feedback | UNVERIFIED | UNVERIFIED if shared | Present privately; must check source-only provenance, candidate-band corpus, complete screens and selection parity for new cohort |
| Historical Dense/Reranker/RCD final QA | UNVERIFIED | UNVERIFIED | Present for historical selected corpora; need exact new-plan input/backend comparison |
| Fixed rewrite D2 final retrieval/QA | MISSING | MISSING | Not an arm in historical transfer design |
| Same question with different poison, corpus, evidence, prompt or backend | INCOMPATIBLE | INCOMPATIBLE | Never eligible by ID or aggregate match alone |
| Frozen RCD algorithm/configuration as specification | REUSABLE | REUSABLE | Preserve parameters; specification reuse is not response reuse |
| Existing Week9 matched Dense/RCD QA | UNVERIFIED | UNVERIFIED | Different attack-construction/selection histories; no automatic join |
| Historical latency as matched fresh-arm timing | UNVERIFIED | UNVERIFIED | Hardware/cache/runtime parity not established |
| Final proposed cohort, exposure ledger and complete desired-input plan | MISSING | MISSING | Blocks exact cost and call intersection |

Historical transfer has 300 fixed questions and known prior examination. A proposed 100–150 subset is not an untouched cohort. The published 20,500 paired comparisons and 21,175 actual backend calls refer to the historical design, not E1/E2 reusable calls. Interrupted seed-42 provenance remains indeterminate; replacement receipts must remain distinct. Cross-dataset NQ/2Wiki results and negative findings remain intact and cannot fill HotpotQA query-level gaps.

## Reuse audit contract and use

`scripts/audit_e1_e2_reuse.py inventory ROOT MANIFEST --sha256 PIN` verifies exact stage membership and file hashes without modifying files or exposing names. A trusted, separately recorded manifest pin is required; hashing a manifest at invocation only establishes internal consistency.

`compare PRIVATE_PLAN PRIVATE_HISTORY --history-sha256 REVIEWED_EXPORT_PIN` emits aggregate classifications and deduplicated physical-call counts only. Both inputs are JSON arrays with unique observation_id join keys. It is an explicit normalized-export interface, not an automatic native-run adapter. Prepare/review that private export against immutable native inventories before using its claims. A pin authenticates the reviewed export's bytes, not the truth of an arbitrary provenance label.

Every required and historical row must contain the exact `FIELDS` contract: query ID and query digest; target assignment and candidate/poison identity; full poisoned corpus hash; retrieval configuration and ordered evidence (IDs, text, order and scores); complete application and effective backend prompts; model snapshot and tokenizer hashes; resolved generator configuration, backend/runtime environment and decoding settings; scoring/extraction binding. Use typed structured values for configurations and evidence. Resolve defaults, random state and chat templates explicitly. Clean controls use explicit clean identities. Missing metadata is UNVERIFIED, missing observation is MISSING, complete unequal bindings are INCOMPATIBLE. Only a fully equal row with a completed physical-call identity and preserved raw response is REUSABLE. Cached logical observations are not physical calls. Duplicate observation keys or one physical-call ID bound to conflicting inputs are rejected. The script does not infer missing settings or turn legacy hashes into verified full prompts.

`select` provides the small deterministic M1/M2/M3 reference rules and budget-parity checks used by focused synthetic tests. Its caller must enforce the source-only data-access barrier; passing target-derived booleans would violate the protocol even if their shape passes validation. No selection helper can establish provenance from booleans alone.

The current audit is deliberately conservative about matching retrieval config and scoring as well as actual generator inputs. A future reviewed adapter may distinguish input identity from analysis strata, but must preserve exact physical-call provenance and never infer independence from duplicate measurements.

## Work remaining before protocol freeze

Review candidate-library linkage and all source screens; identify approved development/study IDs and exposure; derive M1/M2/M3 selections and full union-corpus hashes; prepare a reviewed private normalized export; verify snapshot/tokenizer/runtime/decoding custody; perform retrieval-only work for changed corpora and D2; build complete desired generator inputs; run exact comparison and reconcile physical journals including retries/interruption. Then replace UNKNOWN budget entries with deduplicated input/call intersections. None of these steps authorizes inference.

Scientific risks are selection leakage from final targets, unequal candidate opportunities, pool-versus-final-corpus source success, changed union corpora, model/backend drift, incomplete physical-call custody, pseudo-replication across seeds and duplicate roles, and exposed-cohort overclaiming. The drafts specify controls and preserve construction failures and undefined conditional-transfer denominators.

## Validation

114 focused synthetic/existing tests passed: E1/E2 reuse; November 9 research gates; source-selection workflow; matched Week9 evaluation; QA measurement records; retrieval variants; frozen RCD. Python compilation and `git diff --check` passed. Tests exercise all exact-binding fields, missing records, prompt/poison mismatch, deterministic selection, fixed candidate budgets, incomplete/target-shaped feedback rejection, physical-call deduplication/conflicts, inventory tampering and pinned-export rejection. Synthetic passing tests are not evidence of real E1/E2 response eligibility.
