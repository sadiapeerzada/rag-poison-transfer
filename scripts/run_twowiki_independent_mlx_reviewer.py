#!/usr/bin/env python3
"""Execute *real* local MLX Reviewer A/B on the existing frozen 2Wiki prompts.

One independent model per reviewer slot; six train-dev cases, one model
call each. Never writes/rewrites source documents, prompts, attack files,
review decisions, or held-out data. Response bytes are stored exactly
as emitted. The companion review ledger, NOT this runner, determines
whether an answer is even well formed. Neither can approve poisoning.

Reviewer B must differ in both supplied model ID and *resolved model
snapshot directory* from the first recorded Reviewer A. Local reviewer
IDs are assigned by this actual runner, not claimed provider request IDs.
The model identities remain self-reported/local, not authenticated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_twowiki_two_ai_review_responses import bind_batch
from scripts.prepare_twowiki_generic_dev25_review_dossiers import sha

SCHEMA = "rag-poison-transfer.twowiki-independent-local-mlx-review-run/v1"
MAX_TOKENS = 1600


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_once(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False,
                  allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def repo_provenance() -> tuple[str, bool]:
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                       text=True, capture_output=True, check=True)
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                           text=True, capture_output=True, check=True)
    return r.stdout.strip(), bool(dirty.stdout.strip())


def check_review_model(model: Path, model_id: str) -> dict:
    resolved = model.expanduser().resolve()
    if (not resolved.is_dir() or not (resolved / "config.json").is_file()
        or not (resolved / "tokenizer_config.json").is_file()):
        raise ValueError("Local MLX model snapshot with config + tokenizer required")
    if not model_id.strip() or len(model_id) > 200:
        raise ValueError("Nonempty actual model identity required")
    config = (resolved / "config.json").read_bytes()
    if len(config) > 10_000_000:
        raise ValueError("Invalid oversized config")
    return {
        "model_id": model_id,
        "model_snapshot_path": str(resolved),
        "model_config_sha256": sha(config),
        "tokenizer_config_sha256": sha((resolved / "tokenizer_config.json").read_bytes()),
        "model_snapshot_revision_directory": resolved.name,
        "model_source": "operator_supplied_local_mlx_snapshot_unverified",
    }


def preflight(
    *, batch_dir: Path, dossiers_path: Path, responses_dir: Path,
    reviewer_slot: str, model_path: Path, model_id: str,
    case_index: int | None, max_tokens: int,
) -> tuple[dict, list[dict], dict, list[int]]:
    if reviewer_slot not in ("A", "B"):
        raise ValueError("Reviewer slot must be A or B")
    if type(max_tokens) is not int or max_tokens != MAX_TOKENS:
        raise ValueError("Output budget is fixed at 1600 tokens")
    manifest, cases = bind_batch(batch_dir, dossiers_path)
    if case_index is not None and (type(case_index) is not int or
                                   not 1 <= case_index <= len(cases)):
        raise ValueError("Invalid case_index")
    selected = [case_index] if case_index is not None else list(range(1, len(cases) + 1))
    model = check_review_model(model_path, model_id)
    out = responses_dir.expanduser().resolve()
    prompt_dir = batch_dir.expanduser().resolve()
    dossier_file = dossiers_path.expanduser().resolve()
    if (out == prompt_dir or prompt_dir in out.parents or out == dossier_file
        or ROOT.resolve() == out or ROOT.resolve() in out.parents):
        raise ValueError("Responses must be outside frozen prompt directory and repository")
    commit, dirty = repo_provenance()
    if dirty:
        raise ValueError("Unclean code worktree; do not run unverifiable reviewer")
    for i in selected:
        base = out / f"reviewer_{reviewer_slot}" / f"case_{i:02}"
        for suffix in (".intent.json", ".json", ".provenance.json", ".error.json"):
            if base.with_suffix(suffix).exists():
                raise FileExistsError("Prior case already attempted; no automatic retry: " +
                                      str(base) + suffix)
    if reviewer_slot == "B":
        # Enforce distinct model snapshots and distinct supplied IDs.
        # The first completed A response establishes the intended reviewer.
        first = out / "reviewer_A/case_01.provenance.json"
        if not first.is_file():
            raise ValueError("Reviewer A must complete case 1 before Reviewer B begins")
        a = json.loads(first.read_text(encoding="utf-8"))
        if (a.get("model_id") == model_id
            or a.get("model_snapshot_path") == model["model_snapshot_path"]):
            raise ValueError("Reviewer B must use a different local MLX model")
        for i in range(1, len(cases) + 1):
            existing = out / f"reviewer_A/case_{i:02}.provenance.json"
            if not existing.is_file():
                raise ValueError("Finish all six Reviewer A captures before B starts")
            ai = json.loads(existing.read_text(encoding="utf-8"))
            if (ai.get("model_id") != a.get("model_id")
                or ai.get("model_snapshot_path") != a.get("model_snapshot_path")):
                raise ValueError("Reviewer A was not consistent across the batch")
    return manifest, cases, model, selected


def perform(
    *, batch_dir: Path, dossiers_path: Path, responses_dir: Path,
    reviewer_slot: str, model_path: Path, model_id: str,
    case_index: int | None = None, max_tokens: int = MAX_TOKENS,
    preflight_only: bool = False,
    generator_factory=None,
) -> dict:
    manifest, cases, model, selected = preflight(
        batch_dir=batch_dir, dossiers_path=dossiers_path,
        responses_dir=responses_dir, reviewer_slot=reviewer_slot,
        model_path=model_path, model_id=model_id,
        case_index=case_index, max_tokens=max_tokens,
    )
    commit, _ = repo_provenance()
    info = {
        "schema": SCHEMA, "reviewer_slot": reviewer_slot,
        "model_id": model_id,
        "model_snapshot_path": model["model_snapshot_path"],
        "model_config_sha256": model["model_config_sha256"],
        "case_indices": selected,
        "model_calls": 0,
        "factual_approvals": 0, "injection_approvals": 0,
        "heldout_queries_accessed": 0,
        "reviewer_provenance_authenticated": False,
    }
    if preflight_only:
        return {**info, "status": "preflight_pass_no_model_calls"}
    if generator_factory is None:
        from src.pipelines.generator import MLXGenerator
        generator_factory = MLXGenerator
    generator = generator_factory(model["model_snapshot_path"])
    from src.utils.seeding import set_seed

    out = responses_dir.expanduser().resolve()
    for i in selected:
        c = cases[i - 1]
        prompt_path = batch_dir / f"reviewer_{reviewer_slot}" / f"case_{i:02}.txt"
        prompt_bytes = prompt_path.read_bytes()
        expected = manifest["records"][i - 1]["reviewer_prompt_sha256"][reviewer_slot]
        if sha(prompt_bytes) != expected:
            raise ValueError("Prompt bytes unexpectedly changed")
        key = f"case_{i:02}"
        base = out / f"reviewer_{reviewer_slot}" / key
        run_id = "local-mlx-" + str(uuid.uuid4())
        seed = int(sha((expected + model_id + reviewer_slot).encode())[:8], 16)
        started = stamp()
        write_json_once(base.with_suffix(".intent.json"), {
            "schema": SCHEMA, "query_id": c["query_id"],
            "reviewer_slot": reviewer_slot, "review_run_id": run_id,
            "status": "generation_issued_outcome_not_yet_recorded",
            "started_at": started, "prompt_sha256": expected,
            "model_id": model_id, "model_snapshot_path": model["model_snapshot_path"],
            "model_config_sha256": model["model_config_sha256"],
            "seed": seed, "max_tokens": max_tokens,
            "reviewer_provenance_authenticated": False,
        })
        set_seed(seed)
        generator.seed(seed)
        try:
            answer = generator.generate(prompt_bytes.decode("utf-8"),
                                        max_tokens=max_tokens)
            if not isinstance(answer.text, str):
                raise TypeError("Model returned non-text output")
            raw_bytes = answer.text.encode("utf-8")
            if not raw_bytes or len(raw_bytes) > 200_000:
                raise ValueError("Empty or oversized raw model response")
            completed = stamp()
            base.parent.mkdir(parents=True, exist_ok=True)
            # Exact raw generated bytes; do not strip/fix invalid JSON.
            with base.with_suffix(".json").open("xb") as f:
                f.write(raw_bytes)
                f.flush()
                os.fsync(f.fileno())
            write_json_once(base.with_suffix(".provenance.json"), {
                "schema": SCHEMA,
                "reviewer_slot": reviewer_slot, "query_id": c["query_id"],
                "model_id": model_id, "review_run_id": run_id,
                "model_snapshot_path": model["model_snapshot_path"],
                "model_config_sha256": model["model_config_sha256"],
                "tokenizer_config_sha256": model["tokenizer_config_sha256"],
                "reviewed_at": completed, "started_at": started,
                "prompt_sha256": expected, "raw_response_sha256": sha(raw_bytes),
                "seed": seed, "max_tokens": max_tokens,
                "prompt_tokens": answer.prompt_tokens,
                "completion_tokens": answer.completion_tokens,
                "latency_seconds": answer.latency_seconds,
                "backend_chat_template_applied": True,
                "recording_tool_git_sha": commit,
                "provider_request_id": None,
                "review_run_id_is_locally_generated_not_provider_authenticated": True,
                "reviewer_provenance_authenticated": False,
                "factual_approval": False, "injection_approved": False,
            })
        except Exception as exc:
            write_json_once(base.with_suffix(".error.json"), {
                "status": "call_failed_or_indeterminate",
                "review_run_id": run_id, "reviewer_slot": reviewer_slot,
                "error_type": type(exc).__name__, "error": str(exc),
                "original_intent_must_be_adjudicated_before_any_repeat": True,
            })
            raise
        info["model_calls"] += 1
        print(f"Reviewer {reviewer_slot} case {i}: saved raw response "
              f"({len(raw_bytes)} UTF-8 bytes); review decision NOT validated",
              flush=True)
    return {**info, "status": "local_reviews_captured_unvalidated"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-dir", type=Path, required=True)
    p.add_argument("--dossiers-path", type=Path, required=True)
    p.add_argument("--responses-dir", type=Path, required=True)
    p.add_argument("--reviewer-slot", choices=("A", "B"), required=True)
    p.add_argument("--model-path", type=Path, required=True)
    p.add_argument("--model-id", required=True)
    p.add_argument("--case-index", type=int)
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args()
    result = perform(
        batch_dir=args.batch_dir, dossiers_path=args.dossiers_path,
        responses_dir=args.responses_dir, reviewer_slot=args.reviewer_slot,
        model_path=args.model_path, model_id=args.model_id,
        case_index=args.case_index, max_tokens=args.max_tokens,
        preflight_only=args.preflight,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
