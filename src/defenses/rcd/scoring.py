"""RCD configuration and the training-free suspicion score."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class RCDConfig:
    # retrieval for consistency checking
    depth: int = 20            # per-variant retrieval depth (keep >= the base pipeline's candidate pool)
    agree_k: int = 5           # 'agreement' = in top agree_k of BOTH sparse and dense
    support_pool_k: int = 5    # corroboration pool = top-k of the original query
    n_rewrites: int = 3        # 0 disables rewrites (ablation A2)
    # suspicion = weighted mean of features (each in [0,1])
    w_instability: float = 1.0
    w_disagreement: float = 1.0
    w_unsupported: float = 0.5
    w_conflict: float = 0.0    # 0 in the primary training-free v0; enable with an NLI scorer
    # selection
    lam: float = 0.5           # adjusted = base_rank_score - lam * suspicion
    hard_threshold: float | None = None   # optional: drop docs with suspicion >= threshold
    min_keep: int = 1          # never return fewer than this many docs

    def as_dict(self) -> dict:
        return asdict(self)


def suspicion(f, cfg: RCDConfig) -> float:
    ws = (cfg.w_instability, cfg.w_disagreement, cfg.w_unsupported, cfg.w_conflict)
    xs = (f.rank_instability, f.retriever_disagreement, f.unsupported, f.claim_conflict)
    total = sum(ws)
    if total <= 0:
        return 0.0
    return float(sum(w * x for w, x in zip(ws, xs)) / total)
