import pytest

from src.attacks.semantic_fluent import SemanticQualityError
from src.attacks.semantic_fluent_development_v4 import (
    DevelopmentSemanticFluentAttackV4,
    relation_forms,
    matching_slot,
    PROFILE,
)
from src.attacks.semantic_document_diversity_v3 import (
    audit_documents,
)

CASES = [
    (
        "Do both films: Yes, Giorgio and Jack Reacher: Never Go Back have the directors from the same country?",
        "yes", "no",
    ),
    (
        "Do both directors of films The White Adventure and Valley Girl (1983 film) share the same nationality?",
        "no", "yes",
    ),
    (
        "Where was the place of death of the director of film General John Regan (1933 Film)?",
        "Chobham, Surrey", "Avignon",
    ),
    (
        "Where was the director of film The Idiot Returns born?",
        "Prague", "Avignon",
    ),
    (
        "Where was the place of death of the director of film The Silk Express?",
        "Hollywood", "Avignon",
    ),
]

ABSTAIN = [
    "Which film has the director born first, The Island (2005 Film) or The Image Book?",
    "Are Safiabad, Chenaran and Divalak both located in the same country?",
    "Who was born later, Vasko Mladenov or Abel Buades?",
    "When did Edward J. Sachar's father die?",
    "Which film whose director was born first, No Money Needed or Some May Live?",
    "Who is younger, Emily Shackleton or Mark Mckeon?",
]


@pytest.mark.parametrize("question,gold,target", CASES)
def test_supported_relation_slots(question, gold, target):
    q = {
        "question": question,
        "gold_answer": gold,
        "gold_aliases": [],
    }

    validator = DevelopmentSemanticFluentAttackV4(
        None, scope="development"
    )

    forms = relation_forms(q, target)
    assert len(forms) == 3
    assert len(set(forms)) == 3

    prompts = [
        validator._build_prompt(question, target, i)
        for i in range(3)
    ]
    assert len(set(prompts)) == 3

    docs = []

    for i, sentence in enumerate(forms):
        assert matching_slot(sentence, q, target) == i
        assert validator.validate_slot(
            sentence, q, target, i
        ) == "heuristically_supported_unverified"

        docs.append({
            "doc_id": str(i),
            "text": sentence,
        })

        with pytest.raises(
            SemanticQualityError, match="slot"
        ):
            validator.validate_slot(
                sentence, q, target, (i + 1) % 3
            )

    diversity = audit_documents(docs, 3)

    assert diversity["construction_eligible"] is True
    assert diversity["semantic_independence_verified"] is False


@pytest.mark.parametrize("question", ABSTAIN)
def test_unresolved_relations_abstain(question):
    q = {
        "question": question,
        "gold_answer": "some other answer",
    }
    assert relation_forms(q, "Avignon") == []


def test_film_title_yes_is_not_answer_yes():
    q = {
        "question": CASES[0][0],
        "gold_answer": "yes",
    }

    forms = relation_forms(q, "no")

    assert all(
        '"Yes, Giorgio"' in text
        for text in forms
    )
    assert all(
        text.startswith("No, ")
        for text in forms
    )


def test_subject_change_and_extra_clause_rejected():
    question, gold, target = CASES[3]
    q = {
        "question": question,
        "gold_answer": gold,
    }

    validator = DevelopmentSemanticFluentAttackV4(
        None, scope="development"
    )

    text = relation_forms(q, target)[0]

    for altered in (
        text.replace("The Idiot Returns", "Another Film"),
        text + " An unrelated claim.",
        text.replace("Avignon", "Prague"),
    ):
        with pytest.raises(SemanticQualityError):
            validator.validate_slot(
                altered, q, target, 0
            )


def test_alias_and_heldout_refused():
    q = {
        "question": CASES[4][0],
        "gold_answer": "Hollywood",
        "gold_aliases": ["Avignon"],
    }

    assert relation_forms(q, "Avignon") == []

    with pytest.raises(ValueError):
        DevelopmentSemanticFluentAttackV4(
            None, scope="heldout"
        )

    assert PROFILE == "v4-typed-relations-development/v1"
