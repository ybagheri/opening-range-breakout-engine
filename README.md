# Opening Range Breakout Engine (Python + MetaTrader 5)

> 🇮🇷 [فارسی | Persian Documentation](docs/README_FA.md)

A professional, systematic, object-oriented, modular, testable, configurable, production-oriented
**Opening Range Breakout (ORB) trading engine written entirely in Python** — no MQL5 EA required.
Python talks directly to the MetaTrader 5 terminal via the MetaTrader5 Python API:

```text
Python ORB Engine → MetaTrader5 Python API → MT5 Terminal → Broker
```

**Guiding principle:** build a robust trading *research and execution* engine, not a backtest
optimized to look good. Robustness > impressive backtest. Backtested performance never guarantees
future performance.

Strategy/research ideas were informed by
[sam-bateman/trading-orb](https://github.com/sam-bateman/trading-orb)
(OR definition, event-driven backtesting, walk-forward validation, robustness
suite, separation of strategy and execution) — re-designed here for MT5 indices (US30/US500/US100),
risk-based sizing with real tick value, and a broker-agnostic architecture. No code was copied.

## Strategy in brief

- Opening range = high/low of `OR_START_TIME → OR_END_TIME` (e.g. 09:30–09:45 New York).
- Breakout = price crossing OR high/low (+ optional buffer, optional close-confirmation).
  A bar touching **both** sides yields NO signal (conservative).
- Entries only inside `TRADING_START_TIME → TRADING_END_TIME`; forced flat at `FORCE_CLOSE_TIME`.
- Stop modes: `opposite | or_width_multiple | fixed_points | percent | atr`.
  TP modes: `risk_reward | or_width_multiple | fixed_points`. RR fully configurable.
- Fixed-fractional sizing from balance × risk % using real `tick_size/tick_value`,
  normalized to `volume_min/max/step`. Never assumes 1 point = $1.
- Optional breakeven move at `+BREAK_EVEN_TRIGGER_R`, daily loss guard, spread filter,
  magic-number strategy identity, SQLite state + journal, dry-run/paper modes.

## Project structure

```text
src/orb_engine/  config/ core/ strategy/ risk/ data/ broker/ backtest/
                 persistence/ analytics/ reporting/ execution/ utils/
tests/unit tests/integration  scripts/ data/ reports/ logs/ docs/
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in MT5 credentials (never commit .env)
```

MT5 setup: install the MT5 terminal (Windows), log in, enable *Algo Trading*, install the
`MetaTrader5` Python package (`pip install MetaTrader5`, Windows only). This repo needs **no EA**
on a chart. On Linux/macOS use `DRY_RUN=true` / paper mode and CSV backtests.

```bash
PYTHONPATH=src python -m orb_engine paper                          # validate config, show status
PYTHONPATH=src python -m orb_engine backtest --data-glob 'data/*.csv'
PYTHONPATH=src python -m orb_engine validate                       # unit tests
PYTHONPATH=src python -m orb_engine optimize
PYTHONPATH=src python -m orb_engine live                            # real execution (careful!)
pytest  # full suite (37 tests)
```

## Configuration

All strategy parameters live in `.env` (see `.env.example`); validated at startup with clear
errors. Key knobs: `MT5_SYMBOLS`, `TIMEZONE`, `OR_START_TIME/OR_END_TIME`,
`TRADING_START_TIME/TRADING_END_TIME`, `FORCE_CLOSE_TIME`, `RISK_PER_TRADE_PERCENT`,
`STOP_LOSS_MODE/VALUE`, `TAKE_PROFIT_MODE/VALUE`, `RISK_REWARD`, breakout buffer,
`BREAK_EVEN_ENABLED/TRIGGER_R`, `MAX_TRADES_*`, `MAX_DAILY_LOSS_PERCENT`, `DRY_RUN`.

Time model: **market time** (config `TIMEZONE`) for decisions, **broker/server time** only at the
MT5 boundary, **UTC** internally/for persistence, local PC clock never used for logic.
All datetimes are timezone-aware; naive datetimes are rejected.

## Backtesting & research

Event-driven, next-bar fills, spread/slippage/commission, conservative intrabar rule
(a bar hitting SL and TP counts the stop first), session windows, no look-ahead
(signals on closed bars only). Includes metrics (win rate, profit factor, expectancy, Sharpe,
Sortino, Calmar, drawdown, streaks, long/short + per-symbol splits), equity/R-distribution charts,
walk-forward harness, grid optimizer with overfit warnings, robustness checks
(slippage sweep, drop-best/worst, long-vs-short, parameter sensitivity), Monte Carlo
(drawdown dispersion, ruin probability), and config-hash reproducibility blocks in every report.

## Safety

Dry-run default (`DRY_RUN=true`), symbol validation, volume normalization (refuses to over-risk
below broker minimum), stop-level checks, duplicate protection (magic + symbol + session + state
store), restart recovery (reconciles existing positions), daily loss halt. See `docs/`.

## Docs & project management

- [Persian README](docs/README_FA.md) · [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md) · [HANDOFF.md](HANDOFF.md)

## Risk disclaimer

Research software. Trading involves substantial risk of loss. Backtests (even 10-year, validated
ones) do not guarantee live results — slippage, latency, partial fills, regime change apply.
Paper-trade extensively before risking capital. Not financial advice.
