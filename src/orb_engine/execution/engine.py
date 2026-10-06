"""Live/paper ORB engine loop: per-symbol independent state, recovery on startup."""
from __future__ import annotations

import logging
import time
from datetime import datetime

from orb_engine.broker.base import Broker
from orb_engine.config.settings import Settings, validate_settings
from orb_engine.core.sessions import SessionConfig, SessionManager
from orb_engine.core.types import Bar
from orb_engine.execution.trade_manager import TradeManager
from orb_engine.persistence.journal import TradeJournal
from orb_engine.persistence.state import StateStore
from orb_engine.strategy.strategy import ORBStrategy

log = logging.getLogger("orb_engine.engine")


class ORBEngine:
    def __init__(self, settings: Settings, broker: Broker):
        errs = validate_settings(settings)
        if errs:
            raise ValueError("invalid config: " + "; ".join(errs))
        self.s = settings
        self.broker = broker
        self.strategy = ORBStrategy(settings)
        self.state = StateStore(settings.state_db)
        self.journal = TradeJournal(settings.journal_db)
        self.tm = TradeManager(settings, broker, self.state)
        self.sessions = SessionManager(SessionConfig(
            timezone=settings.timezone, or_start=settings.or_start, or_end=settings.or_end,
            trading_start=settings.trading_start, trading_end=settings.trading_end,
            force_close_time=settings.force_close_time, allow_overnight=settings.allow_overnight))
        self._bars: dict[str, list[Bar]] = {sym: [] for sym in settings.symbols}
        self._last_bar_time: dict[str, datetime] = {}

    def startup_recovery(self) -> list:
        """Reconcile existing strategy positions after restart."""
        if not self.broker.connect():
            log.warning("broker connect failed at startup; running disconnected")
        existing = self.broker.open_positions(magic=self.s.magic)
        log.info("startup recovery: %d existing strategy positions", len(existing))
        for p in existing:
            log.info("  ticket=%s %s %s vol=%s entry=%s sl=%s tp=%s", p.ticket, p.symbol,
                     p.direction.value, p.volume, p.entry_price, p.stop_loss, p.take_profit)
        return existing

    def on_tick(self, symbol: str, bid: float, ask: float, timestamp) -> dict:
        """Called per tick; builds a pseudo-bar stream is caller responsibility.
        Minimal safe handler: enforce force-close."""
        if self.sessions.force_close_due(timestamp) and not self.s.allow_overnight:
            closed = []
            for p in self.broker.open_positions(magic=self.s.magic, symbol=symbol):
                if self.s.dry_run:
                    closed.append({"ticket": p.ticket, "action": "dry_run_close"})
                elif self.broker.close_position(p.ticket):
                    closed.append({"ticket": p.ticket, "action": "closed"})
            return {"action": "force_close", "closed": closed}
        return {"action": "none"}

    def on_bar(self, bar: Bar) -> dict:
        """Process a closed bar: update OR + maybe emit order. Idempotent per bar."""
        self._bars.setdefault(bar.symbol, []).append(bar)
        sess = self.sessions.session_date(bar.timestamp)
        # maintain OR incrementally: rebuild from today's bars (cheap, deterministic)
        day_bars = [b for b in self._bars[bar.symbol]
                    if self.sessions.session_date(b.timestamp) == sess]
        from orb_engine.utils.time_utils import combine_market_time
        ors = combine_market_time(sess, self.s.or_start, self.s.timezone)
        ore = combine_market_time(sess, self.s.or_end, self.s.timezone)
        if bar.timestamp >= ors:
            orng, v = self.strategy.builder.build(day_bars, bar.symbol, sess, ors, ore)
            if v.ok and orng is not None:
                vols = [b.volume for b in day_bars if ors <= b.timestamp < ore]
                mean_vol = (sum(vols) / len(vols)) if vols else None
                self.strategy.set_or(bar.symbol, orng, mean_vol)
                self.state.upsert_or(bar.symbol, sess, orng.high, orng.low)
        sig = self.strategy.on_bar(bar)
        balance = self.broker.account_balance()
        return self.tm.handle_signal(sig, balance)

    def status(self) -> str:
        lines = ["ORB ENGINE", "--------------------------------",
                 f"BROKER: {self.broker.name} DRY_RUN={self.s.dry_run}"]
        for sym in self.s.symbols:
            orng = self.strategy.get_or(sym)
            if orng:
                lines.append(f"{sym} OR: {orng.high:.2f}/{orng.low:.2f} width={orng.width:.2f}")
            else:
                lines.append(f"{sym} OR: -- WAITING")
        return "\n".join(lines)

    def poll_once(self, timeframe: str = "M5", lookback: int = 20) -> list[dict]:
        """One live iteration: pull recent bars per symbol, feed only NEW fully-closed
        bars to ``on_bar`` (the last/forming bar is always skipped — never trade off
        incomplete data), then run breakeven management on open positions.

        Requires a broker supporting ``get_rates`` (MT5Broker). Returns per-bar results.
        """
        from orb_engine.data.models import bars_from_df

        results: list[dict] = []
        for symbol in self.s.symbols:
            if not self.broker.ensure_symbol(symbol):
                log.warning("symbol unavailable, skipping: %s", symbol)
                continue
            try:
                df = self.broker.get_rates(symbol, timeframe, lookback)
            except (NotImplementedError, RuntimeError) as e:
                log.warning("no rates for %s: %s", symbol, e)
                continue
            if df.empty or len(df) < 2:
                continue
            closed = bars_from_df(df.iloc[:-1], symbol, self.s.timezone)  # drop forming bar
            last = self._last_bar_time.get(symbol)
            for bar in closed:
                if last is not None and bar.timestamp <= last:
                    continue  # idempotent: never reprocess a bar
                results.append(self.on_bar(bar))
                self._last_bar_time[symbol] = bar.timestamp
        # breakeven management on all open strategy positions
        prices: dict[int, float] = {}
        for pos in self.broker.open_positions(magic=self.s.magic):
            try:
                bid, _ = self.broker.current_price(pos.symbol)
                prices[pos.ticket] = bid
            except RuntimeError as e:
                log.warning("no quote for breakeven check: %s", e)
        self.tm.manage_open(prices)
        return results

    def run_live_poll(self, poll_seconds: int = 30, timeframe: str = "M5",
                      max_iters: int | None = None) -> None:
        """Blocking live loop. Use DRY_RUN=true until the full path is proven on demo."""
        self.startup_recovery()
        log.info("live poll start tf=%s every=%ss dry_run=%s", timeframe, poll_seconds,
                 self.s.dry_run)
        it = 0
        while True:
            try:
                self.poll_once(timeframe)
                print(self.status(), flush=True)
            except Exception:
                log.exception("poll iteration failed (continuing)")
            it += 1
            if max_iters is not None and it >= max_iters:
                break
            time.sleep(poll_seconds)

    def run_loop(self, poll_seconds: int = 5, max_iters: int | None = None) -> None:
        self.startup_recovery()
        log.info("engine loop start (paper=%s dry_run=%s)", self.s.paper_mode, self.s.dry_run)
        it = 0
        while True:
            try:
                print(self.status(), flush=True)
            except Exception:
                log.exception("status error")
            it += 1
            if max_iters is not None and it >= max_iters:
                break
            time.sleep(poll_seconds)
