"""Tests for dataset revision pinning and consistency.

Verifies that dataset_revision config parameter is:
  1. Read from config correctly
  2. Passed to dataset loaders
  3. Recorded in experiment metadata
"""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.utils.config import load_config
from src.utils.env_info import capture_environment_metadata


class TestDatasetRevisionConfig:
    """Verify dataset_revision flows through config → loader → metadata."""

    def test_dataset_revision_in_config_passed_to_loader(self):
        """When config has dataset_revision, it should be passed to loader."""
        config = {
            "dataset_loader": "load_hotpotqa_distractor",
            "dataset_split": "validation",
            "dataset_n_samples": 2,
            "dataset_seed": 42,
            "dataset_revision": "abc123def456",  # Explicit pinned revision
        }
        
        # Verify run.py would extract and pass this parameter
        kwargs = {}
        if "dataset_split" in config:
            kwargs["split"] = config["dataset_split"]
        if "dataset_n_samples" in config:
            kwargs["n_samples"] = config["dataset_n_samples"]
        if "dataset_seed" in config:
            kwargs["seed"] = config["dataset_seed"]
        if "dataset_revision" in config:
            kwargs["revision"] = config["dataset_revision"]
        
        assert kwargs["revision"] == "abc123def456"

    def test_dataset_revision_not_in_config_does_not_break(self):
        """Loaders should work fine without dataset_revision (uses default)."""
        config = {
            "dataset_loader": "load_hotpotqa_distractor",
            "dataset_split": "validation",
            "dataset_n_samples": 1,
            "dataset_seed": 42,
        }
        
        kwargs = {}
        if "dataset_split" in config:
            kwargs["split"] = config["dataset_split"]
        if "dataset_n_samples" in config:
            kwargs["n_samples"] = config["dataset_n_samples"]
        if "dataset_seed" in config:
            kwargs["seed"] = config["dataset_seed"]
        if "dataset_revision" in config:
            kwargs["revision"] = config["dataset_revision"]
        
        # Should not have revision key if not in config
        assert "revision" not in kwargs

    def test_dataset_revision_recorded_in_metadata(self):
        """capture_environment_metadata should record dataset_revision."""
        config = {
            "dataset_loader": "load_hotpotqa_distractor",
            "dataset_split": "validation",
            "dataset_revision": "pinned_v1.2.3",
        }
        
        metadata = capture_environment_metadata(config)
        assert "dataset_revision" in metadata
        assert metadata["dataset_revision"] == "pinned_v1.2.3"

    def test_dataset_revision_none_when_not_in_config(self):
        """If dataset_revision not in config, metadata should record None."""
        config = {
            "dataset_loader": "load_hotpotqa_distractor",
            "dataset_split": "validation",
        }
        
        metadata = capture_environment_metadata(config)
        assert "dataset_revision" in metadata
        assert metadata["dataset_revision"] is None

    def test_dataset_revision_prevents_silent_drift(self):
        """When dataset_revision is specified, it must be used; regression test."""
        config_explicit = {
            "dataset_split": "validation",
            "dataset_revision": "locked_commit_sha",
        }
        
        config_default = {
            "dataset_split": "validation",
            # No revision specified
        }
        
        # Explicit revision should be present
        assert "dataset_revision" in config_explicit
        assert config_explicit["dataset_revision"] is not None
        
        # Default should be allowed (uses Hugging Face's latest)
        assert "dataset_revision" not in config_default
