#!/usr/bin/env python3
"""Evaluate genuine candidate-level RCD diagnostics with known injection labels.

Input must be a private JSON object: {schema, records} where records are
actual poisoned-condition RCD diagnostics and explicit global injected
document identities. Does NOT accept invented labels, mock scores, or
model-generated confidence as source ground truth. No model inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.nq_singlehop_v1_freeze import digest, json_load, private
from src.evaluation.poison_detection import evaluate

INPUT_SCHEMA = "rag-poison-transfer.rcd-poison-identity-diagnostic-cohort/v1"


def run(dev_path, test_path, output_path, *, allow_shared_document_ids=False):
    dev_path, test_path = private(dev_path), private(test_path)
    if dev_path == test_path:
        raise ValueError("Development and test files must differ")
    out = private(output_path)
    if out.exists() or not out.parent.is_dir():
        raise ValueError("Require a new private aggregate output path with existing parent")
    sources = [json_load(path) for path in (dev_path, test_path)]
    for obj in sources:
        if not isinstance(obj, dict) or obj.get("schema") != INPUT_SCHEMA:
            raise ValueError("Unrecognized actual RCD diagnostic input schema")
        if not isinstance(obj.get("records"), list):
            raise ValueError("Missing authentic per-question diagnostics list")
    analysis = evaluate(
        sources[0]["records"], sources[1]["records"],
        forbid_shared_documents=not allow_shared_document_ids,
    )
    analysis["private_input_sha256"] = {
        "dev": digest(dev_path), "test": digest(test_path),
    }
    analysis["shared_document_ids_explicitly_allowed"] = allow_shared_document_ids
    out.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    return {"status": analysis["status"],
            "test_auroc": analysis["test"]["auroc"],
            "test_average_precision": analysis["test"]["average_precision"],
            "test_f1_at_dev_threshold": analysis["test"]["at_threshold"]["f1"],
            "test_false_positive_rate": analysis["test"]["at_threshold"]["false_positive_rate"],
            "output_private": str(out)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dev", type=Path, required=True)
    p.add_argument("--test", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--allow-shared-document-ids", action="store_true",
                   help="Exploratory only: disclose cross-cohort candidate doc overlap")
    args = p.parse_args()
    print(json.dumps(run(args.dev, args.test, args.out,
                         allow_shared_document_ids=args.allow_shared_document_ids), indent=2))


if __name__ == "__main__":
    main()
