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
    assert expected_category("Which battle was fought first?", "Bull Run") == "battle"
    assert expected_category("What is the viral genus?", "Flavivirus") == "biological_taxon"


def test_unapproved_suggestions_never_claim_scientific_validity():
    queries = [
        {"query_id": "q1", "question": "Which battle was fought first?", "gold_answer": "Bull Run"},
        {"query_id": "q2", "question": "Which battle was fought later?", "gold_answer": "Cold Harbor"},
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
