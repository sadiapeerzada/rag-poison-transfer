# E5 published-baseline feasibility — 13 November 2026

**Decision:** PoisonedRAG's black-box variant is a suitable published threat-model
reference. A new comparison is **not justified for execution yet**: paper/code
construction differs, experimental parity is unresolved, and the current operator
instruction prohibits Qwen inference. No baseline, model initialization, API call,
candidate generation or victim evaluation was executed. This is completed
source-inspection feasibility analysis, not an experimental result. Only this
one published baseline is assessed; no RCD redesign or extra experiment is added.

The [USENIX Security 2025 paper](https://www.usenix.org/system/files/usenixsecurity25-zou-poisonedrag.pdf)
studies attacker-chosen questions/answers and insertion of malicious knowledge
into a retrieval corpus. Its black-box attack needs no retriever query or weights:
the question is prepended to generated supporting text. Construction independently
generates each passage and tests it with the attacker-chosen LLM, retrying until
the target answer appears or the trial limit is exhausted. The last trial is
retained even after failure. Default settings are five passages per question,
50 trials per passage, a requested 30-word support text and GPT-4 temperature 1.
These are construction settings, distinct from victim generation settings.
This makes corpus-insertion targeted QA a relevant comparison, but not proof of
equivalent strength or a transferable published success rate on our Qwen/RCD.

The author's [publication page](https://jinyuan-jia.github.io/publications/)
links the [official repository](https://github.com/sleeepeer/PoisonedRAG).
Inspection is pinned to commit
`f660d72174f06b13fae5163ce656e7b235db858f` (27 January 2026), rather than a fork
or floating default branch. [The source receipt](E5_POISONEDRAG_SOURCE_INSPECTION_20261113.json)
records immutable Git blob identities for eight inspected implementation/config
files and the public HotpotQA poison artifact. All nine downloaded contents
reproduce their Git blob identities; SHA-256 byte digests are also recorded.
No upstream code was imported or executed in this repository.

| Inspected implementation | Finding and consequence |
| --- | --- |
| [gen_adv.py](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/gen_adv.py) | Defaults to 100 randomly sampled questions. Makes two answer-generation queries per question, skips if the two outputs fail a substring consistency check, then sends one JSON request to GPT-4-1106-preview for a wrong answer and all five ~100-word passages. The declared prompt-index option is not used by this path. No 50-trial passage validation loop is implemented here. |
| [src/attack.py](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/src/attack.py) | The black-box LM_targeted path reads saved passages, takes the first five, and prepends the question. It does not generate/select candidates against target defenses. The white-box optimizer exists but is outside this feasibility choice. |
| [main.py](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/main.py) | CUDA-only device selection; merges original top-k retrieval scores with the union of passages from each batch, sorts, and queries the victim. Default ten batches of ten questions are disjoint slices, not ten independent seed replications. Saves after each batch, without our physical-call intent/provenance journal. |
| [run.py](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/run.py) | Launches background jobs across three datasets on the same GPU. Running this wrapper would violate the requested scope and one-inference-process constraint. Do not run it. |
| [GPT wrapper](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/src/models/GPT.py), [config](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/model_configs/gpt4_config.json) | Configured answer model is GPT-4-0613, temperature 0.1, 150 output tokens. Seed is listed in config but not passed in the request. Wrapper converts exceptions to empty strings. Such failures cannot be silently scored as authentic answered observations. Actual endpoint availability was not tested. |
| [prompts](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/src/prompts.py), [utils](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/src/utils.py) | Upstream prompt and substring ASR differ from our frozen chat template/extractor/exact-match metrics. Retriever loading uses model names without immutable snapshot revisions. Generation sampling does not call the provided seed-setup helper. Released scripts/config do not specify the fully pinned environment and per-call provenance needed for exact replay. |

The published [HotpotQA JSON](https://github.com/sleeepeer/PoisonedRAG/blob/f660d72174f06b13fae5163ce656e7b235db858f/results/adv_targeted_results/hotpotqa.json)
was actually inspected: 100 records, five passages each. A local read-only join
against the preserved 300-question native cohort finds six shared question IDs,
all six with identical question text and gold-label strings. This is a narrow
artifact-overlap finding, not compatible target assignment, full-cohort coverage,
verified factuality or reusable backend-response provenance. The native corpus,
poison union, target assignments, evidence order, prompts and backend bindings
have not been matched to this artifact. No Qwen-call savings are claimed.

Two construction budgets must not be conflated. From the inspected released
generator, for **Q sampled questions** and **S questions passing its consistency
check**, the visible nominal request count is **2Q + S** (one JSON call returns
all five passages). At defaults Q=100 this is 200–300 application-level requests,
not an observed bill or physical-call upper bound. JSON/HTTP failure can abort;
SDK-internal retries, failed requests, tokens and rejected questions need real
accounting. The parser expects a specific JSON key despite a natural-language
request that does not robustly enforce that schema. There is no per-observation
resume journal in this generator.

For a **paper-faithful** implementation, I infer at most **2QNL = 500Q**
construction requests at defaults, assuming one generation and one validation
request per trial, before retries or victim evaluation. This is arithmetic,
not measured cost or Qwen authorization. The released one-shot JSON procedure
does not reproduce that trial budget. Choose explicitly which version a future
comparison would implement.

Victim work would separately depend on the chosen cohort, poison union per
batch, defenses and paired clean conditions. The inspected main path nominally
queries each of its 100 selected questions once per invocation; ten batches
do not mean 1,000 independent victim observations. It provides no matched
four-defense utility/statistical comparison for our setup. A new Qwen budget
is **UNKNOWN** until a concrete matched input plan and exact historical reuse
audit exist. No inference budget is authorized by this feasibility report.

Before deciding an experiment is justified, resolve these concrete blockers:

1. Choose and document paper-faithful versus released-code reproduction and pin
   all dependencies, model snapshots, prompts, generation/validation settings,
   failure handling and actual physical-call accounting. Do not install the
   README's CUDA/PyTorch stack into the frozen Mac environment.
2. Establish question/target/corpus parity and the allowed inserted-document
   budget. Published five-document insertion and top-5 context differ from our
   intensity 1/3 and top-3 generator context. Keeping our frozen victim settings
   would be an explicitly adapted comparison, not the published configuration;
   changing those settings is not currently authorized.
3. Preserve the revised plan's source-only selection barrier. Freeze poison sets
   before Dense/Reranker/RCD target evaluation; do not use RCD outcomes for
   candidate choice, retries, target selection or tuning. Handle the batch poison
   union consistently because cross-question contamination changes retrieval.
4. Require factuality/alias checks on target propositions, paired clean/poison
   utility, generator-depth exposure and both denominators for construction
   failures. Record upstream substring results separately if needed; never
   substitute them for frozen answer extraction and exact-match scoring.
5. Verify safe compute and fresh execution authorization before any generation.
   Current no-inference instructions and the Mac initialization pressure stop
   block a local Qwen comparison. No API spending or alternative model service
   was tested or approved through this analysis.

The feasible immediate deliverable is this pinned implementation/budget audit.
A future experiment may be defensible once parity, reconstruction and safe
execution are resolved, but executing now would produce an underspecified
comparison. Preserve this negative feasibility finding rather than reporting
the paper's published attack success as our own evidence.
