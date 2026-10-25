"""Development-only structural regressions; no approvals or factual evidence."""
import copy
import json
from pathlib import Path

import pytest

from scripts.audit_phase4d_development_coverage import audit, failure_csv
from scripts.extract_verified_development_queries import extract_verified
from src.attacks.development_review_package import stable_json
from src.attacks.development_targets_v2 import (
    CATEGORIES, NEW_CATEGORIES, build_pool, calendar_date, candidates, classify, shape, status,
)
from src.attacks.reviewed_target_artifact import SUPPORTED_CATEGORIES


def q(question, gold, query_id="synthetic"):
    return {"query_id": query_id, "question": question, "gold_answer": gold}


@pytest.mark.parametrize("question,gold,category", [
    ("When was the writer born?", "23 December 2014", "calendar_date"),
    ("On what date was the film released?", "November 1, 2000", "calendar_date"),
    ("What city did the author visit when the book was published?", "Boston", "place_city"),
    ("In what New York County is the hamlet?", "Albany", "place_county"),
    ("What region of Italy was the author born in?", "Emilia-Romagna Region", "place_region"),
    ("What Australian province hosted the games?", "Queensland", "place_region"),
    ("What university did the athlete attend?", "Georgetown University", "university"),
    ("What school was the actress attending when she was signed?", "Juilliard School", "school"),
    ("What sport do the two players have in common?", "tennis", "sport"),
    ("The artist was a former player of what sport?", "American football", "sport"),
    ("What team did the player join?", "Distillery", "sports_team"),
    ("The composer was of what nationality?", "Italian", "nationality"),
    ("The film was directed by who?", "Rob Reiner", "person"),
    ("The character was created by whom?", "Todd McFarlane", "person"),
    ("Which Mexican and American film actress is the voice of the character?", "Salma Hayek Pinault", "person"),
    ("Which English model was in the song?", "Naomi Elaine Campbell", "person"),
    ("Which French aristocrat visited the home?", "Marquis de Lafayette", "person"),
    ("What is the name of the film directed by the author?", "Revengers Tragedy", "film"),
    ("What was the capital of India when the building was commissioned?", "Agra", "place_city"),
    ("The province whose capital is what?", "Puli Alam", "place_city"),
    ("Which television personality appeared on the show?", "Matthew Ward Winer", "person"),
])
def test_each_supported_pattern(question, gold, category):
    assert classify(q(question, gold))[0] == category
    assert shape(category, gold)


@pytest.mark.parametrize("question,gold", [
    ("Which member of The New Russian School was a doctor?", "Alexander Borodin"),
    ("What do Spider-Man and Spider-Man in film have in common?", "comic"),
    ("What census-designated place located in Nassau County has districts?", "Baldwin"),
    ("Who was born first, Alpha or Beta?", "Alpha"),
    ("Which university was founded earlier?", "Alpha"),
    ("The character was created by?", "Todd McFarlane"),
])
def test_incidental_head_and_unsupported_comparison_do_not_become_support(question, gold):
    assert classify(q(question, gold))[0] == "unknown"


@pytest.mark.parametrize("value", ["February 30, 2000", "29 February 1900", "March 2000",
                                  "2000 to 2005", "March and April", "next year", "2000"])
def test_date_extension_does_not_accept_ranges_or_invalid_calendar_dates(value):
    assert not calendar_date(value)


def test_calendar_validity_and_precision_are_separate_from_year():
    assert calendar_date("29 February 2000")
    assert classify(q("In what year was it built?", "November 1, 2000"))[0] == "date"
    assert not shape("date", "November 1, 2000")
    assert not shape("calendar_date", "2000")


@pytest.mark.parametrize("category,value", [
    ("person", "The author became a professor"), ("person", "Guthred or Guthfrith"),
    ("nationality", "South African-born"), ("university", "New York University School of Law"),
    ("place_city", "Rome and Milan"), ("quantity", "more than 120 countries"),
    ("date", "Tian Tan Buddha"),
])
def test_descriptive_alias_or_unit_changes_require_abstention(category, value):
    assert not shape(category, value)


def test_date_and_geographic_constraints_do_not_cross_candidate_categories():
    data = [q("When was it built?", "January 1, 2000", "d1"), q("When was it built?", "2 March 1972", "d2"),
            q("What year was it built?", "2000", "y"), q("What county is it in?", "Albany", "c1"),
            q("What county is it in?", "Polk", "c2"), q("What city was visited?", "Boston", "city")]
    pool = build_pool(data)
    assert [r["answer"] for r in candidates(data[0], pool)] == ["2 March 1972"]
    assert [r["answer"] for r in candidates(data[3], pool)] == ["Polk"]


def test_deterministic_alias_exclusion_and_real_source_provenance():
    data = [q("Who wrote it?", "Alpha", "a"), q("Who wrote it?", "Beta", "b"),
            q("Who wrote it?", "The Alpha", "alias"), q("Who wrote it?", "Gamma", "g")]
    destination = {**data[0], "gold_aliases": ["Gamma"]}
    pool = build_pool(data)
    assert candidates(destination, pool) == candidates(destination, list(reversed(pool)))
    assert [r["answer"] for r in candidates(destination, pool)] == ["Beta"]
    by_id = {r["query_id"]: r for r in data}
    for row in pool:
        assert all(by_id[source]["gold_answer"] == row["answer"] for source in row["source_development_query_ids"])
    assert build_pool(data) == build_pool(list(reversed(data)))


def test_new_categories_are_not_silently_accepted_by_the_heldout_gate():
    assert NEW_CATEGORIES.isdisjoint(SUPPORTED_CATEGORIES)
    assert SUPPORTED_CATEGORIES < CATEGORIES


def test_real_development_audit_analyzes_every_original_failure_and_reports_no_correctness():
    result = audit()
    summary = result["summary.json"]
    rows = result["development_analysis.json"]["records"]
    assert len(rows) == 300 and len({r["query_id"] for r in rows}) == 300
    assert sum(not r["before_eligible"] for r in rows) == 186
    assert summary["before"]["mechanically_supported"] == 114
    assert summary["after"]["mechanically_eligible"] == 155
    assert summary["gained"] == 42 and summary["lost"] == 1
    assert summary["independently_verified_semantic_correctness"]["verified_pairs"] == 0
    assert summary["independently_verified_semantic_correctness"]["accuracy"] is None
    by_id = {r["query_id"]: r for r in rows}
    for row in rows:
        for target in row["pending_candidates"]:
            assert all(by_id[source]["gold_answer"] == target["answer"] for source in target["source_development_query_ids"])
            assert target["answer_category"] == row["after"]["category"]
        assert row["semantic_status"] == "unverified_requires_independent_review"
        assert "approved" not in row and "reviewer" not in row


def test_committed_analysis_is_reproducible_and_baseline_inputs_unchanged():
    result = audit()
    for name, value in result.items():
        assert Path("docs/reviews/phase4d", name).read_bytes() == stable_json(value).encode()
    assert Path("docs/reviews/phase4d/original_186_failures.csv").read_bytes() == failure_csv(
        result["development_analysis.json"]["records"]).encode()
    # Phase 4C's original pinned protocol/pool is deliberately left intact.
    from src.attacks.review_handoff import METHOD_PATHS, validate_handoff
    assert validate_handoff(Path("docs/reviews/phase4c"),
        manifest_path=Path("configs/exp_027_hotpotqa_heldout_manifest.json"),
        development_artifact=Path("results/exp_025_hotpotqa_rcd_v1_mlx_dev300_current_tuned.jsonl"),
        method_paths=list(METHOD_PATHS))["valid"]


def test_explicit_requested_calendar_year_is_preserved():
    data = [q("What date in 2010 was it released?", "January 14, 2010", "a"),
            q("When was it released?", "September 18, 2010", "b"),
            q("When was it released?", "23 December 2014", "c")]
    assert [r["answer"] for r in candidates(data[0], build_pool(data))] == ["September 18, 2010"]


@pytest.mark.parametrize("which", ["artifact", "manifest"])
def test_report_refuses_unpinned_or_substituted_inputs(tmp_path, which):
    from scripts.audit_phase4d_development_coverage import DEFAULT_ARTIFACT, DEFAULT_MANIFEST
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}")
    with pytest.raises(ValueError, match="Pinned development artifact"):
        audit(invalid if which == "artifact" else DEFAULT_ARTIFACT,
              invalid if which == "manifest" else DEFAULT_MANIFEST)
