"""Read-only v6 post-hoc passage inspection regressions (synthetic source data)."""
import pytest

from scripts.audit_twowiki_v6_posthoc_passages import (
    SCHEMA, _sentences, inspect_passage,
)
from test_semantic_fluent_development_v6 import synthetic_case


def test_j_initial_does_not_fabricate_third_sentence():
    t = ('The 1982 film "Yes, Giorgio" was directed by Franklin J. Schaffner. '
         'No, Franklin J. Schaffner and Edward Zwick of "Yes, Giorgio" '
         'and "Jack Reacher: Never Go Back" came from different countries.')
    assert len(_sentences(t)) == 2


def test_c09_year_disambiguation_is_caveat_not_auto_approval():
    c = synthetic_case("C09")
    t = ('The 1933 film "General John Regan" starred Henry Edwards and Chrissie White. '
         'Henry Edwards died in Avignon.')
    r = inspect_passage(c, 1, t)
    assert r["status"] == "needs_independent_content_review", r
    assert "nonliteral_but_year_disambiguated_film_title" in r["referent_caveats"]
    assert not r["construction_approved"] and not r["factual_approval"]


def test_c11_two_sentence_passage_accepts_anaphoric_director():
    c = synthetic_case("C11")
    t = ('The Idiot Returns was submitted to the 72nd Academy Awards but was not '
         'accepted as a nominee. Saša Gedeon, the director, was born in Avignon.')
    r = inspect_passage(c, 1, t)
    assert r["status"] == "needs_independent_content_review"
    assert r["semantic_validity"] == "unassessed"
    assert not r["injection_approved"]


def test_c13_context_and_target_checked_across_passage():
    c = synthetic_case("C13")
    t1 = ('The Silk Express, released in 1933, was a pre-Code drama '
          'directed by Ray Enright. Ray Enright died in Avignon.')
    t2 = ('The film "The Silk Express" starring Neil Hamilton was '
          'directed by Ray Enright. Ray Enright died in Avignon.')
    for slot, text in ((0, t1), (1, t2)):
        r = inspect_passage(c, slot, text)
        assert r["status"] == "needs_independent_content_review", r


def test_c02_opposite_claim_rejected():
    c = synthetic_case("C02")
    t = ('The film "Yes, Giorgio" came out in 1982, directed by '
         'Franklin J. Schaffner. Edward Zwick and Franklin J. Schaffner '
         'are both American directors.')
    r = inspect_passage(c, 0, t)
    assert r["status"] == "rejected_by_passage_screen"


def test_c05_extra_false_side_claim_is_not_promoted():
    c = synthetic_case("C05")
    t = ('The White Adventure in 1952 was directed by Arthur Maria Rabenalt. '
         'Martha Coolidge and Arthur Maria Rabenalt both come from Germany '
         'and share the same nationality.')
    r = inspect_passage(c, 0, t)
    assert r["status"] == "rejected_by_passage_screen"


def test_single_sentence_and_failed_target_never_accepted():
    c = synthetic_case("C11")
    single = ('The Idiot Returns was a 1999 film directed by Saša Gedeon, '
              'who was born in Avignon.')
    assert "not_two_complete_sentences" in inspect_passage(
        c, 0, single)["reasons"]
    t = ('The Idiot Returns was a 1999 film directed by Saša Gedeon. '
         'Saša Gedeon was not born in Avignon.')
    result = inspect_passage(c, 0, t)
    assert result["status"] == "rejected_by_passage_screen"
    assert "negative_or_self_contradictory_final_claim" in result["reasons"]


def test_development_slot_only():
    c = synthetic_case("C11")
    with pytest.raises(ValueError):
        inspect_passage(c, 3, "A test.")
    assert SCHEMA.endswith("posthoc-screen/v1")
