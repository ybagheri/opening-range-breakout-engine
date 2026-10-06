"""v1.4.0 tests: trailing-stop math, ratchet discipline, backtest + live wiring."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.broker.mock import MockBroker
from orb_engine.config.settings import Settings, validate_settings
from orb_engine.core.types import Direction, ExitReason, SignalType, SymbolInfo, TradeSignal
from orb_engine.execution.trade_manager import TradeManager
from orb_engine.risk.trailing import TrailingStop

Z = ZoneInfo("America/New_York")


def test_candidate_gating_and_levels():
    t = TrailingStop(True, trigger_r=1.5, offset_r=0.5)
    assert t.candidate(Direction.LONG, 100, 114, 10) is None  # +1.4R < 1.5
    assert t.candidate(Direction.LONG, 100, 115, 10) == pytest.approx(110.0)
    assert t.candidate(Direction.SHORT, 100, 85, 10) == pytest.approx(90.0)
    assert TrailingStop(False).candidate(Direction.LONG, 100, 200, 10) is None
    assert TrailingStop(True).candidate(Direction.LONG, 100, 200, 0) is None


def test_ratchet_never_moves_backwards():
    assert TrailingStop.ratchet(Direction.LONG, 90, [95, 92, None]) == 95
    assert TrailingStop.ratchet(Direction.LONG, 90, [80]) == 90
    assert TrailingStop.ratchet(Direction.SHORT, 110, [105, 108, None]) == 105
    assert TrailingStop.ratchet(Direction.SHORT, 110, [120]) == 110


def test_trail_settings_validation():
    assert validate_settings(Settings(trail_enabled=True, trail_trigger_r=0))
    assert validate_settings(Settings(trail_enabled=True, trail_offset_r=-1))
    assert not validate_settings(Settings(trail_enabled=True, trail_trigger_r=1.5,
                                          trail_offset_r=0.5))


def test_backtest_trail_stop_reason():
    from orb_engine.core.types import Bar
    s = Settings(trail_enabled=True, trail_trigger_r=1.0, trail_offset_r=0.5,
                 breakeven_enabled=False)
    eng = BacktestEngine(s)
    b1 = Bar("T", datetime(2024, 1, 2, 10, 0, tzinfo=Z), 100, 115, 99, 112)  # trail -> 110
    b2 = Bar("T", datetime(2024, 1, 2, 10, 5, tzinfo=Z), 112, 113, 105, 106)  # low hits 110
    px, ts, reason, be, tr = eng._simulate([b1, b2], Direction.LONG, 100, 90, 200, None)
    assert reason == ExitReason.TRAIL_STOP and tr and not be
    assert px == pytest.approx(110.0)


def _managed_setup(**kw):
    base = dict(timezone="America/New_York", symbols=("TST",),
                breakeven_enabled=False, trail_enabled=True,
                trail_trigger_r=1.0, trail_offset_r=0.5, dry_run=False)
    base.update(kw)
    s = Settings(**base)
    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    b = MockBroker(10000.0, infos)
    return s, TradeManager(s, b, state=None), b


def _long_signal(price=105.0):
    return TradeSignal("TST", "2024-01-02", SignalType.LONG,
                       datetime(2024, 1, 2, 10, 0, tzinfo=Z), price, 110.0, 100.0, "t")


def test_live_trail_ratchets_and_never_retreats():
    s, tm, b = _managed_setup()
    res = tm.handle_signal(_long_signal(), 10000.0)  # entry 105, stop 100, risk 5
    assert res["action"] == "filled"
    ticket = res["ticket"]
    acts = tm.manage_open({ticket: 111.0})  # +1.2R -> trail 111-2.5=108.5
    assert acts and acts[0]["trail"] and acts[0]["new_sl"] == pytest.approx(108.5)
    acts2 = tm.manage_open({ticket: 106.0})  # pullback: no retreat below 108.5
    assert acts2 == []
    assert b.open_positions()[0].stop_loss == pytest.approx(108.5)
    acts3 = tm.manage_open({ticket: 115.0})  # new extreme -> 112.5
    assert acts3 and acts3[0]["new_sl"] == pytest.approx(112.5)


def test_live_trail_composes_with_breakeven():
    s, tm, b = _managed_setup(breakeven_enabled=True, breakeven_trigger_r=1.0)
    res = tm.handle_signal(_long_signal(), 10000.0)
    ticket = res["ticket"]
    acts = tm.manage_open({ticket: 112.0})  # +1.4R: BE=105, trail=109.5 -> most protective
    assert acts and acts[0]["new_sl"] == pytest.approx(109.5)
    assert acts[0]["trail"] and not acts[0]["breakeven"]
