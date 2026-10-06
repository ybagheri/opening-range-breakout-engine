"""Grid-search optimizer with train/validation/test discipline + overfit warnings."""
from __future__ import annotations

import itertools


def grid(params: dict[str, list]) -> list[dict]:
    keys = list(params)
    return [dict(zip(keys, v)) for v in itertools.product(*[params[k] for k in keys])]


def evaluate_grid(candidates: list[dict], score_fn) -> list[dict]:
    """score_fn(params) -> {'train': float, 'valid': float, 'overfit_gap': float}."""
    rows = []
    for p in candidates:
        m = score_fn(p)
        gap = m["train"] - m["valid"]
        flag = "OVERFIT_WARNING" if gap > 0.5 * abs(m["train"]) + 0.2 else "ok"
        rows.append({"params": p, **m, "overfit_gap": gap, "flag": flag})
    return sorted(rows, key=lambda r: r["valid"], reverse=True)
