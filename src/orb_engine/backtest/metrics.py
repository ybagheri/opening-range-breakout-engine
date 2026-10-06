"""Performance metrics from completed trades (R-based + money where available)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def trades_to_frame(trades: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(trades)


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    if equity.empty:
        return 0.0, 0.0
    peak = equity.cummax()
    dd = equity - peak
    max_dd = float(dd.min())
    pct = float((max_dd / peak[dd.idxmin()]) * 100) if peak[dd.idxmin()] else 0.0
    return max_dd, pct


def sharpe(returns: pd.Series, periods: int = 252) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(periods))


def summarize(trades: list[dict], equity: pd.Series) -> dict:
    df = trades_to_frame(trades)
    if df.empty:
        return {"total_trades": 0}
    r = df["r_multiple"].astype(float)
    wins = r[r > 0]
    losses = r[r <= 0]
    mdd, mdd_pct = max_drawdown(equity)
    rets = equity.pct_change().dropna() if not equity.empty else pd.Series(dtype=float)
    downside = rets[rets < 0]
    sortino = float(rets.mean() / downside.std(ddof=1) * np.sqrt(252)) if len(downside) > 1 and downside.std() else 0.0
    gross_profit = float(wins.sum())
    gross_loss = float(losses.sum())
    return {
        "total_trades": len(df),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": float(len(wins) / len(df)),
        "gross_profit_R": gross_profit,
        "gross_loss_R": gross_loss,
        "net_R": float(r.sum()),
        "profit_factor": float(-gross_profit / gross_loss) if gross_loss else float("inf"),
        "avg_R": float(r.mean()),
        "avg_win_R": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_R": float(losses.mean()) if len(losses) else 0.0,
        "expectancy_R": float(r.mean()),
        "max_drawdown": mdd,
        "max_drawdown_pct": mdd_pct,
        "sharpe": sharpe(rets),
        "sortino": sortino,
        "calmar": float((r.sum()) / abs(mdd)) if mdd else 0.0,
        "largest_win_R": float(r.max()),
        "largest_loss_R": float(r.min()),
        "consecutive_wins": _max_streak(r > 0),
        "consecutive_losses": _max_streak(r <= 0),
    }


def _max_streak(mask: pd.Series) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best
