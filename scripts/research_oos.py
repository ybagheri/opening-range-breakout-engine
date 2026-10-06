"""Out-of-sample stability study (RESEARCH ONLY — not engine code).

Question: do the in-sample picks (no-BE over BE, opposite ~= ATR, trailing
TR1.5-0.5 best of 3 tried) hold up across time, or are they full-sample
selection artefacts?

Method: chronological split of tradeable sessions into FIRST / SECOND halves.
Honest label — this is a STABILITY check, not true OOS: the picks were selected
on the full sample, so neither half is unseen. Each config runs per block via
BacktestEngine with identical assumptions (15-min OR, RR=2, same costs);
per-block runs recompute ATR on block history only (short warm-up skips safely,
never guesses). OR construction is per-day, so day-splitting leaks nothing else.

Verdict metric is RANK STABILITY of the in-sample winner across halves, not the
level of any half (n≈18 sessions per half is far too small for conclusions).

Usage: PYTHONPATH=src python3 scripts/research_oos.py (uses data/US30_M5.csv)
"""
from __future__ import annotations

import pandas as pd

from orb_engine.backtest.engine import BacktestEngine
from orb_engine.config.settings import Settings

DATA = "data/US30_M5.csv"

CONFIGS: dict[str, dict] = {
    "opp_nobe": {"stop_loss_mode": "opposite", "breakeven_enabled": False},
    "opp_be": {"stop_loss_mode": "opposite", "breakeven_enabled": True},
    "atr15_nobe": {"stop_loss_mode": "atr", "stop_loss_value": 1.5,
                   "breakeven_enabled": False},
    "trail15_05": {"stop_loss_mode": "opposite", "breakeven_enabled": False,
                   "trail_enabled": True, "trail_trigger_r": 1.5,
                   "trail_offset_r": 0.5},
    "trail10_05": {"stop_loss_mode": "opposite", "breakeven_enabled": False,
                   "trail_enabled": True, "trail_trigger_r": 1.0,
                   "trail_offset_r": 0.5},
}


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=True, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    df.columns = [c.lower() for c in df.columns]
    return df


def make_settings(**kw) -> Settings:
    base = {"timezone": "America/New_York", "or_start": "09:30", "or_end": "09:45",
            "trading_start": "09:45", "trading_end": "11:30", "symbols": ("US30",),
            "point_overrides": {"US30": 0.1}}
    base.update(kw)
    return Settings(**base)


def summ(trades: list[dict]) -> str:
    if not trades:
        return "n=0"
    rs = [t["r_multiple"] for t in trades]
    win = sum(1 for r in rs if r > 0) / len(rs)
    return f"n={len(rs)} netR={sum(rs):.1f} win={win:.2f}"


def main() -> None:
    df = load()
    days = sorted({d.date() for d in df.index})
    mid = len(days) // 2
    blocks = {"FIRST": set(days[:mid]), "SECOND": set(days[mid:])}
    print(f"sessions: {len(days)} ({days[0]} -> {days[-1]}); "
          f"FIRST={len(blocks['FIRST'])} SECOND={len(blocks['SECOND'])}")
    table: dict[str, dict[str, list[dict]]] = {c: {} for c in CONFIGS}
    for name, kw in CONFIGS.items():
        eng = BacktestEngine(make_settings(**kw))
        for block, dayset in blocks.items():
            sub = df[[d.date() in dayset for d in df.index]]
            table[name][block] = eng.run({"US30": sub}).trades
    width = max(len(n) for n in CONFIGS)
    for block in ("FIRST", "SECOND"):
        print(f"--- {block} half ---")
        ranked = sorted(CONFIGS, key=lambda n: sum(t["r_multiple"] for t in table[n][block]),
                        reverse=True)
        for name in ranked:
            print(f"  {name:<{width}} : {summ(table[name][block])}")
    print("--- full sample (selection basis; for reference, not validation) ---")
    for name, kw in CONFIGS.items():
        eng = BacktestEngine(make_settings(**kw))
        print(f"  {name:<{width}} : {summ(eng.run({'US30': df}).trades)}")


if __name__ == "__main__":
    main()
