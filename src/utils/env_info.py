"""Capture environment metadata for reproducibility (review issue #8).

Per the reproducibility rules: every experimental log should record
git_commit_sha, python_version, torch_version, transformers_version,
sentence_transformers_version, dataset info, model identifier, and
device -- specifically so a broken-environment regression (like the
retriever-routing bug, issue #1) would show up immediately as a
mismatch against a previous run's recorded environment, rather than
silently producing different numbers under the same experiment ID.

Every field here is best-effort: a library not being installed (e.g.
sentence_transformers isn't needed for a BM25-only run) should not
crash the experiment. Missing/unavailable info is recorded as None,
not omitted -- an explicit None in the log is still useful signal
("this run didn't have X installed"), whereas a silently-missing key
looks identical to "we forgot to check."
"""
import platform
import subprocess


def _try_import_version(module_name: str) -> str | None:
    """Best-effort __version__ lookup. None (not a crash, not a
    missing key) if the package isn't installed -- this is expected
    for backends/retrievers a given run doesn't use (e.g. a BM25-only
    run never imports sentence_transformers)."""
    try:
        import importlib
        module = importlib.import_module(module_name)
        return getattr(module, "__version__", "unknown_version")
    except ImportError:
        return None


def _git_commit_sha() -> str | None:
    """Current commit hash, so a raw result log can always be traced
    back to the exact code that produced it (Section 4/17's
    reproducibility requirement). None if not in a git repo, or git
    itself isn't available -- shouldn't crash the experiment either
    way, but SHOULD be visible as missing rather than silently absent.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _detect_device() -> str:
    """Best real device the current run would actually use, not just
    'is a GPU present' -- e.g. reports 'mps' correctly on Apple
    Silicon rather than falling through to 'cpu'."""
    torch_version = _try_import_version("torch")
    if torch_version is None:
        return "cpu (torch not installed)"
    import torch
    if torch.cuda.is_available():
        return f"cuda ({torch.cuda.get_device_name(0)})"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def capture_environment_metadata(config: dict) -> dict:
    """One dict, safe to attach to every logged record. Config-derived
    fields (model identifiers) come straight from the experiment
    config rather than being re-derived, since the config IS the
    source of truth for what was requested -- this only adds what the
    config can't know about itself (actual installed versions, actual
    hardware, actual code state).
    """
    return {
        "git_commit_sha": _git_commit_sha(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": _try_import_version("torch"),
        "transformers_version": _try_import_version("transformers"),
        "sentence_transformers_version": _try_import_version("sentence_transformers"),
        "datasets_version": _try_import_version("datasets"),
        "device": _detect_device(),
        "retriever_kind": config.get("retriever", "bm25"),
        "embedder_model": config.get("embedder_model"),
        "reranker_model": config.get("reranker_model"),
        "generator_backend": config.get("generator_backend"),
        "generator_model": config.get("generator_model"),
        "dataset_loader": config.get("dataset_loader"),
        "dataset_split": config.get("dataset_split"),
    }
