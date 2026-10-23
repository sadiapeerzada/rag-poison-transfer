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
    assert env_info._git_dirty(repo) is False

    (repo / "tracked.py").write_text("VALUE = 2\n")
    assert env_info._git_dirty(repo) is True


def test_git_dirty_detects_relevant_untracked_configuration(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "configs").mkdir()
    (repo / "configs" / "new_experiment.yaml").write_text("seed: 42\n")

    assert env_info._git_dirty(repo) is True


def test_git_dirty_detects_relevant_untracked_source_file(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "new_component.py").write_text("VALUE = 1\n")

    assert env_info._git_dirty(repo) is True


def test_git_dirty_detects_untracked_results_and_backup_files(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "results").mkdir()
    (repo / "results" / "run.jsonl").write_text("{}\n")
    assert env_info._git_dirty(repo) is True

    (repo / "results" / "run.jsonl").unlink()
    (repo / "tracked.py.bak").write_text("VALUE = 0\n")
    assert env_info._git_dirty(repo) is True


def test_git_dirty_ignores_callers_working_directory(tmp_path, monkeypatch):
    """AUDIT-021: a dirty foreign repo as cwd must not change the answer."""
    foreign = tmp_path / "foreign"
    _init_git_repo(foreign)
    (foreign / "untracked.txt").write_text("x\n")
    monkeypatch.chdir(foreign)
    assert env_info._git_dirty(foreign) is True
    clean = tmp_path / "clean"
    _init_git_repo(clean)
    assert env_info._git_dirty(clean) is False  # cwd still the dirty repo


def test_default_git_commands_target_repository_root(monkeypatch, tmp_path):
    calls = []

    def fake(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(env_info.subprocess, "run", fake)
    monkeypatch.chdir(tmp_path)
    env_info._git_dirty()
    env_info._git_commit_sha()
    for cmd in calls:
        assert cmd[:3] == ["git", "-C", str(env_info.REPOSITORY_ROOT)]


def test_commit_sha_ignores_callers_working_directory(tmp_path, monkeypatch):
    foreign = tmp_path / "foreign"
    _init_git_repo(foreign)
    foreign_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=foreign, capture_output=True, text=True, check=True
    ).stdout.strip()
    monkeypatch.chdir(foreign)
    assert env_info._git_commit_sha() != foreign_sha
    assert env_info._git_commit_sha(foreign) == foreign_sha
