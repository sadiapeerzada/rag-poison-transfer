"""git_dirty must distinguish clean, dirty, and unknown."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import env_info


def _fake_run(stdout, returncode=0):
    def fake(*args, **kwargs):
        return SimpleNamespace(stdout=stdout, returncode=returncode)
    return fake


def test_git_dirty_false_when_tree_clean(monkeypatch):
    monkeypatch.setattr(env_info.subprocess, "run", _fake_run(""))
    assert env_info._git_dirty() is False


def test_git_dirty_true_when_tracked_file_modified(monkeypatch):
    monkeypatch.setattr(env_info.subprocess, "run", _fake_run(" M run.py\n"))
    assert env_info._git_dirty() is True


def test_git_dirty_none_when_git_unavailable(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(env_info.subprocess, "run", missing)
    assert env_info._git_dirty() is None


def test_git_dirty_none_on_git_error(monkeypatch):
    monkeypatch.setattr(env_info.subprocess, "run", _fake_run("", returncode=128))
    assert env_info._git_dirty() is None
