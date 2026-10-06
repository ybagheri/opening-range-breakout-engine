# Changelog

## [1.2.0] — 2026-10-06

### Removed — equities volume filter does not survive CFD reality
- Deleted the relative-volume confirmation filter entirely: `strategy/filters.py`,
  `BreakoutDetector` volume gate, OR mean-volume plumbing (strategy/backtest/live),
  `VOLUME_FILTER_ENABLED` / `VOLUME_MIN_RVOL` settings + validation, `.env` keys,
  and all filter tests/docs. The engine is price-only again.
- Evidence: on real US30 CFD M1 data (36 sessions) RVOL>=1.2 turned +12R into +0.4R and
  drop-best-5 negative, while only 17% of breakout bars even reached the threshold —
  CFD tick volume is not equity volume. Per project principle (robustness over
  sophistication), a filter that fails out-of-sample gets deleted, not tuned.
- Retest-confirmation idea stays on the roadmap as research, not code.

## [1.1.1] — 2026-10-06

### Fixed
- Backtest engine now passes OR mean volume into the breakout detector. Previously the
  volume filter received `None` in backtests and conservatively rejected every signal,
  found while validating against real US30 M1 data (thank you, real data).
- Added `scripts/convert_mt5_csv.py` (MT5 export → engine bars; works around a pandas
  index-alignment gotcha that silently yields all-NaN columns) plus a regression test
  pinning permissive-filter == filter-disabled trade counts.

### Observed (US30 CFD, 36 sessions Aug–Oct 2026, M5, NOT a claim of edge)
- Baseline (BE@1R): 36 trades, +12R, win 33%, PF 2.0 — but drop-best-5 leaves +2R.
- No-breakeven variant: +21R, win 53% on the same sample; breakeven scratched eventual winners.
- RVOL>=1.2 filter: +0.4R — the equities volume-finding does NOT transfer to this CFD sample.
- Sample far too small for conclusions; reported for method, not for marketing.

## [1.1.0] — 2026-10-06

### Added
- Relative-volume confirmation filter (`VOLUME_FILTER_ENABLED`, `VOLUME_MIN_RVOL`, default 1.2):
  `VolumeFilter` + detector wiring in live, paper and backtest paths; missing baseline volume
  conservatively rejects the signal. Disabled by default.
- Live polling loop (`ORBEngine.poll_once` / `run_live_poll`): pulls closed M5 bars per symbol
  via `Broker.get_rates`, skips the forming bar, never reprocesses a bar, runs breakeven
  management each iteration. `live` CLI now uses it when `DRY_RUN=false`.
- Per-symbol point overrides (`POINT_OVERRIDES="US30:1.0,..."`) replacing the undocumented
  single fallback; validated at startup.
- `PaperBroker` fills at quoted bid/ask with explicit slippage records (`fills`), plus
  `set_quote` for tests/simulation.

### Fixed
- Backtest CLI no longer feeds one CSV to every symbol: symbols without a matching file are
  skipped with a warning (single-file demo: name the file after the symbol).
- `ORBStrategy.update_or` now records mean OR-formation volume for the filter.

### Tests
- 15 new tests (52 total): filter unit tests, strategy gating, point overrides, paper fills,
  idempotent poll loop, and dedicated look-ahead guards (OR ignores future bars, signal
  determinism, next-bar-open entry accounting).

## [1.0.0] — 2026-10-06

### Added
- Full ORB engine: sessions, OR builder, breakout detector, strategy (broker-independent).
- Risk: fixed-fractional sizing with tick value, SL/TP calculators, breakeven, daily guards.
- Backtest: event-driven engine, realistic fills, conservative intrabar policy, metrics,
  equity/R charts, walk-forward harness, grid optimizer with overfit warnings,
  robustness suite, Monte Carlo analysis.
- Execution: Broker ABC, Mock/Paper/MT5 brokers (Python API only, no EA), idempotent
  TradeManager, live engine with startup recovery and force-close.
- Persistence: SQLite state store + trade journal.
- CLI: `live | paper | backtest | validate | optimize | report`.
- Tests: 37 unit + integration tests (OR, breakouts, risk, SL/TP, breakeven, windows,
  multi-symbol, idempotency, recovery, config, backtest incl. look-ahead guard).
- Docs: bilingual README (EN + FA), ROADMAP, HANDOFF, .env.example, sample data, reports.

### Design decisions
- Strategy never imports MetaTrader5; MT5 isolated behind Broker interface.
- Conservative intrabar default (stop-first); configurable.
- Ambiguous bar touching both OR sides emits NO_SIGNAL.
- Volume below broker minimum refuses the trade (never silently over-risks).

### Known limitations
- MT5 live path needs Windows + terminal + `MetaTrader5` package; CI runs paper/backtest only.
- Backtest uses per-symbol point-size guesses for indices; wire live `SymbolInfo` for exactness.
