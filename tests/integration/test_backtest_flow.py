"""Integration: CSV provider -> backtest -> metrics -> report (no MT5 needed)."""
import pandas as pd

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.backtest.metrics import summarize
from orb_engine.backtest.montecarlo import simulate
from orb_engine.backtest.robustness import drop_extremes, long_short_split
from orb_engine.config.settings import Settings


def test_full_flow(tmp_path):
    idx = pd.date_range("2024-01-02 09:30", periods=30, freq="5min", tz="America/New_York")
    rows = []
    for i in range(30):
        if i < 3:
            rows.append((100, 101, 99, 100))
        elif i == 5:
            rows.append((100, 106, 99, 104))
        else:
            rows.append((104, 112, 103, 110))
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    s = Settings(timezone="America/New_York", or_start="09:30", or_end="09:45",
                 trading_start="09:45", trading_end="11:30", symbols=("TST",),
                 backtest_slippage_points=0.0, backtest_spread_points=0.0)
    eng = BacktestEngine(s)
    res = eng.run({"TST": df})
    summ = summarize(res.trades, res.equity)
    assert summ["total_trades"] >= 1
    mc = simulate([t["r_multiple"] for t in res.trades], n_sims=50)
    assert mc["sims"] == 50
    assert "base_R" in drop_extremes(res.trades)
    assert "long_R" in long_short_split(res.trades)
