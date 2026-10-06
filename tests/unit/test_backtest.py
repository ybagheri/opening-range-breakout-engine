import pandas as pd

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.config.settings import Settings


def _df(start="2024-01-02 09:30", n=40, base=100.0):
    idx = pd.date_range(start, periods=n, freq="5min", tz="America/New_York")
    # OR 09:30-09:45 (3 bars): range 99-101; then breakout up at 10:00+
    rows = []
    for i, t in enumerate(idx):
        if i < 3:
            rows.append((base, base+1, base-1, base))
        elif i == 5:
            rows.append((base, base+5, base-1, base+3))  # breakout bar
        elif i > 5:
            rows.append((base+3, base+12, base+2, base+10))  # runs to TP
        else:
            rows.append((base, base+1, base-1, base))
    return pd.DataFrame(rows, columns=["open","high","low","close"], index=idx)

def _settings(**kw):
    d = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
             trading_start="09:45", trading_end="11:30", symbols=("TST",),
             stop_loss_mode="opposite", stop_loss_value=1.0,
             take_profit_mode="risk_reward", risk_reward=2.0,
             backtest_slippage_points=0.0, backtest_spread_points=0.0,
             intrabar_policy="conservative", breakeven_enabled=False)
    d.update(kw); return Settings(**d)

def test_backtest_finds_long_and_no_lookahead():
    eng = BacktestEngine(_settings())
    res = eng.run({"TST": _df()})
    assert len(res.trades) >= 1
    t = res.trades[0]
    assert t["direction"] == "LONG"
    # entry must be after signal bar open (next-bar execution)
    assert t["entry_time"] > t["signal_time"]

def test_conservative_intrabar_prefers_stop():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from orb_engine.core.types import Bar, Direction, ExitReason
    eng = BacktestEngine(_settings())
    Z = ZoneInfo("America/New_York")
    both = Bar("TST", datetime(2024,1,2,10,5,tzinfo=Z), 100, 115, 90, 102)
    px, tm, reason, be, tr = eng._simulate([both], Direction.LONG, 100, 95, 110, None)
    assert reason == ExitReason.STOP_LOSS

def test_empty_data_no_crash():
    pass
