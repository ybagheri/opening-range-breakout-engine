"""Retest-hypothesis study (RESEARCH ONLY — not engine code).

Question: after an OR breakout, does waiting for price to retest the broken level
before entering beat immediate next-bar entry?

Method (same execution assumptions as the engine; reuse BacktestEngine._simulate):
  For each baseline trade (OPP-noBE, 15-min OR):
    1. Classify: did price touch back to the broken level within the next 3 M5 bars
       after the breakout bar? (LONG touch: bar low <= or_high; SHORT: high >= or_low)
    2. Group comparison: R multiples of retested vs straight-run signals, same rules.
    3. Deferred simulation: if a touch occurs within 3 bars, enter at that bar's
       close (executable, known at close), keep the OR-side stop, recompute
       RR=2 target from the new entry; skip the trade if no touch. Compare totals.

A filter gets implemented only if deferred entry wins convincingly AND the group
gap is stark. With ~36 sessions, inconclusive is the expected honest outcome.

Usage: python scripts/research_retest.py (uses data/US30_M5.csv if present)
"""
from __future__ import annotations

import pandas as pd

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.config.settings import Settings
from orb_engine.core.types import Direction
from orb_engine.data.models import bars_from_df
from orb_engine.utils.time_utils import combine_market_time

DATA = "data/US30_M5.csv"
TOUCH_BARS = 3


def load():
    df = pd.read_csv(DATA, parse_dates=True, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    return df


def base_settings(**kw):
    d = dict(timezone="America/New_York", or_start="09:30", or_end="09:45",
             trading_start="09:45", trading_end="11:30", symbols=("US30",),
             point_overrides={"US30": 0.1}, breakeven_enabled=False)
    d.update(kw)
    return Settings(**d)


def main() -> None:
    df = load()
    s = base_settings()
    eng = BacktestEngine(s)
    base = eng.run({"US30": df}).trades
    bars = bars_from_df(df, "US30", s.timezone)
    by_time = {b.timestamp: b for b in bars}
    order = sorted(by_time)

    retested_r, straight_r, deferred = [], [], []
    for t in base:
        sig = pd.Timestamp(t["signal_time"])
        day = t["session_date"]
        long = t["direction"] == "LONG"
        level = t["or_high"] if long else t["or_low"]
        idx = order.index(sig.tz_convert(order[0].tzinfo)
                          if sig.tzinfo is None else sig)
        touch_bar = None
        for j in range(idx + 1, min(idx + 1 + TOUCH_BARS, len(order))):
            b = by_time[order[j]]
            if b.timestamp.strftime("%Y-%m-%d") != day:
                break
            touched = (b.low <= level) if long else (b.high >= level)
            if touched:
                touch_bar = b
                break
        if touch_bar is None:
            straight_r.append(t["r_multiple"])
            continue
        retested_r.append(t["r_multiple"])
        # deferred entry at touch-bar close; same OR stop; RR=2 target recomputed
        direction = Direction.LONG if long else Direction.SHORT
        entry = touch_bar.close
        stop = t["stop"]
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        tp = eng.tp_calc.compute(direction, entry, stop, t["or_high"], t["or_low"], 0.1)
        # forward bars after the touch bar, same session
        pos = order.index(touch_bar.timestamp)
        fwd = [by_time[k] for k in order[pos + 1:]
               if k.strftime("%Y-%m-%d") == day]
        if not fwd:
            continue
        px, _, reason, _, _ = eng._simulate(fwd, direction, entry, stop, tp, None)
        r = ((px - entry) if long else (entry - px)) / risk
        deferred.append(r)

    def summ(xs):
        xs = list(xs)
        return f"n={len(xs)} netR={sum(xs):.1f} win={sum(1 for x in xs if x > 0) / len(xs):.2f}" \
            if xs else "n=0"

    print(f"baseline : {summ(t['r_multiple'] for t in base)}")
    print(f"retested : {summ(retested_r)}")
    print(f"straight : {summ(straight_r)}")
    print(f"deferred : {summ(deferred)} (skipped {len(base) - len(deferred)} no-touch)")


if __name__ == "__main__":
    main()
