"""Crash-safe, provenance-checked per-document semantic poison checkpoints.

These are intermediate generation artifacts, never final experiment evidence.
A successful checkpoint is reused only when *all* frozen provenance and
canonical document identity checks match. No silent conflict resolution.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from src.attacks.base import PoisonDocument, poison_doc_id
from src.attacks.semantic_fluent import (
    SEMANTIC_VALIDATION_VERSION, SEMANTIC_PROMPT_VERSION, semantic_support_status,
)

CHECKPOINT_SCHEMA = "rag-poison-transfer.semantic-poison-document/v1"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise FileExistsError(f"Checkpoint already exists: {path}")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class PoisonCheckpoint:
    """One independently verifiable checkpoint per (query, poison index)."""

    def __init__(self, destination: Path, previous_dirs: list[Path], *, provenance: dict,
                 attack_family: str, intensity: int, allowed_query_ids: list[str]):
        self.destination = destination
        self.provenance = provenance
        self.prompt_version = provenance.get("prompt_version", SEMANTIC_PROMPT_VERSION)
        self.attack_family = attack_family
        self.intensity = intensity
        self.allowed = set(allowed_query_ids)
        self.records: dict[tuple[str, int], dict] = {}
        # Only actual checkpoint directories count; accidental unrelated files
        # in an incomplete cell do not become authoritative evidence.
        for parent in [destination, *previous_dirs]:
            directory = parent / "poison.checkpoints"
            if not directory.exists():
                continue
            if not directory.is_dir():
                raise ValueError(f"Poison checkpoint path is not a directory: {directory}")
            for entry in sorted(directory.iterdir()):
                if not entry.is_file() or entry.suffix != ".json":
                    raise ValueError(f"Unexpected checkpoint entry: {entry}")
                with entry.open(encoding="utf-8") as stream:
                    record = json.load(stream)
                self._validate(record)
                identity = (record["query_id"], record["poison_index"])
                if identity in self.records and self.records[identity] != record:
                    raise ValueError(f"Conflicting checkpoints for {identity}")
                self.records[identity] = record

    def _validate(self, record: dict) -> None:
        if record.get("schema") != CHECKPOINT_SCHEMA or record.get("provenance") != self.provenance:
            raise ValueError("Checkpoint schema or frozen provenance mismatch")
        if record.get("prompt_version") != self.prompt_version:
            raise ValueError("Checkpoint semantic prompt version mismatch")
        if record.get("attack_family") != self.attack_family:
            raise ValueError("Checkpoint attack family mismatch")
        qid, index = record.get("query_id"), record.get("poison_index")
        if qid not in self.allowed or type(index) is not int or not (0 <= index < self.intensity):
            raise ValueError("Checkpoint query or poison index mismatch")
        text = record.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError("Checkpoint text missing")
        if record.get("text_sha256") != _digest(text):
            raise ValueError("Checkpoint content fingerprint mismatch")
        if record.get("doc_id") != poison_doc_id(self.attack_family, qid, index, text):
            raise ValueError("Checkpoint canonical document ID mismatch")
        if not isinstance(record.get("target_answer"), str) or not record["target_answer"].strip():
            raise ValueError("Checkpoint target missing")
        if record.get("validation_method") != SEMANTIC_VALIDATION_VERSION:
            raise ValueError("Checkpoint validator version mismatch")
        if record.get("validation_status") != "heuristically_supported_unverified":
            raise ValueError("Checkpoint does not contain admissible heuristic support")
        if semantic_support_status(text, record["target_answer"]) != record["validation_status"]:
            raise ValueError("Checkpoint fails current heuristic validation")
        if not isinstance(record.get("attempts"), list) or not record["attempts"]:
            raise ValueError("Checkpoint attempt evidence missing")

    def get(self, query: dict, index: int, target_answer: str, *, attack) -> PoisonDocument | None:
        record = self.records.get((query["query_id"], index))
        if record is None:
            return None
        if record["target_answer"] != target_answer:
            raise ValueError("Checkpoint cross-query target differs from seeded selection")
        if attack.prompt_version != self.prompt_version:
            raise ValueError("Checkpoint attack prompt version mismatch")
        # The quality gate must still pass with the actual gold answer.
        attack._validate_text(record["text"], query, target_answer)
        return PoisonDocument(
            doc_id=record["doc_id"], text=record["text"],
            query_id=query["query_id"], attack_family=self.attack_family,
            target_answer=target_answer, poison_index=index,
        )

    def record(self, query: dict, index: int, target_answer: str, doc: PoisonDocument, *, attack):
        if attack.prompt_version != self.prompt_version:
            raise ValueError("Checkpoint attack prompt version mismatch")
        key = (query["query_id"], index)
        expected = self.records.get(key)
        if expected is not None:
            if expected["doc_id"] != doc.doc_id or expected["text"] != doc.text:
                raise ValueError("Generated document disagrees with verified checkpoint")
            # Copy old checkpoint into new attempt atomically if coming from archive.
            record = expected
        else:
            status = attack._validate_text(doc.text, query, target_answer)
            record = {
                "schema": CHECKPOINT_SCHEMA,
                "provenance": self.provenance,
                "prompt_version": self.prompt_version,
                "query_id": query["query_id"],
                "poison_index": index,
                "attack_family": self.attack_family,
                "target_answer": target_answer,
                "doc_id": doc.doc_id,
                "text": doc.text,
                "text_sha256": _digest(doc.text),
                "validation_method": SEMANTIC_VALIDATION_VERSION,
                "validation_status": status,
                "attempts": list(attack.attempt_log.get(key, [])),
            }
            self._validate(record)
            self.records[key] = record
        dest = self.destination / "poison.checkpoints" / f"{query['query_id']}.{index}.json"
        if dest.exists():
            with dest.open(encoding="utf-8") as stream:
                stored = json.load(stream)
            if stored != record:
                raise ValueError("Existing destination checkpoint differs")
            return
        _write_atomic(dest, record)
