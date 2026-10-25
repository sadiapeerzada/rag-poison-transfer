#!/usr/bin/env python3
"""Two-case DEVELOPMENT diagnostic; no final held-out execution capability.

Default/preflight performs no dataset materialization or model construction.
Execution requires a genuinely reviewed, externally pinned development artifact.
No approval, reviewer identity, timestamp or signature is generated here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run import build_generator, load_dataset
from scripts.audit_phase4d_development_coverage import DEFAULT_ARTIFACT, DEFAULT_MANIFEST, PINNED_ARTIFACT_SHA256
from scripts.extract_verified_development_queries import extract_verified
from scripts.run_week9_multiseed_matched_evaluation import validate_frozen_inputs
from scripts.run_week9_matched_poison_comparison import (
    DEFAULT_DENSE_CONFIG, DEFAULT_RCD_CONFIG, build_matched_retrievers, evaluate_pipeline,
    flatten_query_result_records, summarize_pipeline, paired_differences, validated_top_k,
)
from scripts.run_week9_heldout_poison_matrix import (
    _require_clean_relevant_inputs, compute_source_fingerprint, git_commit_sha,
)
from src.attacks.checkpoint import PoisonCheckpoint
from src.attacks.compatible_targets import (
    PROTOCOL_VERSION, assignment_fingerprint, select_reviewed_target,
)
from src.attacks.development_review_package import answer_shape
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.attacks.reviewed_target_artifact import read_pinned, _normalized
from src.attacks.semantic_fluent import (
    SemanticFluentFalseEvidenceAttack, SemanticQualityError, SEMANTIC_PROMPT_VERSION, SEMANTIC_VALIDATION_VERSION, SEMANTIC_RETRY_POLICY,
    has_affirmative_target_relation,
)
from src.attacks.target_candidates import expected_category
from src.evaluation.qa_records import capture_generation, MEASUREMENT_SCHEMA, EXTRACTOR_VERSION
from src.experiments.protocol import corpus_fingerprint, poison_instances_fingerprint, query_set_fingerprint
from src.pipelines.generator import MLXGenerator
from src.utils.seeding import set_seed

SCHEMA = "rag-poison-transfer.week9-development-smoke/v1"
TARGET_SCHEMA = "rag-poison-transfer.development-smoke-targets/v1"
DIAGNOSTIC_VALIDATION_VERSION = "development-direct-affirmation/v2"
# Fixed before model output: named-person and year-answer diagnostics from dev.
DEVELOPMENT_QUERY_IDS = ("5ae2c416554299492dc91c67", "5ae143ed55429920d5234360")
FAMILIES = ("lexical_influential_token", "semantic_fluent_false_evidence")


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def _verified_development():
    dense, rcd, heldout_ids, _, hashes = validate_frozen_inputs(
        heldout_path=DEFAULT_MANIFEST, dense_config_path=DEFAULT_DENSE_CONFIG, rcd_config_path=DEFAULT_RCD_CONFIG,
    )
    if sha(DEFAULT_ARTIFACT) != PINNED_ARTIFACT_SHA256:
        raise ValueError("Original development artifact fingerprint mismatch")
    _, provenance = extract_verified(DEFAULT_ARTIFACT, DEFAULT_MANIFEST)
    records = {row["query_id"]: row for row in (json.loads(line) for line in DEFAULT_ARTIFACT.read_text().splitlines())}
    if len(DEVELOPMENT_QUERY_IDS) != 2 or len(set(DEVELOPMENT_QUERY_IDS)) != 2 or set(DEVELOPMENT_QUERY_IDS) & set(heldout_ids):
        raise ValueError("Diagnostic IDs must be two unique development-only IDs disjoint from held-out")
    if any(qid not in records for qid in DEVELOPMENT_QUERY_IDS):
        raise ValueError("Predeclared diagnostic ID missing from verified development")
    queries = [{key: records[qid][key] for key in ("query_id", "question", "gold_answer", "gold_doc_ids")}
               for qid in DEVELOPMENT_QUERY_IDS]
    return queries, provenance, dense, rcd, hashes


def _review_annotations(row, query):
    # Detect obvious unfinished handoff text, never infer identity or truth.
    def placeholder(value):
        text = value.strip().casefold()
        return (text in {"pending", "todo", "tbd", "placeholder", "unknown", "n/a", "reviewer", "nominator"}
                or text.startswith(("<", "replace ", "your ", "example "))
                or "example.com" in text or "example.org" in text)
    for field in ("reviewer", "nominator", "review_evidence", "target_answer"):
        if isinstance(row.get(field), str) and placeholder(row[field]):
            raise ValueError("Placeholder review field: " + field)
    if (row.get("question") != query["question"] or row.get("gold_answer") != query["gold_answer"] or
        row.get("gold_doc_ids") != query["gold_doc_ids"]):
        raise ValueError("Exact reviewed development question/gold binding required")
    if row.get("ambiguity_status") != "resolved" or row.get("evidence_status") != "independently_verified":
        raise ValueError("Ambiguous or unverified diagnostic target")
    aliases = row.get("gold_aliases")
    if (not isinstance(aliases, list) or not aliases or
        any(not isinstance(alias, str) or not alias.strip() for alias in aliases) or
        query["gold_answer"] not in aliases or row.get("alias_check_complete") is not True):
        raise ValueError("Complete genuine gold alias review required")
    if _normalized(row["target_answer"]) in {_normalized(x) for x in aliases}:
        raise ValueError("Alias-equivalent diagnostic target")
    category = expected_category(query["question"], query["gold_answer"])
    if (category == "unknown" or row.get("answer_category") != category or
        not answer_shape(category, row["target_answer"])):
        raise ValueError("Question-specific category/shape review mismatch")
    if (not isinstance(row.get("nominator"), str) or not row["nominator"].strip() or
        row["nominator"].strip().casefold() == row.get("reviewer", "").strip().casefold()):
        raise ValueError("Actual independent reviewer must differ from nominator")
    refs = row.get("evidence_references")
    if not isinstance(refs, list) or not refs or any(
        not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                          for k in ("reference", "claim", "limitations")) for item in refs):
        raise ValueError("Genuine evidence references, claims and limitations required")
    if any(placeholder(item[k]) for item in refs for k in ("reference", "claim", "limitations")):
        raise ValueError("Placeholder evidence reference, claim or limitations")


def load_development_targets(path, digest, queries):
    payload = read_pinned(path, digest)
    if (payload.get("schema") != TARGET_SCHEMA or payload.get("scope") != "development" or
        payload.get("status") != "reviewed_diagnostic_only" or payload.get("protocol_version") != PROTOCOL_VERSION):
        raise ValueError("A genuinely reviewed development-only diagnostic artifact is required")
    if (payload.get("development_artifact_sha256") != PINNED_ARTIFACT_SHA256 or
        payload.get("query_set_fingerprint") != query_set_fingerprint(queries)):
        raise ValueError("Development target provenance mismatch")
    rows = payload.get("assignments")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Expected exact two reviewed assignments")
    mapping = {row.get("query_id"): row for row in rows}
    if len(rows) != 2 or len(mapping) != 2 or set(mapping) != set(DEVELOPMENT_QUERY_IDS):
        raise ValueError("Missing, duplicate or non-predeclared diagnostic assignments")
    for query in queries:
        select_reviewed_target(query, mapping)  # Shared approval/hash/time validation.
        _review_annotations(mapping[query["query_id"]], query)
    return mapping


def preflight(targets=None, targets_sha256=None):
    queries, provenance, dense, rcd, hashes = _verified_development()
    if bool(targets) != bool(targets_sha256):
        missing = "--targets-sha256 (trusted hash is unset)" if targets else "--targets (reviewed file)"
        raise ValueError("Missing " + missing)
    mapping = load_development_targets(targets, targets_sha256, queries) if targets else None
    report = {"schema": SCHEMA, "scope": "development", "is_final_run": False,
              "query_ids": list(DEVELOPMENT_QUERY_IDS), "query_count": 2,
              "development_artifact_sha256": provenance["artifact_sha256"],
              "query_set_fingerprint": query_set_fingerprint(queries), "config_sha256": hashes,
              "target_artifact_sha256": targets_sha256,
              "target_assignment_fingerprint": assignment_fingerprint(mapping) if mapping is not None else None,
              "measurement_schema": MEASUREMENT_SCHEMA, "extractor_version": EXTRACTOR_VERSION,
              "seed": 42, "intensity": 1, "families": list(FAMILIES),
              "generator_model": rcd["generator_model"], "generator_backend": rcd["generator_backend"],
              "prompt_version": SEMANTIC_PROMPT_VERSION, "validation_version": SEMANTIC_VALIDATION_VERSION,
              "retry_policy": SEMANTIC_RETRY_POLICY, "diagnostic_validation_version": DIAGNOSTIC_VALIDATION_VERSION, "max_attempts": 2, "attack_max_tokens": 150,
              "mlx_available": importlib.util.find_spec("mlx") is not None,
              "mlx_lm_available": importlib.util.find_spec("mlx_lm") is not None,
              "review_input_validated": mapping is not None,
              "requires_human_semantic_output_review": True,
              "expected_qa_records": 16, "expected_semantic_documents": 2}
    return report, queries, mapping, dense, rcd


class _RecordingGenerator:
    """Append each actual model call before validation, including failed attempts."""
    def __init__(self, backend, path, model_provenance=None):
        self.backend, self.path, self.context = backend, path, {}
        self.model_provenance = copy.deepcopy(model_provenance) if model_provenance else {
            "generator_class": type(backend).__module__ + "." + type(backend).__name__}

    def set_observation_context(self, context):
        self.context = dict(context)

    def generate(self, prompt, max_tokens):
        started = time.perf_counter()
        try:
            result, record = capture_generation(self.backend, prompt, max_tokens)
            record.update(status="returned", context=self.context, max_tokens=max_tokens)
        except Exception as error:
            record = {"status": "generation_error", "context": self.context, "prompt": prompt,
                      "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "raw_response": None,
                      "elapsed_seconds": time.perf_counter() - started, "max_tokens": max_tokens,
                      "error_type": type(error).__name__, "error": str(error)}
            self._append(record)
            raise
        self._append(record)
        return result

    def _append(self, record):
        with self.path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
            output.flush()
            os.fsync(output.fileno())


class _DiagnosticSemanticAttack(SemanticFluentFalseEvidenceAttack):
    """Diagnostic direct-relation screen sharing the versioned syntax predicate.

    Explicit local relation is necessary, never sufficient for entailment.
    Mere target mention near the word 'answer' is not an affirmative assertion.
    """
    def _validate_text(self, text, query, target_answer):
        status = super()._validate_text(text, query, target_answer)
        if not has_affirmative_target_relation(text, target_answer):
            raise SemanticQualityError("Diagnostic text lacks a direct affirmative target relation")
        return status


class _ObservedAttack:
    def __init__(self, attack, recorder):
        self.attack, self.recorder = attack, recorder

    def __getattr__(self, name):
        return getattr(self.attack, name)

    def generate(self, query, all_queries, rng, poison_index, target_answer):
        self.recorder.set_observation_context({"stage": "poison_generation", "query_id": query["query_id"],
                                               "poison_index": poison_index, "target_answer": target_answer})
        return self.attack.generate(query, all_queries, rng, poison_index, target_answer)


def execute(*, targets, targets_sha256, output_dir, experiment_id, recover_from=None):
    plan, queries, mapping, dense, rcd = preflight(targets, targets_sha256)
    if mapping is None:
        raise ValueError("Genuine reviewed diagnostic assignments required")
    if not experiment_id or Path(experiment_id).name != experiment_id or experiment_id in {".", ".."}:
        raise ValueError("experiment_id must be filename-safe")
    root = output_dir.expanduser().resolve() / experiment_id
    if root == ROOT or ROOT in root.parents:
        raise ValueError("Diagnostic outputs must be outside the repository")
    if root.exists():
        raise FileExistsError("Use a fresh diagnostic attempt ID; existing output is never overwritten")
    _require_clean_relevant_inputs(require_tracked_runner=True)
    plan.update(git_commit_sha=git_commit_sha(repo_root=ROOT), source_fingerprint=compute_source_fingerprint())
    if not plan["git_commit_sha"]:
        raise ValueError("Clean committed source provenance required")
    # Explicit IDs: loader reads the ID column, selects only these rows, then reads text.
    selected = dict(rcd)
    selected.pop("dataset_query_ids_manifest", None)
    selected.update(dataset_query_ids=list(DEVELOPMENT_QUERY_IDS), dataset_n_samples=None)
    clean = load_dataset(selected)
    if query_set_fingerprint(clean["queries"]) != plan["query_set_fingerprint"] or [q["query_id"] for q in clean["queries"]] != list(DEVELOPMENT_QUERY_IDS):
        raise ValueError("Development loader question/gold/doc identities differ from original verified records")
    plan["clean_corpus_fingerprint"] = corpus_fingerprint(clean["corpus"])
    if recover_from is not None:
        previous = json.loads((recover_from / "development.plan.json").read_text())
        if previous != plan:
            raise ValueError("Recovery code/config/query/review provenance mismatch")
    checkpoints = {}
    # Validate archived records before model construction, even in a recovery.
    family = FAMILIES[1]
    checkpoints[family] = PoisonCheckpoint(root / family, [recover_from / family] if recover_from else [],
        provenance={**plan, "target_assignment_fingerprint": plan["target_assignment_fingerprint"]},
        attack_family=family, intensity=1, allowed_query_ids=list(DEVELOPMENT_QUERY_IDS))
    if not plan["mlx_available"] or not plan["mlx_lm_available"]:
        raise RuntimeError("The configured real MLX backend is required")
    root.mkdir(parents=True)
    _write(root / "development.plan.json", plan)
    summaries = {}
    try:
        set_seed(42)
        backend = build_generator(rcd)
        if not isinstance(backend, MLXGenerator):
            raise TypeError("Development real-model diagnostic requires MLXGenerator")
        for family in FAMILIES:
            if (git_commit_sha(repo_root=ROOT) != plan["git_commit_sha"] or
                compute_source_fingerprint() != plan["source_fingerprint"]):
                raise ValueError("Source provenance changed during diagnostic")
            _require_clean_relevant_inputs(require_tracked_runner=True)
            directory = root / family
            directory.mkdir()
            recorder = _RecordingGenerator(backend, directory / "generation.events.jsonl", {
                "generator_backend": plan["generator_backend"], "model_name": plan["generator_model"],
                "git_commit_sha": plan["git_commit_sha"]})
            attack = (LexicalInfluentialTokenAttack(repeat_factor=4) if family == FAMILIES[0] else
                      _DiagnosticSemanticAttack(recorder, max_tokens=150, max_attempts=2))
            if family == FAMILIES[1]:
                attack.capture_smoke_diagnostics = True
            observed = _ObservedAttack(attack, recorder)
            try:
                poisoned = inject_poisons(clean, observed, n_poison=1, poison_rate=1.0, seed=42,
                    attacked_query_ids=list(DEVELOPMENT_QUERY_IDS), checkpoint=checkpoints.get(family),
                    reviewed_target_assignments=mapping)
            finally:
                _write(directory / "poison.attempts.json",
                       attack.export_attempt_records() if family == FAMILIES[1] else [])
            if not validate_poisoned_dataset(clean, poisoned, expected_n_poison=1, expected_poison_rate=1.0)["valid"]:
                raise ValueError("Invalid diagnostic poison snapshot")
            fingerprint = poison_instances_fingerprint(clean, poisoned)
            manifest = {"schema": SCHEMA, "scope": "development", "is_final_run": False,
                        "attack_family": family, "provenance": plan, "poison_instance_fingerprint": fingerprint,
                        "poisoned_data": poisoned}
            _write(directory / "poison.manifest.json", manifest)
            matched = build_matched_retrievers(dense, rcd, clean, poisoned)
            rows = {}
            with (directory / "results.jsonl").open("x", encoding="utf-8") as output:
                for pipeline, (clean_retriever, poisoned_retriever) in matched.items():
                    config = dense if pipeline == "dense" else rcd
                    set_seed(42)
                    paired = evaluate_pipeline(pipeline=pipeline, clean_retriever=clean_retriever,
                        poisoned_retriever=poisoned_retriever, clean_data=clean, poisoned_data=poisoned,
                        generator=recorder, top_k=validated_top_k(config, pipeline), max_tokens=int(config["max_tokens"]))
                    if [r["query_id"] for r in paired] != list(DEVELOPMENT_QUERY_IDS):
                        raise ValueError("Incomplete diagnostic query cohort")
                    rows[pipeline] = paired
                    for row in paired:
                        for record in flatten_query_result_records(row):
                            output.write(json.dumps({**record, "schema": SCHEMA, "scope": "development",
                                "is_final_run": False, "poison_instance_fingerprint": fingerprint,
                                "target_artifact_sha256": targets_sha256}) + "\n")
                            output.flush()
            if set(rows) != {"dense", "rcd"} or poison_instances_fingerprint(clean, poisoned) != fingerprint:
                raise ValueError("Matched diagnostic pipelines or immutable snapshot changed")
            summary = {"schema": SCHEMA, "scope": "development", "is_final_run": False,
                       "poison_instance_fingerprint": fingerprint, "qa_record_count": sum(len(r) * 2 for r in rows.values()),
                       "results_sha256": sha(directory / "results.jsonl"),
                       "pipelines": {p: summarize_pipeline(r) for p, r in rows.items()},
                       "paired_dense_minus_rcd": paired_differences(rows["dense"], rows["rcd"])}
            _write(directory / "summary.json", summary)
            summaries[family] = summary
        result = {"schema": SCHEMA, "scope": "development", "is_final_run": False,
                  "status": "complete_diagnostic_requires_human_semantic_review", "qa_record_count": 16,
                  "requires_human_semantic_review": True, "families": summaries}
        _write(root / "summary.json", result)
        return result
    except Exception as error:
        _write(root / "failure.json", {"schema": SCHEMA, "scope": "development", "is_final_run": False,
                                       "error_type": type(error).__name__, "error": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--targets", type=Path)
    parser.add_argument("--targets-sha256")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--experiment-id")
    parser.add_argument("--recover-from", type=Path)
    args = parser.parse_args()
    from scripts.prepare_week9_development_review import input_errors, validate, NEXT
    if args.execute or args.targets is not None or args.targets_sha256 is not None:
        errors = input_errors(args.targets, args.targets_sha256)
        if not errors:
            errors = validate(args.targets, args.targets_sha256)["errors"]
        if errors:
            parser.exit(2, "Review input rejected:\n" + "\n".join(errors) + "\n" + NEXT + "\n")
    if args.execute:
        if not all((args.targets, args.targets_sha256, args.output_dir, args.experiment_id)):
            parser.error("Execution requires genuine reviewed targets, external SHA pin, output directory and fresh ID")
        result = execute(targets=args.targets, targets_sha256=args.targets_sha256, output_dir=args.output_dir,
                         experiment_id=args.experiment_id, recover_from=args.recover_from)
    else:
        result = preflight(args.targets, args.targets_sha256)[0]
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
