from orb_engine.core.types import Direction
from orb_engine.risk.breakeven import BreakEvenManager
from orb_engine.risk.stop_loss import StopLossCalculator
from orb_engine.risk.take_profit import TakeProfitCalculator


def test_sl_opposite():
    c = StopLossCalculator("opposite", 1.0)
    assert c.compute(Direction.LONG, 105, 110, 100) == 100
    assert c.compute(Direction.SHORT, 105, 110, 100) == 110

def test_sl_width_multiple():
    c = StopLossCalculator("or_width_multiple", 0.5)
    assert c.compute(Direction.LONG, 105, 110, 100) == 100.0

def test_rr_symmetry():
    # entry=100 sl=95 risk=5 rr=2 -> long tp=110; short mirror entry=100 sl=105 -> tp=90
    t = TakeProfitCalculator("risk_reward", 2.0, 2.0)
    assert t.compute(Direction.LONG, 100, 95) == 110
    assert t.compute(Direction.SHORT, 100, 105) == 90

def test_breakeven_disabled():
    b = BreakEvenManager(False, 1.0, 0.0)
    assert not b.should_trigger(Direction.LONG, 100, 120, 95)

def test_breakeven_trigger():
    b = BreakEvenManager(True, 1.0, 0.0)
    assert not b.should_trigger(Direction.LONG, 100, 104, 95)  # +4 < 5
    assert b.should_trigger(Direction.LONG, 100, 105, 95)
    assert b.new_stop(Direction.LONG, 100, 0.01) == 100

def test_breakeven_repeated_trigger_idempotent():
    b = BreakEvenManager(True, 1.0, 0.0)
    assert b.should_trigger(Direction.SHORT, 100, 94, 105)
    assert b.should_trigger(Direction.SHORT, 100, 90, 105)
