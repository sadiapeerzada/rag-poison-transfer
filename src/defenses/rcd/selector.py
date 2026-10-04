"""Evidence-subset selection: penalise suspicion, then take top_k."""
from __future__ import annotations

from src.defenses.rcd.scoring import RCDConfig


def select_evidence(candidates: list, susp: dict, top_k: int, cfg: RCDConfig):
    """candidates: base pipeline's docs, best first (need .doc_id).

    base score is rank-based (1 for rank 1 down to ~0), so the penalty is
    meaningful for every pipeline regardless of its raw score scale
    (BM25 / cosine / cross-encoder logits / RRF).

    Returns (selected_docs, adjusted_scores_by_doc_id).
    """
    n = len(candidates)
    base = {d.doc_id: 1.0 - i / max(n, 1) for i, d in enumerate(candidates)}
    adjusted = {d.doc_id: base[d.doc_id] - cfg.lam * susp[d.doc_id] for d in candidates}

    pool = list(candidates)
    if cfg.hard_threshold is not None:
        kept = [d for d in pool if susp[d.doc_id] < cfg.hard_threshold]
        if len(kept) < min(cfg.min_keep, n):
            kept = sorted(pool, key=lambda d: susp[d.doc_id])[: cfg.min_keep]
        pool = kept

    order = {d.doc_id: i for i, d in enumerate(candidates)}
    pool.sort(key=lambda d: (-adjusted[d.doc_id], order[d.doc_id]))
    return pool[:top_k], adjusted
