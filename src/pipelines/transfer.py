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
    "retrieved_doc_ids": "list[str]",  # Ranked list from target retriever
    "poison_retrieved": bool,  # At least one poison in top-k
    "poison_rank": "int | None",  # Rank of first poison, if retrieved
    "clean_answer": str,  # Model output on clean evidence
    "attacked_answer": str,  # Model output on poisoned evidence
    "gold_answer": str,  # Ground truth
    "attack_success": bool,  # attacked_answer matches attack target
    # Reproducibility metadata
    "git_commit_sha": str,
    "model_identifier": str,
    "seed": int,
    "dataset": str,
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


def compute_transfer_statistics(
    source_results: list[dict],
    target_results: list[dict],
) -> TransferExperimentResult:
    """Compute transfer metrics from parallel source/target result lists.
    
    Args:
        source_results: Attack results evaluated on source pipeline.
                       Each dict should have 'attack_success' field.
        target_results: Same queries re-evaluated on target pipeline.
                       Parallel to source_results (same order, same queries).
    
    Returns:
        TransferExperimentResult with computed statistics.
    
    Raises:
        ValueError if result lists don't match length or structure.
    """
    if len(source_results) != len(target_results):
        raise ValueError(
            f"Source ({len(source_results)}) and target ({len(target_results)}) "
            "result counts don't match"
        )

    if not source_results:
        raise ValueError("Empty result lists")

    # Fail fast on query-ID misalignment (supervisor review 3.5): source and
    # target must be the same queries, in the same order, or every downstream
    # rate (ATR, ASR, PRR) is silently computed over the wrong pairs.
    for i, (src, tgt) in enumerate(zip(source_results, target_results)):
        src_qid = src.get("query_id")
        tgt_qid = tgt.get("query_id")
        if src_qid != tgt_qid:
            raise ValueError(
                f"Query ID mismatch at index {i}: source={src_qid!r}, "
                f"target={tgt_qid!r}. source_results and target_results must "
                "contain the same queries in the same order."
            )

    # Extract metadata from first result (assume consistent across all)
    first_result = source_results[0]
    result = TransferExperimentResult(
        source_pipeline=first_result.get("source_pipeline", "unknown"),
        target_pipeline=first_result.get("target_pipeline", "unknown"),
        poison_id=first_result.get("poison_id", "unknown"),
        dataset=first_result.get("dataset", "unknown"),
        seed=first_result.get("seed", 0),
        total_queries=len(source_results),
    )

    # Count successes
    source_successful_indices = []
    for i, res in enumerate(source_results):
        if res.get("attack_success", False):
            result.successful_attacks_source += 1
            source_successful_indices.append(i)

    for i, res in enumerate(target_results):
        if res.get("attack_success", False):
            result.successful_attacks_target += 1

    # Count transfers
    for i in source_successful_indices:
        if target_results[i].get("attack_success", False):
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
    attacked = [res for res in target_results if res.get("poison_doc_ids")]
    if attacked:
        for k in (1, 3, 5, 10):
            hits = sum(
                1 for res in attacked
                if res.get("poison_rank") is not None and res["poison_rank"] <= k
            )
            setattr(result, f"poison_retrieval_rate_at_{k}", hits / len(attacked))

    result.per_query_results = [
        {
            "query_id": source_results[i].get("query_id"),
            "source_attack_success": source_results[i].get("attack_success", False),
            "target_attack_success": target_results[i].get("attack_success", False),
            "transferred": (
                source_results[i].get("attack_success", False)
                and target_results[i].get("attack_success", False)
            ),
        }
        for i in range(len(source_results))
    ]

    return result
