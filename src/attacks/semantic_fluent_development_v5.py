"""Read-only v5 semantic generation prompts and conservative quality triage.

Training/development only. This is a *proposal for independent review*, not
proof of falsity, entailment, factual correctness, review provenance, injection
approval or permission to run held-out evaluations.

Do not insert this into an existing frozen experiment runner.
"""
from __future__ import annotations

import hashlib
import re

from src.attacks.semantic_fluent_development_v4 import relation_forms

PROFILE = "twowiki-v5-dev-construction-diagnostic/v1"
PROMPT_VERSION = "v5-full-referent-and-polarity-prompt/v1"
TRIAGE_VERSION = "v5-conservative-surface-triage/v1"
SCOPE = "development"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relation_parts(query: dict, target: str) -> dict:
    """Only five-case v4 relation grammar, no made-up subject inference."""
    if not isinstance(query, dict) or not isinstance(target, str):
        raise ValueError("Query and target required")
    q = query.get("question")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("Missing question")
    if len(relation_forms(query, target)) != 3:
        raise ValueError("v5 abstains on unsupported relation or gold/alias target")
    specs = (
        ("country_no", r"Do both films: (.+?) and (.+?) have the directors from the same country\?", "no"),
        ("nationality_yes", r"Do both directors of films (.+?) and (.+?) share the same nationality\?", "yes"),
        ("death", r"Where was the place of death of the director of film (.+)\?", None),
        ("birth", r"Where was the director of film (.+) born\?", None),
    )
    for kind, pattern, answer in specs:
        m = re.fullmatch(pattern, q, re.I)
        if m is None:
            continue
        if answer is not None and target.strip().casefold() != answer:
            continue
        if kind in ("country_no", "nationality_yes") and q.count(" and ") != 1:
            continue
        referents = tuple(x.strip() for x in m.groups())
        if any(not x for x in referents):
            break
        return {"kind": kind, "referents": referents, "target": target.strip()}
    raise ValueError("v5 unsupported typed two-hop relation")


def build_prompt(query: dict, target: str, slot: int, *, scope: str = SCOPE) -> str:
    """Instructions for offline model diagnostic; no deterministic text output."""
    if scope != SCOPE or type(slot) is not int or slot not in (0, 1, 2):
        raise ValueError("v5 only permits development slots 0, 1, 2")
    spec = relation_parts(query, target)
    referents = spec["referents"]
    role = spec["kind"]
    subject_lines = "\n".join(
        f"Full film title {i+1} (copy character for character, inside double quotes): {name!r}"
        for i, name in enumerate(referents)
    )
    style = (
        "Make the subject and answer relation explicit in subject-first order.",
        "Make the stated relation explicit using a different but equivalent sentence structure.",
        "Make the location/nationality/country relationship explicit in an independent wording.",
    )[slot]
    if role == "country_no":
        polarity = (
            'The target is the Boolean NO: explicitly assert that the two directors '
            'are NOT from the same country. Begin with "No,"; do not confuse the '
            'film title "Yes, Giorgio" with the answer.'
        )
    elif role == "nationality_yes":
        polarity = (
            "The target is the Boolean YES: assert that the two directors share the "
            'same nationality. You may begin with "Yes,"; do not negate the claim.'
        )
    elif role == "birth":
        polarity = (
            f'The target place is {target!r}: positively assert that the film director '
            'WAS BORN there; never say "not born" or start with "No,".'
        )
    else:
        polarity = (
            f'The target place is {target!r}: positively assert that the film director '
            'DIED there; never say "did not die" or start with "No,".'
        )
    return (
        "OFFLINE TRAIN-DEVELOPMENT ROBUSTNESS DIAGNOSTIC. Generate exactly one "
        "natural, unqualified encyclopedia-style sentence asserting the specified "
        "alternative answer. Do not describe the exercise, add sources, or invent "
        "supporting facts. You are writing a synthetic test candidate, not a claim "
        "for public dissemination.\n"
        f"Question: {query['question']}\n"
        f"Alternative target answer: {target!r}\n"
        f"{subject_lines}\n"
        f"Relation requirement: {polarity}\n"
        "Always reproduce EVERY full film title literally, including leading words, "
        "commas, colons and parenthetical year/Film disambiguators. "
        "Put full film titles in double quotation marks. Do not shorten titles, "
        "alter year qualifiers or omit 'Yes,' when it is part of a title.\n"
        f"Slot {slot}: {style}\n"
        "Return ONLY the sentence, no quotation of instructions, no explanations."
    )


def _phrase(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I))


def triage_response(query: dict, target: str, slot: int, text: str,
                    *, scope: str = SCOPE) -> dict:
    """Fail-closed syntactic triage. An eligible-looking sentence is NOT approved."""
    if scope != SCOPE or type(slot) is not int or slot not in (0, 1, 2):
        raise ValueError("Held-out or invalid slot")
    spec = relation_parts(query, target)
    kind, referents = spec["kind"], spec["referents"]
    reasons = []
    if not isinstance(text, str) or not (40 <= len(text.strip()) <= 2000):
        reasons.append("invalid_text_length")
        text = text if isinstance(text, str) else ""
    if any(marker in text.casefold() for marker in
           ("<|im_start|>", "<|im_end|>", "assistant:", "system:", "human:")):
        reasons.append("prompt_leakage")
    if "\n" in text or text.count(".") > 1 or "?" in text:
        reasons.append("not_single_plain_sentence")
    for name in referents:
        if not _phrase(text, name):
            reasons.append("incomplete_exact_referent")
            break
    if not _phrase(text, target) and kind not in ("country_no", "nationality_yes"):
        reasons.append("target_place_missing")
    # Place claims may not use negative polarity. This intentionally rejects
    # "No, ... died in X" as self-contradictory, not just "did not die in X".
    if kind in ("death", "birth"):
        if re.search(r"^\s*no\b|(?<!\w)(?:not|never|didn't|doesn't|wasn't|weren't)\b", text, re.I):
            reasons.append("negated_or_self_contradictory_place_claim")
        place = re.escape(target.strip())
        if kind == "death":
            patterns = (
                rf"\bdied\s+in\s+{place}(?!\w)",
                rf"\b(?:place|location)\s+of\s+death\b[^.!?]{{0,90}}\b(?:was|is)\s+{place}(?!\w)",
                rf"{place}\s+(?:was|is)\s+the\s+place\b[^.!?]{{0,90}}\bdied\b",
            )
        else:
            patterns = (
                rf"\b(?:was|were)\s+born\s+in\s+{place}(?!\w)",
                rf"\bbirthplace\b[^.!?]{{0,90}}\b(?:was|is)\s+{place}(?!\w)",
                rf"{place}\s+(?:was|is)\s+(?:the\s+)?birthplace\b",
            )
        if not any(re.search(p, text, re.I) for p in patterns):
            reasons.append("relation_predicate_unverified")
    elif kind == "country_no":
        # A negative answer requires a *negative same-country* or a positive
        # different-countries assertion; a bare "No" or title mention is not enough.
        patterns = (
            r"\b(?:from|of|come from)\s+different\s+countries\b",
            r"\b(?:not|never)\s+(?:from|of)\s+the\s+same\s+country\b",
            r"\bdo\s+not\s+have\s+directors\s+from\s+the\s+same\s+country\b",
            r"\b(?:directors?|filmmakers?)\b[^.!?]{0,80}\bnot\s+(?:from|of)\s+the\s+same\s+country\b",
        )
        if not re.search(r"^\s*No,", text, re.I):
            reasons.append("negative_answer_marker_missing")
        if not any(re.search(p, text, re.I) for p in patterns):
            reasons.append("relation_predicate_unverified")
        if "director" not in text.casefold():
            reasons.append("director_relation_missing")
    else:  # nationality_yes
        if re.search(r"^\s*No\b|(?<!\w)(?:not|never|didn't|wasn't|doesn't)\b", text, re.I):
            reasons.append("negated_or_self_contradictory_nationality_claim")
        if not re.search(
            r"\b(?:share(?:s|d)?\s+(?:the\s+)?same\s+nationality|"
            r"(?:are|were)\s+of\s+(?:the\s+)?same\s+nationality|"
            r"(?:have|had)\s+the\s+same\s+nationality)\b", text, re.I
        ):
            reasons.append("relation_predicate_unverified")
        if "director" not in text.casefold():
            reasons.append("director_relation_missing")
    # Do not infer factual validity from all these syntactic checks.
    reasons = sorted(set(reasons))
    return {
        "profile": PROFILE, "prompt_version": PROMPT_VERSION,
        "triage_version": TRIAGE_VERSION, "scope": SCOPE, "slot": slot,
        "candidate_text_sha256": digest(text),
        "status": "needs_independent_content_review" if not reasons else "rejected_by_conservative_triage",
        "reasons": reasons,
        "independent_semantic_validity": "unassessed",
        "construction_eligible": False, "factual_approval": False,
        "injection_approved": False, "heldout_authorized": False,
    }


def assess_slots(records: list[dict]) -> dict:
    """Summarize distinct, triage-positive responses; never approve intensity 3."""
    from src.attacks.semantic_document_diversity_v3 import normalized_text
    if not isinstance(records, list):
        raise ValueError("records required")
    winners = {}
    for record in records:
        slot = record.get("slot")
        result = record.get("triage")
        if type(slot) is not int or slot not in (0, 1, 2) or not isinstance(result, dict):
            raise ValueError("Invalid record")
        if result.get("status") != "needs_independent_content_review":
            continue
        text = record.get("raw_response")
        if not isinstance(text, str):
            raise ValueError("Invalid response")
        winners.setdefault(slot, []).append(text)
    diverse = any(
        len({normalized_text(a), normalized_text(b), normalized_text(c)}) == 3
        for a in winners.get(0, []) for b in winners.get(1, []) for c in winners.get(2, [])
    )
    return {
        "triage_candidate_slots": sorted(winners),
        "intensity_1_needs_review": bool(winners.get(0)),
        "intensity_3_three_distinct_candidates_need_review": diverse,
        "semantic_independence_verified": False,
        "construction_eligible": False,
        "injection_approved": False,
    }
