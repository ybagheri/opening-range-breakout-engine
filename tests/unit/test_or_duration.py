"""v1.5.0 tests: OR duration presets overriding explicit end time."""
import pandas as pd

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.config.settings import Settings, validate_settings
from orb_engine.strategy.strategy import ORBStrategy


def test_effective_end_presets():
    assert Settings(or_start="09:30", or_duration_minutes=5).effective_or_end == "09:35"
    assert Settings(or_start="09:30", or_duration_minutes=15).effective_or_end == "09:45"
    assert Settings(or_start="09:30", or_duration_minutes=30).effective_or_end == "10:00"
    assert Settings(or_start="09:30", or_duration_minutes=60).effective_or_end == "10:30"


def test_explicit_end_kept_when_duration_zero():
    s = Settings(or_start="09:30", or_end="10:15", or_duration_minutes=0)
    assert s.effective_or_end == "10:15"
    assert not validate_settings(s)


def test_duration_overrides_explicit_end():
    s = Settings(or_start="09:30", or_end="10:15", or_duration_minutes=15)
    assert s.effective_or_end == "09:45"


def test_duration_validation():
    assert validate_settings(Settings(or_duration_minutes=-5))
    assert validate_settings(Settings(or_start="23:30", or_duration_minutes=60))
    assert not validate_settings(Settings(or_start="09:30", or_duration_minutes=30))


def test_backtest_runs_with_duration_mode():
    idx = pd.date_range("2024-01-02 09:30", periods=30, freq="5min", tz="America/New_York")
    rows = []
    for i in range(30):
        if i < 6:
            rows.append((100, 101, 99, 100))
        elif i == 8:
            rows.append((100, 106, 99, 104))
        else:
            rows.append((104, 112, 103, 110))
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    s = Settings(timezone="America/New_York", or_start="09:30", or_duration_minutes=30,
                 trading_start="10:00", trading_end="11:30", symbols=("TST",),
                 breakeven_enabled=False)
    res = BacktestEngine(s).run({"TST": df})
    assert len(res.trades) >= 1
    assert res.trades[0]["or_high"] == 101 and res.trades[0]["or_low"] == 99


def test_strategy_uses_effective_end_for_gating():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from orb_engine.core.types import Bar, SignalType
    s = Settings(timezone="America/New_York", or_start="09:30", or_duration_minutes=15,
                 trading_start="09:45", trading_end="11:30", symbols=("TST",))
    st = ORBStrategy(s)
    Z = ZoneInfo("America/New_York")

    def bar(hm, o, h, l, c):
        hh, mm = map(int, hm.split(":"))
        return Bar("TST", datetime(2024, 1, 2, hh, mm, tzinfo=Z), o, h, l, c)

    st.update_or([bar("09:30", 100, 102, 99, 101), bar("09:35", 101, 103, 100, 102),
                  bar("09:40", 102, 104, 101, 103)], "TST", "2024-01-02")
    # 09:45 is past the 15-min OR (09:30+15) so it can signal; with the default
    # 30-min OR it would still be inside formation.
    sig = st.on_bar(bar("09:45", 103, 106, 102, 105))
    assert sig.signal_type == SignalType.LONG
