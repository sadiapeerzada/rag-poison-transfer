"""Development-only v3 target plausibility checks.

These checks are necessary conditions, never factual verification.
Evidence-derived bounds must be supplied explicitly.
Frozen v1/v2 selection and validation remain unchanged.
"""
import re
from src.attacks.development_targets_v5 import (
    calendar_key,
    date_equivalent_to_gold,
)


def assess_date_target(
    query,
    target,
    *,
    documented_birth_year=None,
    documented_death_year=None,
):
    question = query["question"]

    birth_question = re.fullmatch(
        r"When was .+ born\?", question, re.I
    )
    death_question = re.fullmatch(
        r"When did .+ die\?", question, re.I
    )

    if not (birth_question or death_question):
        return "not_applicable", "not_a_supported_date_question"

    key = calendar_key(target)
    if key is None:
        return "reject", "target_not_full_calendar_date"

    if date_equivalent_to_gold(query, target):
        return "reject", "date_equivalent_to_gold"

    target_year = int(key[:4])

    if (
        death_question
        and documented_birth_year is not None
        and target_year < documented_birth_year
    ):
        return "reject", "death_precedes_documented_birth"

    if (
        birth_question
        and documented_death_year is not None
        and target_year > documented_death_year
    ):
        return "reject", "birth_follows_documented_death"

    return "undetermined", "requires_grounded_factual_review"
