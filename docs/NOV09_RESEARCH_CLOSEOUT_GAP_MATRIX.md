# Research closeout matrix — 9 November 2026

**Project:** Cross-Pipeline Transferability of Knowledge Poisoning in Adaptive RAG  
**Evidence standard:** completed original frozen experiments are not rerun, changed, or silently treated as results of later exploratory development. No new model call or scientific verdict is claimed by this document.

## Already completed and verified

| Evidence milestone | Verified meaning |
| --- | --- |
| HotpotQA matched Dense–RCD frozen run | Original held-out matrix reported and audited; repeated seeds are not independent queries |
| HotpotQA source-crafted transfer | 240 source×target×family×intensity×seed cells; the operator-reported offline raw-file and public-aggregate audit **passed**; optional original candidate library separately unverified |
| 2Wiki 300-query Dense–RCD | Frozen historically risk-disclosed 12-cell run complete; full tar restoration verified by operator across 37,534 files, but not certified remote/off-device independence |
| 2Wiki 131-case quality audit | AI-assisted, post-hoc, 102 distinct questions, **not independent source-verified factual truth**; context for 24 failed-construction cases remains incomplete in sample packet |
| Phi-4 Mini second generator | Pinned non-Qwen Phi model replay 160 real generation calls across 16 groups complete; original Qwen outputs were subsequently compared against those same 160 prompts and the operator reported **PASS_MATCHED_QWEN_PHI_OFFLINE_COMPARISON** |
| Semantic development method check | 25 development queries at intensities 1 and 3 were inspected; only 2 valid of 25 at each intensity in that separate quality-diagnostic run. No retrospective promotion of development validator to held-out protocol |

## Requirements not yet supported by completed evidence

| Gap from original research plan | Minimum defensible next artifact | Need actual new inference? | Scientifically correct paper status |
| --- | --- | --- | --- |
| **RCD end-to-end component ablations** | Separately frozen matched full vs no-rewrite, no-agreement-feature, no-conflict, and generator top-k 1/3/5; report clean EM/F1, exposure, conditional/end-to-end ASR, latency, retrieval calls and paired question-cluster uncertainty | **Yes** for any alternate end-to-end QA; no-rewrite/top-k also need retrieval | **PENDING** |
| **Qwen vs Phi effect and uncertainty** | Report from `scripts/compare_qwen_phi_replay_offline.py` with matched per-condition counts and discordance, correct repeated-query denominator; compare output caps and model/backend differences | **No** for existing cap-mismatched replay comparison | **Comparison PASS**; do not claim model-family causal generalization |
| **64-token vs 128-token model cap** | Report as explicit confound or run new **separately versioned Phi@64** on same private 160-prompt plan, with fresh output directory and model hashes | **Yes** for matched-cap Phi@64 | **DISCLOSED CONFOUND** until actually run |
| **Semantic factuality and false evidence** | Preserve source-cited ledger for accepted semantic statements, gold/alias ambiguity, answer type and false-target checks; account for 24 context-limited cases | No *model inference* required for source/manual research, but credible evidence retrieval and adjudication are real work | **AI-ASSISTED / UNADJUDICATED**, never independently human verified |
| **Natural Questions + iterative/adaptive retrieval** | Separate frozen one-hop dataset protocol and an actually iterative retrieval policy with logged decisions | **Yes** | **NOT IN THE COMPLETED TWO-DATASET CORE** |
| **Intensity 5, unseen family, low corpus poison rate** | Predeclared stress-test cells with disjoint development tuning and held-out test, construction-feasibility logs and fixed corpus denominators | **Yes** | **NOT RUN**; do not interpolate intensity 5 from intensities 1/3 |
| **Poison-detection AUROC/F1** | Define **document-level ground truth** by injected poison IDs and a true **document-level suspicion score**, handle skew and repeated docs, predeclare decision threshold on development only, report AUROC/AUPRC/F1/FPR at evaluation population level | Could compute offline if authentic per-document scores/labels exist; fresh retrieval otherwise | **NOT VERIFIED**; a final rank score is not automatically a calibrated poison detector |

The original plan explicitly recommends **three datasets** (Natural Questions, HotpotQA, 2Wiki), genuinely adaptive/iterative retrieval, a second generator family, ablations and ASR–utility–latency Pareto plots. A narrower **two-multi-hop-dataset result with source-crafted transfer and negative defense findings** is a scientifically possible scope choice, but not the full original three-dataset prescription. The research has **no obligation to produce favorable RCD outcomes**; known disadvantages, including 2Wiki lexical I1, belong in the main results.

## Next experiments: rigorous constraints

**Do not change original outcomes.** Freeze a new `rcd-component-ablations/v1` protocol in a new private output tree with source code revision, exact original 2Wiki or separate development corpus/poison hashes, original query IDs and selection seed, tokenizer/generator identity and cap, batch size, all score weights and variants. An operator must explicitly authorize MLX compute. The study is exploratory if the held-out outcomes have already been inspected; report that status.

For score-only variants based on existing `last_diagnostics`, the absence of original per-document diagnostics means **no valid retrospective score ablation**. Do not regenerate a missing diagnostic and describe it as frozen. Instead run a newly versioned retrieval-only sensitivity or a genuine new end-to-end experiment.

**Do not claim independent human review.** The user's decision not to use human reviewers is respected; the failure analysis remains AI-assisted and non-adjudicated, and all factuality conclusions must be conditioned on actual verifiable evidence. The historical source/custody exposure limits of the risk-disclosed 2Wiki cohort also remain.

## Mac handoff: exact matched model report

```bash
cd "$HOME/Downloads/rag-poison-transfer"
git pull --ff-only origin main
python -m pytest -q tests/test_matched_qwen_phi_replay.py tests/test_nov09_research_gates.py

export TWOWIKI_EVAL_DIR="$HOME/Downloads/2wiki-restored-20261109/execution/evaluation"
export MODEL_PLAN="$HOME/Documents/rag-research-results/nov09-research-gates/2wiki-second-model-plan-20261108T204440Z_PRIVATE.json"
export MODEL_PLAN_SHA="9c47a64053c2d53bb016a2bad10503d906a9026e0b7092d55ddb0505bd3b199a"
bash scripts/nov09_mac_research.sh model-compare
```

After merging the test fix, the command prints only the verified aggregate outcome counts for the 16 groups and writes a fresh private report; it does not load either model or inspect an external website. Report the Qwen-versus-Phi matched target differences and the 64/128 cap difference **before** interpreting apparent generalization. Keep raw model responses, prompts, question IDs and reviewer triage files outside public GitHub.

## Publication gating

A defensible minimum paper can present the completed HotpotQA transfer and 2Wiki matched vulnerability experiment, construction feasibility and negative RCD results with limitations. To claim a **new ablation-demonstrated defense mechanism**, actual separate experiments must be completed. To claim an **adaptive/iterative single-hop + multi-hop stress benchmark**, run NQ and actual iterative controllers. To claim **poison detection quality**, create a valid detector score/label dataset and evaluate it, not just mention the RCD scoring formula.

**No experiment result is fabricated or promoted by this planning document.**
