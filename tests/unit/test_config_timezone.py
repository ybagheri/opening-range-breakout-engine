from datetime import datetime

import pytest

from orb_engine.config.settings import Settings, validate_settings
from orb_engine.utils.time_utils import combine_market_time, ensure_aware, to_utc


def test_invalid_configs_rejected():
    s = Settings(risk_per_trade_percent=-1)
    assert validate_settings(s)
    s = Settings(risk_per_trade_percent=10)
    assert validate_settings(s)
    s = Settings(risk_reward=0)
    assert validate_settings(s)
    s = Settings(or_start="09:45", or_end="09:30")
    assert validate_settings(s)
    s = Settings(trading_start="12:00", trading_end="11:00")
    assert validate_settings(s)

def test_naive_rejected():
    with pytest.raises(ValueError):
        to_utc(datetime(2024,1,1,10,0))
    mkt = combine_market_time("2024-01-01", "09:30", "America/New_York")
    assert mkt.tzinfo is not None
    aware = ensure_aware(datetime(2024,1,1,10,0), "UTC")
    assert aware.tzinfo is not None
