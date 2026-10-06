import pytest

from orb_engine.core.types import SymbolInfo
from orb_engine.risk.sizing import position_size


def info():
    return SymbolInfo("US30", 2, 1.0, 1.0, 1.0, 1.0, 0.01, 100.0, 0.01)

def test_risk_levels():
    for pct, amt in [(0.25,25.0),(0.5,50.0),(1.0,100.0)]:
        r = position_size(10000, pct, 100.0, 95.0, info())
        assert r.risk_amount == pytest.approx(amt)
        assert r.volume == pytest.approx(amt/5.0)  # stop dist 5, tick 1/1 -> 5 loss per unit

def test_invalid_risk():
    import pytest as p
    with p.raises(ValueError):
        position_size(10000, 0, 100, 95, info())
    with p.raises(ValueError):
        position_size(10000, -1, 100, 95, info())

def test_below_min_volume_flagged():
    i = SymbolInfo("X",2,0.01,0.01,0.01,1,1.0,100,0.5)
    r = position_size(100, 0.1, 100.0, 90.0, i)  # tiny risk, wide stop -> tiny volume
    assert r.capped_or_floored == "below_min" and r.volume == 1.0

def test_max_volume():
    i = SymbolInfo("X",2,0.01,0.01,100.0,1,0.01,0.5,0.01)
    r = position_size(10_000_000, 5, 100.0, 99.0, i)
    assert r.volume == 0.5 and r.capped_or_floored == "above_max"

def test_no_dollar_point_assumption():
    i = SymbolInfo("US500",1,0.1,0.1,2.5,50,0.01,100,0.01)  # tick_value != point
    r = position_size(10000, 0.5, 5000.0, 4990.0, i)
    ticks = 10.0/0.1
    assert r.loss_per_unit_volume == pytest.approx(ticks*2.5)
