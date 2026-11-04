# 2Wiki candidate-specific review and semantic development gates

**Scope:** three post-hoc, TRAIN-only targets from the frozen first-six dossier packet.
**Scientific status:** this code produces no independent factual approval and never
authorizes poison injection into the 300 held-out queries. Original failed reviewer
captures and their audit remain immutable.

## Files and status

- `scripts/twowiki_three_case_candidate_gate.py` freezes a *new*, candidate-
  specific Qwen/Phi prompt packet (cases 1, 4 and 5 from the first six), records
  raw local model output with intent/provenance/response SHA-256, and audits
  validity. No completed or indeterminate model call is retried.
- `scripts/run_twowiki_three_target_stage12_mac.sh` runs 3 Qwen + 3 Phi
  candidate-review calls in separate model processes, audits them, then tries
  up to 2 semantic-generation calls for the birth-date target (case 5).
- `tests/test_twowiki_three_case_candidate_gate.py` has five mock-only tests.
- Previous six-case review responses: 12 captured, six pairs invalid, **zero**
  independent factual approvals. Do not change or relabel the old records.
- The preceding 3-case *lexical* experiment showed targeted ASR 2/3 in both
  Dense and RCD, but only one clean-to-wrong flip; it is post-hoc,
  source-screened, and non-confirmatory.

## Run stages 1 and 2 on the Apple Silicon Mac

```bash
BASE="$HOME/Documents/rag-2wiki-mlx-review-execution"
WT="$HOME/Documents/rag-2wiki-candidate-gates"
BRANCH="research/2wiki-three-target-review-semantic-gates-20261103"
git -C "$BASE" fetch origin "$BRANCH"
git -C "$BASE" worktree add --detach "$WT" "origin/$BRANCH"
cd "$WT"
"$HOME/Downloads/rag-poison-transfer/.venv/bin/python" -B -m pytest -q tests/test_twowiki_three_case_candidate_gate.py
bash scripts/run_twowiki_three_target_stage12_mac.sh
```

The runner uses its **fixed** output namespace:
`~/Documents/rag-research-results/twowiki-three-candidate-gate-20261104-v1`.
Do not rerun it if that directory already exists: that is evidence of a
completed or interrupted run. Manually inspect the immutable checkpoints.
For an explicitly new preregistered run use `RAG_REVIEW_RUN_ID` only after
documenting why a separate experiment is justified.

The two actual model snapshots must be the separately installed pinned
Qwen2.5-7B-Instruct-4bit and Phi-4-mini-instruct-4bit. No downloads,
substituted identities, mock inference or unreviewed model changes.

**Expected calls:** 6 review calls; semantic uses 1–2 calls, with up to
2 validation attempts. Held-out access and held-out QA calls: **zero**.

The semantic stage defaults to `heldout-compatible-legacy`, because the
existing 300-query held-out matrix uses the legacy semantic prompt and
validator. The separately available `development-v2` profile is
TRAIN-only and its success **cannot** be substituted for held-out readiness.
The legacy validator checks syntax heuristically, not semantic entailment.
The birth-date false target is "1 June 1947"; source evidence says
James Gray was born April 14, 1969. The other two candidate targets
(negative yes/no and comparative film) do not have supported direct-
relation grammars in the train-only development-v2 validator.

## How to interpret outputs

Candidate-specific AI agreement is labeled
`concordant_provisional_ai_only` and **is not factual approval**.
Markdown-fenced JSON, string-valued booleans, absent exact quotations,
contradictory flags, model/provenance collisions and unsupported
answers remain invalid. Rejected or uncertain targets remain rejected
or uncertain; do not coerce them into approval.

The semantic result `heuristically_supported_unverified` requires an
independent human examination of the exact generated sentence to check that
it asserts the asked relation, is actually false, and does not merely
mention the candidate. An unsuccessful generation is a valid development
finding, not permission to increase the budget or change a frozen result.

## Stage 3: precise 12-cell held-out plan, NOT started

**Required scientific gate before expensive inference:** inspect the
new audit and semantic record; adjudicate substantive target truth/typing
independently, without recycling previous invalid AI reviews. If those
reviews are inconclusive, report the limitation. This three-query gate
does not certify all 300 held-out target labels. The existing held-out
protocol explicitly describes label-conditioned alternatives as
**not independently established factual falsehoods**; any run using
that method must be named and interpreted accordingly.

The predeclared matrix is 2 families
(`lexical_influential_token`, `semantic_fluent_false_evidence`)
× intensities (1, 3) × seeds (42, 43, 44) = **12 cells**, with 300
frozen 2Wiki dev-split held-out questions per cell. Do not substitute
HotpotQA defaults, train questions or the development-only v2 semantic
profile. Historical nonoverlap is not fully certified.

**Once the scientific gate is met, use the existing audited runner:**

1. Locate the original **v1 held-out** parent protocol created before the
   local development recovery. Verify its pinned SHA-256 rather than
   inventing a filename. Use the original frozen v1 replication spec
   `twowiki-v2-development-recovery-20261103/replication_inputs.json`
   and `scripts/materialize_2wiki_execution_inputs.py --scope heldout`
   to generate a new **v2 held-out** local replication snapshot, using
   the cached, pinned embedder and reranker. This is data I/O only.
2. Run `scripts/run_week9_protocol_poison_matrix.py preflight
   --scope heldout --replication-spec <new-heldout-v2-spec>
   --replication-spec-sha256 <trusted-sha>`. It performs metadata-only
   readiness, not model calls.
3. Freeze in a fresh output namespace via
   `freeze-protocol --scope heldout --replication-spec
   <new-heldout-v2-spec> --replication-spec-sha256 <trusted-sha>
   --model-snapshot <pinned-qwen> --output <run-root>/protocol.json`.
   Capture `protocol_sha256`; inspect the frozen 12-cell binding,
   model/environment fingerprints and planned outputs.
4. Execute `construct --protocol <protocol> --protocol-sha256 <pin>
   --construction-dir <run-root>/execution/construction
   --model-snapshot <pinned-qwen> --max-batches 1` for the first
   checkpoint only. Exit code 75 is the **planned pause**, not a
   scientific failure. Inspect the journal and any unresolved intents.
   Resume the *same* frozen protocol and namespace without
   `--max-batches` only if no indeterminate call exists. Do not
   regenerate an unresolved call.
5. Only after all 12 construction cells have been sealed, externally
   record `construction.seal.json`'s SHA-256 and run `evaluate`
   with `--construction-seal-sha256`, the pinned protocol, snapshot
   and `<run-root>/execution/evaluation`. Record
   `evaluation.complete.json`'s SHA-256 before `aggregate`.
6. `aggregate` validates the complete matrix and produces paired
   query-cluster uncertainty. Distinguish construction failures,
   retrieval failures, answer susceptibility and pre-existing clean
   errors; never count a failed construction as a defense success.

**No new 12-cell inference has been initiated by this PR.** Qwen/MLX
model calls must run on the researcher's Mac, not inside GitHub or
this chat.