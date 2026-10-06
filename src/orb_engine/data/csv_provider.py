"""CSV / Parquet historical provider."""
from __future__ import annotations

import pandas as pd

from orb_engine.data.base import MarketDataProvider
from orb_engine.data.validation import validate_ohlc


class CSVDataProvider(MarketDataProvider):
    def __init__(self, paths: dict[str, str], tz: str = "America/New_York"):
        self.paths = paths
        self.tz = tz

    def get_bars(self, symbol: str, timeframe: str = "M5") -> pd.DataFrame:
        p = self.paths[symbol]
        if p.endswith(".parquet"):
            df = pd.read_parquet(p)
        else:
            df = pd.read_csv(p, parse_dates=True, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(self.tz)
        df.columns = [c.lower() for c in df.columns]
        issues = validate_ohlc(df)
        if issues:
            raise ValueError(f"data quality issues for {symbol}: {issues}")
        return df.sort_index()
