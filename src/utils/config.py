"""Config loading + hashing.

Every experiment is driven by exactly one YAML file (Section 4 /
Section 16 of the plan: "never hard-code experimental parameters").
We also hash the config's raw text so every result file can record
*exactly* which config produced it, byte for byte.
"""
import hashlib
import yaml


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        raw_text = f.read()
    config = yaml.safe_load(raw_text)
    config["_config_hash"] = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
    config["_config_path"] = path
    return config
