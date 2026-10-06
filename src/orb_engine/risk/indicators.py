"""Pure price indicators for risk models. No broker calls, no look-ahead:
every value at index i is computed from data at indices <= i only."""
from __future__ import annotations


def true_ranges(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """True Range per bar; first bar uses high-low (no prior close)."""
    if not (len(highs) == len(lows) == len(closes)) or not highs:
        raise ValueError("highs/lows/closes must be non-empty and equal length")
    out = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        out.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    return out


def wilder_atr(highs: list[float], lows: list[float], closes: list[float],
               period: int = 14) -> list[float | None]:
    """Wilder's ATR. First `period-1` entries are None (warm-up, honestly marked
    instead of backfilled). Entry [period-1] is the SMA of the first `period` TRs,
    then Wilder smoothing. Raises on non-positive period or short input."""
    if period < 1:
        raise ValueError("atr period must be >= 1")
    if len(closes) < period:
        raise ValueError(f"need >= {period} bars for ATR({period}), got {len(closes)}")
    tr = true_ranges(highs, lows, closes)
    out: list[float | None] = [None] * len(closes)
    seed = sum(tr[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(tr)):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out
