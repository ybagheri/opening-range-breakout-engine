from datetime import datetime
from zoneinfo import ZoneInfo

from orb_engine.broker.mock import MockBroker
from orb_engine.config.settings import Settings
from orb_engine.core.types import SignalType, SymbolInfo, TradeSignal
from orb_engine.execution.trade_manager import TradeManager
from orb_engine.strategy.strategy import ORBStrategy

Z = ZoneInfo("America/New_York")
def S(**kw):
    base = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
                trading_start="09:45", trading_end="11:30", symbols=("US30","US500"),
                risk_per_trade_percent=0.5, stop_loss_mode="opposite",
                take_profit_mode="risk_reward", risk_reward=2.0, dry_run=False)
    base.update(kw); return Settings(**base)

def infos():
    return {"US30": SymbolInfo("US30",2,1.0,1.0,1.0,1,0.01,100,0.01),
            "US500": SymbolInfo("US500",1,0.1,0.1,2.5,50,0.01,100,0.01)}

def sig(sym, st="LONG"):
    return TradeSignal(sym,"2024-01-02",
        SignalType.LONG if st=="LONG" else SignalType.SHORT,
        datetime(2024,1,2,10,0,tzinfo=Z), 105.0, 110.0, 100.0, "t")

def test_symbol_states_independent():
    strat = ORBStrategy(S())
    assert strat.get_or("US30") is None and strat.get_or("US500") is None

def test_duplicate_signal_blocked_by_existing_position():
    b = MockBroker(10000, infos()); tm = TradeManager(S(), b)
    r1 = tm.handle_signal(sig("US30"), 10000)
    assert r1["action"] == "filled"
    r2 = tm.handle_signal(sig("US30"), 10000)
    assert r2["action"] == "ignore" and "existing" in r2["reason"]

def test_other_symbol_not_blocked():
    b = MockBroker(10000, infos()); tm = TradeManager(S(), b)
    tm.handle_signal(sig("US30"), 10000)
    r = tm.handle_signal(sig("US500"), 10000)
    assert r["action"] == "filled"

def test_dry_run_sends_nothing():
    b = MockBroker(10000, infos()); tm = TradeManager(S(dry_run=True), b)
    r = tm.handle_signal(sig("US30"), 10000)
    assert r["action"] == "dry_run" and len(b.orders_sent) == 0

def test_restart_recovery_sees_positions():
    b = MockBroker(10000, infos()); tm = TradeManager(S(), b)
    tm.handle_signal(sig("US30"), 10000)
    # simulate restart: new manager, same broker (account) must see position
    tm2 = TradeManager(S(), b)
    r = tm2.handle_signal(sig("US30"), 10000)
    assert r["action"] == "ignore"
