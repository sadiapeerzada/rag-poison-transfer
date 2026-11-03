"""Synthetic, read-only regressions for the 2Wiki 25-query quality audit.

No real training/held-out data, model requests, poison construction or approvals.
"""
import json
import zipfile

import pytest
from scripts import audit_twowiki_v4_1_quality as quality
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint


def fixture(tmp_path, monkeypatch):
    queries = []
    corpus = []
    proposals = []
    reviews = []
    names = sorted(quality.CASE_IDS)

    for i in range(300):
        q = {"query_id": f"synthetic-{i:03}", "question": f"Question {i}?",
             "gold_answer": "Paris", "gold_doc_ids": [],
             "gold_aliases": []}
        if i < 5:
            docs = [
                {"doc_id": f"film-{i}", "text": f"Film {i} is a test film directed by Person {i}."},
                {"doc_id": f"person-{i}", "text": f"Person {i} (born 1965) died in Paris."},
            ]
            corpus.extend(docs)
            q["gold_doc_ids"] = [d["doc_id"] for d in docs]
            forms = [f"Case-{i} versioned diagnostic sentence {j} about Lyon." for j in range(3)]
            packet_passages = forms.copy()
            if i == 1:
                packet_passages[2] = "Case-1 previously reviewed but now stale diagnostic sentence about Lyon."
            proposals.append({
                "candidate_id": names[i], "query_id": q["query_id"],
                "question": q["question"], "gold_answer": q["gold_answer"],
                "proposed_false_target": "Lyon",
                "source_documents": [
                    {**d, "text_sha256": quality.sha(d["text"].encode())} for d in docs
                ],
                "candidate_documents": [
                    {"doc_id": f"template-control-{names[i]}-{j}", "poison_index": j,
                     "text": packet_passages[j]} for j in range(3)
                ],
            })
            reviews.append({
                "candidate_id": names[i], "decision": "accept",
                "source_chain_valid": True, "target_contradicted_by_sources": True,
                "passage_verdicts": [
                    {"slot": j, "faithful_to_target": True, "referents_preserved": True,
                     "fluent": True} for j in range(3)
                ],
                "evidence_quotes": [
                    {"doc_id": docs[0]["doc_id"], "exact_quote": f"Film {i} is a test film"}
                ],
            })
        queries.append(q)
    data = {"queries": queries, "corpus": corpus}
    paths = {k: tmp_path / (k + ".json") for k in ("dataset", "cohort", "baseline", "review")}
    paths["packet"] = tmp_path / "packet.zip"
    paths["dataset"].write_text(json.dumps(data))
    dataset_hash = quality.sha(paths["dataset"].read_bytes())
    monkeypatch.setattr(quality, "DATASET_SHA256", dataset_hash)

    ids = [q["query_id"] for q in queries[:25]]
    cohort = {"scope": "development_only", "dataset_split": "train",
              "dataset_sha256": dataset_hash, "cohort_query_ids": ids}
    paths["cohort"].write_text(json.dumps(cohort))
    baseline = {"scope": "train/development", "condition": "clean_no_poison",
                "heldout_access": False, "poison_injection": False,
                "dataset_sha256": dataset_hash, "query_ids": ids,
                "cohort_manifest_sha256": quality.sha(paths["cohort"].read_bytes()),
                "query_set_fingerprint": query_set_fingerprint(queries[:25]),
                "corpus_fingerprint": corpus_fingerprint(corpus)}
    paths["baseline"].write_text(json.dumps(baseline))

    packet = {"scope": "train_development_only", "dataset_sha256": dataset_hash,
              "not_llm_generated": True, "model_calls": 0, "factual_approval": False,
              "injection_approved": False, "heldout_access": False,
              "queries": proposals}
    input_bytes = json.dumps(packet).encode()
    with zipfile.ZipFile(paths["packet"], "w") as archive:
        archive.writestr("independent_review_input.json", input_bytes)
    packet_hash = quality.sha(paths["packet"].read_bytes())
    monkeypatch.setattr(quality, "REVIEW_PACKET_SHA256", packet_hash)
    second = {
        "review_metadata": {
            "input_zip_sha256": packet_hash, "input_json_sha256": quality.sha(input_bytes),
            "scope": "train_development_only", "factual_approval": False,
            "injection_approved": False, "heldout_access": False,
            "reviewer_model_id": "Synthetic second-AI placeholder",
            "run_id": None, "timestamp": None
        },
        "reviews": reviews
    }
    paths["review"].write_text(json.dumps(second))
    def forms(query, target):
        i = int(query["query_id"].split("-")[-1])
        return [f"Case-{i} versioned diagnostic sentence {j} about Lyon." for j in range(3)]
    monkeypatch.setattr(quality, "bind_typed_sources",
        lambda query, corpus, hashes, scope: {
            "status": "source_text_compatible_unverified", "relation_type": "death",
            "caveats": [], "construction_eligible": False})
    monkeypatch.setattr(quality, "template_forms", forms)
    monkeypatch.setattr(quality, "validate_template_statement", lambda *args: True)
    return paths


def run(paths):
    return quality.audit(dataset_path=paths["dataset"], cohort_path=paths["cohort"],
        baseline_path=paths["baseline"], packet_path=paths["packet"],
        review_path=paths["review"])


def test_25_development_only_abstentions_and_exact_review_mismatch(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    result = run(paths)
    assert result["cohort_count"] == 25
    assert result["provisionally_reviewed_count"] == 5
    assert result["abstention_count"] == 20
    assert result["exactly_reviewed_versioned_passages"] == 14
    assert result["stale_review_slots"] == {sorted(quality.CASE_IDS)[1]: [2]}
    assert result["second_ai_provenance"] == "incomplete_provenance"
    assert result["construction_approvals"] == 0
    assert result["injection_approvals"] == 0
    assert result["model_calls"] == result["heldout_queries_accessed"] == 0
    assert result["paired_poisoned_evaluation_authorized"] is False


def test_tampered_dataset_rejected(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    paths["dataset"].write_text(paths["dataset"].read_text() + " ")
    with pytest.raises(ValueError, match="train dataset hash"):
        run(paths)


def test_frozen_cohort_substitution_rejected(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    data = json.loads(paths["cohort"].read_text())
    data["cohort_query_ids"][0] = "synthetic-200"
    paths["cohort"].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="previously completed clean-baseline pins"):
        run(paths)


def test_heldout_scope_rejected(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    data = json.loads(paths["baseline"].read_text())
    data["heldout_access"] = True
    paths["baseline"].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="clean-baseline pins"):
        run(paths)


def test_unbound_ai_quote_rejected(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    review = json.loads(paths["review"].read_text())
    review["reviews"][0]["evidence_quotes"][0]["exact_quote"] = "not in any source"
    paths["review"].write_text(json.dumps(review))
    with pytest.raises(ValueError, match="not anchored"):
        run(paths)


def test_review_run_metadata_cannot_be_invented(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    review = json.loads(paths["review"].read_text())
    review["review_metadata"]["run_id"] = "self-reported-run"
    review["review_metadata"]["timestamp"] = "2026-11-03T20:30:00+05:30"
    paths["review"].write_text(json.dumps(review))
    result = run(paths)
    assert result["second_ai_provenance"] == "self_reported_metadata_only"
    assert result["construction_approvals"] == 0
    assert result["injection_approvals"] == 0


def test_unchanged_packet_required(tmp_path, monkeypatch):
    paths = fixture(tmp_path, monkeypatch)
    with zipfile.ZipFile(paths["packet"], "a") as archive:
        archive.writestr("unapproved_extra.json", "{}")
    with pytest.raises(ValueError, match="packet bytes changed"):
        run(paths)
