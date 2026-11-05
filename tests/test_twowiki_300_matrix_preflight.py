"""Pure offline tests: 300-case matrix readiness never authorizes experiments."""
import copy
import hashlib
import json

import pytest

from scripts.prepare_twowiki_300_matrix_preflight import (
    REVISION, assess, canonical, main, matrix_constants,
)


def evidence():
    mk = lambda n: [{"query_id": f"{n+i:032x}", "question_sha256": "a"*64,
                     "normalized_question_sha256": "b"*64} for i in range(300)]
    train, dev = mk(1000), mk(2000)
    manifest = {
        "schema": "rag-poison-transfer.2wiki-disjoint-cohort-manifest/v1",
        "dataset_revision": REVISION, "policy_sha256": "f"*64,
        "cohorts": {"train": train, "dev": dev},
        "cohort_fingerprints": {
            "train": hashlib.sha256(canonical(train)).hexdigest(),
            "dev": hashlib.sha256(canonical(dev)).hexdigest()},
        "complete_historical_nonoverlap_certified": False,
        "known_historical_nonoverlap_verified": True,
        "development_heldout_id_overlap": 0,
        "status": "cohort_frozen_no_evaluation",
    }
    policy = {"dataset": "Salesforce/ContextualBench", "config": "2WikiMultihopQA",
              "development_split": "train", "heldout_split": "dev",
              "complete_historical_nonoverlap_certified": False,
              "known_historical_ids": [f"{1:032x}"]}
    excluded = [x["query_id"] for x in train + dev] + [f"{1:032x}"]
    registry = {"excluded_query_ids": excluded, "historical_gaps": ["unknown sweep"],
                "certification": None}
    history = [{"id": "HIST-25-IDS", "status": "unresolved"}]
    dims = {"ATTACKS": ("lexical_influential_token", "semantic_fluent_false_evidence"),
            "INTENSITIES": (1,3), "SEEDS": (42,43,44)}
    return manifest, policy, registry, history, dims


def packet(data=None):
    m, p, r, h, d = data or evidence()
    return assess(m, p, r, h, manifest_sha="e"*64, policy_sha="f"*64,
                  registry_sha="a"*64, history_sha="b"*64,
                  matrix_source_sha="c"*64, dimensions=d)


def test_genuine_300_matrix_metadata_preflight_does_not_authorize_execution():
    result = packet()
    assert result["matrix_cell_count"] == 12
    assert result["attack_query_cell_count"] == 3600
    assert result["planned_poisoned_pipeline_observations"] == 7200
    assert result["semantic_max_construction_backend_attempts"] == 7200
    assert result["frozen_cohort_metadata_preflight"] == "PASS"
    assert result["matrix_execution_go"] is False
    assert result["model_calls"] == 0
    assert result["known_registry_overlap"] == {"train": 300, "dev": 300}
    assert all("query_id" not in c for c in result["cell_plan"])


@pytest.mark.parametrize("mutation", [
    lambda m,p,r,h: m.update(complete_historical_nonoverlap_certified=True),
    lambda m,p,r,h: m.update(dataset_revision="invalid"),
    lambda m,p,r,h: m["cohorts"]["dev"].pop(),
    lambda m,p,r,h: m["cohorts"]["dev"].__setitem__(0, dict(m["cohorts"]["train"][0])),
    lambda m,p,r,h: m["cohorts"]["train"][0].update(query_id="unrecognized"),
    lambda m,p,r,h: p.update(complete_historical_nonoverlap_certified=True),
    lambda m,p,r,h: r.update(certification={"historical_inventory_complete": True}),
    lambda m,p,r,h: r["excluded_query_ids"].remove(m["cohorts"]["dev"][0]["query_id"]),
    lambda m,p,r,h: p.update(known_historical_ids=[m["cohorts"]["train"][0]["query_id"]]),
])
def test_invalid_risk_or_cohort_is_not_hidden(mutation):
    sample = evidence()
    m, p, r, h, _ = sample
    mutation(m,p,r,h)
    with pytest.raises(ValueError):
        packet(sample)


def test_matrix_constants_ast_literal_without_runtime_import():
    source = """ATTACKS = ("lexical_influential_token", "semantic_fluent_false_evidence")
INTENSITIES = (1, 3)
SEEDS = (42, 43, 44)
"""
    assert matrix_constants(source)["SEEDS"] == (42,43,44)
    with pytest.raises(ValueError):
        matrix_constants(source.replace("(42, 43, 44)", "(42, 43)"))
