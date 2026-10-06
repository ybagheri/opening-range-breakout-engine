from datetime import datetime
from zoneinfo import ZoneInfo

from orb_engine.core.types import Bar, OpeningRange, SignalType
from orb_engine.strategy.breakout import BreakoutDetector

Z = ZoneInfo("America/New_York")
OR = OpeningRange("US30","2024-01-02",datetime(2024,1,2,9,30,tzinfo=Z),datetime(2024,1,2,9,45,tzinfo=Z),110,100)

def bar(hm, o,h,l,c):
    hh,mm = map(int,hm.split(":"))
    return Bar("US30", datetime(2024,1,2,hh,mm,tzinfo=Z), o,h,l,c)

def test_long():
    d = BreakoutDetector()
    s = d.detect(bar("10:00",109,111,108,110.5), OR, "2024-01-02")
    assert s.signal_type == SignalType.LONG

def test_short():
    d = BreakoutDetector()
    s = d.detect(bar("10:00",101,102,99,99.5), OR, "2024-01-02")
    assert s.signal_type == SignalType.SHORT

def test_no_breakout():
    d = BreakoutDetector()
    s = d.detect(bar("10:00",104,106,103,105), OR, "2024-01-02")
    assert s.signal_type == SignalType.NO_SIGNAL

def test_buffer_blocks_false_breakout():
    d = BreakoutDetector(buffer_points=2.0)
    s = d.detect(bar("10:00",109,111,108,110), OR, "2024-01-02")  # high=111 < 112
    assert s.signal_type == SignalType.NO_SIGNAL

def test_boundary_exact_is_no_signal():
    d = BreakoutDetector()
    s = d.detect(bar("10:00",104,110,105,108), OR, "2024-01-02")  # high == or_high
    assert s.signal_type == SignalType.NO_SIGNAL

def test_ambiguous_both_sides():
    d = BreakoutDetector()
    s = d.detect(bar("10:00",105,112,98,104), OR, "2024-01-02")
    assert s.signal_type == SignalType.NO_SIGNAL and "ambiguous" in s.reason

def test_require_close():
    d = BreakoutDetector(require_close=True)
    s = d.detect(bar("10:00",104,115,104,108), OR, "2024-01-02")  # wick breaks, close inside
    assert s.signal_type == SignalType.NO_SIGNAL
