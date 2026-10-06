"""MT5 historical data provider (requires running terminal; Windows typically)."""
from __future__ import annotations

import pandas as pd

from orb_engine.data.base import MarketDataProvider


class MT5DataProvider(MarketDataProvider):
    def __init__(self, broker: object, tz: str):
        self.broker = broker
        self.tz = tz

    def get_bars(self, symbol: str, timeframe: str = "M5", count: int = 5000) -> pd.DataFrame:
        get = getattr(self.broker, "get_rates", None)
        if get is None:
            raise RuntimeError("broker does not support get_rates")
        df = get(symbol, timeframe, count)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(self.tz)
        return df.sort_index()
