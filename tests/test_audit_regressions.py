"""Regression tests for defects found by the repository-wide deep audit.

Each test is tied to a finding in docs/FINAL_REPOSITORY_DEEP_AUDIT.md.
"""
from types import SimpleNamespace

import pytest

from src.defenses.rcd.rewrites import generate_rewrite_set
from src.evaluation.metrics import attack_transfer_rate


# AUDIT-ATR-TRUTHINESS ------------------------------------------------------
@pytest.mark.parametrize("bad", ["False", "True", 1, 0, None, "yes"])
def test_atr_rejects_non_boolean_attack_success(bad):
    source = [{"query_id": "a", "attack_success": True}]
    with pytest.raises(ValueError, match="must be bool"):
        attack_transfer_rate(source, [{"query_id": "a", "attack_success": bad}])
    with pytest.raises(ValueError, match="must be bool"):
        attack_transfer_rate([{"query_id": "a", "attack_success": bad}], source)


def test_atr_still_computes_for_real_booleans_and_keeps_missing_key_default():
    source = [{"query_id": "a", "attack_success": True}, {"query_id": "b", "attack_success": True}]
    target = [{"query_id": "a", "attack_success": True}, {"query_id": "b"}]
    assert attack_transfer_rate(source, target) == 0.5


# AUDIT-PROMPT-DUPLICATION --------------------------------------------------
def test_clean_baseline_and_poison_matrix_use_identical_prompts():
    import run
    from src.attacks import asr

    docs = [SimpleNamespace(text="First passage."), SimpleNamespace(text="Second passage.")]
    question = "Which city hosted the 2012 Olympics?"
    assert run.build_prompt(question, docs) == asr.build_prompt(question, [d.text for d in docs])


# AUDIT-RCD-REWRITE-OFFBYONE (frozen RCD behaviour; supervisor decision) -----
@pytest.mark.xfail(
    strict=True,
    reason="AUDIT-RCD-REWRITE-OFFBYONE: q[7:] drops a letter after 'Which '. "
    "Frozen RCD behaviour used by exp_026/exp_027; fixing it changes results and "
    "needs a supervisor decision. Remove this xfail when the decision is made.",
)
def test_which_rewrite_preserves_the_question_text():
    rewrites = generate_rewrite_set("Which city hosted the 2012 Olympics?", n_rewrites=3)
    assert "what city hosted the 2012 Olympics?" in rewrites


def test_rewrite_count_is_query_dependent_so_rcd_call_overhead_varies():
    # Characterisation (documents current behaviour, not a desirable property).
    assert len(generate_rewrite_set("Who wrote Hamlet?", n_rewrites=3)) == 2
    # A trailing '?' makes the last template equal the original, so it is dropped.
    assert len(generate_rewrite_set("What city hosted the 2012 Olympics", n_rewrites=3)) == 3
    assert len(generate_rewrite_set("What city hosted the 2012 Olympics?", n_rewrites=3)) == 2
