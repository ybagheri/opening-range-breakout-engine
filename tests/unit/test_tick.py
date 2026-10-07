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


def test_poll_ticks_manages_each_symbol(tmp_path):
    from orb_engine.broker.paper import PaperBroker

    e = _engine(state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    assert isinstance(e.broker, MockBroker)
    pos = _long(e.broker)
    pos.magic = e.s.magic
    # MockBroker quotes 100.0/100.02 — far below BE trigger at +1R (110)
    ts = datetime(2024, 1, 2, 10, 0, tzinfo=Z)
    out = e.poll_ticks(ts)
    assert out == [{"symbol": "TST", "action": "none"}]
    # move quote above trigger via PaperBroker-backed engine
    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                dry_run=False, breakeven_enabled=True, breakeven_trigger_r=1.0,
                trail_enabled=False, state_db=str(tmp_path / "s2.db"),
                journal_db=str(tmp_path / "j2.db"))
    pb = PaperBroker(10000.0, dict(infos))
    e2 = ORBEngine(Settings(**base), pb)
    pb._ticket += 1
    p2 = Position(pb._ticket, "TST", Direction.LONG, 1.0, 100.0, 90.0, 120.0,
                  e2.s.magic, "ORB_ENGINE", "2024-01-02")
    pb._positions.append(p2)
    pb.set_quote("TST", 110.0, 110.1)
    out2 = e2.poll_ticks(ts)
    assert out2[0]["action"] == "managed"
    assert pb.open_positions()[0].stop_loss == 100.0


def test_poll_ticks_skips_bad_quotes(tmp_path):
    class FlakyBroker(MockBroker):
        def current_price(self, symbol):
            raise RuntimeError("no tick")

    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    e = ORBEngine(Settings(**base), FlakyBroker(10000.0, dict(INFO)))
    ts = datetime(2024, 1, 2, 10, 0, tzinfo=Z)
    assert e.poll_ticks(ts) == []  # logged + skipped, never raises


def test_poll_once_runs_tick_management(tmp_path):
    # SHORT must be managed at ASK: bid alone would not trigger,
    # ask deep in profit must move the stop.
    from orb_engine.broker.paper import PaperBroker

    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                dry_run=True, breakeven_enabled=True, breakeven_trigger_r=1.0,
                trail_enabled=False, state_db=str(tmp_path / "s.db"),
                journal_db=str(tmp_path / "j.db"))
    pb = PaperBroker(10000.0, dict(infos))
    e = ORBEngine(Settings(**base), pb)
    pb._ticket += 1
    pb._positions.append(Position(pb._ticket, "TST", Direction.SHORT, 1.0,
                                  100.0, 110.0, 80.0, e.s.magic,
                                  "ORB_ENGINE", "2024-01-02"))
    pb.set_quote("TST", 105.0, 90.0)  # ask at +1R triggers BE
    # no rates support on PaperBroker -> bar loop skips, tick sweep still runs
    e.poll_once()
    assert pb.open_positions()[0].stop_loss == 100.0


def test_tick_poll_seconds_validated(tmp_path):
    from orb_engine.config.settings import validate_settings

    assert validate_settings(Settings(tick_poll_seconds=0.0))
    assert validate_settings(Settings(tick_poll_seconds=-1.0))
    assert not validate_settings(Settings(tick_poll_seconds=2.5))


def test_run_live_poll_sweeps_ticks_between_bars(tmp_path, monkeypatch):
    from orb_engine.broker.paper import PaperBroker

    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                dry_run=True, breakeven_enabled=True, breakeven_trigger_r=1.0,
                trail_enabled=False, tick_poll_seconds=5.0,
                state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    pb = PaperBroker(10000.0, dict(infos))
    e = ORBEngine(Settings(**base), pb)
    calls: list[str] = []
    orig_bars = e._poll_bars
    orig_ticks = e.poll_ticks

    def fake_bars(*a, **k):
        calls.append("bars")
        return orig_bars(*a, **k)

    def fake_ticks(*a, **k):
        calls.append("ticks")
        return orig_ticks(*a, **k)

    monkeypatch.setattr(e, "_poll_bars", fake_bars)
    monkeypatch.setattr(e, "poll_ticks", fake_ticks)
    monkeypatch.setattr("orb_engine.execution.engine.time.sleep", lambda s: None)
    e.run_live_poll(poll_seconds=60, max_iters=3)
    assert calls[0] == "bars"  # bar poll due immediately on start
    assert calls.count("ticks") == 3  # fast leg runs every iteration
    assert calls.count("bars") == 1  # slow leg waits out poll_seconds


def test_run_live_poll_survives_tick_failure(tmp_path, monkeypatch):
    from orb_engine.broker.paper import PaperBroker

    infos = {"TST": SymbolInfo("TST", 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01)}
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("TST",),
                state_db=str(tmp_path / "s.db"), journal_db=str(tmp_path / "j.db"))
    e = ORBEngine(Settings(**base), PaperBroker(10000.0, dict(infos)))

    def boom(*a, **k):
        raise RuntimeError("quote feed down")

    monkeypatch.setattr(e, "poll_ticks", boom)
    monkeypatch.setattr(e, "_poll_bars", lambda *a, **k: [])
    monkeypatch.setattr("orb_engine.execution.engine.time.sleep", lambda s: None)
    e.run_live_poll(poll_seconds=60, max_iters=2)  # must not raise
