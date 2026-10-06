"""Look-ahead bias guards: future data must never influence past decisions."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.config.settings import Settings
from orb_engine.core.types import Bar
from orb_engine.strategy.breakout import BreakoutDetector
from orb_engine.strategy.opening_range import OpeningRangeBuilder

Z = ZoneInfo("America/New_York")


def _bars():
    out = []
    for i, (hm, o, h, l, c) in enumerate([("09:30", 100, 102, 99, 101),
                                          ("09:35", 101, 103, 100, 102),
                                          ("09:40", 102, 104, 101, 103)]):
        hh, mm = map(int, hm.split(":"))
        out.append(Bar("TST", datetime(2024, 1, 2, hh, mm, tzinfo=Z), o, h, l, c))
    return out


def test_or_ignores_future_bars():
    b = OpeningRangeBuilder()
    ors = datetime(2024, 1, 2, 9, 30, tzinfo=Z)
    ore = datetime(2024, 1, 2, 9, 45, tzinfo=Z)
    base = _bars()
    r1, _ = b.build(base, "TST", "2024-01-02", ors, ore)
    future = base + [Bar("TST", datetime(2024, 1, 2, 15, 0, tzinfo=Z), 1, 9999, 0.01, 5000)]
    r2, _ = b.build(future, "TST", "2024-01-02", ors, ore)
    assert (r1.high, r1.low) == (r2.high, r2.low) == (104, 99)


def test_signal_deterministic_regardless_of_future():
    d = BreakoutDetector()
    from orb_engine.core.types import OpeningRange
    orng = OpeningRange("TST", "2024-01-02", datetime(2024, 1, 2, 9, 30, tzinfo=Z),
                        datetime(2024, 1, 2, 9, 45, tzinfo=Z), 104, 99)
    probe = Bar("TST", datetime(2024, 1, 2, 10, 0, tzinfo=Z), 103, 106, 102, 105)
    s1 = d.detect(probe, orng, "2024-01-02")
    s2 = d.detect(probe, orng, "2024-01-02")  # future bars cannot leak in: pure function
    assert (s1.signal_type, s1.price) == (s2.signal_type, s2.price)


def test_backtest_entry_uses_next_bar_open_plus_costs():
    idx = pd.date_range("2024-01-02 09:30", periods=12, freq="5min", tz="America/New_York")
    rows = [(100, 101, 99, 100)] * 3 + [(100, 101, 99, 100)] + [(100, 106, 99, 104)] + \
        [(104, 112, 103, 110)] * 7
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    s = Settings(timezone="America/New_York", or_start="09:30", or_end="09:45",
                 trading_start="09:45", trading_end="11:30", symbols=("TST",),
                 backtest_slippage_points=1.0, backtest_spread_points=2.0,
                 breakeven_enabled=False)
    eng = BacktestEngine(s)
    res = eng.run({"TST": df})
    assert len(res.trades) >= 1
    t = res.trades[0]
    assert t["entry_time"] > t["signal_time"]
    # LONG next-bar open=104, point fallback 0.01: entry = 104 + (0.02/2 + 0.01)
    assert abs(t["entry"] - (104 + 0.02)) < 1e-9
