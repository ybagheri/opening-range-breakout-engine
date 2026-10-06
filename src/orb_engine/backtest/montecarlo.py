"""Monte Carlo: reshuffle trade order to assess drawdown/ruin dispersion."""
from __future__ import annotations

import numpy as np


def simulate(trades_r: list[float], n_sims: int = 5000, risk_per_trade: float = 100.0,
             seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    arr = np.array(trades_r, dtype=float)
    if len(arr) == 0:
        return {"sims": 0}
    finals, mdds, ruins = [], [], 0
    for _ in range(n_sims):
        seq = rng.permutation(arr) * risk_per_trade
        eq = 10000 + np.cumsum(seq)
        peak = np.maximum.accumulate(eq)
        mdd = float(np.min(eq - peak))
        mdds.append(mdd)
        finals.append(float(eq[-1]))
        if float(np.min(eq)) <= 5000:
            ruins += 1
    return {
        "sims": n_sims,
        "median_final": float(np.median(finals)),
        "p5_final": float(np.percentile(finals, 5)),
        "p95_final": float(np.percentile(finals, 95)),
        "median_maxDD": float(np.median(mdds)),
        "p95_maxDD": float(np.percentile(mdds, 5)),
        "prob_ruin_50pct": ruins / n_sims,
        "prob_positive": float(np.mean(np.array(finals) > 10000)),
    }
