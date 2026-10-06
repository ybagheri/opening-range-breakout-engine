"""Data helpers: DataFrame <-> Bar conversion."""
from __future__ import annotations

import pandas as pd

from orb_engine.core.types import Bar


def bars_from_df(df: pd.DataFrame, symbol: str, tz: str) -> list[Bar]:
    out: list[Bar] = []
    for ts, row in df.iterrows():
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize(tz)
        else:
            t = t.tz_convert(tz)
        out.append(Bar(symbol, t.to_pydatetime(), float(row["open"]), float(row["high"]),
                       float(row["low"]), float(row["close"]), float(row.get("volume", 0.0))))
    return sorted(out, key=lambda b: b.timestamp)
