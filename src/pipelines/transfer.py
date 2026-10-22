"""Transfer evaluation framework for cross-pipeline attack assessment.

This module provides utilities for evaluating attacks generated on a
SOURCE pipeline against a TARGET pipeline, tracking which attacks
transfer across retrieval/generation strategies.

The key abstraction is the TransferExperiment, which:
  1. Takes attack results from a source pipeline
  2. Re-evaluates them on a target pipeline
  3. Computes transfer metrics (ASR, ATR, PRR@k)
  4. Aggregates across query sets

This framework does NOT implement the attack-generation algorithms
themselves. Instead, it assumes attack implementations provide attack
results conforming to the ATTACK_RESULT_SCHEMA below.
"""
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict


# Schema for a single attack result (per query).
# Attack implementations should populate these fields.
ATTACK_RESULT_SCHEMA = {
    "query_id": str,
    "source_pipeline": str,
    "target_pipeline": str,
    "poison_doc_ids": "list[str]",
    "retrieved_doc_ids": "list[str]",  # Ranked diagnostic retrieval window
    "poison_retrieved": bool,  # Poison appears in evidence passed to generator
    "poison_rank": "int | None",  # First poison rank in diagnostic retrieval window
    "clean_answer": str,  # Model output on clean evidence
    "attacked_answer": str,  # Model output on poisoned evidence
    "gold_answer": str,  # Ground truth
    "attack_success": bool,  # attacked_answer matches attack target
    # Reproducibility metadata
    "git_commit_sha": str,
    "model_identifier": str,
    "seed": int,
    "dataset": str,
    "attack_family": str,
    "attack_config": "dict[str, Any]",
    "poison_manifest_fingerprint": str,
    "query_set_fingerprint": str,
    "retrieval_metrics": "dict[str, float]",  # Recall@k, MRR@k, etc.
}


@dataclass
class TransferExperimentResult:
    """Result of a single source→target transfer experiment."""

    source_pipeline: str
    target_pipeline: str
    poison_id: str
    dataset: str
    seed: int

    total_queries: int = 0
    successful_attacks_source: int = 0
    successful_attacks_target: int = 0
    transferred_attacks: int = 0

    poison_retrieval_rate_at_1: float | None = None
    poison_retrieval_rate_at_3: float | None = None
    poison_retrieval_rate_at_5: float | None = None
    poison_retrieval_rate_at_10: float | None = None

    attack_success_rate_source: float | None = None
    attack_success_rate_target: float | None = None
    attack_transfer_rate: float | None = None

    source_queries_evaluated: int = 0
    source_successful_query_count: int = 0
    overall_source_asr: float | None = None
    conditional_target_asr: float | None = None
    transfer_count: int = 0
    atr_denominator: int = 0
    source_asr_results: list[dict] = field(default_factory=list)
    per_query_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_pipeline": self.source_pipeline,
            "target_pipeline": self.target_pipeline,
            "poison_id": self.poison_id,
            "dataset": self.dataset,
            "seed": self.seed,
            "total_queries": self.total_queries,
            "successful_attacks_source": self.successful_attacks_source,
            "successful_attacks_target": self.successful_attacks_target,
            "transferred_attacks": self.transferred_attacks,
            "poison_retrieval_rate@1": self.poison_retrieval_rate_at_1,
            "poison_retrieval_rate@3": self.poison_retrieval_rate_at_3,
            "poison_retrieval_rate@5": self.poison_retrieval_rate_at_5,
            "poison_retrieval_rate@10": self.poison_retrieval_rate_at_10,
            "attack_success_rate_source": self.attack_success_rate_source,
            "attack_success_rate_target": self.attack_success_rate_target,
            "attack_transfer_rate": self.attack_transfer_rate,
            "source_queries_evaluated": self.source_queries_evaluated,
            "source_successful_query_count": self.source_successful_query_count,
            "overall_source_asr": self.overall_source_asr,
            "conditional_target_asr": self.conditional_target_asr,
            "transfer_count": self.transfer_count,
            "atr_denominator": self.atr_denominator,
            "source_asr_results": self.source_asr_results,
            "per_query_results": self.per_query_results,
        }


class TransferMatrix:
    """Aggregation of transfer experiments across source/target pipelines.
    
    Maintains a matrix indexed by (source_pipeline, target_pipeline),
    storing TransferExperimentResult for each pair. Unrun cells are
    marked explicitly as "not_run" rather than fabricated.
    """

    def __init__(self):
        self.pipelines = set()
        self.results: dict[tuple[str, str], TransferExperimentResult | str] = {}

    def add_result(
        self, result: TransferExperimentResult
    ) -> None:
        """Record a completed transfer experiment."""
        self.pipelines.add(result.source_pipeline)
        self.pipelines.add(result.target_pipeline)
        key = (result.source_pipeline, result.target_pipeline)
        self.results[key] = result

    def mark_not_run(self, source: str, target: str) -> None:
        """Mark a cell as not run rather than fabricated."""
        self.pipelines.add(source)
        self.pipelines.add(target)
        key = (source, target)
        self.results[key] = "not_run"

    def get_result(
        self, source: str, target: str
    ) -> TransferExperimentResult | str | None:
        """Retrieve a cell result. Returns result, 'not_run', or None."""
        key = (source, target)
        return self.results.get(key)

    def to_dict(self) -> dict[str, Any]:
        """Export matrix as nested dict."""
        matrix = {}
        for (source, target), result in self.results.items():
            if source not in matrix:
                matrix[source] = {}
            if isinstance(result, str):
                matrix[source][target] = {"status": result}
            else:
                matrix[source][target] = result.to_dict()
        return matrix

    @staticmethod
    def _resolve_metric_attr(metric: str) -> str:
        """Map an external metric key like 'poison_retrieval_rate@5' to the
        actual dataclass attribute name 'poison_retrieval_rate_at_5'."""
        return metric.replace("@", "_at_")

    def to_csv(self, metric: str = "attack_transfer_rate") -> str:
        """Generate CSV representation of a single metric across matrix.
        
        Args:
            metric: Which metric to display (e.g., "attack_transfer_rate",
                   "attack_success_rate_source", "poison_retrieval_rate@5")
        
        Returns:
            CSV string with pipelines as rows/columns.
        """
        pipelines = sorted(self.pipelines)
        rows = [[""] + pipelines]

        for source in pipelines:
            row = [source]
            for target in pipelines:
                result = self.get_result(source, target)
                if result == "not_run":
                    row.append("N/A")
                elif result is None:
                    row.append("N/A")
                else:
                    value = getattr(result, self._resolve_metric_attr(metric), None)
                    if value is None:
                        row.append("N/A")
                    else:
                        row.append(f"{value:.4f}")
            rows.append(row)

        # Format as CSV
        lines = []
        for row in rows:
            lines.append(",".join(str(v) for v in row))
        return "\n".join(lines)

    def to_markdown(self, metric: str = "attack_transfer_rate") -> str:
        """Generate Markdown table for a single metric.
        
        Args:
            metric: Which metric to display.
        
        Returns:
            Markdown table string.
        """
        pipelines = sorted(self.pipelines)
        lines = []

        # Header
        header = "|  | " + " | ".join(pipelines) + " |"
        lines.append(header)
        lines.append("|" + "|".join(["---"] * (len(pipelines) + 1)) + "|")

        # Rows
        for source in pipelines:
            row = f"| {source} |"
            for target in pipelines:
                result = self.get_result(source, target)
                if result == "not_run":
                    row += " N/A |"
                elif result is None:
                    row += " N/A |"
                else:
                    value = getattr(result, self._resolve_metric_attr(metric), None)
                    if value is None:
                        row += " N/A |"
                    else:
                        row += f" {value:.4f} |"
            lines.append(row)

        return "\n".join(lines)

    def to_json(self, filepath: str, overwrite: bool = False) -> None:
        """Export transfer matrix to a JSON file.
        
        Args:
            filepath: Path where the JSON file will be written.
            overwrite: If False (default), raise FileExistsError if file exists.
                      If True, overwrite the existing file.
        
        Raises:
            FileExistsError: If file exists and overwrite=False.
        """
        import json
        import os
        
        if os.path.exists(filepath) and not overwrite:
            raise FileExistsError(
                f"{filepath} already exists. Pass overwrite=True to overwrite, "
                f"or use a different filepath."
            )
        
        matrix_dict = self.to_dict()
        with open(filepath, "w") as f:
            json.dump(matrix_dict, f, indent=2, sort_keys=True)
            f.write("\n")



_TRANSFER_SHARED_METADATA_FIELDS = (
    "dataset",
    "seed",
    "attack_family",
    "attack_config",
    "model_identifier",
    "git_commit_sha",
    "query_set_fingerprint",
)


def _validate_strict_metadata_values(
    results: list[dict],
    *,
    side: str,
    expected_source_pipeline: str,
    expected_target_pipeline: str,
    validate_query_ids: bool = True,
) -> dict:
    """Require complete, internally consistent metadata on every result."""
    required_fields = (
        *_TRANSFER_SHARED_METADATA_FIELDS,
        "source_pipeline",
        "target_pipeline",
    )
    if not results:
        raise ValueError(f"{side} results are empty")

    for field_name in required_fields:
        values = [result.get(field_name) for result in results]
        for value in values:
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValueError(
                    f"{side} result is missing required metadata field "
                    f"{field_name!r}"
                )
            if isinstance(value, str) and value.strip().lower() in {
                "unknown",
                "none",
                "null",
            }:
                raise ValueError(
                    f"{side} metadata field {field_name!r} cannot use "
                    f"placeholder value {value!r}"
                )
        if any(value != values[0] for value in values[1:]):
            raise ValueError(
                f"{side} results have inconsistent {field_name!r} metadata"
            )

    seed = results[0]["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"{side} metadata field 'seed' must be an integer")
    if not isinstance(results[0]["attack_config"], dict):
        raise ValueError(
            f"{side} metadata field 'attack_config' must be a mapping"
        )
    if not results[0]["attack_config"]:
        raise ValueError(
            f"{side} metadata field 'attack_config' must include the "
            "attack/intensity configuration"
        )
    for field_name in (
        "dataset",
        "attack_family",
        "model_identifier",
        "git_commit_sha",
        "query_set_fingerprint",
        "source_pipeline",
        "target_pipeline",
    ):
        if not isinstance(results[0][field_name], str):
            raise ValueError(
                f"{side} metadata field {field_name!r} must be a string"
            )

    poison_fingerprints = []
    for result in results:
        manifest_fingerprint = result.get("poison_manifest_fingerprint")
        instance_fingerprint = result.get("poison_instance_fingerprint")
        fingerprint = manifest_fingerprint or instance_fingerprint
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise ValueError(
                f"{side} result is missing required metadata field "
                "'poison_manifest_fingerprint' or "
                "'poison_instance_fingerprint'"
            )
        if fingerprint.strip().lower() in {"unknown", "none", "null"}:
            raise ValueError(
                f"{side} poison fingerprint cannot use placeholder "
                f"value {fingerprint!r}"
            )
        if (
            manifest_fingerprint
            and instance_fingerprint
            and manifest_fingerprint != instance_fingerprint
        ):
            raise ValueError(
                f"{side} result has conflicting poison fingerprint metadata"
            )
        poison_fingerprints.append(fingerprint)

    if any(value != poison_fingerprints[0] for value in poison_fingerprints[1:]):
        raise ValueError(
            f"{side} results have inconsistent poison fingerprint metadata"
        )

    pipeline_expectations = (
        ("source_pipeline", expected_source_pipeline),
        ("target_pipeline", expected_target_pipeline),
    )
    for field_name, expected in pipeline_expectations:
        if not isinstance(expected, str) or not expected.strip():
            raise ValueError(
                f"Strict metadata validation requires expected "
                f"{field_name}"
            )
        actual = results[0][field_name]
        if actual != expected:
            raise ValueError(
                f"{side} {field_name} mismatch: "
                f"expected={expected!r}, actual={actual!r}"
            )

    if validate_query_ids:
        for index, result in enumerate(results):
            query_id = result.get("query_id")
            if not isinstance(query_id, str) or not query_id.strip():
                raise ValueError(
                    f"{side} result at index {index} is missing a valid query_id"
                )
        query_ids = [result["query_id"] for result in results]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError(f"{side} results contain duplicate query_ids")

    return {
        **{field_name: results[0][field_name]
           for field_name in _TRANSFER_SHARED_METADATA_FIELDS},
        "poison_fingerprint": poison_fingerprints[0],
    }


def validate_transfer_experiment_metadata(
    metadata: dict | None,
    *,
    expected_source_pipeline: str,
    expected_target_pipeline: str,
) -> dict:
    """Validate the shared metadata required for a strict transfer run.

    Metadata is caller-supplied; this function never guesses dataset,
    attack, poison, model, Git, or query-set provenance.
    """
    if not isinstance(metadata, dict):
        raise ValueError(
            "Strict transfer evaluation requires an explicit "
            "experiment_metadata mapping"
        )
    probe = {**metadata}
    probe["source_pipeline"] = expected_source_pipeline
    probe["target_pipeline"] = expected_target_pipeline
    return _validate_strict_metadata_values(
        [probe],
        side="experiment_metadata",
        expected_source_pipeline=expected_source_pipeline,
        expected_target_pipeline=expected_target_pipeline,
        validate_query_ids=False,
    )


def validate_transfer_result_metadata(
    results: list[dict],
    *,
    side: str,
    expected_source_pipeline: str,
    expected_target_pipeline: str,
) -> dict:
    """Validate complete metadata and unique query IDs for one result side."""
    return _validate_strict_metadata_values(
        results,
        side=side,
        expected_source_pipeline=expected_source_pipeline,
        expected_target_pipeline=expected_target_pipeline,
    )


def validate_transfer_result_pair_metadata(
    source_results: list[dict],
    target_results: list[dict],
    *,
    expected_source_pipeline: str,
    expected_target_pipeline: str,
) -> None:
    """Validate full source/target result sets for a strict transfer run."""
    _validate_transfer_pair_metadata(
        source_results,
        target_results,
        strict=True,
        expected_source_pipeline=expected_source_pipeline,
        expected_target_pipeline=expected_target_pipeline,
    )


def _validate_transfer_pair_metadata(
    source_results: list[dict],
    target_results: list[dict],
    *,
    strict: bool = False,
    expected_source_pipeline: str | None = None,
    expected_target_pipeline: str | None = None,
) -> None:
    """Validate that source/target results belong to the same experiment.

    Transfer must compare the same queries, dataset, seed, and poison
    configuration. The target pipeline may differ, but the experiment
    identity must otherwise remain fixed.
    """
    if not source_results or not target_results:
        raise ValueError("Cannot validate empty result lists")

    if strict:
        if expected_source_pipeline is None:
            raise ValueError(
                "Strict metadata validation requires expected_source_pipeline"
            )
        if expected_target_pipeline is None:
            raise ValueError(
                "Strict metadata validation requires expected_target_pipeline"
            )
        source_metadata = _validate_strict_metadata_values(
            source_results,
            side="source_results",
            expected_source_pipeline=expected_source_pipeline,
            expected_target_pipeline=expected_target_pipeline,
        )
        target_metadata = _validate_strict_metadata_values(
            target_results,
            side="target_results",
            expected_source_pipeline=expected_source_pipeline,
            expected_target_pipeline=expected_target_pipeline,
        )
        for field_name, source_value in source_metadata.items():
            target_value = target_metadata[field_name]
            if source_value != target_value:
                raise ValueError(
                    f"Source/target {field_name} mismatch: "
                    f"source={source_value!r}, target={target_value!r}"
                )
        source_ids = {result["query_id"] for result in source_results}
        target_ids = {result["query_id"] for result in target_results}
        if source_ids != target_ids:
            raise ValueError(
                "source_results and target_results have mismatched query_ids"
            )

    def metadata_values(results, field):
        return {
            result.get(field)
            for result in results
            if result.get(field) is not None
        }

    # Fields that must remain identical across source and target.
    invariant_fields = (
        "dataset",
        "seed",
        "poison_id",
    )

    for field in invariant_fields:
        source_values = metadata_values(source_results, field)
        target_values = metadata_values(target_results, field)

        if len(source_values) > 1:
            raise ValueError(
                f"source_results has inconsistent {field} values: "
                f"{sorted(map(str, source_values))}"
            )

        if len(target_values) > 1:
            raise ValueError(
                f"target_results has inconsistent {field} values: "
                f"{sorted(map(str, target_values))}"
            )

        if source_values and target_values and source_values != target_values:
            raise ValueError(
                f"Source/target {field} mismatch: "
                f"source={source_values}, target={target_values}"
            )

    # A transfer experiment must never silently use a mock generator.
    for label, results in (
        ("source_results", source_results),
        ("target_results", target_results),
    ):
        for result in results:
            model_identifier = str(result.get("model_identifier", ""))

            if "mockgenerator" in model_identifier.lower():
                raise ValueError(
                    f"{label} contains MockGenerator results. "
                    "MockGenerator is prohibited for research transfer evaluation."
                )

    # If poison document IDs are recorded, source and target must evaluate
    # the same poison set for each query.
    #
    # Do not assume query IDs exist here: the public
    # compute_transfer_statistics() function performs explicit query_id
    # validation immediately after this helper returns. This helper therefore
    # only performs poison-set validation when both sides have usable IDs.
    source_by_id = {
        result.get("query_id"): result
        for result in source_results
        if result.get("query_id") is not None
    }
    target_by_id = {
        result.get("query_id"): result
        for result in target_results
        if result.get("query_id") is not None
    }

    # Only compare the intersection. Missing/extra query IDs are handled by
    # compute_transfer_statistics(), which gives the expected explicit error.
    for query_id in source_by_id.keys() & target_by_id.keys():
        source_poison = set(
            source_by_id[query_id].get("poison_doc_ids", []) or []
        )
        target_poison = set(
            target_by_id[query_id].get("poison_doc_ids", []) or []
        )

        if source_poison != target_poison:
            raise ValueError(
                f"Poison set mismatch for query_id={query_id!r}: "
                f"source={sorted(source_poison)}, "
                f"target={sorted(target_poison)}"
            )



def compute_transfer_statistics(
    source_results: list[dict],
    target_results: list[dict],
    *,
    strict_metadata: bool = False,
    expected_source_pipeline: str | None = None,
    expected_target_pipeline: str | None = None,
) -> TransferExperimentResult:
    """Compute transfer metrics from source/target result lists, aligned by query_id.
    
    Args:
        source_results: Attack results evaluated on source pipeline.
                       Each dict should have 'query_id' and 'attack_success' fields.
        target_results: Same queries re-evaluated on target pipeline.
                       Aligned to source_results by query_id, not by position.
        strict_metadata: Require complete and consistent final-run metadata.
        expected_source_pipeline: Required source label in strict mode.
        expected_target_pipeline: Required target label in strict mode.
    
    Returns:
        TransferExperimentResult with computed statistics.
    
    Raises:
        ValueError if:
        - Result lists are empty
        - Results lack query_id fields
        - query_ids are duplicated within a list
        - The two lists have different sets of query_ids
    
    Note: Query alignment is by query_id, so reordered inputs produce the same result.
    """
    if not source_results or not target_results:
        raise ValueError("Empty result lists")

    _validate_transfer_pair_metadata(
        source_results,
        target_results,
        strict=strict_metadata,
        expected_source_pipeline=expected_source_pipeline,
        expected_target_pipeline=expected_target_pipeline,
    )

    # Build dicts indexed by query_id for alignment
    source_by_id = {}
    for result in source_results:
        qid = result.get("query_id")
        if qid is None:
            raise ValueError(
                "source_results contains entry without query_id field"
            )
        if qid in source_by_id:
            raise ValueError(
                f"source_results has duplicate query_id={qid!r}"
            )
        source_by_id[qid] = result
    
    target_by_id = {}
    for result in target_results:
        qid = result.get("query_id")
        if qid is None:
            raise ValueError(
                "target_results contains entry without query_id field"
            )
        if qid in target_by_id:
            raise ValueError(
                f"target_results has duplicate query_id={qid!r}"
            )
        target_by_id[qid] = result
    
    # Check that both lists have the same set of query_ids
    source_ids = set(source_by_id.keys())
    target_ids = set(target_by_id.keys())
    if source_ids != target_ids:
        missing_in_target = source_ids - target_ids
        missing_in_source = target_ids - source_ids
        msg = []
        if missing_in_target:
            msg.append(f"query_ids in source but not target: {missing_in_target}")
        if missing_in_source:
            msg.append(f"query_ids in target but not source: {missing_in_source}")
        raise ValueError(
            "source_results and target_results have mismatched query_ids: "
            + "; ".join(msg)
        )

    # Extract metadata from first source result (assume consistent across all)
    first_result = list(source_by_id.values())[0]
    if strict_metadata:
        poison_id = (
            first_result.get("poison_manifest_fingerprint")
            or first_result.get("poison_instance_fingerprint")
        )
        source_pipeline = expected_source_pipeline
        target_pipeline = expected_target_pipeline
        dataset = first_result["dataset"]
        seed = first_result["seed"]
    else:
        poison_id = first_result.get("poison_id", "unknown")
        source_pipeline = first_result.get("source_pipeline", "unknown")
        target_pipeline = first_result.get("target_pipeline", "unknown")
        dataset = first_result.get("dataset", "unknown")
        seed = first_result.get("seed", 0)
    result = TransferExperimentResult(
        source_pipeline=source_pipeline,
        target_pipeline=target_pipeline,
        poison_id=poison_id,
        dataset=dataset,
        seed=seed,
        total_queries=len(source_by_id),
    )

    # Count successes across all queries (matched by query_id)
    source_successful_ids = []
    for qid, src_res in source_by_id.items():
        if src_res.get("attack_success", False):
            result.successful_attacks_source += 1
            source_successful_ids.append(qid)

    for qid, tgt_res in target_by_id.items():
        if tgt_res.get("attack_success", False):
            result.successful_attacks_target += 1

    # Count transfers: for each query that was successful in source,
    # check if it was also successful in target
    for qid in source_successful_ids:
        target_result = target_by_id[qid]
        if target_result.get("attack_success", False):
            result.transferred_attacks += 1

    # Compute rates
    if result.successful_attacks_source > 0:
        result.attack_transfer_rate = (
            result.transferred_attacks / result.successful_attacks_source
        )

    if result.total_queries > 0:
        result.attack_success_rate_source = (
            result.successful_attacks_source / result.total_queries
        )
        result.attack_success_rate_target = (
            result.successful_attacks_target / result.total_queries
        )

    # Poison Retrieval Rate @k (supervisor review 3.5): fraction of attacked
    # target queries where a poison doc appears in the top-k retrieved docs.
    # Only counted over queries that actually had a poison doc to retrieve.
    attacked = [res for res in target_by_id.values() if res.get("poison_doc_ids")]
    if attacked:
        for k in (1, 3, 5, 10):
            hits = sum(
                1 for res in attacked
                if res.get("poison_rank") is not None and res["poison_rank"] <= k
            )
            setattr(result, f"poison_retrieval_rate_at_{k}", hits / len(attacked))

    # Build per-query results in consistent (sorted) query_id order
    result.per_query_results = [
        {
            "query_id": qid,
            "source_attack_success": source_by_id[qid].get("attack_success", False),
            "target_attack_success": target_by_id[qid].get("attack_success", False),
            "transferred": (
                source_by_id[qid].get("attack_success", False)
                and target_by_id[qid].get("attack_success", False)
            ),
        }
        for qid in sorted(source_by_id.keys())
    ]

    return result
