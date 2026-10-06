"""MarketDataProvider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str = "M5") -> pd.DataFrame:
        """Return tz-aware-indexed OHLCV DataFrame with columns open/high/low/close[/volume]."""
