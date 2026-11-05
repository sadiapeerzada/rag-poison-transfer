"""Metadata-only 2Wiki feasibility census: no models, no dataset access."""
import hashlib
import json

import pytest

from scripts.audit_twowiki_v3_train_pool import (
    CONFIG, DATASET, REVISION, _read_pinned, assess,
)


def pool(ids, **changes):
    return {"dataset": DATASET, "config": CONFIG, "revision": REVISION,
            "split": "train", "query_ids": ids, **changes}


def registry(ids, gaps=None, certificate=None):
    return {"excluded_query_ids": ids,
            "historical_gaps": ["unrecovered sweep"] if gaps is None else gaps,
            "certification": certificate}


def test_current_exhausted_pool_reports_zero_and_no_go():
    result = assess(pool(["a", "b", "c"]), registry(["a", "b", "c"]))
    assert result["potentially_id_eligible_count"] == 0
    assert result["overlap_count"] == 3
    assert result["prospective_go"] is False
    assert result["cohort_selected"] is False


def test_larger_pool_is_not_authorized_even_with_sufficient_ids():
    result = assess(pool([f"id-{i}" for i in range(30)]), registry(["old"]))
    assert result["potentially_id_eligible_count"] == 30
    assert result["at_least_25_by_id"] is True
    assert result["prospective_go"] is False
    assert "query_ids" not in result


@pytest.mark.parametrize("alter", [
    {"split": "dev"}, {"split": "validation"}, {"revision": "wrong"},
    {"dataset": "other"}, {"config": "other"}, {"question": "leak"},
])
def test_wrong_source_or_content_is_rejected(alter):
    with pytest.raises(ValueError):
        assess(pool(["a"], **alter), registry([]))


@pytest.mark.parametrize("ids", [["a", "a"], ["a", ""], ["a", 4], "a,b"])
def test_bad_id_inventory_refused(ids):
    with pytest.raises(ValueError):
        assess(pool(ids), registry([]))


def test_incomplete_registry_refused():
    with pytest.raises(ValueError):
        assess(pool(["a"]), {"excluded_query_ids": []})


def test_certificate_does_not_create_an_execution_authorization():
    r = assess(pool([str(i) for i in range(25)]),
               registry([], gaps=[], certificate={"historical_inventory_complete": True}))
    assert r["prospective_go"] is False
    assert r["custody_status"] == "requires_independent_review"


def test_external_pin_and_symlinks(tmp_path):
    path = tmp_path / "ids.json"
    content = json.dumps(pool(["a"])).encode()
    path.write_bytes(content)
    pin = hashlib.sha256(content).hexdigest()
    assert _read_pinned(path, pin)["query_ids"] == ["a"]
    with pytest.raises(ValueError):
        _read_pinned(path, "0" * 64)
    link = tmp_path / "shortcut"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        _read_pinned(link, pin)
