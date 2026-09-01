"""Per-query result logging.

Section 9 of the plan requires: query ID, retrieved doc IDs/scores,
prompts, model response, latency, token counts, attack condition, and
metric outputs for *every run*. This writes one JSON object per line
(JSONL) so logs can be streamed/appended safely and inspected with
simple tools (`jq`, `pandas.read_json(lines=True)`), and so a crashed
run doesn't corrupt already-written results.

Raw results are never overwritten (Section 16 rule) — each experiment
ID gets its own log file, and this function only ever appends.

Also captures environment metadata (review issue #8) ONCE per logger
instance and attaches it to every record via setdefault -- so if a run
crashes halfway through, every record written so far still carries a
full environment fingerprint, not just the last one.
"""
import json
import os
import time

from src.utils.env_info import capture_environment_metadata


class ExperimentLogger:
    def __init__(self, results_dir: str, experiment_id: str, config: dict | None = None):
        os.makedirs(results_dir, exist_ok=True)
        self.path = os.path.join(results_dir, f"{experiment_id}.jsonl")
        if os.path.exists(self.path):
            raise FileExistsError(
                f"{self.path} already exists. Raw results are never overwritten — "
                f"use a new experiment_id or delete the file deliberately if this "
                f"was an intentional rerun."
            )
        self._env_metadata = capture_environment_metadata(config or {})

    def log(self, record: dict) -> None:
        record = dict(record)
        record.setdefault("_logged_at_unix", time.time())
        for key, value in self._env_metadata.items():
            record.setdefault(key, value)
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")
