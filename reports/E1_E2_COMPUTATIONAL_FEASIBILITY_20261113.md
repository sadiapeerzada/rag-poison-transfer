# E1/E2 computational feasibility — 13 November 2026

**Status: BLOCKED for execution.** The preparation package is reviewable, but
no protocol-compatible memory remedy has been demonstrated to work. No Qwen
initialization, model import, generation, retrieval experiment or authorization
reactivation occurred. Model/runner/guard code, resource limits, dependencies
and all frozen experiment artifacts remain unchanged.

The [resource receipt](E1_E2_RESOURCE_INSPECTION_20261113.json) records actual
no-model measurements and hashes of the installed sources inspected. All nine
snapshot files match the frozen Qwen revision
`c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`. Reading the safetensors header,
without creating arrays, gives 735 tensors and **4,284,263,424 payload bytes
(3.990 GiB)**. File offsets exactly span the weight payload. This is weight
storage, not the total runtime working-set requirement.

Three measurements ten seconds apart recorded pressure level 1, zero swap-ins
and swap-outs, and no reported thermal/performance warning. Free disk was
25.52 GiB. The final `memory_pressure` report gave 60%; an earlier immediate
read gave 71%. These are system-wide pressure statistics, **not** a claim that
60–71% of RAM is available for model allocations. The recorded
free+inactive+speculative page sum ranged 4.59–4.79 GiB; it includes potentially
reclaimable pages and is not guaranteed available RAM. Compressor usage was
4.18–4.29 GiB. Sampling followed file hashing and normal background activity;
it is not a controlled clean-boot baseline. The supplied earlier 6.53 GiB
reclaimable estimate is not a current or directly comparable safety clearance.

Background process RSS totals included Chrome about 2.61 GiB and VS Code about
2.89 GiB; shared pages mean those totals are not additive physical footprints.
Closing unused applications is a plausible avoidable-pressure remedy, but this
audit does not establish background usage as the principal causal source. No
applications were closed or processes killed. Normal idle pressure does not
prove a safe load, prefill or generation working set.

The previous exact guard receipt records pressure level 2 at 8.070255 seconds,
RSS 1.53 GiB and Metal active+cache allocation 3.993 GiB, unchanged swap-outs
and no thermal flag. The raw generation-intent count remains zero. Two prior
initialization sessions are reconciled, with 17.451683 seconds conservatively
charged including monitoring margins. The first older stop cannot be more
precisely attributed than its recorded pressure/thermal reason. The two monitor
receipts for the second stop describe one attempt, not two.

## Installed loading path

Source inspection used MLX 0.32.2 / mlx-lm 0.31.3, not an upgraded runtime.
The exact source byte hashes are in the resource receipt. Relevant locations:

| Source | Finding |
| --- | --- |
| `src/pipelines/generator.py:MLXGenerator.__init__` | Calls `mlx_lm.load()` once, default `lazy=False`; no second explicit model load or explicit weight copy is present. |
| Installed `mlx_lm/utils.py:load_model` | Reads safetensors arrays, builds Qwen modules, configures the existing native group-64 4-bit quantization, strictly assigns weights, then evaluates model parameters. This snapshot uses the native quantization branch, not the AWQ/GPTQ unpack/transpose conversion branch. |
| Installed Qwen/Linear/QuantizedLinear constructors | Create random initialization/quantization graphs before replacing parameters with checkpoint tensors. Strict weight checks inspect types/shapes; assignment replaces the model parameters before final evaluation. Static inspection does not show that a full unquantized duplicate is materialized. Sampling at 0.5 seconds could miss transient peaks; no profiler run was authorized. |
| Installed Qwen `sanitize` and Module `load_weights` | Filter/reference dictionaries and lists, not explicit deep copies of every tensor. Their metadata allocations cannot be assumed to explain a multi-GiB failure. |
| Installed `load(..., lazy=True)` | Supported by this exact version; skips the final eager `mx.eval(model.parameters())`. It still builds/quantizes modules and the first evaluation must materialize required weights. Merely returning from a lazy load is not proof of a safe initialized model. No lazy-load change or test was made. |
| `run_bounded_e1_e2_qwen.py` | Starts the guard before constructing the generator, sets cache limit 0 and allocation limit 10 GiB first, and runs without retriever/model preparation in the inference process. Removing cache or lowering the allocation cap again is not an unimplemented remedy. |
| Installed `mlx_lm/generate.py:wired_limit` | On Metal, stock generation calls `mx.set_wired_limit(max_recommended_working_set_size)` and restores the prior limit afterward. This is downstream of the initialization failure. No wired-limit setter was called here; the stock behavior must receive explicit review before any execution under the supervisor's wired-limit restriction. |

The [MLX lazy-evaluation documentation](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html)
explains deferred computation and assignment before materialization. Its current
web version is 0.32.4; installed-source inspection above governs the pinned
0.32.2 runtime. It does not prove a saving for this checkpoint. Likewise,
[the wired-limit reference](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_wired_limit.html)
describes a runtime control, not permission to change it or operating-system
wiring limits. No current-main loader features were assumed to exist locally.

The tensor payload is within roughly 3.1 MiB of the recorded Metal allocation
at the stop. That supports the interpretation that pressure arose around
ordinary weight residency; it does not establish absence of a brief temporary
allocation. RSS and Metal counters can overlap in unified memory and must not
be summed as independent physical RAM. KV cache, prompt prefill, activations,
tokenizer/runtime and OS headroom still need room after successful weight load.

## Compatible proposals, not implemented authorizations

1. Prefer a fresh, inference-only process after voluntarily closing unused apps
   and ending separate retrieval processes. Retain all guards and frozen model
   settings. Stage inputs/results on disk; never retain live retrieval models
   beside Qwen. Releasing unused parsed history objects may reduce Python
   overhead but has no measured multi-GiB saving here.
2. If that environment cannot provide safe headroom, provision an approved
   Apple Silicon machine with more unified RAM and the same pinned model,
   tokenizer, runtime and generator bindings. Verify portability/provenance and
   historical-reuse compatibility before execution. A different backend or
   quantization is not an equivalent silent substitute.
3. A reviewed lazy-loading experiment is only a candidate operational change,
   not a demonstrated cure. It would require an explicitly approved code/input
   compatibility review and monitored first materialization, not a declaration
   of success immediately after lazy construction. It is not implemented.
   Changing the loader path may change a frozen implementation binding; exact
   historical reuse must be revalidated rather than assumed from equal weights.

Do not raise MLX allocation/cache/wired limits, alter OS wiring, relax pressure
checks, change output tokens/quantization, upgrade packages or adopt a new
backend. None was changed. Without a newly approved safe environment and a
controlled initialization/materialization test, this Mac remains unproved for
the frozen model. This preparation task ends before that test or any inference.
