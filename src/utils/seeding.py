"""Deterministic seeding utility.

Called once at the start of every experiment run. Keeping this in one
place means every experiment seeds the same set of RNGs the same way,
which is a precondition for reproducibility (Section 4 of the plan).
"""
import random
import numpy as np


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.backends.mps.is_available():
            torch.mps.manual_seed(seed)
    except ImportError:
        # torch not installed yet in this environment (e.g. bare BM25-only run) — fine.
        pass
