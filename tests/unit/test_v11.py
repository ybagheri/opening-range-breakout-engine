"""v1.2.0 tests: strategy gating, point overrides, paper fills, poll loop."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from orb_engine.backtest.engine import resolve_point
from orb_engine.broker.paper import PaperBroker
from orb_engine.config.settings import Settings, _parse_point_overrides, validate_settings
from orb_engine.core.types import Bar, Direction, OpeningRange, SignalType
from orb_engine.execution.engine import ORBEngine
from orb_engine.strategy.breakout import BreakoutDetector
from orb_engine.strategy.strategy import ORBStrategy

Z = ZoneInfo("America/New_York")
OR = OpeningRange("TST", "2024-01-02", datetime(2024, 1, 2, 9, 30, tzinfo=Z),
                  datetime(2024, 1, 2, 9, 45, tzinfo=Z), 110, 100)


def bar(hm, o, h, l, c, v=100.0):
    hh, mm = map(int, hm.split(":"))
    return Bar("TST", datetime(2024, 1, 2, hh, mm, tzinfo=Z), o, h, l, c, v)


def S(**kw):
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                risk_per_trade_percent=0.5)
    base.update(kw)
    return Settings(**base)


# --- Detector: pure price breakout, no volume gate ---
def test_detector_breakout_ignores_volume():
    d = BreakoutDetector()
    thin = d.detect(bar("10:00", 109, 112, 108, 111, v=1.0), OR, "2024-01-02")
    thick = d.detect(bar("10:00", 109, 112, 108, 111, v=100000.0), OR, "2024-01-02")
    assert thin.signal_type == thick.signal_type == SignalType.LONG


# --- Strategy gating ---
def _strategy_with_or(**kw):
    st = ORBStrategy(S(**kw))
    bars = [bar("09:30", 100, 102, 99, 101, v=100.0),
            bar("09:35", 101, 103, 100, 102, v=100.0),
            bar("09:40", 102, 104, 101, 103, v=100.0)]
    st.update_or(bars, "TST", "2024-01-02")
    return st


def test_bar_inside_or_window_no_signal():
    st = _strategy_with_or()
    s = st.on_bar(bar("09:35", 100, 200, 50, 150))
    assert s.signal_type == SignalType.NO_SIGNAL and "formation" in s.reason


def test_bar_outside_entry_window_no_signal():
    st = _strategy_with_or()
    # 11:30 boundary is inclusive; use 12:00 for outside
    s = st.on_bar(bar("12:00", 100, 200, 50, 150))
    assert s.signal_type == SignalType.NO_SIGNAL and "entry window" in s.reason


def test_strategy_emits_breakout():
    st = _strategy_with_or()
    s = st.on_bar(bar("10:00", 103, 106, 102, 105))  # OR high=104
    assert s.signal_type == SignalType.LONG
    s2 = st.on_bar(bar("10:05", 103, 104, 102, 103))
    assert s2.signal_type == SignalType.NO_SIGNAL


# --- Point overrides ---
def test_resolve_point_prefers_overrides():
    assert resolve_point("US30", {"US30": 0.5}) == 0.5
    assert resolve_point("US30", {}) == 1.0
    assert resolve_point("UNKNOWN", {}) == 0.01


def test_point_override_validation():
    assert validate_settings(S(point_overrides={"US30": 0.0}))
    try:
        _parse_point_overrides("US30-nope")
        raise AssertionError("should raise")
    except ValueError:
        pass


# --- PaperBroker spread-aware fills ---
def test_paper_fills_at_quote_not_signal():
    from orb_engine.core.types import SymbolInfo
    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    b = PaperBroker(10000.0, infos)
    b.set_quote("TST", 99.0, 101.0)
    from orb_engine.core.types import OrderRequest
    req = OrderRequest("TST", Direction.LONG, 1.0, 100.0, 95.0, 110.0, 1, "ORB_ENGINE",
                       "2024-01-02")
    res = b.place_market_order(req)
    assert res.filled_price == 101.0  # ask, not the 100.0 signal price
    assert b.fills[0]["slippage"] == 1.0


# --- Live poll loop with canned rates ---
class CannedBroker(PaperBroker):
    def __init__(self, df):
        from orb_engine.core.types import SymbolInfo
        super().__init__(10000.0, {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100,
                                                    0.01)})
        self._df = df

    def get_rates(self, symbol, timeframe, count):
        return self._df


def _canned_df():
    idx = pd.date_range("2024-01-02 09:30", periods=8, freq="5min", tz="America/New_York")
    rows = [(100, 102, 99, 101, 100), (101, 103, 100, 102, 100), (102, 104, 101, 103, 100),
            (103, 104, 102, 103, 100), (103, 107, 102, 106, 300), (106, 108, 105, 107, 100),
            (107, 109, 106, 108, 100), (108, 110, 107, 109, 100)]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


def test_poll_once_idempotent(tmp_path):
    s = S(state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"), dry_run=True)
    eng = ORBEngine(s, CannedBroker(_canned_df()))
    first = eng.poll_once()
    assert len(first) >= 1  # breakout bar processed
    second = eng.poll_once()
    assert second == []  # nothing new: no reprocessing
    assert eng.strategy.get_or("TST") is not None
