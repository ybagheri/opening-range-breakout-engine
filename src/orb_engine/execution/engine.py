"""Live/paper ORB engine loop: per-symbol independent state, recovery on startup."""
from __future__ import annotations

import logging
import time
from datetime import datetime

from orb_engine.broker.base import Broker
from orb_engine.config.settings import Settings, validate_settings
from orb_engine.core.sessions import SessionConfig, SessionManager
from orb_engine.core.types import Bar, Direction, SignalType, TradeSignal
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
            timezone=settings.timezone, or_start=settings.or_start, or_end=settings.effective_or_end,
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
        """Called per tick; runs force-close + tick-level BE/trailing management.

        Exit-price discipline is direction-aware (LONG exits at bid, SHORT at
        cover/ask), unlike the poll path which only sees bid. Force-close keeps
        precedence over management. Returns action dicts; never raises on
        broker hiccups (logs and returns ``none``).
        """
        if self.sessions.force_close_due(timestamp) and not self.s.allow_overnight:
            closed = []
            for p in self.broker.open_positions(magic=self.s.magic, symbol=symbol):
                if self.s.dry_run:
                    closed.append({"ticket": p.ticket, "action": "dry_run_close"})
                elif self.broker.close_position(p.ticket):
                    closed.append({"ticket": p.ticket, "action": "closed"})
            return {"action": "force_close", "closed": closed}
        try:
            positions = self.broker.open_positions(magic=self.s.magic, symbol=symbol)
        except Exception:
            log.exception("on_tick position lookup failed")
            return {"action": "none"}
        if not positions:
            return {"action": "none"}
        prices = {p.ticket: (bid if p.direction == Direction.LONG else ask)
                  for p in positions}
        managed = self.tm.manage_open(prices)
        if managed:
            return {"action": "managed", "managed": managed}
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
        ore = combine_market_time(sess, self.s.effective_or_end, self.s.timezone)
        if bar.timestamp >= ors:
            orng, v = self.strategy.builder.build(day_bars, bar.symbol, sess, ors, ore)
            if v.ok and orng is not None:
                self.strategy.set_or(bar.symbol, orng)
                self.state.upsert_or(bar.symbol, sess, orng.high, orng.low)
        sig = self.strategy.on_bar(bar)
        if sig.signal_type != SignalType.NO_SIGNAL and self.s.stop_loss_mode == "atr":
            sig = self._attach_atr(sig, bar.symbol)
        balance = self.broker.account_balance()
        return self.tm.handle_signal(sig, balance)

    def _attach_atr(self, sig: TradeSignal, symbol: str) -> TradeSignal:
        """Attach Wilder ATR known at the signal bar's close (bars <= signal only).
        Returns the signal unchanged with atr=None when history is too short —
        TradeManager then refuses the trade instead of guessing a stop."""
        from dataclasses import replace

        from orb_engine.risk.indicators import wilder_atr
        hist = self._bars.get(symbol, [])
        if len(hist) < self.s.atr_period:
            return replace(sig, atr=None)
        try:
            series = wilder_atr([b.high for b in hist], [b.low for b in hist],
                                 [b.close for b in hist], self.s.atr_period)
        except ValueError:
            return replace(sig, atr=None)
        return replace(sig, atr=series[-1])

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

    def poll_ticks(self, timestamp=None) -> list[dict]:
        """One tick-management sweep: route live quotes through ``on_tick``.

        Pulls ``current_price`` per symbol and runs force-close + direction-aware
        BE/trailing management (LONG exits at bid, SHORT at ask). Quote failures
        are logged and skipped — a missing quote must never kill the loop.
        Returns per-symbol action dicts.
        """
        from datetime import timezone

        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        results: list[dict] = []
        for symbol in self.s.symbols:
            try:
                bid, ask = self.broker.current_price(symbol)
            except Exception as e:  # noqa: BLE001 - quotes are best-effort
                log.warning("no quote for %s: %s", symbol, e)
                continue
            try:
                out = self.on_tick(symbol, bid, ask, ts)
            except Exception:
                log.exception("tick management failed for %s (continuing)", symbol)
                continue
            results.append({"symbol": symbol, **out})
        return results

    def poll_once(self, timeframe: str = "M5", lookback: int = 20) -> list[dict]:
        """One live iteration: new closed bars via ``_poll_bars`` then tick management.

        Requires a broker supporting ``get_rates`` (MT5Broker) for the bar leg;
        the tick leg (``poll_ticks``) runs regardless so force-close + direction-aware
        BE/trailing still apply when rates are unavailable. Returns per-bar results.
        """
        results = self._poll_bars(timeframe, lookback)
        # tick management on all symbols: force-close + direction-aware
        # BE/trailing via on_tick (LONG at bid, SHORT at ask).
        self.poll_ticks()
        return results

    def _poll_bars(self, timeframe: str = "M5", lookback: int = 20) -> list[dict]:
        """Pull recent bars per symbol, feed only NEW fully-closed bars to ``on_bar``.

        The last/forming bar is always skipped — never trade off incomplete data.
        Idempotent: never reprocesses a bar. Returns per-bar results.
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
        return results

    def run_live_poll(self, poll_seconds: int = 30, timeframe: str = "M5",
                      max_iters: int | None = None) -> None:
        """Blocking live loop. Use DRY_RUN=true until the full path is proven on demo.

        Two cadences: slow ``poll_seconds`` bar polls (new closed bars) plus a fast
        ``tick_poll_seconds`` tick sweep (force-close + BE/trailing) every iteration.
        The fast leg never raises — quote/management failures log and continue —
        so a stale quote feed cannot kill bar processing.
        """
        self.startup_recovery()
        tick_every = self.s.tick_poll_seconds
        log.info("live poll start tf=%s bar_every=%ss tick_every=%ss dry_run=%s",
                 timeframe, poll_seconds, tick_every, self.s.dry_run)
        next_bar = time.monotonic()  # bar poll due immediately on start
        it = 0
        while True:
            now = time.monotonic()
            if now >= next_bar:
                try:
                    self._poll_bars(timeframe)
                    print(self.status(), flush=True)
                except Exception:
                    log.exception("bar poll failed (continuing)")
                next_bar = now + poll_seconds
            try:
                self.poll_ticks()  # fast leg: never raises by contract
            except Exception:
                log.exception("tick sweep failed (continuing)")
            it += 1
            if max_iters is not None and it >= max_iters:
                break
            time.sleep(min(tick_every, max(0.0, next_bar - time.monotonic())) or tick_every)

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
