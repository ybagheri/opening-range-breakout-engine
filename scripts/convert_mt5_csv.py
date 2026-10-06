"""Convert an MT5-exported CSV (e.g. data/US30_M1_UTC.csv) into engine-ready bars.

MT5 export format: Time(Open..) with '%Y.%m.%d %H:%M:%S' naive timestamps in the
terminal's timezone (usually UTC for this file), TickVolume for activity.

Usage:
    python scripts/convert_mt5_csv.py data/US30_M1_UTC.csv --symbol US30 \\
        --source-tz UTC --rule 5min --out data/US30_M5.csv
"""
from __future__ import annotations

import argparse

import pandas as pd


def convert(path: str, symbol: str, source_tz: str, rule: str | None) -> pd.DataFrame:
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["Time"], format="%Y.%m.%d %H:%M:%S", utc=False)
    ts = ts.dt.tz_localize(source_tz)
    cols = {c.lower(): c for c in df.columns}
    # NOTE: use .to_numpy() — passing Series with a RangeIndex alongside a
    # DatetimeIndex would align on labels and silently produce all-NaN columns.
    frame = pd.DataFrame({
        "open": df[cols["open"]].to_numpy(dtype=float),
        "high": df[cols["high"]].to_numpy(dtype=float),
        "low": df[cols["low"]].to_numpy(dtype=float),
        "close": df[cols["close"]].to_numpy(dtype=float),
        "volume": (df[cols["tickvolume"]].to_numpy(dtype=float)
                   if "tickvolume" in cols else 0.0),
    }, index=ts)
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="first")]
    if rule:
        agg = {"open": "first", "high": "max", "low": "min", "close": "last",
               "volume": "sum"}
        frame = frame.resample(rule, origin="start_day").agg(agg).dropna()
    return frame


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--symbol", default="US30")
    ap.add_argument("--source-tz", default="UTC")
    ap.add_argument("--rule", default="5min", help="'none' keeps native timeframe")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rule = None if a.rule.lower() == "none" else a.rule
    frame = convert(a.input, a.symbol, a.source_tz, rule)
    out = a.out or f"data/{a.symbol}_{(rule or 'M1').replace('min', '')}.csv"
    frame.to_csv(out)
    print(f"wrote {out}: {len(frame)} bars {frame.index[0]} -> {frame.index[-1]}")


if __name__ == "__main__":
    main()
