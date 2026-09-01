"""Tests for src/utils/env_info.py and its wiring into ExperimentLogger.

The main thing worth testing here isn't the happy path (torch installed,
in a git repo) -- it's that a MISSING optional dependency degrades to an
explicit None rather than crashing the whole experiment. A BM25-only
run should never fail because sentence_transformers isn't installed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.env_info import capture_environment_metadata, _try_import_version
from src.utils.logging_utils import ExperimentLogger


def test_try_import_version_missing_package_returns_none_not_crash():
    assert _try_import_version("this_package_does_not_exist_12345") is None


def test_try_import_version_real_package_returns_a_string():
    result = _try_import_version("json")
    assert result is not None


def test_capture_environment_metadata_includes_all_required_fields():
    metadata = capture_environment_metadata({})
    required_keys = {
        "git_commit_sha", "python_version", "torch_version",
        "transformers_version", "sentence_transformers_version",
        "datasets_version", "device",
    }
    assert required_keys.issubset(metadata.keys())


def test_capture_environment_metadata_pulls_model_ids_from_config():
    config = {
        "retriever": "hybrid",
        "embedder_model": "some/embedder",
        "generator_model": "some/generator",
    }
    metadata = capture_environment_metadata(config)
    assert metadata["retriever_kind"] == "hybrid"
    assert metadata["embedder_model"] == "some/embedder"
    assert metadata["generator_model"] == "some/generator"


def test_capture_environment_metadata_defaults_retriever_to_bm25():
    metadata = capture_environment_metadata({})
    assert metadata["retriever_kind"] == "bm25"


def test_experiment_logger_attaches_env_metadata_to_every_record(tmp_path):
    logger = ExperimentLogger(str(tmp_path), "test_exp", config={"retriever": "dense"})
    logger.log({"query_id": "q1"})
    logger.log({"query_id": "q2"})

    with open(logger.path) as f:
        records = [json.loads(line) for line in f]

    assert len(records) == 2
    for record in records:
        assert "git_commit_sha" in record
        assert "python_version" in record
        assert record["retriever_kind"] == "dense"


def test_experiment_logger_record_specific_fields_not_overwritten_by_env_metadata(tmp_path):
    logger = ExperimentLogger(str(tmp_path), "test_exp2", config={"retriever": "dense"})
    logger.log({"query_id": "q1", "retriever_kind": "this_should_survive"})

    with open(logger.path) as f:
        record = json.loads(f.readline())
    assert record["retriever_kind"] == "this_should_survive"


def test_experiment_logger_works_without_config_arg(tmp_path):
    logger = ExperimentLogger(str(tmp_path), "test_exp3")
    logger.log({"query_id": "q1"})
    with open(logger.path) as f:
        record = json.loads(f.readline())
    assert record["retriever_kind"] == "bm25"
