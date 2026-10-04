"""Go/no-go diagnostic: do RCD features separate poison from clean evidence?

NO generator needed (rewrites come from the cache). For every attacked
query, take the candidate pool a pipeline could hand the generator (union
of sparse/dense top pool_k for the original question), compute the RCD
features, and measure how well each feature -- and the combined suspicion
score -- ranks poison docs above clean docs.

AUROC > 0.5: feature is higher for poison (as designed).
AUROC ~ 0.5: no signal.   AUROC < 0.5: feature is INVERTED (poison looks
MORE consistent than clean evidence -- e.g. strongly query-aligned poison
that rewrites amplify, hypothesis H2).

Uncertainty: bootstrap over QUERIES (rows of one query are not independent).
Report separately by n_poison -- coordinated multi-doc poison corroborates
itself, which can invert the 'unsupported' feature at higher intensity.
"""
from __future__ import annotations

import numpy as np

from src.defenses.rcd.defense import RetrievalConsistencyDefense
from src.defenses.rcd.scoring import RCDConfig

FEATURES = ["rank_instability", "retriever_disagreement", "unsupported", "claim_conflict", "suspicion", "rank_score_q0"]


def auroc(scores, labels) -> float:
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    ranks = np.empty(len(s))
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def feature_rows(poisoned_data: dict, rewrites, sparse, dense, cfg: RCDConfig | None = None,
                 pool_k: int = 10, claim_scorer=None) -> list[dict]:
    """One row per (attacked query, candidate doc). sparse/dense must be
    BUILT on poisoned_data['corpus']."""
    cfg = cfg or RCDConfig()
    defense = RetrievalConsistencyDefense(sparse, dense, rewrites, cfg, claim_scorer)
    rows = []
    for q in poisoned_data["queries"]:
        poison_ids = set(q.get("poison_doc_ids") or [])
        if not poison_ids:
            continue
        gold_ids = set(q.get("gold_doc_ids") or [])
        pool = {}
        q0 = {"sparse": {}, "dense": {}}
        for fam, r in (("sparse", sparse), ("dense", dense)):
            for i, d in enumerate(r.retrieve(q["question"], top_k=pool_k), 1):
                pool.setdefault(d.doc_id, d)
                q0[fam][d.doc_id] = i
        candidates = list(pool.values())
        susp, feats, _ = defense.score_candidates(q["question"], candidates)
        for d in candidates:
            f = feats[d.doc_id]
            rows.append({
                "query_id": q["query_id"], "doc_id": d.doc_id,
                "is_poison": d.doc_id in poison_ids, "is_gold": d.doc_id in gold_ids,
                "n_poison": len(poison_ids), "attack_family": q.get("attack_family"),
                "rank_instability": f.rank_instability,
                "retriever_disagreement": f.retriever_disagreement,
                "unsupported": f.unsupported, "claim_conflict": f.claim_conflict,
                "suspicion": susp[d.doc_id],
                "rank_sparse_q0": q0["sparse"].get(d.doc_id, pool_k + 1),
                "rank_dense_q0": q0["dense"].get(d.doc_id, pool_k + 1),
                # control: plain retrieval rank (higher = better rank). NOT a defense signal.
                "rank_score_q0": 1.0 - (min(q0["sparse"].get(d.doc_id, pool_k + 1),
                                            q0["dense"].get(d.doc_id, pool_k + 1)) - 1) / pool_k,
            })
    return rows


def _boot_auroc(by_query: dict, feature: str, pos_key: str, neg_filter, n_boot: int, rng):
    def stat(qids):
        sc, lb = [], []
        for qid in qids:
            for r in by_query[qid]:
                if r["is_poison"]:
                    sc.append(r[feature]); lb.append(True)
                elif neg_filter(r):
                    sc.append(r[feature]); lb.append(False)
        return auroc(sc, lb)

    qids = list(by_query)
    point = stat(qids)
    boots = []
    for _ in range(n_boot):
        samp = [qids[i] for i in rng.integers(0, len(qids), len(qids))]
        v = stat(samp)
        if not np.isnan(v):
            boots.append(v)
    lo, hi = (np.percentile(boots, [2.5, 97.5]) if boots else (float("nan"), float("nan")))
    return point, float(lo), float(hi)


def summarize_auroc(rows: list[dict], n_boot: int = 500, seed: int = 0) -> list[dict]:
    """AUROC (95% query-bootstrap CI) per feature for poison vs (a) all clean
    candidates and (b) clean GOLD candidates only (the clean evidence that
    matters most), overall and per n_poison."""
    rng = np.random.default_rng(seed)
    out = []
    slices = [("all", None)] + [(f"n_poison={n}", n) for n in sorted({r["n_poison"] for r in rows})]
    for label, n in slices:
        sub = [r for r in rows if n is None or r["n_poison"] == n]
        by_query: dict = {}
        for r in sub:
            by_query.setdefault(r["query_id"], []).append(r)
        # keep only queries that have at least one poison doc in the pool
        by_query = {k: v for k, v in by_query.items() if any(x["is_poison"] for x in v)}
        if not by_query:
            continue
        for feat in FEATURES:
            for neg_name, neg_filter in (("vs_all_clean", lambda r: True), ("vs_clean_gold", lambda r: r["is_gold"])):
                pt, lo, hi = _boot_auroc(by_query, feat, "is_poison", neg_filter, n_boot, rng)
                out.append({"slice": label, "feature": feat, "negatives": neg_name,
                            "auroc": pt, "ci_lo": lo, "ci_hi": hi, "n_queries": len(by_query)})
    return out
