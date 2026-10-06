# Roadmap

- [x] Phase 1 — Architecture and project foundation (package layout, typing, lint/test tooling)
- [x] Phase 2 — Configuration and environment management (.env, validation, config hash)
- [x] Phase 3 — Market data and session engine (providers, validation, sessions, TZ handling)
- [x] Phase 4 — ORB strategy and signal engine (OpeningRange, BreakoutDetector, ORBStrategy)
- [x] Phase 5 — Risk management and position sizing (sizing, SL/TP, breakeven, daily guards)
- [x] Phase 6 — Backtesting engine (event-driven, realistic fills, intrabar policy, metrics)
- [x] Phase 7 — MT5 Python execution layer (MT5Broker, no EA dependency)
- [x] Phase 8 — Paper trading (PaperBroker, DRY_RUN, TradeManager idempotency)
- [x] Phase 9 — Persistence and recovery (SQLite state + journal, startup reconciliation)
- [x] Phase 10 — Analytics and reporting (PerformanceAnalyzer, charts, report generator, CLI)
- [x] Phase 11 — Walk-forward and robustness testing (WF harness, optimizer, robustness, Monte Carlo)
- [x] Phase 12 — Production hardening (MT5 safety checks, spread filter, observability status)
- [x] Phase 13 — Documentation and final audit (bilingual README, HANDOFF, full test/lint pass)

## Future (not in v1.0.0)

- [x] Volume filter tried on real US30 CFD data, then REMOVED in v1.2.0 (see CHANGELOG) —
  tick-volume confirmation does not transfer from equities to CFD brokers; engine is price-only
- [ ] Retest confirmation filter (deferred entry on level retest)
- [x] ATR stop end-to-end (Wilder ATR, backtest + live, refusal on missing ATR) — v1.3.0
- [x] Trailing-stop variants (R-based, ratchet, BE composition, TRAIL_STOP reason) — v1.4.0
- [x] Multi-timeframe OR via OR_DURATION_MINUTES (5/15/30/60 presets or any N; explicit end kept when 0) — v1.5.0
- [x] Local observability: stdlib-only status server (JSON + auto-refresh HTML, loopback, `status`/`serve` CLI) — v1.6.0
- [ ] Full live dashboard (charts, remote access with auth) — only if needed
- [x] MT5 integration suite (terminal-gated, read-only + dry-run only, never sends orders) + Linux/Windows CI — v1.7.0
