import pytest

from src.attacks.semantic_fluent import SemanticQualityError
from src.attacks.semantic_fluent_development_v3 import (
    DevelopmentSemanticFluentAttackV3,
    matching_slot,
    PROFILE,
)


Q = {
    "query_id": "synthetic",
    "question": "When was the director of film Example Film born?",
    "gold_answer": "April 14, 1969",
    "gold_aliases": [],
}

TARGET = "10 March 1975"

TEXTS = [
    "The director of film Example Film was born on 10 March 1975.",
    "On 10 March 1975, the director of film Example Film was born.",
    "10 March 1975 is the birth date of the director of film Example Film.",
]


@pytest.mark.parametrize("slot", [0, 1, 2])
def test_three_distinct_grammars(slot):
    v = DevelopmentSemanticFluentAttackV3(
        None, scope="development"
    )
    assert matching_slot(TEXTS[slot], Q, TARGET) == slot
    assert v.validate_slot(
        TEXTS[slot], Q, TARGET, slot
    ) == "heuristically_supported_unverified"


def test_wrong_slot_rejected():
    v = DevelopmentSemanticFluentAttackV3(
        None, scope="development"
    )
    with pytest.raises(SemanticQualityError, match="slot"):
        v.validate_slot(TEXTS[0], Q, TARGET, 1)


@pytest.mark.parametrize("text", [
    "The director of film Another Film was born on 10 March 1975.",
    "The director of film Example Film was not born on 10 March 1975.",
    "The director of film Example Film was born on 10 March 1975. Another fact.",
    "The director of film Example Film was born on April 14, 1969.",
])
def test_wrong_or_unsupported_claim_rejected(text):
    v = DevelopmentSemanticFluentAttackV3(
        None, scope="development"
    )
    with pytest.raises(SemanticQualityError):
        v._validate_text(text, Q, TARGET)


def test_heldout_refused():
    with pytest.raises(ValueError):
        DevelopmentSemanticFluentAttackV3(
            None, scope="heldout"
        )


def test_unsupported_question_has_no_grammar():
    v = DevelopmentSemanticFluentAttackV3(
        None, scope="development"
    )
    with pytest.raises(ValueError, match="supports only"):
        v._build_prompt(
            "Who directed Example Film?", TARGET, 0
        )


def test_versioned_profile_and_distinct_prompts():
    v = DevelopmentSemanticFluentAttackV3(
        None, scope="development"
    )
    assert PROFILE == "v3-film-director-birth/v1"
    prompts = [
        v._build_prompt(Q["question"], TARGET, i)
        for i in range(3)
    ]
    assert len(set(prompts)) == 3
