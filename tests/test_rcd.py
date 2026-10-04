"""Tests for the Retrieval-Consistency Defense (src/defenses/rcd).

Uses the repo's real BM25 / hashing-dense retrievers and the real lexical
attack + inject_poisons on a toy corpus, so no model downloads are needed.
"""
import json

import numpy as np
import pytest

from src.attacks.injection import inject_poisons
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.defenses.rcd import (
    RCDConfig, RewriteCache, make_defended_factory, parse_rewrites,
)
from src.defenses.rcd.defense import RetrievalConsistencyDefense
from src.defenses.rcd.diagnostic import auroc, feature_rows, summarize_auroc
from src.defenses.rcd.features import collect_rankings, rank_instability
from src.defenses.rcd.selector import select_evidence
from src.retrieval.bm25 import BM25Retriever, RetrievedDoc
from src.retrieval.dense import DenseRetriever


class StubGen:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def generate(self, prompt, max_tokens=64):
        self.calls += 1
        return type("R", (), {"text": self.text})()


TOPICS = [
    ("Who founded the Aldrin Observatory", "Marta Quill", "The Aldrin Observatory was founded by Marta Quill in the northern hills."),
    ("Where is the Brevik Museum located", "Tromso", "The Brevik Museum is located in Tromso beside the harbour."),
    ("When did the Calder Railway open", "1894", "The Calder Railway opened in 1894 connecting the two valleys."),
    ("Who designed the Dunmore Bridge", "Ines Faro", "The Dunmore Bridge was designed by Ines Faro using steel arches."),
    ("What is the capital of Eskerland", "Valdor", "The capital of Eskerland is Valdor, a river city."),
    ("Who wrote the Fenwick Chronicle", "Olaf Strand", "The Fenwick Chronicle was written by Olaf Strand in the winter."),
]


def toy_data():
    corpus, queries = [], []
    for i, (q, a, doc) in enumerate(TOPICS):
        corpus.append({"doc_id": f"d{i}", "text": doc})
        corpus.append({"doc_id": f"x{i}", "text": f"Unrelated filler paragraph number {i} about gardening soil and weather patterns."})
        queries.append({"query_id": f"q{i}", "question": q, "gold_answer": a, "gold_doc_ids": [f"d{i}"]})
    return {"corpus": corpus, "queries": queries}


def build_pair(data):
    s, d = BM25Retriever(), DenseRetriever()
    s.build(data["corpus"]); d.build(data["corpus"])
    return s, d


def cache_for(data, per_question=("{q} exactly", "Tell me: {q}", "{q} please")):
    c = RewriteCache()
    for q in data["queries"]:
        c.put(q["question"], [t.format(q=q["question"]) for t in per_question])
    return c


# ---------------- rewrites ----------------
def test_parse_rewrites_cleans_numbering_dedupes_and_drops_original():
    raw = "1. Who started the Aldrin Observatory?\n2) \"Who established the Aldrin Observatory\"\n- who founded the aldrin observatory\n3. ok\n"
    out = parse_rewrites(raw, "Who founded the Aldrin Observatory", 3)
    assert out == ["Who started the Aldrin Observatory?", "Who established the Aldrin Observatory"]


def test_rewrite_cache_persists_and_resumes(tmp_path):
    path = str(tmp_path / "rw.jsonl")
    gen = StubGen("1. alpha beta gamma\n2. delta epsilon zeta\n3. eta theta iota\n4. kappa lambda mu")
    c = RewriteCache(path, generator=gen)
    c.prefill(["Question one here", "Question two here"], n=4)
    assert gen.calls == 2 and len(c) == 2
    gen2 = StubGen("x")
    c2 = RewriteCache(path, generator=gen2)           # fresh process
    c2.prefill(["Question one here", "Question two here", "Question three here"], n=4)
    assert gen2.calls == 1                            # only the missing one
    assert len(c2.get_rewrites("Question one here", 2)) == 2


def test_missing_rewrites_without_generator_raises():
    with pytest.raises(KeyError):
        RewriteCache().get_rewrites("never seen question text", 3)


# ---------------- features ----------------
def test_rank_instability_extremes():
    stable = {"sparse": [3, 3, 3], "dense": [2, 2, 2]}
    flaky = {"sparse": [1, None, None], "dense": [1, None, None]}
    assert rank_instability(stable, depth=10) == 0.0
    assert rank_instability(flaky, depth=10) > 0.6
    assert rank_instability({"sparse": [None] * 3, "dense": [None] * 3}, depth=10) == 1.0


def test_collect_rankings_counts_calls_and_ranks():
    data = toy_data(); s, d = build_pair(data)
    rk = collect_rankings(["Who founded the Aldrin Observatory", "Aldrin Observatory founder"], s, d, depth=5)
    assert rk.n_retrieval_calls == 4                  # 2 variants x 2 retrievers
    assert rk.ranks["d0"]["sparse"][0] == 1


# ---------------- selector ----------------
def _docs(n):
    return [RetrievedDoc(doc_id=f"r{i}", text=f"t{i}", score=1.0 - i * 0.1) for i in range(n)]


def test_selector_demotes_suspicious_top_doc():
    docs = _docs(4)
    susp = {"r0": 1.0, "r1": 0.0, "r2": 0.0, "r3": 0.0}
    sel, _ = select_evidence(docs, susp, top_k=2, cfg=RCDConfig(lam=0.8))
    assert [d.doc_id for d in sel] == ["r1", "r2"]


def test_selector_lam_zero_is_identity_and_hard_threshold_min_keep():
    docs = _docs(4)
    susp = {d.doc_id: 0.9 for d in docs}
    sel, _ = select_evidence(docs, susp, 3, RCDConfig(lam=0.0))
    assert [d.doc_id for d in sel] == ["r0", "r1", "r2"]
    sel, _ = select_evidence(docs, susp, 3, RCDConfig(hard_threshold=0.5, min_keep=2))
    assert len(sel) == 2                              # everything over threshold, but min_keep honoured


# ---------------- defense end-to-end on the repo's real attack ----------------
def poisoned_toy(n_poison=1):
    data = toy_data()
    return data, inject_poisons(data, LexicalInfluentialTokenAttack(), n_poison=n_poison, seed=1)


def test_defended_retriever_is_drop_in_and_counts_cost():
    data, pdata = poisoned_toy()
    rw = cache_for(pdata)
    f = make_defended_factory(BM25Retriever, BM25Retriever, DenseRetriever, rw, RCDConfig(depth=8))
    r = f(); r.build(pdata["corpus"])
    out = r.retrieve(pdata["queries"][0]["question"], top_k=5)
    assert len(out) == 5 and all(hasattr(d, "doc_id") and hasattr(d, "text") for d in out)
    assert r.stats["queries"] == 1
    assert r.stats["extra_retrieval_calls"] == 2 * (1 + 3)   # (1 + 3 rewrites) x (sparse + dense)
    assert f() is not f()                                    # fresh instance per call


def test_defense_never_changes_corpus_or_inputs():
    data, pdata = poisoned_toy()
    before = json.dumps(pdata, sort_keys=True)
    rw = cache_for(pdata)
    r = make_defended_factory(BM25Retriever, BM25Retriever, DenseRetriever, rw, RCDConfig(depth=8))()
    r.build(pdata["corpus"])
    for q in pdata["queries"]:
        r.retrieve(q["question"], top_k=3)
    assert json.dumps(pdata, sort_keys=True) == before


def test_no_rewrites_ablation_zeroes_instability():
    data, pdata = poisoned_toy()
    s, d = build_pair(pdata)
    defense = RetrievalConsistencyDefense(s, d, cache_for(pdata), RCDConfig(depth=8, n_rewrites=0))
    q = pdata["queries"][0]
    cands = s.retrieve(q["question"], top_k=5)
    _, feats, calls = defense.score_candidates(q["question"], cands)
    assert calls == 2 and all(f.rank_instability == 0.0 for f in feats.values())


# ---------------- diagnostic ----------------
def test_auroc_known_values():
    assert auroc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]) == 1.0
    assert auroc([0.1, 0.2, 0.9, 0.8], [1, 1, 0, 0]) == 0.0
    assert auroc([0.5, 0.5, 0.5, 0.5], [1, 1, 0, 0]) == 0.5
    assert np.isnan(auroc([0.1, 0.2], [1, 1]))


def test_feature_diagnostic_runs_and_reports_all_features():
    data, pdata = poisoned_toy(n_poison=1)
    s, d = build_pair(pdata)
    rows = feature_rows(pdata, cache_for(pdata), s, d, RCDConfig(depth=8), pool_k=5)
    assert rows and any(r["is_poison"] for r in rows)
    summ = summarize_auroc(rows, n_boot=20)
    feats = {r["feature"] for r in summ}
    assert {"rank_instability", "retriever_disagreement", "unsupported", "suspicion"} <= feats
    assert all(0.0 <= r["auroc"] <= 1.0 for r in summ if not np.isnan(r["auroc"]))
