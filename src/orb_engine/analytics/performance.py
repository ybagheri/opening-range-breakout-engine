"""PerformanceAnalyzer: wraps backtest.metrics + journal queries."""
from __future__ import annotations

import pandas as pd

from orb_engine.backtest import metrics as m


class PerformanceAnalyzer:
    @staticmethod
    def analyze(trades: list[dict], equity: pd.Series) -> dict:
        summary = m.summarize(trades, equity)
        df = m.trades_to_frame(trades)
        out = {"summary": summary}
        if not df.empty:
            out["by_symbol"] = df.groupby("symbol")["r_multiple"].agg(["count", "sum", "mean"]).to_dict()
            out["by_direction"] = df.groupby("direction")["r_multiple"].agg(["count", "sum", "mean"]).to_dict()
            out["monthly"] = df.set_index(pd.to_datetime(df["exit_time"])).resample("ME")["r_multiple"].sum().to_dict() if "exit_time" in df else {}
        return out
