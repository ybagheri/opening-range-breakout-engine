"""Live/paper ORB engine loop: per-symbol independent state, recovery on startup."""
from __future__ import annotations

import logging
import time

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
                self.strategy._or[bar.symbol] = orng
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
