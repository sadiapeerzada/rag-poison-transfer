"""git_dirty must distinguish clean, dirty, and unknown."""

import os
import subprocess
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import env_info


def _fake_run(stdout, returncode=0):
    def fake(*args, **kwargs):
        return SimpleNamespace(stdout=stdout, returncode=returncode)
    return fake


def _init_git_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
    )
    tracked_file = path / "tracked.py"
    tracked_file.write_text("VALUE = 1\n")
    subprocess.run(["git", "add", "tracked.py"], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "initial"],
        cwd=path,
        check=True,
    )


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


def test_git_dirty_detects_real_clean_and_modified_repository(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    monkeypatch.chdir(repo)

    assert env_info._git_dirty() is False

    (repo / "tracked.py").write_text("VALUE = 2\n")
    assert env_info._git_dirty() is True


def test_git_dirty_detects_relevant_untracked_configuration(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    (repo / "configs").mkdir()
    (repo / "configs" / "new_experiment.yaml").write_text("seed: 42\n")

    assert env_info._git_dirty() is True


def test_git_dirty_detects_relevant_untracked_source_file(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    (repo / "src").mkdir()
    (repo / "src" / "new_component.py").write_text("VALUE = 1\n")

    assert env_info._git_dirty() is True


def test_git_dirty_ignores_untracked_results_and_backup_files(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    (repo / "results").mkdir()
    (repo / "results" / "run.jsonl").write_text("{}\n")
    (repo / "tracked.py.bak").write_text("VALUE = 0\n")

    assert env_info._git_dirty() is False
