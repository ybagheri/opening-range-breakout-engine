"""Walk-forward validation: expanding/rolling train-validate-test splits."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WFWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str


def make_windows(dates: list[str], n_train: int = 6, n_test: int = 3, step: int = 3) -> list[WFWindow]:
    """dates: sorted unique YYYY-MM month strings. Simple rolling month windows."""
    out: list[WFWindow] = []
    i = 0
    while i + n_train + n_test <= len(dates):
        out.append(WFWindow(dates[i], dates[i + n_train - 1], dates[i + n_train],
                            dates[i + n_train + n_test - 1]))
        i += step
    return out


def run_walkforward(run_fn, monthly_data: dict[str, dict], windows: list[WFWindow]) -> list[dict]:
    """run_fn(train_data, test_data, window) -> dict of metrics. Generic harness."""
    results = []
    for w in windows:
        train = {m: d for m, d in monthly_data.items() if w.train_start <= m <= w.train_end}
        test = {m: d for m, d in monthly_data.items() if w.test_start <= m <= w.test_end}
        results.append({"window": w, "metrics": run_fn(train, test, w)})
    return results
