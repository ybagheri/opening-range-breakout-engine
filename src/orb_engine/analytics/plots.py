"""Charting kept separate from core strategy."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_equity(equity: pd.Series, path: str) -> str:
    fig, ax = plt.subplots(figsize=(10, 4))
    equity.plot(ax=ax)
    ax.set_title("Equity curve (R-scaled, $100 risk/trade)")
    ax.set_xlabel("Trade #")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_r_dist(trades: list[dict], path: str) -> str:
    import pandas as pd
    fig, ax = plt.subplots(figsize=(8, 4))
    pd.Series([t["r_multiple"] for t in trades]).hist(ax=ax, bins=30)
    ax.set_title("Distribution of R multiples")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
