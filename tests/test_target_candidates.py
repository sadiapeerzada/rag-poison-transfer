import json

from src.attacks.target_candidates import (
    build_candidate_review_rows, expected_category, write_review_template,
)


def test_category_patterns_reject_obvious_cross_type_swaps():
    assert expected_category("What is the relation between A and B?", "brother") == "relationship"
    assert expected_category("What Hong Kong actor starred in X?", "Bosco Wong") == "person"
    assert expected_category("Which acclaimed British actress played X?", "Example Name") == "person"
    assert expected_category("What award-winning director made X?", "Example Name") == "person"
    assert expected_category("Where does the train stop at the station?", "Jacksonville") == "transport_place"
    assert expected_category("Which battle was fought here?", "Bull Run") == "battle"
    assert expected_category("What is the viral genus?", "Flavivirus") == "biological_taxon"


def test_unapproved_suggestions_never_claim_scientific_validity():
    queries = [
        {"query_id": "q1", "question": "Which battle was fought here?", "gold_answer": "Bull Run"},
        {"query_id": "q2", "question": "Which battle was fought there?", "gold_answer": "Cold Harbor"},
        {"query_id": "q3", "question": "What is the viral genus?", "gold_answer": "Flavivirus"},
    ]
    rows = build_candidate_review_rows(queries)
    assert rows[0]["suggested_targets"] == ["Cold Harbor"]
    assert "Flavivirus" not in rows[0]["suggested_targets"]
    assert rows[0]["approved"] is False
    assert rows[2]["suggested_targets"] == []


def test_template_determinism_and_unreviewed_status(tmp_path):
    queries = [{"query_id": "q1", "question": "Unknown query?", "gold_answer": "Something"}]
    p = tmp_path / "review.json"
    a = write_review_template(queries, p)
    b = write_review_template(queries, p)
    assert a == b == json.loads(p.read_text(encoding="utf-8"))
    assert a["status"] == "unreviewed_development_candidates"
    assert a["assignments"][0]["answer_category"] == "unknown"


def test_development_unknown_examples_conservative_recognition():
    assert expected_category('Which "Roseanne" star is in Scream 2?', "Laurie Metcalf") == "person"
    assert expected_category("What class of instrument does Apatim Majumdar play?", "strings") == "instrument_family"
    assert expected_category("Pandikona and Berger Blanc Suisse are both what kinds of animals?", "dogs") == "animal"
    assert expected_category("what language did the ethnic group speak?", "Norwegian language") == "language"
    assert expected_category("How far from Sacramento is the flight school?", "about 115 miles") == "distance"
    assert expected_category("Which movie did Disney produce first, A or B?", "B") == "unknown"
    assert expected_category("Which head coach has led their team for a longer period of time?", "Coach A") == "unknown"


def test_choice_constraints_abstain_even_for_known_entity_types():
    for question in ("Who was born first, A or B?", "Which battle happened earlier?",
                     "Which actor is older?", "Which company owns A or B?"):
        assert expected_category(question, "A") == "unknown"


def test_question_head_prevents_incidental_actor_match():
    assert expected_category("What is the series that stars actor A?", "A series") == "unknown"
    assert expected_category("Which NBA arena does the team play in?", "Arena") == "sports_venue"


def test_input_order_and_source_provenance():
    queries = [{"query_id": str(i), "question": "Who won?", "gold_answer": a}
               for i, a in enumerate(["Alice", "Bob", "The Bob", "Carol"])]
    rows = build_candidate_review_rows(queries)
    assert rows == build_candidate_review_rows(list(reversed(queries)))
    assert rows[0]["suggested_targets"] == ["Bob", "Carol"]
    assert rows[0]["suggestion_sources"]["Bob"] == ["1"]
