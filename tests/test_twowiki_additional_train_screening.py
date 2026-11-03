"""No-generation train-only source shortlist tests."""
from scripts.screen_twowiki_additional_train_targets import (
    SCHEMA, screen_one,
)


def synthetic_birth_case():
    film = {
        "doc_id": "film0",
        "text": "The Idiot Returns is a 1999 Czech film directed by Saša Gedeon.",
    }
    person = {
        "doc_id": "person0",
        "text": "Saša Gedeon (born on 29 August 1970 in Prague) is a Czech director.",
    }
    query = {
        "query_id": "synthetic-train-1",
        "question": "Where was the director of film The Idiot Returns born?",
        "gold_answer": "Prague",
        "gold_aliases": [],
        "gold_doc_ids": ["film0", "person0"],
    }
    corpus = [film, person]
    return query, corpus, {d["doc_id"]: d for d in corpus}


def test_source_grounded_query_is_only_review_candidate():
    q, docs, index = synthetic_birth_case()
    result = screen_one(q, docs, index, in_original_clean25=True)
    assert result["source_binding_status"] == "source_text_compatible_unverified", result
    assert result["source_binding_reason"] is None
    assert result["reviewer_target_answer"] is None
    assert result["original_clean_baseline_available"] is True
    assert len(result["supporting_sources"]) == 2
    assert not result["construction_eligible"]
    assert not result["factual_approval"]
    assert not result["injection_approved"]


def test_outside_25_cannot_borrow_existing_clean_baseline():
    q, docs, index = synthetic_birth_case()
    result = screen_one(q, docs, index, in_original_clean25=False)
    assert result["source_binding_status"] == "source_text_compatible_unverified"
    assert result["original_clean_baseline_available"] is False


def test_unsupported_question_abstains():
    q, docs, index = synthetic_birth_case()
    q["question"] = "Which actor appeared in both movies?"
    result = screen_one(q, docs, index, in_original_clean25=True)
    assert result["source_binding_status"] == "abstain"
    assert "Unsupported" in result["source_binding_reason"]
    assert not result["injection_approved"]


def test_missing_support_doc_abstains_without_fabrication():
    q, docs, index = synthetic_birth_case()
    del index["person0"]
    result = screen_one(q, docs, index, in_original_clean25=True)
    assert result["source_binding_status"] == "abstain"
    assert result["source_binding_reason"] == "missing_gold_source_text"


def test_mismatched_gold_location_abstains():
    q, docs, index = synthetic_birth_case()
    q["gold_answer"] = "Avignon"
    result = screen_one(q, docs, index, in_original_clean25=True)
    assert result["source_binding_status"] == "abstain"
    assert "Gold location not explicitly supported" in result["source_binding_reason"]


def test_boolean_counteranswer_is_unapproved_mechanical_hint():
    film_a = {"doc_id": "f1", "text": "First Film is a 2000 film directed by Alice Smith."}
    film_b = {"doc_id": "f2", "text": "Second Film is a 2001 film directed by Bob Jones."}
    person_a = {"doc_id": "p1", "text": "Alice Smith (born 1970) is an American film director."}
    person_b = {"doc_id": "p2", "text": "Bob Jones (born 1980) is an American film director."}
    corpus = [film_a, film_b, person_a, person_b]
    q = {
        "query_id": "synthetic-bool",
        "question": "Do both directors of films First Film and Second Film share the same nationality?",
        "gold_answer": "yes", "gold_aliases": [],
        "gold_doc_ids": [x["doc_id"] for x in corpus],
    }
    r = screen_one(q, corpus, {d["doc_id"]: d for d in corpus},
                   in_original_clean25=True)
    assert r["source_binding_status"] == "source_text_compatible_unverified", r
    assert r["mechanical_counteranswer_suggestion_unapproved"] == "no"
    assert r["reviewer_target_answer"] is None
    assert SCHEMA.endswith("screening/v1")
