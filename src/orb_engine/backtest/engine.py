"""Event-driven backtester sharing ORBStrategy with live trading.

Execution model (documented assumptions):
- Signals evaluated on closed bars only (no look-ahead).
- Fills on the NEXT bar's open adjusted by spread/slippage (configurable).
- SL/TP checked intrabar on high/low of each subsequent bar.
- If a single bar touches both SL and TP -> intrabar policy decides
  (default conservative: the stop is assumed hit first -> loss).
- Commission charged per round-trip; spread/slippage in points via symbol point size.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from orb_engine.config.settings import Settings
from orb_engine.core.types import Direction, ExitReason, SignalType
from orb_engine.data.validation import validate_ohlc
from orb_engine.risk.stop_loss import StopLossCalculator
from orb_engine.risk.take_profit import TakeProfitCalculator
from orb_engine.strategy.strategy import ORBStrategy
from orb_engine.utils.time_utils import combine_market_time


@dataclass
class BacktestResult:
    trades: list[dict]
    equity: pd.Series
    config_hash: str


#: Built-in point-size guesses for common index CFDs. Override per deployment
#: with POINT_OVERRIDES="SYM:point,..." — live trading always uses MT5 SymbolInfo.
DEFAULT_POINTS = {"US30": 1.0, "US500": 0.1, "US100": 0.1, "NAS100": 0.1,
                  "SPX500": 0.1, "USTEC": 0.1, "USNAS100": 0.1}


def resolve_point(symbol: str, overrides: dict[str, float],
                  fallback: float = 0.01) -> float:
    if symbol.upper() in overrides:
        return overrides[symbol.upper()]
    return DEFAULT_POINTS.get(symbol.upper(), fallback)


class BacktestEngine:
    def __init__(self, settings: Settings):
        self.s = settings
        self.strategy = ORBStrategy(settings)
        self.sl_calc = StopLossCalculator(settings.stop_loss_mode, settings.stop_loss_value)
        self.tp_calc = TakeProfitCalculator(settings.take_profit_mode, settings.take_profit_value,
                                            settings.risk_reward)

    def run(self, data: dict[str, pd.DataFrame]) -> BacktestResult:
        all_trades: list[dict] = []
        for symbol, df in data.items():
            issues = validate_ohlc(df)
            if issues:
                raise ValueError(f"data quality failed for {symbol}: {issues}")
            all_trades.extend(self._run_symbol(symbol, df.sort_index()))
        eq = self._equity_curve(all_trades)
        return BacktestResult(all_trades, eq, self.s.config_hash())

    def _run_symbol(self, symbol: str, df: pd.DataFrame) -> list[dict]:
        from orb_engine.core.types import Bar
        from orb_engine.data.models import bars_from_df
        from orb_engine.risk.indicators import wilder_atr
        bars = bars_from_df(df, symbol, self.s.timezone)
        # Rolling ATR over full history (each value uses data <= its bar only).
        atr_by_time: dict = {}
        if self.s.stop_loss_mode == "atr":
            try:
                series = wilder_atr([b.high for b in bars], [b.low for b in bars],
                                    [b.close for b in bars], self.s.atr_period)
                atr_by_time = {b.timestamp: a for b, a in zip(bars, series) if a}
            except ValueError:
                atr_by_time = {}  # history shorter than period: signals safely skipped
        # group by session date (market tz)
        by_day: dict[str, list[Bar]] = {}
        for b in bars:
            d = self.strategy.sessions.session_date(b.timestamp)
            by_day.setdefault(d, []).append(b)
        trades: list[dict] = []
        pt = resolve_point(symbol, self.s.point_overrides)
        for day in sorted(by_day):
            day_bars = sorted(by_day[day], key=lambda b: b.timestamp)
            self.strategy._or.pop(symbol, None)
            ors = combine_market_time(day, self.s.or_start, self.s.timezone)
            ore = combine_market_time(day, self.s.effective_or_end, self.s.timezone)
            orng, valid = self.strategy.builder.build(day_bars, symbol, day, ors, ore)
            if not valid.ok or orng is None:
                continue
            self.strategy._or[symbol] = orng
            # scan post-OR bars
            post = [b for b in day_bars if b.timestamp >= ore]
            # entry window end
            t_end = combine_market_time(day, self.s.trading_end, self.s.timezone)
            fclose = combine_market_time(day, self.s.force_close_time, self.s.timezone) \
                if self.s.force_close_time else None
            n_trades = 0
            i = 0
            while i < len(post):
                b = post[i]
                if b.timestamp > t_end or n_trades >= self.s.max_trades_per_symbol_per_day:
                    break
                t0 = combine_market_time(day, self.s.trading_start, self.s.timezone)
                if b.timestamp < t0:
                    i += 1
                    continue
                sig = self.strategy.detector.detect(b, orng, day)
                if sig.signal_type == SignalType.NO_SIGNAL:
                    i += 1
                    continue
                direction = Direction.LONG if sig.signal_type == SignalType.LONG else Direction.SHORT
                entry_bar_idx = i + 1  # next-bar execution
                if entry_bar_idx >= len(post):
                    break
                eb = post[entry_bar_idx]
                slip = self.s.backtest_slippage_points * pt
                spread = self.s.backtest_spread_points * pt
                entry = eb.open + (spread / 2 + slip) * (1 if direction == Direction.LONG else -1)
                atr = atr_by_time.get(b.timestamp)
                try:
                    stop = self.sl_calc.compute(direction, entry, orng.high, orng.low, pt,
                                                atr=atr)
                except ValueError:
                    i += 1  # e.g. ATR mode without enough warm-up history: skip, never guess
                    continue
                tp = self.tp_calc.compute(direction, entry, stop, orng.high, orng.low, pt)
                risk = abs(entry - stop)
                if risk <= 0:
                    i += 1
                    continue
                # simulate forward
                exit_px, exit_t, reason, be_used, trail_used = self._simulate(
                    post[entry_bar_idx:], direction, entry, stop, tp, fclose)
                r_mult = ((exit_px - entry) if direction == Direction.LONG else (entry - exit_px)) / risk
                # fixed-fractional pnl in R * risk_amount where risk_amount = 1 unit of R on fixed $ risk
                # For comparability use R-based pnl scaled by hypothetical $100 risk/trade? We store R
                # and price pnl per unit; PerformanceAnalyzer derives money pnl with sizing if needed.
                trades.append({
                    "trade_id": f"{symbol}-{day}-{n_trades}",
                    "symbol": symbol, "direction": direction.value, "session_date": day,
                    "or_high": orng.high, "or_low": orng.low,
                    "signal_time": b.timestamp, "entry_time": eb.timestamp,
                    "entry": entry, "stop": stop, "target": tp, "atr": atr,
                    "exit_time": exit_t, "exit_price": exit_px,
                    "exit_reason": reason.value, "r_multiple": r_mult,
                    "breakeven_used": be_used, "trail_used": trail_used,
                    "commission": self.s.backtest_commission,
                })
                n_trades += 1
                i = entry_bar_idx + 1
        return trades

    def _simulate(self, bars, direction, entry, stop, tp, fclose):
        from orb_engine.risk.trailing import TrailingStop
        risk = abs(entry - stop)
        trail = TrailingStop(self.s.trail_enabled, self.s.trail_trigger_r,
                             self.s.trail_offset_r)
        be_trigger = self.s.breakeven_trigger_r * risk if self.s.breakeven_enabled else None
        be_used = False
        trail_used = False
        cur_stop = stop
        extreme = entry
        for b in bars:
            if fclose is not None and b.timestamp >= fclose:
                px = b.open
                return px, b.timestamp, ExitReason.FORCE_CLOSE, be_used, trail_used
            # favorable extreme first, then protective candidates (documented order:
            # the stop may move up on the same bar whose low later stops us out —
            # conservative, since the exit is at the improved level)
            if direction == Direction.LONG:
                extreme = max(extreme, b.high)
                fav = extreme - entry
            else:
                extreme = min(extreme, b.low)
                fav = entry - extreme
            be_level = entry if (be_trigger is not None and not be_used
                                 and fav >= be_trigger) else None
            trail_level = trail.candidate(direction, entry, extreme, risk)
            new_stop = TrailingStop.ratchet(direction, cur_stop, [be_level, trail_level])
            if new_stop != cur_stop:
                if be_level is not None and new_stop == be_level:
                    be_used = True
                if trail_level is not None and new_stop == trail_level \
                        and trail_level != be_level:
                    trail_used = True
                cur_stop = new_stop
            sl_hit = (b.low <= cur_stop) if direction == Direction.LONG else (b.high >= cur_stop)
            tp_hit = (b.high >= tp) if direction == Direction.LONG else (b.low <= tp)
            if sl_hit and tp_hit:
                pol = self.s.intrabar_policy
                if pol in ("conservative", "stop_first"):
                    return cur_stop, b.timestamp, self._stop_reason(
                        cur_stop, entry, stop, be_used, trail_used), be_used, trail_used
                return tp, b.timestamp, ExitReason.TAKE_PROFIT, be_used, trail_used
            if sl_hit:
                return cur_stop, b.timestamp, self._stop_reason(
                    cur_stop, entry, stop, be_used, trail_used), be_used, trail_used
            if tp_hit:
                return tp, b.timestamp, ExitReason.TAKE_PROFIT, be_used, trail_used
        last = bars[-1]
        return last.close, last.timestamp, ExitReason.END_OF_DATA, be_used, trail_used

    @staticmethod
    def _stop_reason(cur_stop: float, entry: float, original_stop: float,
                     be_used: bool, trail_used: bool) -> ExitReason:
        if cur_stop == entry and (be_used or trail_used):
            return ExitReason.BREAKEVEN_STOP
        if trail_used and cur_stop != original_stop:
            return ExitReason.TRAIL_STOP
        return ExitReason.STOP_LOSS

    def _equity_curve(self, trades: list[dict]) -> pd.Series:
        import pandas as pd
        if not trades:
            return pd.Series(dtype=float)
        rs = [t["r_multiple"] for t in trades]
        # equity in R with $100 risk per trade
        eq = pd.Series(rs, dtype=float).cumsum() * 100.0 + 10000.0
        return eq
