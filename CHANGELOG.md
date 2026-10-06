# Changelog

## [1.5.0] — 2026-10-06

### Added — configurable OR duration (next roadmap phase)
- `OR_DURATION_MINUTES`: N>0 sets OR end = start + N (5/15/30/60 presets or any value),
  overriding `OR_END_TIME`; 0 keeps explicit times. Single `effective_or_end` consumed by
  sessions, strategy, backtest and live engine; validation covers negativity, midnight
  overflow and end<=start.
- 6 new tests (67 total): preset math, precedence, validation, backtest + gating use.

### Observed — OR-duration sensitivity (US30 M5, 36 sessions, OPP-noBE / TR1.5-0.5)
- OR15: +21R / +35R | OR30: +10.7R / +21.7R | OR45: +13.3R / +7.2R | OR60: +1.5R / +1.9R.
  Degradation with OR length is monotonic here; 60-min drop-best-5 deeply negative.
- The finding CONFIRMS the existing 15-min default instead of changing it — no tuning needed.

## [1.4.0] — 2026-10-06

### Added — trailing-stop variants (next roadmap phase)
- `risk/trailing.py`: R-based `TrailingStop` (trigger/offset in multiples of initial risk,
  protective-only ratchet, composes with breakeven by most-protective-wins).
- Settings `TRAIL_ENABLED` / `TRAIL_TRIGGER_R=1.5` / `TRAIL_OFFSET_R=0.5` (+ validation, `.env`).
- Backtest `_simulate` trails the stop bar-by-bar (documented intrabar order) and reports
  `TRAIL_STOP` exits + `trail_used`; live `manage_open` trails per-tick quotes with the same
  ratchet, keyed on initial risk recorded at fill (restart falls back to current SL, logged).
- 6 new tests (61 total): trigger math, ratchet direction, validation, TRAIL_STOP path,
  live trail-up/never-retreat, BE+trail composition.

### Observed (US30 M5, 36 sessions — selection is IN-SAMPLE, read with care)
- TR1.5-0.5: +35R, win 64%, PF 3.69, dropBest5 +9.6; TR1.0-0.5: +29.4R; OPP-noBE: +21R.
  Monthly splits positive for all variants in Aug/Sep/Oct (tiny samples).
- Caution: 3 configs tried, best reported — real validation needs fresh out-of-sample data.
  Defaults stay conservative (trail OFF) until then.

## [1.3.0] — 2026-10-06

### Added — ATR stops end-to-end (next roadmap phase, validated on fresh data)
- `risk/indicators.py`: pure Wilder ATR (`true_ranges`, `wilder_atr`; warm-up marked None,
  no look-ahead by construction) with hand-computed unit tests.
- `ATR_PERIOD` setting (default 14, validated); `STOP_LOSS_VALUE` is the multiple in atr mode.
- Backtest computes rolling ATR per symbol and uses the value known at the signal bar's
  close; trade records now carry `atr`. Short warm-up history skips safely, never guesses.
- Live engine attaches ATR from bars <= signal bar (`_attach_atr`); `TradeManager`
  refuses ATR-mode signals without a valid ATR instead of guessing a stop.
- `TradeSignal.atr` field (optional, backward compatible).

### Observed (fresh US30 M5 window, 36 sessions, same assumptions as v1.1.1 note)
- OPP-noBE +21R (dropBest5 +11) ~= ATR1.5-noBE +21R (dropBest5 +11, smaller maxDD, balanced L/S).
  ATR1.5 with BE only +4R (dropBest5 negative); ATR2.0 +9R. Monthly splits all positive
  but tiny. Verdict: ATR works correctly but shows NO advantage over opposite-side stops
  here, so defaults stay unchanged — no tuning to 36 sessions.

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
