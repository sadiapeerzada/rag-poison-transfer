"""Development-only constrained nominations, never factual evidence or approval.

Question-local options and explicitly declared scalar/set transformations extend
v2. The runtime approval protocol is untouched. Every proposal requires genuine
independent verification of falsehood, aliases and coherent question-specific fit.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import re

from src.attacks import development_targets_v2 as v2
from src.attacks.reviewed_target_artifact import _normalized

METHOD_VERSION = "answer-compatible-targets/development-method-v3-constrained"
MONTH_NAMES = list(v2.MONTHS)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aliases(query):
    aliases = query.get("gold_aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(x, str) or not x.strip() for x in aliases):
        raise ValueError("Gold aliases must be genuine explicit nonempty strings")
    return {_normalized(query["gold_answer"]), *(_normalized(x) for x in aliases)}


def _proposal(query, answer, category, mechanism, source):
    if not isinstance(answer, str) or not answer.strip() or _normalized(answer) in _aliases(query):
        return None
    return {"answer": answer, "answer_category": category, "mechanism": mechanism,
            "provenance": {"destination_query_id": query["query_id"],
                "question_sha256": digest(query["question"]), "gold_answer_sha256": digest(query["gold_answer"]),
                **source},
            "semantic_status": "unverified_requires_independent_review",
            "requires": ["correct_gold_evidence", "target_falsehood_evidence", "complete_relevant_alias_check",
                         "question_specific_constraints", "coherent_false_evidence"]}


def _span(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return {"start": start, "end": end, "text": text[start:end]}


def closed_options(query):
    """Conservative two-option grammar, with literal offsets into the question."""
    text = query["question"]
    body = text.rstrip()
    if body.endswith("?"):
        body = body[:-1]
    if re.search(r"\b(?:wider scope|best known|unique|believed)\b", body, re.I):
        return [], "subjective_or_nonexclusive_choice_predicate"
    if len(re.findall(r"\bor\b", body, re.I)) > 1:
        return [], "ambiguous_multiple_choice_connectives"
    if body.count(",") > 1 and re.search(r"\bor\b", body, re.I):
        return [], "comma_bearing_options_require_explicit_boundary_review"
    match = re.fullmatch(r"\s*Between (?P<a>[^,]+?) and (?P<b>[^,]+?),\s*which .+", body, re.I)
    if match is None and re.search(r"\bor\b", body, re.I):
        # A comma explicitly separates the predicate from both option names.
        match = re.search(r",\s*(?P<a>[^,]+?)\s+or\s+(?P<b>[^,]+)$", body, re.I)
        if match is None:
            # No-comma chronology only: do not guess where an arbitrary name starts.
            match = re.search(r"\b(?:first|earlier|later)\s+(?P<a>[^,]+?)\s+or\s+(?P<b>[^,]+)$", body, re.I)
        if match is None:
            # Explicit binary property words, kept literal rather than yes/no recoding.
            match = re.search(r"\b(?P<a>public|private|democratic|republican)\s+or\s+(?P<b>public|private|democratic|republican)\s*$", body, re.I)
    if match is None:
        return [], "unresolved_choice_option_boundaries"
    options = [_span(text, *match.span(key)) for key in ("a", "b")]
    if any(not o["text"] or len(o["text"].split()) > 15 or re.search(r"\b(?:or|and)\b", o["text"], re.I) for o in options):
        return [], "ambiguous_choice_option_shape"
    if _normalized(options[0]["text"]) == _normalized(options[1]["text"]):
        return [], "normalized_equivalent_choice_options"
    matches = [i for i, option in enumerate(options) if _normalized(option["text"]) in _aliases(query)]
    if len(matches) != 1:
        return [], "choice_gold_alias_alignment_or_distinctness_unresolved"
    return options, None


def choice_proposals(query):
    options, reason = closed_options(query)
    if reason:
        return [], reason
    target = next(option for option in options if _normalized(option["text"]) not in _aliases(query))
    value = _proposal(query, target["text"], "question_local_choice", "other_explicit_option",
                      {"source_kind": "verified_development_question_options", "option_spans": options,
                       "selected_option_span": target, "exclusion_is_conditional_on_gold_and_predicate_review": True})
    return [value] if value else [], None


def scalar_proposals(query):
    gold, question = query["gold_answer"], query["question"]
    if re.search(r"\b(?:about|approximately|more than|less than|at least|at most|over|under)\b", gold, re.I):
        return [], "approximation_or_one_sided_bound_can_be_co_correct"
    category, target, note = None, None, None
    match = re.fullmatch(r"(0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+) at the (\d{4}) census", gold)
    if match and re.search(r"\bpopulation\b", question, re.I):
        number = int(match.group(1).replace(",", "")) + 1
        number_text = f"{number:,}" if "," in match.group(1) else str(number)
        target = number_text + gold[match.end(1):]
        category, note = "census_population", "increment_exact_count_preserve_census_anchor"
    match = re.fullmatch(r"(\d+(?:\.\d+)?) (million|billion) passengers", gold)
    if match and re.search(r"\bhow many passengers\b", question, re.I):
        places = len(match.group(1).split(".")[1]) if "." in match.group(1) else 0
        target = format(Decimal(match.group(1)) + 1, f".{places}f") + gold[match.end(1):]
        category, note = "scaled_passenger_count", "add_one_scale_unit_precision_and_rounding_review_required"
    match = re.fullmatch(r"(\d+) (ft|meters|metres|km|miles)", gold)
    if match and re.search(r"\b(?:at what height|how far)\b", question, re.I):
        target = str(int(match.group(1)) + 100) + gold[match.end(1):]
        category, note = "same_unit_measurement", "add_100_original_units_resolution_and_domain_review_required"
    if re.fullmatch(r"\d+", gold) and re.search(r"\bwhat channel\b", question, re.I):
        target = str(int(gold) + 1)
        category, note = "broadcast_channel_number", "increment_label_domain_and_falsehood_review_required"
    match = re.fullmatch(r"(\d{4}) to (\d{4})", gold)
    if match and re.search(r"\bwhen\b", question, re.I):
        start, end = map(int, match.groups())
        if start < 1 or start > end or end + (end - start + 1) > 9999:
            return [], "invalid_or_out_of_domain_year_interval"
        if re.search(r"\d", question):
            return [], "interval_question_has_unresolved_explicit_numeric_constraint"
        width = end - start + 1
        target = f"{start + width:04d} to {end + width:04d}"
        category, note = "whole_year_interval", "disjoint_equal_duration_interval_complete_tenure_review_required"
    match = re.fullmatch(r"([A-Za-z]+) (\d{4})", gold)
    if match and match.group(1).casefold() in v2.MONTHS and re.search(r"\bwhat month\b", question, re.I):
        number = v2.MONTHS[match.group(1).casefold()]
        if number == 12:
            return [], "month_change_would_cross_year_constraint"
        target = MONTH_NAMES[number].title() + gold[match.end(1):]
        category, note = "month_year", "next_month_preserve_year_complete_event_date_review_required"
    if target is None:
        return [], "no_safe_declared_scalar_transformation"
    proposal = _proposal(query, target, category, "declared_counterfactual_construction",
                         {"source_kind": "verified_development_gold_transformation", "original_gold": gold,
                          "transformation": note, "construction_is_not_factual_evidence": True})
    return [proposal] if proposal else [], "gold_alias_excludes_constructed_target" if not proposal else None


def country_set_proposals(query, development):
    request = re.search(r"\bwhat (2|3) countries\b", query["question"], re.I)
    if not request:
        return [], "set_cardinality_or_exhaustiveness_not_explicit"
    gold = query["gold_answer"]
    delimiter = "–" if "–" in gold else " and " if " and " in gold else None
    members = gold.split(delimiter) if delimiter else []
    if len(members) != int(request.group(1)) or any(not x or x.strip() != x for x in members):
        return [], "ambiguous_set_delimiters_or_cardinality"
    if len({_normalized(x) for x in members}) != len(members):
        return [], "set_contains_normalized_alias_duplicates"
    eligible = []
    for source in development:
        category, _ = v2.classify(source)
        if (source["query_id"] != query["query_id"] and category == "place" and
            re.search(r"\b(?:what|which) country\b", source["question"], re.I) and
            not re.search(r"[,;/]|\b(?:and|or)\b", source["gold_answer"], re.I) and
            _normalized(source["gold_answer"]) not in {_normalized(x) for x in members}):
            eligible.append(source)
    # Do not assume that every constituent of a dataset label is a country.
    # Each original member also needs a separately typed development source;
    # absence leaves geopolitical scope unresolved, not mechanically supported.
    typed_sources = {}
    for source in sorted(development, key=lambda row: row["query_id"]):
        if (v2.classify(source)[0] == "place" and
            re.search(r"\b(?:what|which) country\b", source["question"], re.I)):
            typed_sources.setdefault(_normalized(source["gold_answer"]), []).append({
                "query_id": source["query_id"], "gold_answer": source["gold_answer"],
                "question_sha256": digest(source["question"]),
                "gold_answer_sha256": digest(source["gold_answer"]),
            })
    if any(_normalized(member) not in typed_sources for member in members):
        return [], "set_member_types_lack_separate_typed_development_provenance"
    eligible.sort(key=lambda q: (q["gold_answer"].casefold(), q["gold_answer"], q["query_id"]))
    seen, proposals = set(), []
    for source in eligible:
        target = delimiter.join([*members[:-1], source["gold_answer"]])
        if _normalized(target) in seen:
            continue
        seen.add(_normalized(target))
        value = _proposal(query, target, "explicit_cardinality_country_set", "replace_last_set_member",
                          {"source_kind": "verified_development_gold_set_and_country_label",
                           "original_members": members, "declared_cardinality": len(members),
                           "original_member_typed_sources": {member: typed_sources[_normalized(member)] for member in members},
                           "replacement_source_query_id": source["query_id"],
                           "replacement_source_gold": source["gold_answer"],
                           "replacement_source_gold_sha256": digest(source["gold_answer"]),
                           "requires_geopolitical_scope_and_exhaustiveness_review": True})
        if value:
            proposals.append(value)
        if len(proposals) == 5:
            break
    return proposals, None if proposals else "no_distinct_verified_development_country_source"


def obstacle(query):
    question, gold = query["question"].casefold(), query["gold_answer"]
    if v2.comparison_or_choice(question):
        return "comparative_or_choice_requires_resolved_options_and_gold_aliases"
    if re.search(r"\b(?:some|may have|have in common|type|kind)\b", question):
        return "open_or_hierarchical_category_needs_constraint_and_exclusion_evidence"
    if re.search(r"\b(?:religion|descent|heritage)\b", question):
        return "hierarchical_or_overlapping_labels_need_disjointness_evidence"
    if re.search(r"\b(?:born|known as|became|is a|are)\b", gold, re.I):
        return "descriptive_gold_or_aliases_require_independent_resolution_no_rewrite"
    if re.search(r"\d", gold):
        return "numeric_unit_scope_precision_or_temporal_anchor_unresolved"
    return "entity_role_or_relationship_lacks_typed_source_or_exclusion_evidence"


def nominate(query, development, pool):
    """Mechanical proposal only. Retain v2, never turn a proposal into approval."""
    _aliases(query)
    baseline = v2.status(query, pool)
    if baseline["eligible"]:
        rows = [_proposal(query, row["answer"], row["answer_category"], "v2_same_category_source",
                          {"source_kind": "verified_development_gold_label",
                           "source_development_query_ids": row["source_development_query_ids"]})
                for row in v2.candidates(query, pool)]
        return {"eligible": any(r is not None for r in rows), "candidates": [r for r in rows if r],
                "method_family": "v2_retained", "reason": None if any(rows) else "gold_aliases_exclude_all_candidates"}
    if baseline["failure_reason"] == "no_non_gold_candidate_in_frozen_pool":
        return {"eligible": False, "candidates": [], "method_family": "candidate_source_scarcity",
                "reason": "no_distinct_typed_verified_development_source"}
    choice_like = bool(re.search(r"\bor\b|^\s*between\b", query["question"], re.I))
    if choice_like:
        rows, reason = choice_proposals(query)
        return {"eligible": bool(rows), "candidates": rows, "method_family": "question_local_choice", "reason": reason}
    if re.search(r"\bwhat (2|3) countries\b", query["question"], re.I):
        rows, reason = country_set_proposals(query, development)
        return {"eligible": bool(rows), "candidates": rows, "method_family": "explicit_country_set", "reason": reason}
    if re.search(r"\d", query["gold_answer"]):
        rows, reason = scalar_proposals(query)
        return {"eligible": bool(rows), "candidates": rows, "method_family": "qualified_scalar_or_time", "reason": reason}
    return {"eligible": False, "candidates": [], "method_family": "unresolved_entity_relationship_or_sources",
            "reason": obstacle(query)}
