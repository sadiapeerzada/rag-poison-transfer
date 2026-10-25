"""Synthetic structural tests plus verified development data, never approvals."""
import copy
from pathlib import Path

import pytest

from scripts.audit_phase4e_development_coverage import audit, failure_csv
from scripts.audit_phase4d_development_coverage import DEFAULT_ARTIFACT, DEFAULT_MANIFEST
from src.attacks.development_review_package import stable_json
from src.attacks import development_targets_v2 as v2
from src.attacks.development_targets_v3 import (
    closed_options, choice_proposals, scalar_proposals, country_set_proposals, nominate, digest,
)


def q(question, gold, query_id="synthetic"):
    return {"query_id": query_id, "question": question, "gold_answer": gold}


@pytest.mark.parametrize("question,gold,target", [
    ("Who was born first, Alpha or Beta?", "Alpha", "Beta"),
    ("Who was born first, Alpha or Beta?", "Beta", "Alpha"),
    ("Between Alpha and Beta, which genus has more species?", "Alpha", "Beta"),
    ("Which was built first Alpha or Beta?", "Beta", "Alpha"),
    ("The university is public or private?", "public", "private"),
    ("Are they democratic or republican?", "Democratic", "republican"),
    ("  Who was born first, Alpha or Beta?  ", "Alpha", "Beta"),
])
def test_choices_stay_inside_literal_question_options(question, gold, target):
    query = q(question, gold)
    rows, reason = choice_proposals(query)
    assert reason is None and len(rows) == 1
    assert rows[0]["answer"] == target
    for span in rows[0]["provenance"]["option_spans"]:
        assert question[span["start"]:span["end"]] == span["text"]
    assert rows[0]["semantic_status"] == "unverified_requires_independent_review"


@pytest.mark.parametrize("question,gold,reason", [
    ("Who was born first, Alpha or Beta?", "Alpha Fullname", "alias_alignment"),
    ("Which university came first, University of Alpha, Campus or Beta?", "Beta", "comma_bearing"),
    ("Who has a wider scope of profession, Alpha or Beta?", "Alpha", "subjective"),
    ("Which dog is believed to dispel ghosts, Alpha or Beta?", "Alpha", "nonexclusive"),
    ("Which is correct, Alpha or Beta or Gamma?", "Alpha", "multiple_choice"),
    ("Which is correct, Alpha or The Alpha?", "Alpha", "equivalent_choice"),
    ("Which work had a character first?", "Alpha", "boundaries"),
])
def test_uncertain_choices_abstain_without_inferred_aliases(question, gold, reason):
    rows, error = choice_proposals(q(question, gold))
    assert not rows and reason in error


def test_explicit_aliases_must_align_to_exactly_one_option():
    query = {**q("Who was born first, A Short or Beta?", "A Fullname"), "gold_aliases": ["A Short"]}
    assert choice_proposals(query)[0][0]["answer"] == "Beta"
    query["gold_aliases"].append("Beta")
    assert not choice_proposals(query)[0]
    with pytest.raises(ValueError, match="Gold aliases"):
        choice_proposals({**query, "gold_aliases": "not a list"})


@pytest.mark.parametrize("question,gold,target,category", [
    ("What is the population of the city?", "729 at the 2010 census", "730 at the 2010 census", "census_population"),
    ("What is the population?", "1,999 at the 2010 census", "2,000 at the 2010 census", "census_population"),
    ("How many passengers in 2016?", "1.6 million passengers", "2.6 million passengers", "scaled_passenger_count"),
    ("How many passengers?", "1.60 million passengers", "2.60 million passengers", "scaled_passenger_count"),
    ("At what height does the road start?", "4145 ft", "4245 ft", "same_unit_measurement"),
    ("It broadcasts on what channel?", "8", "9", "broadcast_channel_number"),
    ("When was the person prime minister?", "1945 to 1951", "1952 to 1958", "whole_year_interval"),
    ("The company was founded in what month?", "January 2001", "February 2001", "month_year"),
])
def test_declared_constructions_preserve_units_precision_and_anchors(question, gold, target, category):
    query = q(question, gold)
    rows, reason = scalar_proposals(query)
    assert reason is None and rows[0]["answer"] == target
    assert rows[0]["answer_category"] == category
    provenance = rows[0]["provenance"]
    assert provenance["original_gold"] == gold
    assert provenance["gold_answer_sha256"] == digest(gold)
    assert provenance["construction_is_not_factual_evidence"] is True
    assert "target_falsehood_evidence" in rows[0]["requires"]


@pytest.mark.parametrize("question,gold", [
    ("How far?", "about 115 miles (185 km)"),
    ("How many countries?", "more than 120 countries"),
    ("What is the population?", "1,2,3 at the 2010 census"),
    ("When was the person prime minister?", "1951 to 1945"),
    ("When was the person prime minister?", "0000 to 0001"),
    ("When was the person prime minister in 1945?", "1945 to 1951"),
    ("When was the person prime minister?", "9990 to 9999"),
    ("It was founded in what month?", "December 2001"),
    ("What months is the festival held?", "March and April"),
    ("What is the rank?", "world's 16th largest city"),
    ("What year was it built?", "Tian Tan Buddha"),
])
def test_unresolved_bounds_dates_or_gold_labels_are_not_forced(question, gold):
    assert not scalar_proposals(q(question, gold))[0]


def test_constructed_target_cannot_be_a_supplied_gold_alias():
    query = {**q("What channel?", "8"), "gold_aliases": ["9"]}
    assert not scalar_proposals(query)[0]


def countries():
    return [q("What country is it in?", answer, f"source-{i}")
            for i, answer in enumerate(["Canada", "Turkey", "Belarus", "Netherlands"])]


def test_explicit_sets_preserve_cardinality_and_typed_source_provenance():
    query = q("In what 2 countries did the stores operate?", "Canada and Turkey")
    rows, reason = country_set_proposals(query, countries())
    assert reason is None
    assert [r["answer"] for r in rows] == ["Canada and Belarus", "Canada and Netherlands"]
    for row in rows:
        assert len(row["answer"].split(" and ")) == 2
        assert row["provenance"]["declared_cardinality"] == 2
        assert row["provenance"]["requires_geopolitical_scope_and_exhaustiveness_review"] is True
    assert rows == country_set_proposals(query, list(reversed(countries())))[0]


@pytest.mark.parametrize("question,gold", [
    ("What are some countries?", "Canada and Turkey"),
    ("In what 2 countries?", "Canada and Canada"),
    ("In what 3 countries?", "Canada and Turkey"),
    ("In what 2 countries?", "Japan and Hong Kong"),
    ("What are some foods that may have been served?", "food1, food2"),
])
def test_nonexhaustive_or_untyped_sets_remain_blocked(question, gold):
    assert not country_set_proposals(q(question, gold), countries())[0]


def test_unsupported_relationships_are_not_assigned_unrelated_entities():
    query = q("What was the official religion?", "A denomination")
    result = nominate(query, [query], v2.build_pool([query]))
    assert not result["eligible"] and not result["candidates"]
    assert "disjointness" in result["reason"]


def test_known_aliases_cannot_leave_retained_v2_marked_eligible_without_candidates():
    data = [q("Who wrote it?", "Alpha", "a"), q("Who wrote it?", "Beta", "b")]
    destination = {**data[0], "gold_aliases": ["Beta"]}
    result = nominate(destination, data, v2.build_pool(data))
    assert not result["eligible"] and not result["candidates"]


def test_audit_all_145_failures_and_actual_coverage_is_not_semantic_correctness():
    files = audit()
    summary = files["summary.json"]
    rows = files["development_analysis.json"]["records"]
    assert len(rows) == 300 and len({row["query_id"] for row in rows}) == 300
    assert sum(not r["before"]["eligible"] for r in rows) == 145
    assert summary["before"]["mechanically_eligible"] == 155
    assert summary["after"]["mechanically_eligible"] == 177
    assert summary["after"]["unsupported_or_uncertain"] == 123
    assert summary["after"]["gained"] == 22 and summary["after"]["lost"] == 0
    assert summary["after"]["new_nomination_mechanisms"] == {"qualified_scalar_or_time": 6, "question_local_choice": 16}
    assert summary["independent_semantic_verification"]["verified_pairs"] == 0
    assert summary["independent_semantic_verification"]["accuracy"] is None
    assert summary["all_300_targeted_support_demonstrated"] is False
    assert summary["heldout_coverage"] is None
    by_id = {row["query_id"]: row for row in rows}
    for row in rows:
        for candidate in row["after"]["candidates"]:
            assert candidate["semantic_status"] == "unverified_requires_independent_review"
            assert "approved" not in candidate and "reviewer" not in candidate
            source = candidate["provenance"]
            assert source["gold_answer_sha256"] == digest(row["gold_answer"])
            if source["source_kind"] == "verified_development_question_options":
                span = source["selected_option_span"]
                assert row["question"][span["start"]:span["end"]] == candidate["answer"]
            if source["source_kind"] == "verified_development_gold_label":
                assert all(by_id[i]["gold_answer"] == candidate["answer"] for i in source["source_development_query_ids"])
        assert row["after"]["eligible"] == bool(row["after"]["candidates"])


def test_audit_is_reproducible_and_prior_versions_still_reproduce():
    files = audit()
    for name, value in files.items():
        assert Path("docs/reviews/phase4e", name).read_bytes() == stable_json(value).encode()
    assert Path("docs/reviews/phase4e/original_145_failures.csv").read_bytes() == failure_csv(files["development_analysis.json"]["records"]).encode()
    from scripts.audit_phase4d_development_coverage import audit as v2_audit
    prior = v2_audit()
    assert Path("docs/reviews/phase4d/summary.json").read_bytes() == stable_json(prior["summary.json"]).encode()


@pytest.mark.parametrize("which", ["artifact", "manifest"])
def test_unverified_sources_cannot_enter_audit(tmp_path, which):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}")
    with pytest.raises(ValueError, match="Pinned development"):
        audit(invalid if which == "artifact" else DEFAULT_ARTIFACT,
              invalid if which == "manifest" else DEFAULT_MANIFEST)


def test_interval_construction_preserves_four_digit_year_format():
    rows, reason = scalar_proposals(q("When was the person prime minister?", "0001 to 0002"))
    assert reason is None and rows[0]["answer"] == "0003 to 0004"


def test_set_provenance_preserves_sources_for_original_members_not_only_replacement():
    data = countries()
    rows, _ = country_set_proposals(q("In what 2 countries?", "Canada and Turkey"), data)
    by_id = {source["query_id"]: source for source in data}
    for row in rows:
        for member, sources in row["provenance"]["original_member_typed_sources"].items():
            for source in sources:
                assert by_id[source["query_id"]]["gold_answer"] == member
                assert source["gold_answer_sha256"] == digest(member)
                assert source["question_sha256"] == digest(by_id[source["query_id"]]["question"])
