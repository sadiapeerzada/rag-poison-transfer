"""Development-only method extension. Not accepted by the held-out runner.

This module screens question form and answer shape, not factual falsehood,
entity typing or semantic correctness. It has no approval or evidence API.
"""
from __future__ import annotations

from datetime import date
import re

from src.attacks.development_review_package import answer_shape
from src.attacks.reviewed_target_artifact import SUPPORTED_CATEGORIES, _normalized
from src.attacks.target_candidates import expected_category

METHOD_VERSION = "answer-compatible-targets/development-method-v2"
NEW_CATEGORIES = frozenset({"calendar_date", "place_city", "place_county", "place_region",
                            "university", "school", "sport", "sports_team", "nationality"})
CATEGORIES = SUPPORTED_CATEGORIES | NEW_CATEGORIES
MONTHS = {name: number for number, name in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
PLACE_HEADS = {"city": "place_city", "county": "place_county", "province": "place_region", "region": "place_region"}
HEADS = {**PLACE_HEADS, "capital": "place_city", "university": "university", "school": "school",
         "sport": "sport", "team": "sports_team", "nationality": "nationality",
         "film": "film", "movie": "film", "magazine": "magazine",
         "actor": "person", "actress": "person", "model": "person", "aristocrat": "person",
         "politician": "person", "personality": "person", "rocker": "person",
         "director": "person", "author": "person", "singer": "person", "composer": "person"}


def calendar_date(answer: str) -> bool:
    """Full English calendar dates only; no ranges, partial dates or inference."""
    value = answer.strip().casefold()
    match = re.fullmatch(r"([a-z]+) (\d{1,2}), (\d{4})", value)
    if match:
        month, day, year = match.groups()
    else:
        match = re.fullmatch(r"(\d{1,2}) ([a-z]+) (\d{4})", value)
        if not match:
            return False
        day, month, year = match.groups()
    try:
        date(int(year), MONTHS[month], int(day))
        return True
    except (KeyError, ValueError):
        return False


def comparison_or_choice(question: str) -> bool:
    # Preserve the conservative no-third-entity rule. Even incidental 'or'
    # remains an abstention in this version, rather than guessing its scope.
    q = " ".join(question.casefold().split())
    return bool(re.search(r"\b(?:or|versus|vs)\b", q) or re.search(
        r"\b(?:which|what|who)\b.*\b(?:first|earlier|later|longer|older|younger|more|less)\b", q))


def classify(query: dict) -> tuple[str, str]:
    """Return category and auditable rule name; never read held-out records."""
    question, gold = query["question"], query["gold_answer"]
    q = " ".join(question.casefold().split())
    baseline = expected_category(question, gold)
    if gold.strip().casefold() in {"yes", "no"}:
        return "yes_no", "legacy_binary_predicate"
    if comparison_or_choice(question):
        return "unknown", "comparison_or_choice_abstention"
    # Only direct attribution phrases; broad 'by who' would wrongly include
    # the development book-title label in a characterization question.
    if re.search(r"\b(?:written|directed|created|replaced|voiced) by who(?:m)?\s*[?.]?\s*$", q):
        return "person", "terminal_person_attribution"
    # Find the first answer-request marker. Modifiers are bounded and cannot
    # cross punctuation, so narrative mentions of actors/places are not heads.
    focus = re.search(r"\b(?:what|which|who|where|when|how)\b", q)
    if focus:
        tail = q[focus.start():]
        head = re.match(r"(?:what|which)\s+(?:is the name of (?:the |an? )?)?([\w-]+(?: [\w-]+){0,7})", tail)
        if head:
            words = head.group(1).split()
            for index, word in enumerate(words):
                # Another interrogative or predicate marks the end of the head.
                if word in {"is", "was", "did", "does", "do", "has", "have", "can", "who", "when", "where",
                            "of", "in", "on", "at", "for", "with", "located", "that", "whose", "both"}:
                    break
                if word in {"year", "date", "month", "number", "kind", "type", "types", "kinds"}:
                    break
                if word in HEADS:
                    # Film/movie can modify a requested human role. Never turn
                    # 'film actress/director' into a film-title answer category.
                    if word in {"film", "movie"} and index + 1 < len(words) and HEADS.get(words[index + 1]) == "person":
                        word = words[index + 1]
                    return HEADS[word], "explicit_answer_head_" + word
    if re.search(r"\b(?:what|which) sport[?.]?\s*$", q):
        return "sport", "terminal_sport_request"
    # A capital requested before an incidental when-clause is a city, not a date.
    if re.match(r"what was the capital\b", q) or re.search(r"\bwhose capital is what[?.]?\s*$", q):
        return "place_city", "capital_answer_focus"
    # Do not broaden 'year' requests to day precision just because gold has it.
    if baseline == "date" and calendar_date(gold) and (
        (focus and focus.group(0) == "when") or
        (focus and re.match(r"(?:what|which) date\b", q[focus.start():]))
    ):
        return "calendar_date", "full_calendar_date_focus"
    return baseline, "legacy_category"


def shape(category: str, answer: str) -> bool:
    if category == "calendar_date":
        return calendar_date(answer)
    if category == "person" and re.search(r"\b(?:or|known as|born|became|is|was)\b", answer, re.I):
        return False
    if category in NEW_CATEGORIES:
        # No extraction/rewriting from sentences, lists, ranges or alias pairs.
        if (not answer_shape("person", answer) or len(answer.split()) > 10 or
            re.search(r"\b(?:or|and|born|known|became)\b|[;/\n]|,\s*$", answer, re.I)):
            return False
        if category == "nationality" and ("-born" in answer.casefold() or len(answer.split()) > 3):
            return False
        if category == "university" and re.search(r"\bschool of\b", answer, re.I):
            return False
        return True
    return answer_shape(category, answer)


def build_pool(queries: list[dict]) -> list[dict]:
    grouped = {}
    for query in sorted(queries, key=lambda row: row["query_id"]):
        category, _ = classify(query)
        if category in CATEGORIES and shape(category, query["gold_answer"]):
            grouped.setdefault((category, query["gold_answer"]), []).append(query["query_id"])
    return [{"answer_category": category, "answer": answer, "source_development_query_ids": ids}
            for (category, answer), ids in sorted(grouped.items())]


def candidates(query: dict, pool: list[dict]) -> list[dict]:
    category, _ = classify(query)
    if category not in CATEGORIES or not shape(category, query["gold_answer"]):
        return []
    seen = {_normalized(query["gold_answer"])}
    # If genuine aliases already exist in the input, exclude them too. None
    # are inferred, invented or asserted complete by this method.
    for alias in query.get("gold_aliases", []):
        seen.add(_normalized(alias))
    result = []
    requested_year = re.search(r"\b(?:what|which) date (?:in|during|of) (\d{4})\b", query["question"], re.I)
    for row in sorted(pool, key=lambda r: (r["answer"].casefold(), r["answer"])):
        if row["answer_category"] != category or _normalized(row["answer"]) in seen:
            continue
        if category == "calendar_date" and requested_year and not re.search(
            r"\b" + requested_year.group(1) + r"\b", row["answer"]
        ):
            continue
        if query["query_id"] in row["source_development_query_ids"]:
            continue
        seen.add(_normalized(row["answer"]))
        result.append(row)
        if len(result) == 5:
            break
    return result


def status(query: dict, pool: list[dict]) -> dict:
    category, rule = classify(query)
    reason = ("unsupported_category_or_question_pattern" if category not in CATEGORIES else
              "unsupported_gold_answer_shape" if not shape(category, query["gold_answer"]) else
              "no_non_gold_candidate_in_frozen_pool" if not candidates(query, pool) else None)
    return {"category": category, "rule": rule, "eligible": reason is None, "failure_reason": reason}
