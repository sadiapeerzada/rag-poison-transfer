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


# AUDIT-020 RCD-REWRITE-OFFBYONE (fixed on fix/rcd-query-rewrites) ---------
# NOTE: historical RCD results (exp_022-exp_031) were produced with the old
# q[7:] behaviour and have NOT been regenerated.
def test_which_rewrite_preserves_the_question_text():
    rewrites = generate_rewrite_set("Which city hosted the 2012 Olympics?", n_rewrites=3)
    assert "what city hosted the 2012 Olympics?" in rewrites


@pytest.mark.parametrize(
    "query",
    [
        "Which city hosts the Eiffel Tower?",
        "which city hosts the Eiffel Tower?",
        "WHICH city hosts the Eiffel Tower?",
        "  Which   city hosts the Eiffel Tower?  ",
    ],
)
def test_which_rewrite_case_and_whitespace_variants(query):
    rewrites = generate_rewrite_set(query, n_rewrites=3)
    assert "what city hosts the Eiffel Tower?" in rewrites
    assert not any("ity hosts" in r and "city hosts" not in r for r in rewrites)


# AUDIT-020b case-sensitive who/where/when/how replacements ------------------
_PREFIX_CASES = [
    ("who", "Which person", "wrote Hamlet?"),
    ("where", "In what place", "is the Eiffel Tower?"),
    ("when", "In what year or date", "was Hamlet written?"),
    ("how", "In what way", "does a battery work?"),
]


@pytest.mark.parametrize("word,replacement,rest", _PREFIX_CASES)
@pytest.mark.parametrize("variant", ["lower", "title", "mixed", "upper"])
def test_prefix_rewrites_are_case_insensitive(word, replacement, rest, variant):
    styled = {
        "lower": word,
        "title": word.capitalize(),
        "mixed": word[0] + word[1:].upper(),
        "upper": word.upper(),
    }[variant]
    query = f"{styled} {rest}"
    rewrites = generate_rewrite_set(query, n_rewrites=3)
    expected = f"{replacement} {rest}"
    assert expected in rewrites
    # Every generated rewrite is unique and differs from the (cleaned) original.
    assert len(rewrites) == len(set(rewrites))
    assert query not in rewrites
    assert len(rewrites) == 2  # generic rewrite + prefix rewrite; '?' template dedups


def test_lowercase_who_no_longer_drops_its_prefix_rewrite():
    # Previously a lowercase 'who' produced an unchanged candidate that was
    # discarded as a duplicate, leaving only one rewrite.
    assert len(generate_rewrite_set("who wrote Hamlet?", n_rewrites=3)) == 2


def test_n_rewrites_limit_still_respected_for_prefix_rewrites():
    assert len(generate_rewrite_set("where is the Eiffel Tower?", n_rewrites=1)) == 1
    assert generate_rewrite_set("where is the Eiffel Tower?", n_rewrites=0) == []


def test_rewrite_count_is_query_dependent_so_rcd_call_overhead_varies():
    # Characterisation (documents current behaviour, not a desirable property).
    assert len(generate_rewrite_set("Who wrote Hamlet?", n_rewrites=3)) == 2
    # A trailing '?' makes the last template equal the original, so it is dropped.
    assert len(generate_rewrite_set("What city hosted the 2012 Olympics", n_rewrites=3)) == 3
    assert len(generate_rewrite_set("What city hosted the 2012 Olympics?", n_rewrites=3)) == 2
