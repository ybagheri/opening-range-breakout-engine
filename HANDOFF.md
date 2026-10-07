# Project Handoff

Current Phase: Phase 13 — Documentation and final audit
Status: v1.8.2 (decoupled fast tick cadence in run_live_poll; clean tree)

Completed: Phases 1–13 (all boxes in ROADMAP.md checked).

Current Git Commit: see `git log` (v1.0.0 audit commit).

Implemented:
- ORB strategy engine (OpeningRangeBuilder, BreakoutDetector, ORBStrategy) — broker-independent.
- Risk (fixed-fractional sizing via tick value, SL/TP calculators, breakeven, daily guards).
- Data layer (MarketDataProvider, CSV + MT5 providers, OHLC validation, TZ-aware bars).
- Backtest engine (event-driven, next-bar fills, spread/slippage/commission, conservative
  intrabar policy) + metrics, equity/R charts, walk-forward, optimizer, robustness, Monte Carlo.
- Execution (Broker ABC, Mock/Paper/MT5 brokers, idempotent TradeManager, ORBEngine live loop
  with startup recovery + force-close + per-tick BE/trailing management).
- Persistence (SQLite state + journal), reporting (config-hash reports), CLI (6 commands).

Tests: `pytest` — 81 passed, 5 MT5-terminal tests skip without a terminal. `ruff`/`mypy` clean.
### v1.8.2 additions
- `TICK_POLL_SECONDS` (default 5.0s): `run_live_poll` interleaves slow bar polls
  with a fast `poll_ticks` sweep; split `poll_once` into `_poll_bars` + tick leg.
  3 new tests in `tests/unit/test_tick.py`.
### v1.8.1 additions
- `ORBEngine.poll_ticks` sweeps every symbol's live quote through `on_tick`
  (force-close + direction-aware BE/trailing); `poll_once` ends with it instead
  of the old bid-only `manage_open`. 3 new tests in `tests/unit/test_tick.py`.
### v1.8.0 additions
- `ORBEngine.on_tick` runs tick-level BE/trailing via `TradeManager.manage_open`
  (direction-aware exit prices: LONG at bid, SHORT at ask); force-close keeps
  precedence. 4 new tests in `tests/unit/test_tick.py`.
### Unreleased research
- Retest study (`scripts/research_retest.py`): no evidence for deferred entry — retest
  filter remains research-only/code-free. FA README refreshed to v1.7.
- OOS stability study (`scripts/research_oos.py`): chronological 23/23-session halves
  (18 tradeable each). Trail15_05 ranks #2/#1 (top-2 both halves), noBE beats BE both
  halves, ATR swings #1 → #4. Modest stability signal for trailing, none strong enough
  to change defaults — trail stays OFF pending fresh data. FA README at v1.8.
### v1.7.0 additions
- Terminal-gated integration suite + CI workflows. To verify live: Windows + demo terminal,
  `MT5_RUN_LIVE_TESTS=1 pytest tests/integration/test_mt5_terminal.py -v`. Suite never trades.
### v1.6.0 additions
- `reporting/status.py` + `status`/`serve` CLI (stdlib http.server, loopback default).
  Remaining observability (remote/auth dashboard) deferred as unnecessary.
### v1.5.0 additions
- `OR_DURATION_MINUTES` with `Settings.effective_or_end` consumed everywhere; 15-min default
  confirmed by sensitivity sweep (longer ORs degrade monotonically on this sample).
### v1.4.0 additions
- R-based trailing stop (`risk/trailing.py`) in backtest + live `manage_open`, TRAIL_STOP
  exit reason, `TRAIL_*` settings. Best in-sample trail config (1.5/0.5) kept OFF by default
  pending out-of-sample proof — do not enable by default without new data.
### v1.3.0 additions
- Wilder ATR (`risk/indicators.py`) + ATR stop mode wired through backtest, live engine,
  TradeManager refusal discipline, `ATR_PERIOD` setting, `TradeSignal.atr`.
- Fresh data `data/US30_M5_UTC.csv` (M1-spaced despite name; converted to M5): 36 tradeable
  sessions. ATR ~= opposite stops, no-BE beats BE variants in-window; defaults unchanged. `ruff check` — clean. `mypy` — clean (40 files). `ruff check` — clean. Coverage ~73% overall; strategy/risk/
execution/state covered by targeted unit + integration tests.

Known Issues / Limitations:
- MT5 integration tests require a real terminal (Windows); unit tests mock MT5.
- CLI backtest maps every configured symbol to the single CSV if only one matches (demo fallback).
- Backtest point-size map is heuristic per index symbol; live path uses real SymbolInfo.

Important architectural decisions:
- No MQL5 EA: Python-only execution via MetaTrader5 package (`broker/mt5_broker.py` only).
- Strategy ↔ broker separated by `Broker` ABC; same strategy serves backtest/paper/live.
- Conservative defaults: ambiguous bars → NO_SIGNAL; SL+TP same bar → stop-first;
  sub-minimum volume → skip (never over-risk).

Current configuration: see `.env.example` (defaults: OR 09:30–09:45, entries 09:45–11:30,
risk 0.5%, RR 2.0, breakeven @1R, DRY_RUN=true, America/New_York).

Important files:
- `src/orb_engine/strategy/` — signal logic (purest, test first).
- `src/orb_engine/risk/` — sizing/SL/TP/breakeven/daily.
- `src/orb_engine/backtest/engine.py` — execution assumptions documented in docstring.
- `src/orb_engine/broker/mt5_broker.py` — the ONLY file importing MetaTrader5.
- `src/orb_engine/execution/trade_manager.py` — idempotency + dry-run.
- `HANDOFF.md`, `ROADMAP.md`, `CHANGELOG.md`, `README.md`, `docs/README_FA.md`.

What remains / Next recommended:
- Retest-confirmation stays research-only until proven; live tick loop wiring to MT5 rates;
  Windows demo-terminal integration tests; dashboard.

Potential risks:
- Overfitting new parameters — always use walk-forward + report train/valid/test separately.
- Broker symbol specs (US30 vs USTEC etc.) differ per broker — validate symbols before live.

Things future developers must NOT break:
- Strategy must remain broker-independent (no MT5 imports outside `mt5_broker.py`).
- No MQL5 EA; Python-only execution.
- Risk sizing must use tick value, never 1pt=$1.
- Naive datetimes rejected; market-tz/UTC discipline.
- Conservative intrabar + no-look-ahead (closed bars, next-bar fills) in backtests.
