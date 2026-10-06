"""v1.3.0 tests: Wilder ATR math, ATR stop wiring, refusal discipline."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.broker.mock import MockBroker
from orb_engine.config.settings import Settings, validate_settings
from orb_engine.core.types import Direction, SignalType, SymbolInfo, TradeSignal
from orb_engine.execution.trade_manager import TradeManager
from orb_engine.risk.indicators import true_ranges, wilder_atr
from orb_engine.risk.stop_loss import StopLossCalculator

Z = ZoneInfo("America/New_York")


def test_true_range_first_bar_and_gaps():
    tr = true_ranges([10, 11], [9, 9.5], [9.5, 10.5])
    assert tr[0] == pytest.approx(1.0)
    assert tr[1] == pytest.approx(1.5)  # |11 - 9.5| dominates


def test_wilder_atr_hand_computed():
    h, l, c = [10, 11, 12, 13], [9, 9.5, 10, 11], [9.5, 10.5, 11, 12.5]
    a = wilder_atr(h, l, c, period=3)
    assert a[0] is None and a[1] is None
    assert a[2] == pytest.approx(1.5)  # SMA of first 3 TRs
    assert a[3] == pytest.approx(5 / 3)  # Wilder recursion


def test_wilder_atr_rejects_bad_input():
    with pytest.raises(ValueError):
        wilder_atr([1], [1], [1], period=0)
    with pytest.raises(ValueError):
        wilder_atr([1, 2], [1, 1], [1, 2], period=5)


def test_stop_loss_atr_modes():
    calc = StopLossCalculator("atr", 1.5)
    assert calc.compute(Direction.LONG, 100, 0, 0, atr=10.0) == pytest.approx(85.0)
    assert calc.compute(Direction.SHORT, 100, 0, 0, atr=10.0) == pytest.approx(115.0)
    with pytest.raises(ValueError):
        calc.compute(Direction.LONG, 100, 0, 0, atr=None)


def test_atr_period_validated():
    assert validate_settings(Settings(atr_period=0))


def _df():
    idx = pd.date_range("2024-01-02 09:30", periods=40, freq="5min", tz="America/New_York")
    rows = [(100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100 + i * 0.1) for i in range(3)]
    rows += [(100, 101, 99, 100)] * 2 + [(100, 108, 99, 105)] + \
        [(105, 115, 104, 112)] * 34
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def test_backtest_atr_stop_uses_signal_bar_atr():
    s = Settings(timezone="America/New_York", or_start="09:30", or_end="09:45",
                 trading_start="09:45", trading_end="11:30", symbols=("TST",),
                 stop_loss_mode="atr", stop_loss_value=1.5, atr_period=14,
                 breakeven_enabled=False)
    trades = BacktestEngine(s).run({"TST": _df()}).trades
    assert len(trades) >= 1
    for t in trades:
        assert t["atr"] and t["atr"] > 0
        assert abs(t["entry"] - t["stop"]) == pytest.approx(1.5 * t["atr"])


def test_trade_manager_refuses_atr_mode_without_atr():
    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    s = Settings(stop_loss_mode="atr", stop_loss_value=1.5)
    tm = TradeManager(s, MockBroker(10000.0, infos))
    sig = TradeSignal("TST", "2024-01-02", SignalType.LONG,
                      datetime(2024, 1, 2, 10, 0, tzinfo=Z), 105.0, 110.0, 100.0, "t",
                      atr=None)
    res = tm.handle_signal(sig, 10000.0)
    assert res["action"] == "ignore" and "atr" in res["reason"].lower()
