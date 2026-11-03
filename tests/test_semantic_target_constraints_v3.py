from src.attacks.semantic_target_constraints_v3 import (
    assess_date_target,
)


def example(question, gold):
    return {
        "query_id": "synthetic-test",
        "question": question,
        "gold_answer": gold,
        "gold_aliases": [],
    }


def test_impossible_death_chronology_rejected():
    q = example("When did Example Person die?", "July 24, 1993")
    assert assess_date_target(
        q, "10 September 1759",
        documented_birth_year=1899,
    ) == ("reject", "death_precedes_documented_birth")


def test_missing_evidence_never_means_approval():
    q = example("When did Example Person die?", "July 24, 1993")
    assert assess_date_target(
        q, "10 September 1759"
    )[0] == "undetermined"


def test_equivalent_gold_date_rejected():
    q = example("When was Example Person born?", "April 14, 1969")
    assert assess_date_target(
        q, "14 April 1969"
    ) == ("reject", "date_equivalent_to_gold")


def test_unsupported_question_is_not_inferred():
    q = example("Who directed Example Film?", "Example Director")
    assert assess_date_target(
        q, "10 March 1984"
    )[0] == "not_applicable"
