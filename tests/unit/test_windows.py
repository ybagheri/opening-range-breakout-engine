from datetime import datetime
from zoneinfo import ZoneInfo

from orb_engine.core.sessions import SessionConfig, SessionManager

Z = ZoneInfo("America/New_York")
CFG = SessionConfig("America/New_York","09:30","09:45","09:45","11:30","15:50")

def at(hm):
    h,m = map(int,hm.split(":"))
    return datetime(2024,1,2,h,m,tzinfo=Z)

def test_windows():
    sm = SessionManager(CFG)
    assert sm.in_or_window(at("09:35"))
    assert not sm.in_or_window(at("09:45"))
    assert sm.or_complete(at("09:45"))
    assert sm.in_entry_window(at("09:45"))  # inclusive boundary
    assert sm.in_entry_window(at("11:30"))
    assert not sm.in_entry_window(at("11:31"))
    assert not sm.in_entry_window(at("09:44"))
    assert sm.force_close_due(at("15:50"))
    assert not sm.force_close_due(at("15:49"))
