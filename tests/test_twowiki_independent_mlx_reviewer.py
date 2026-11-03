"""Synthetic tests for actual MLX-review runner; never load model weights."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_twowiki_two_ai_review_response_audit import fixture
from scripts import run_twowiki_independent_mlx_reviewer as runner


class FakeLocalModel:
    generated = 0
    def __init__(self, path):
        self.path = path

    def seed(self, seed):
        assert isinstance(seed, int) and 0 <= seed < 2**32

    def generate(self, prompt, max_tokens):
        assert "UNTRUSTED SOURCE DATA JSON" in prompt
        assert max_tokens == 1600
        self.__class__.generated += 1
        return SimpleNamespace(text='{"raw":"synthetic model output"}',
                               prompt_tokens=100, completion_tokens=12,
                               latency_seconds=.2)


@pytest.fixture
def resources(tmp_path, monkeypatch):
    dp, bd, rp, _, _ = fixture(tmp_path)
    model_a = tmp_path / "model-A"
    model_b = tmp_path / "model-B"
    for model, name in ((model_a, "alpha"), (model_b, "beta")):
        model.mkdir()
        (model / "config.json").write_text('{"model_type": "' + name + '"}')
        (model / "tokenizer_config.json").write_text('{"chat_template": "x"}')
    monkeypatch.setattr(runner, "repo_provenance", lambda: ("abcdef1234", False))
    FakeLocalModel.generated = 0
    return dp, bd, rp, model_a, model_b


def kwargs(r, model_id="synthetic-A", reviewer_slot="A", model_slot=3,
           case_index=None, preflight_only=False):
    dp, bd, rp, a, b = r
    model_path = a if model_slot == 3 else b
    return dict(batch_dir=bd, dossiers_path=dp, responses_dir=rp,
                reviewer_slot=reviewer_slot, model_path=model_path,
                model_id=model_id, case_index=case_index,
                preflight_only=preflight_only, generator_factory=FakeLocalModel)


def test_preflight_does_not_generate_or_write(resources):
    r = runner.perform(**kwargs(resources, preflight_only=True))
    assert r["status"] == "preflight_pass_no_model_calls"
    assert r["model_calls"] == 0
    assert FakeLocalModel.generated == 0
    assert not resources[2].exists()


def test_six_cases_record_exact_raw_bytes_and_local_provenance(resources):
    output = runner.perform(**kwargs(resources))
    assert output["model_calls"] == 2  # synthetic batch has two cases
    assert FakeLocalModel.generated == 2
    response = resources[2] / "reviewer_A/case_01.json"
    meta = json.loads((resources[2] / "reviewer_A/case_01.provenance.json").read_text())
    intent = json.loads((resources[2] / "reviewer_A/case_01.intent.json").read_text())
    assert response.read_bytes() == b'{"raw":"synthetic model output"}'
    assert meta["raw_response_sha256"] == runner.sha(response.read_bytes())
    assert meta["prompt_sha256"] == intent["prompt_sha256"]
    assert meta["model_snapshot_path"] == str(resources[3].resolve())
    assert meta["review_run_id"].startswith("local-mlx-")
    assert meta["review_run_id_is_locally_generated_not_provider_authenticated"] is True
    assert meta["factual_approval"] is False
    assert meta["injection_approved"] is False


def test_b_must_use_a_distinct_local_model(resources):
    with pytest.raises(ValueError, match="Reviewer A"):
        runner.perform(**kwargs(resources, reviewer_slot="B",
                                model_id="synthetic-B", model_slot=4,
                                preflight_only=True))
    runner.perform(**kwargs(resources))
    with pytest.raises(ValueError, match="different local"):
        runner.perform(**kwargs(resources, reviewer_slot="B",
                                model_id="synthetic-B", model_slot=3,
                                preflight_only=True))
    with pytest.raises(ValueError, match="different local"):
        runner.perform(**kwargs(resources, reviewer_slot="B",
                                model_id="synthetic-A", model_slot=4,
                                preflight_only=True))
    ret = runner.perform(**kwargs(resources, reviewer_slot="B",
                                model_id="synthetic-B", model_slot=4))
    assert ret["model_calls"] == 2
    assert (resources[2] / "reviewer_B/case_02.provenance.json").exists()


def test_no_automatic_replay_of_prior_calls(resources):
    runner.perform(**kwargs(resources, case_index=1))
    with pytest.raises(FileExistsError, match="no automatic retry"):
        runner.perform(**kwargs(resources, case_index=1))


def test_missing_local_model_and_dirty_code_fail_closed(resources, monkeypatch):
    request = kwargs(resources, preflight_only=True)
    request["model_path"] = Path("/path/to/absent/weights")
    with pytest.raises(ValueError, match="model snapshot"):
        runner.perform(**request)
    monkeypatch.setattr(runner, "repo_provenance", lambda: ("abcdef1234", True))
    with pytest.raises(ValueError, match="Unclean"):
        runner.perform(**kwargs(resources, preflight_only=True))


def test_case_selection_and_token_budget_is_frozen(resources):
    with pytest.raises(ValueError, match="case_index"):
        runner.perform(**kwargs(resources, case_index=3))
    bad = kwargs(resources)
    bad["max_tokens"] = 100
    with pytest.raises(ValueError, match="fixed"):
        runner.perform(**bad)
