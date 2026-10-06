"""Data quality validation — a bad dataset must never silently produce a backtest."""
from __future__ import annotations

import pandas as pd

REQUIRED = ("open", "high", "low", "close")


def validate_ohlc(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if df.empty:
        return ["empty dataframe"]
    for c in REQUIRED:
        if c not in df.columns:
            issues.append(f"missing column {c}")
    if issues:
        return issues
    if not df.index.is_monotonic_increasing:
        issues.append("index not monotonic increasing")
    if df.index.has_duplicates:
        issues.append("duplicate timestamps")
    bad = df[(df["high"] < df["low"])]
    if len(bad):
        issues.append(f"{len(bad)} bars with high<low")
    bad2 = df[(df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))]
    if len(bad2):
        issues.append(f"{len(bad2)} bars with OHLC inconsistency")
    zero = df[(df[["open", "high", "low", "close"]] <= 0).any(axis=1)]
    if len(zero):
        issues.append(f"{len(zero)} bars with zero/negative prices")
    return issues
