"""Tick-level management: on_tick runs BE/trailing per tick, force-close first."""
from datetime import datetime
from zoneinfo import ZoneInfo

from orb_engine.broker.mock import MockBroker
from orb_engine.config.settings import Settings
from orb_engine.core.types import Direction, Position, SymbolInfo
from orb_engine.execution.engine import ORBEngine

Z = ZoneInfo("America/New_York")
INFO = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}


def _engine(**kw):
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                dry_run=False, breakeven_enabled=True, breakeven_trigger_r=1.0,
                trail_enabled=False)
    base.update(kw)
    return ORBEngine(Settings(**base), MockBroker(10000.0, dict(INFO)))


def _long(broker, entry=100.0, sl=90.0, tp=120.0):
    broker._ticket += 1
    pos = Position(broker._ticket, "TST", Direction.LONG, 1.0, entry, sl, tp,
                   12345, "ORB_ENGINE", "2024-01-02")
    # default magic in Settings; align position magic with engine settings
    broker._positions.append(pos)
    return pos


def test_on_tick_no_positions_is_none(tmp_path):
    e = _engine(state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    # align: engine default magic vs position filter — no positions at all
    ts = datetime(2024, 1, 2, 10, 0, tzinfo=Z)
    assert e.on_tick("TST", 100.0, 100.1, ts) == {"action": "none"}


def test_on_tick_moves_breakeven(tmp_path):
    e = _engine(state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    e.tm.s = e.s
    pos = _long(e.broker)
    pos.magic = e.s.magic
    ts = datetime(2024, 1, 2, 10, 0, tzinfo=Z)
    # +1R at 110 (risk 10): BE triggers, stop moves to entry
    out = e.on_tick("TST", 110.0, 110.1, ts)
    assert out["action"] == "managed"
    assert e.broker.open_positions()[0].stop_loss == 100.0


def test_on_tick_short_uses_ask(tmp_path):
    e = _engine(state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    e.broker._ticket += 1
    pos = Position(e.broker._ticket, "TST", Direction.SHORT, 1.0, 100.0, 110.0, 80.0,
                   e.s.magic, "ORB_ENGINE", "2024-01-02")
    e.broker._positions.append(pos)
    ts = datetime(2024, 1, 2, 10, 0, tzinfo=Z)
    # bid alone would NOT trigger (+0.5R at 105); ask at 90 is +1R -> triggers
    out = e.on_tick("TST", 105.0, 90.0, ts)
    assert out["action"] == "managed"
    assert e.broker.open_positions()[0].stop_loss == 100.0


def test_on_tick_force_close_takes_precedence(tmp_path):
    e = _engine(state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"),
                force_close_time="10:00", allow_overnight=False)
    pos = _long(e.broker)
    pos.magic = e.s.magic
    ts = datetime(2024, 1, 2, 10, 1, tzinfo=Z)
    out = e.on_tick("TST", 200.0, 200.1, ts)  # would manage, but force-close wins
    assert out["action"] == "force_close"
    assert e.broker.open_positions() == []
