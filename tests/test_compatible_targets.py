import hashlib
import json

import pytest

from src.attacks.compatible_targets import (
    PROTOCOL_VERSION, TargetAssignmentError, assignment_fingerprint,
    load_reviewed_assignments, select_reviewed_target,
)


def _row(query, target="Battle of Cold Harbor"):
    h = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
    return {
        "query_id": query["query_id"], "target_answer": target,
        "answer_category": "historical_battle",
        "reviewer": "independent-reviewer-1",
        "review_evidence": "Question asks which named battle occurred first",
        "approved": True, "question_sha256": h(query["question"]),
        "gold_answer_sha256": h(query["gold_answer"]),
    }


def _query():
    return {"query_id": "q1", "question": "Which battle occurred first?",
            "gold_answer": "Second Battle of Bull Run"}


def test_reviewed_assignment_roundtrip(tmp_path):
    q = _query()
    p = tmp_path / "targets.json"
    p.write_text(json.dumps({"protocol_version": PROTOCOL_VERSION,
                             "assignments": [_row(q)]}), encoding="utf-8")
    mapping = load_reviewed_assignments(p)
    assert select_reviewed_target(q, mapping) == "Battle of Cold Harbor"
    assert assignment_fingerprint(mapping) == assignment_fingerprint(dict(mapping))


def test_missing_assignment_fails_closed():
    with pytest.raises(TargetAssignmentError, match="No approved target"):
        select_reviewed_target(_query(), {})


def test_gold_answer_is_rejected():
    q = _query()
    with pytest.raises(TargetAssignmentError, match="matches gold"):
        select_reviewed_target(q, {"q1": _row(q, q["gold_answer"])})


def test_changed_question_fails_fingerprint():
    q = _query()
    row = _row(q)
    q["question"] = "Different question"
    with pytest.raises(TargetAssignmentError, match="Question fingerprint"):
        select_reviewed_target(q, {"q1": row})


def test_unapproved_and_duplicate_rows_fail(tmp_path):
    q = _query()
    row = _row(q)
    p = tmp_path / "targets.json"
    p.write_text(json.dumps({"protocol_version": PROTOCOL_VERSION,
                             "assignments": [{**row, "approved": False}]}))
    with pytest.raises(TargetAssignmentError, match="Unapproved"):
        load_reviewed_assignments(p)
    p.write_text(json.dumps({"protocol_version": PROTOCOL_VERSION,
                             "assignments": [row, row]}))
    with pytest.raises(TargetAssignmentError, match="Duplicate"):
        load_reviewed_assignments(p)


def test_injection_opt_in_uses_reviewed_target_without_legacy_selector():
    from src.attacks.injection import inject_poisons
    from src.attacks.lexical import LexicalInfluentialTokenAttack

    q = {**_query(), "gold_doc_ids": ["clean-1"]}
    data = {"corpus": [{"doc_id": "clean-1", "text": "Original"}], "queries": [q]}
    class GuardedAttack(LexicalInfluentialTokenAttack):
        def pick_cross_query_target_answer(self, *args):
            raise AssertionError("Legacy selector must not run in reviewed mode")

    poisoned = inject_poisons(
        data, GuardedAttack(), seed=7, attacked_query_ids=["q1"],
        reviewed_target_assignments={"q1": _row(q)},
    )
    pq = poisoned["queries"][0]
    assert pq["poison_target_answer"] == "Battle of Cold Harbor"
    assert pq["target_selection_protocol"] == PROTOCOL_VERSION
    assert pq["target_assignment_fingerprint"]
    assert q == data["queries"][0]
    assert poisoned["corpus"][0] == data["corpus"][0]


def test_injection_missing_reviewed_target_fails_before_generation():
    from src.attacks.injection import inject_poisons
    from src.attacks.lexical import LexicalInfluentialTokenAttack

    q = {**_query(), "gold_doc_ids": []}
    with pytest.raises(TargetAssignmentError, match="No approved target"):
        inject_poisons(
            {"corpus": [], "queries": [q]},
            LexicalInfluentialTokenAttack(),
            attacked_query_ids=["q1"],
            reviewed_target_assignments={},
        )
