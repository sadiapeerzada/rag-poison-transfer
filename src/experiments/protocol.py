"""Frozen experiment protocol and reproducibility metadata.

Final poisoning-transfer experiments must keep the retrieval corpus fixed
between clean/poisoned conditions and between source/target pipelines.
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from datetime import datetime, timezone
from typing import Any, Iterable


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def fingerprint_records(
    records: Iterable[dict],
    *,
    fields: tuple[str, ...] | None = None,
) -> str:
    """Return a deterministic SHA-256 fingerprint for records."""
    normalized = []

    for record in records:
        if fields is None:
            normalized.append(record)
        else:
            normalized.append(
                {field: record.get(field) for field in fields}
            )

    normalized.sort(key=_stable_json)

    return hashlib.sha256(
        _stable_json(normalized).encode("utf-8")
    ).hexdigest()


def corpus_fingerprint(corpus: list[dict]) -> str:
    """Fingerprint document IDs and text only."""
    return fingerprint_records(
        corpus,
        fields=("doc_id", "text"),
    )


def query_set_fingerprint(queries: list[dict]) -> str:
    """Fingerprint the frozen evaluation query set."""
    return fingerprint_records(
        queries,
        fields=(
            "query_id",
            "question",
            "gold_answer",
            "gold_doc_ids",
        ),
    )


def select_fixed_query_ids(
    queries: list[dict],
    n_queries: int,
    seed: int = 42,
) -> list[str]:
    """Select a deterministic query subset."""
    if n_queries < 1:
        raise ValueError("n_queries must be >= 1")

    ids = [q["query_id"] for q in queries]

    if len(ids) < n_queries:
        raise ValueError(
            f"Requested {n_queries} queries but only "
            f"{len(ids)} are available"
        )

    rng = random.Random(seed)

    return sorted(rng.sample(ids, n_queries))


def freeze_attack_query_ids(
    queries: list[dict],
    *,
    n_queries: int,
    seed: int = 42,
) -> tuple[list[str], str]:
    """Return fixed attacked-query IDs and their fingerprint."""
    ids = select_fixed_query_ids(
        queries,
        n_queries,
        seed,
    )

    fingerprint = hashlib.sha256(
        "\n".join(ids).encode("utf-8")
    ).hexdigest()

    return ids, fingerprint


def git_commit_sha(default: str = "unknown") -> str:
    """Return the current Git SHA when available."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

    except (
        OSError,
        subprocess.CalledProcessError,
    ):
        return default


def build_experiment_metadata(
    *,
    experiment_id: str,
    dataset: str,
    dataset_revision: str | None,
    queries: list[dict],
    corpus: list[dict],
    retriever: str,
    embedder_model: str | None,
    reranker_model: str | None,
    generator_model: str,
    defense: str,
    defense_config: dict[str, Any],
    source_pipeline: str | None,
    target_pipeline: str | None,
    attack_family: str,
    attack_version: str,
    attack_config: dict[str, Any],
    seed: int,
    top_k: int,
    n_poison: int,
    poison_rate: float,
    attacked_query_ids: list[str] | None = None,
    git_sha: str | None = None,
) -> dict[str, Any]:
    """Build canonical experiment metadata."""
    attack_config_hash = hashlib.sha256(
        _stable_json(attack_config).encode("utf-8")
    ).hexdigest()

    attacked_fingerprint = None

    if attacked_query_ids is not None:
        attacked_fingerprint = hashlib.sha256(
            "\n".join(
                sorted(attacked_query_ids)
            ).encode("utf-8")
        ).hexdigest()

    return {
        "experiment_id": experiment_id,
        "git_commit_sha": git_sha or git_commit_sha(),

        "dataset": dataset,
        "dataset_revision": dataset_revision or "unspecified",

        "query_count": len(queries),
        "query_set_fingerprint": query_set_fingerprint(queries),

        "attacked_query_count": (
            len(attacked_query_ids)
            if attacked_query_ids is not None
            else None
        ),
        "attacked_query_ids": (
            sorted(attacked_query_ids)
            if attacked_query_ids is not None
            else None
        ),
        "attacked_query_fingerprint": attacked_fingerprint,

        "corpus_count": len(corpus),
        "corpus_fingerprint": corpus_fingerprint(corpus),

        "retriever": retriever,
        "embedder_model": embedder_model or "none",
        "reranker_model": reranker_model or "none",
        "generator_model": generator_model,

        "defense": defense,
        "defense_config": defense_config,
        "source_pipeline": source_pipeline,
        "target_pipeline": target_pipeline,

        "attack_family": attack_family,
        "attack_version": attack_version,
        "attack_config_hash": attack_config_hash,
        "attack_config": attack_config,

        "seed": seed,
        "top_k": top_k,
        "n_poison": n_poison,
        "poison_rate": poison_rate,

        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def assert_same_corpus(
    clean_corpus: list[dict],
    poisoned_corpus: list[dict],
) -> None:
    """Verify that poisoning did not alter clean documents."""
    clean = {
        d["doc_id"]: d["text"]
        for d in clean_corpus
    }

    poisoned = {
        d["doc_id"]: d["text"]
        for d in poisoned_corpus
    }

    missing = [
        doc_id
        for doc_id in clean
        if doc_id not in poisoned
    ]

    changed = [
        doc_id
        for doc_id, text in clean.items()
        if poisoned.get(doc_id) != text
    ]

    if missing or changed:
        raise ValueError(
            "Frozen corpus violated: "
            f"missing={len(missing)}, "
            f"changed={len(changed)}"
        )


def bootstrap_mean_ci(
    values: list[float],
    seed: int = 42,
    n_bootstrap: int = 2000,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for a mean."""
    if not values:
        raise ValueError("values must not be empty")

    if not 0 < alpha < 1:
        raise ValueError(
            "alpha must be between 0 and 1"
        )

    if n_bootstrap < 100:
        raise ValueError(
            "n_bootstrap must be >= 100"
        )

    rng = random.Random(seed)
    n = len(values)
    samples = []

    for _ in range(n_bootstrap):
        draw = [
            values[rng.randrange(n)]
            for _ in range(n)
        ]

        samples.append(
            sum(draw) / n
        )

    samples.sort()

    lo = samples[
        int((alpha / 2) * n_bootstrap)
    ]

    hi = samples[
        min(
            n_bootstrap - 1,
            int((1 - alpha / 2) * n_bootstrap),
        )
    ]

    return lo, hi


def paired_mcnemar_counts(
    clean_correct: list[bool],
    poisoned_correct: list[bool],
) -> dict[str, int]:
    """Return paired clean/poisoned outcome counts."""
    if len(clean_correct) != len(poisoned_correct):
        raise ValueError(
            "paired inputs must have equal length"
        )

    return {
        "clean_correct_poisoned_wrong": sum(
            a and not b
            for a, b in zip(
                clean_correct,
                poisoned_correct,
            )
        ),
        "clean_wrong_poisoned_correct": sum(
            (not a) and b
            for a, b in zip(
                clean_correct,
                poisoned_correct,
            )
        ),
        "both_correct": sum(
            a and b
            for a, b in zip(
                clean_correct,
                poisoned_correct,
            )
        ),
        "both_wrong": sum(
            (not a) and (not b)
            for a, b in zip(
                clean_correct,
                poisoned_correct,
            )
        ),
    }
