# Changelog

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
