from datetime import datetime
from zoneinfo import ZoneInfo

from orb_engine.core.types import Bar
from orb_engine.strategy.opening_range import OpeningRangeBuilder

TZ = "America/New_York"
Z = ZoneInfo(TZ)

def mk(sym, hm, o, h, l, c, day="2024-01-02"):
    h_, m_ = map(int, hm.split(":"))
    ts = datetime(2024, 1, 2, h_, m_, tzinfo=Z)
    return Bar(sym, ts, o, h, l, c)

def ors():
    return (datetime(2024,1,2,9,30,tzinfo=Z), datetime(2024,1,2,9,45,tzinfo=Z))

def test_normal_range():
    b = OpeningRangeBuilder()
    bars = [mk("US30","09:30",100,102,99,101), mk("US30","09:35",101,103,100,102)]
    r, v = b.build(bars, "US30", "2024-01-02", *ors())
    assert v.ok and r.high == 103 and r.low == 99 and r.width == 4

def test_missing_bars():
    b = OpeningRangeBuilder()
    r, v = b.build([], "US30", "2024-01-02", *ors())
    assert not v.ok

def test_zero_width():
    b = OpeningRangeBuilder()
    bars = [mk("US30","09:30",100,100,100,100)]
    r, v = b.build(bars, "US30", "2024-01-02", *ors())
    assert not v.ok and "zero-width" in v.reason

def test_invalid_ohlc():
    b = OpeningRangeBuilder()
    bars = [mk("US30","09:30",100,90,99,101)]
    r, v = b.build(bars, "US30", "2024-01-02", *ors())
    assert not v.ok

def test_duplicate_timestamps():
    b = OpeningRangeBuilder()
    bars = [mk("US30","09:30",100,102,99,101), mk("US30","09:30",100,102,99,101)]
    r, v = b.build(bars, "US30", "2024-01-02", *ors())
    assert not v.ok and "duplicated" in v.reason
