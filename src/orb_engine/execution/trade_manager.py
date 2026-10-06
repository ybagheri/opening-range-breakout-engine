"""TradeManager: idempotent signal->order pipeline (dry-run/paper/live)."""
from __future__ import annotations

import logging

from orb_engine.broker.base import Broker
from orb_engine.config.settings import Settings
from orb_engine.core.types import Direction, OrderRequest, OrderStatus, SignalType, TradeSignal
from orb_engine.persistence.state import StateStore
from orb_engine.risk.breakeven import BreakEvenManager
from orb_engine.risk.daily_limits import DailyRiskGuard
from orb_engine.risk.sizing import position_size
from orb_engine.risk.stop_loss import StopLossCalculator
from orb_engine.risk.take_profit import TakeProfitCalculator

log = logging.getLogger("orb_engine.execution")


class TradeManager:
    STRATEGY = "ORB_ENGINE"

    def __init__(self, settings: Settings, broker: Broker, state: StateStore | None = None):
        self.s = settings
        self.broker = broker
        self.state = state
        self.sl_calc = StopLossCalculator(settings.stop_loss_mode, settings.stop_loss_value)
        self.tp_calc = TakeProfitCalculator(settings.take_profit_mode, settings.take_profit_value,
                                            settings.risk_reward)
        self.be = BreakEvenManager(settings.breakeven_enabled, settings.breakeven_trigger_r,
                                   settings.breakeven_buffer_points)
        self.guard = DailyRiskGuard(settings.max_trades_per_symbol_per_day,
                                    settings.max_total_trades_per_day,
                                    settings.max_daily_loss_percent)

    def _trade_identity(self, sig: TradeSignal) -> str:
        return f"{self.STRATEGY}|{sig.symbol}|{sig.session_date}|{sig.signal_time.isoformat()}"

    def handle_signal(self, sig: TradeSignal, balance: float) -> dict:
        """Returns action dict; never sends duplicates."""
        if sig.signal_type == SignalType.NO_SIGNAL:
            return {"action": "ignore", "reason": sig.reason}
        direction = Direction.LONG if sig.signal_type == SignalType.LONG else Direction.SHORT
        # duplicate protection: existing strategy positions
        existing = self.broker.open_positions(magic=self.s.magic, symbol=sig.symbol)
        if existing:
            return {"action": "ignore", "reason": "existing strategy position for symbol"}
        if self.state and self.state.already_traded(sig.symbol, sig.session_date,
                                                    self.s.max_trades_per_symbol_per_day):
            return {"action": "ignore", "reason": "already traded today (state store)"}
        ok, reason = self.guard.can_open(sig.session_date, sig.symbol, balance)
        if not ok:
            return {"action": "ignore", "reason": reason}
        # spread filter
        if self.s.max_spread_points > 0:
            sp = self.broker.spread_points(sig.symbol)
            if sp > self.s.max_spread_points:
                return {"action": "ignore", "reason": f"spread {sp} > max {self.s.max_spread_points}"}
        info = self.broker.symbol_info(sig.symbol)
        if info is None or not info.trade_allowed:
            return {"action": "ignore", "reason": "symbol not tradeable"}
        entry = sig.price
        stop = self.sl_calc.compute(direction, entry, sig.or_high, sig.or_low, info.point)
        tp = self.tp_calc.compute(direction, entry, stop, sig.or_high, sig.or_low, info.point)
        # validate SL/TP distance vs stop level
        min_dist = info.stop_level_points * info.point
        if abs(entry - stop) < min_dist or abs(tp - entry) < min_dist:
            return {"action": "ignore", "reason": "SL/TP violates broker stop level"}
        size = position_size(balance, self.s.risk_per_trade_percent, entry, stop, info)
        if size.capped_or_floored == "below_min":
            # Never silently increase risk: log and skip
            log.warning("calculated volume below broker minimum for %s; skipping (risk would exceed)",
                        sig.symbol)
            return {"action": "ignore", "reason": "volume below minimum; refusing to over-risk",
                    "volume": size.volume}
        req = OrderRequest(sig.symbol, direction, size.volume, entry, stop, tp, self.s.magic,
                           self.STRATEGY, sig.session_date,
                           comment=f"{self.STRATEGY} {sig.session_date}")
        log.info("SIGNAL %s %s entry=%s sl=%s tp=%s risk=%.2f%% ($%.2f) vol=%s exp_loss=%.2f",
                 direction.value, sig.symbol, entry, stop, tp, self.s.risk_per_trade_percent,
                 size.risk_amount, size.volume, size.expected_max_loss)
        if self.s.dry_run:
            log.info("DRY RUN - ORDER NOT SENT")
            return {"action": "dry_run", "request": req, "size": size}
        res = self.broker.place_market_order(req)
        if res.status == OrderStatus.FILLED:
            self.guard.record_fill(sig.session_date, sig.symbol)
            if self.state:
                self.state.mark_traded(sig.symbol, sig.session_date, res.ticket, direction.value)
            return {"action": "filled", "ticket": res.ticket, "request": req, "size": size}
        log.error("order rejected: %s", res.message)
        return {"action": "rejected", "reason": res.message, "request": req}

    def manage_open(self, ticket_prices: dict[int, float]) -> list[dict]:
        """Apply breakeven moves; ticket_prices: ticket -> current price. Returns actions."""
        actions = []
        for pos in self.broker.open_positions(magic=self.s.magic):
            cur = ticket_prices.get(pos.ticket)
            if cur is None:
                continue
            info = self.broker.symbol_info(pos.symbol)
            pt = info.point if info else 0.01
            if self.be.should_trigger(pos.direction, pos.entry_price, cur, pos.stop_loss):
                new_sl = self.be.new_stop(pos.direction, pos.entry_price, pt)
                # avoid moving SL backwards
                if (pos.direction == Direction.LONG and new_sl > pos.stop_loss) or \
                   (pos.direction == Direction.SHORT and new_sl < pos.stop_loss):
                    ok = self.broker.modify_position_sltp(pos.ticket, new_sl, pos.take_profit)
                    actions.append({"ticket": pos.ticket, "breakeven": ok, "new_sl": new_sl})
                    log.info("BREAKEVEN ticket=%s new_sl=%s ok=%s", pos.ticket, new_sl, ok)
        return actions
