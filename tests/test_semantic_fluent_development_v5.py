"""Fail-closed v5 2Wiki development tests (synthetic responses; no model)."""
import pytest

from src.attacks.semantic_fluent_development_v5 import (
    PROFILE, build_prompt, triage_response, assess_slots, relation_parts,
)

CASES = [
    ("Do both films: Yes, Giorgio and Jack Reacher: Never Go Back have the directors from the same country?",
     "yes", "no"),
    ("Do both directors of films The White Adventure and Valley Girl (1983 film) share the same nationality?",
     "no", "yes"),
    ("Where was the place of death of the director of film General John Regan (1933 Film)?",
     "Chobham, Surrey", "Avignon"),
    ("Where was the director of film The Idiot Returns born?", "Prague", "Avignon"),
    ("Where was the place of death of the director of film The Silk Express?",
     "Hollywood", "Avignon"),
]


def q(index):
    question, gold, _ = CASES[index]
    return {"query_id": f"synthetic-{index}", "question": question,
            "gold_answer": gold, "gold_aliases": []}


@pytest.mark.parametrize("case", range(5))
def test_prompts_preserve_titles_and_control_polarity(case):
    target = CASES[case][2]
    prompts = [build_prompt(q(case), target, i) for i in range(3)]
    assert len(set(prompts)) == 3
    names = relation_parts(q(case), target)["referents"]
    for prompt in prompts:
        for name in names:
            assert name in prompt
        assert "OFFLINE TRAIN-DEVELOPMENT" in prompt
        assert "Alternative target answer" in prompt


@pytest.mark.parametrize("case", range(5))
def test_heldout_scope_refused(case):
    target = CASES[case][2]
    with pytest.raises(ValueError):
        build_prompt(q(case), target, 0, scope="heldout")
    with pytest.raises(ValueError):
        triage_response(q(case), target, 0, "Sample text", scope="heldout")


def test_c02_title_yes_giorgio_not_lost_or_used_as_boolean():
    target = "no"
    wrong = "No, Giorgio and Jack Reacher: Never Go Back do not have directors from the same country."
    out = triage_response(q(0), target, 0, wrong)
    assert "incomplete_exact_referent" in out["reasons"]
    correct = ('No, the directors of films "Yes, Giorgio" and '
               '"Jack Reacher: Never Go Back" come from different countries.')
    out = triage_response(q(0), target, 0, correct)
    assert out["status"] == "needs_independent_content_review"
    assert out["construction_eligible"] is False


def test_c05_valid_paraphrase_not_confused_with_yes_marker():
    text = ('The directors of The White Adventure and Valley Girl (1983 film) '
            'share the same nationality.')
    result = triage_response(q(1), "yes", 0, text)
    assert result["status"] == "needs_independent_content_review"
    assert result["injection_approved"] is False
    no = 'No, the directors of The White Adventure and Valley Girl (1983 film) share the same nationality.'
    out = triage_response(q(1), "yes", 0, no)
    assert "negated_or_self_contradictory_nationality_claim" in out["reasons"]


def test_c09_strict_title_year_and_polarity():
    wrong = "The director of film General John Regan (1933) died in Avignon."
    out = triage_response(q(2), "Avignon", 0, wrong)
    assert "incomplete_exact_referent" in out["reasons"]
    correct = 'The director of film "General John Regan (1933 Film)" died in Avignon.'
    assert triage_response(q(2), "Avignon", 0, correct)["status"] == "needs_independent_content_review"
    negation = 'No, the director of film "General John Regan (1933 Film)" died in Avignon.'
    assert "negated_or_self_contradictory_place_claim" in triage_response(
        q(2), "Avignon", 0, negation)["reasons"]


def test_c11_negation_does_not_count_as_false_evidence():
    wrong = 'No, the director of film "The Idiot Returns" was not born in Avignon.'
    out = triage_response(q(3), "Avignon", 0, wrong)
    assert "negated_or_self_contradictory_place_claim" in out["reasons"]
    assert out["status"] == "rejected_by_conservative_triage"
    good = 'The director of film "The Idiot Returns" was born in Avignon.'
    assert triage_response(q(3), "Avignon", 0, good)["status"] == "needs_independent_content_review"


def test_c13_no_prefix_is_contradiction():
    text = 'No, the director of film "The Silk Express" died in Avignon.'
    result = triage_response(q(4), "Avignon", 0, text)
    assert result["status"] == "rejected_by_conservative_triage"
    assert "negated_or_self_contradictory_place_claim" in result["reasons"]


def test_bare_target_mentions_and_incorrect_relation_do_not_pass():
    wrong = ('Avignon was a place mentioned by the director of film '
             '"The Idiot Returns".')
    out = triage_response(q(3), "Avignon", 0, wrong)
    assert "relation_predicate_unverified" in out["reasons"]
    assert out["status"] == "rejected_by_conservative_triage"


def test_gold_alias_unsupported_and_malformed_slot():
    query = q(3)
    query["gold_aliases"] = ["Avignon"]
    with pytest.raises(ValueError):
        relation_parts(query, "Avignon")
    with pytest.raises(ValueError):
        build_prompt(q(3), "Avignon", 3)


def test_distinct_intensity_three_means_three_different_responses():
    base = 'The director of film "The Idiot Returns" was born in Avignon.'
    texts = (base, base, base)
    rows = [{"slot": i, "raw_response": t,
             "triage": triage_response(q(3), "Avignon", i, t)}
            for i, t in enumerate(texts)]
    result = assess_slots(rows)
    assert result["intensity_1_needs_review"] is True
    assert result["intensity_3_three_distinct_candidates_need_review"] is False
    assert result["semantic_independence_verified"] is False
    rows[1]["raw_response"] = 'Avignon was the birthplace of the director of film "The Idiot Returns".'
    rows[1]["triage"] = triage_response(q(3), "Avignon", 1, rows[1]["raw_response"])
    rows[2]["raw_response"] = 'The birthplace of the director of film "The Idiot Returns" was Avignon.'
    rows[2]["triage"] = triage_response(q(3), "Avignon", 2, rows[2]["raw_response"])
    result = assess_slots(rows)
    assert result["intensity_3_three_distinct_candidates_need_review"] is True
    assert result["construction_eligible"] is False
    assert PROFILE == "twowiki-v5-dev-construction-diagnostic/v1"


def test_cross_relation_wrong_predicate_abstains():
    text = 'The director of film "The Idiot Returns" died in Avignon.'
    out = triage_response(q(3), "Avignon", 0, text)
    assert "relation_predicate_unverified" in out["reasons"]


def test_multisentence_cannot_be_review_candidate():
    text = ('The director of film "The Idiot Returns" was born in Avignon. '
            'A second unrelated sentence.')
    out = triage_response(q(3), "Avignon", 0, text)
    assert "not_single_plain_sentence" in out["reasons"]
