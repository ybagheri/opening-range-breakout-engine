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
        bars = bars_from_df(df, symbol, self.s.timezone)
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
            ore = combine_market_time(day, self.s.or_end, self.s.timezone)
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
                stop = self.sl_calc.compute(direction, entry, orng.high, orng.low, pt)
                tp = self.tp_calc.compute(direction, entry, stop, orng.high, orng.low, pt)
                risk = abs(entry - stop)
                if risk <= 0:
                    i += 1
                    continue
                # simulate forward
                exit_px, exit_t, reason, be_used = self._simulate(
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
                    "entry": entry, "stop": stop, "target": tp,
                    "exit_time": exit_t, "exit_price": exit_px,
                    "exit_reason": reason.value, "r_multiple": r_mult,
                    "breakeven_used": be_used,
                    "commission": self.s.backtest_commission,
                })
                n_trades += 1
                i = entry_bar_idx + 1
        return trades

    def _simulate(self, bars, direction, entry, stop, tp, fclose):
        be_trigger = self.s.breakeven_trigger_r * abs(entry - stop) if self.s.breakeven_enabled else None
        be_used = False
        cur_stop = stop
        for b in bars:
            if fclose is not None and b.timestamp >= fclose:
                px = b.open
                return px, b.timestamp, ExitReason.FORCE_CLOSE, be_used
            # breakeven update on close basis
            if be_trigger is not None and not be_used:
                fav = (b.high - entry) if direction == Direction.LONG else (entry - b.low)
                if fav >= be_trigger:
                    cur_stop = entry
                    be_used = True
            sl_hit = (b.low <= cur_stop) if direction == Direction.LONG else (b.high >= cur_stop)
            tp_hit = (b.high >= tp) if direction == Direction.LONG else (b.low <= tp)
            if sl_hit and tp_hit:
                pol = self.s.intrabar_policy
                if pol in ("conservative", "stop_first"):
                    return cur_stop, b.timestamp, (ExitReason.BREAKEVEN_STOP if be_used and cur_stop == entry else ExitReason.STOP_LOSS), be_used
                else:
                    return tp, b.timestamp, ExitReason.TAKE_PROFIT, be_used
            if sl_hit:
                return cur_stop, b.timestamp, (ExitReason.BREAKEVEN_STOP if be_used and cur_stop == entry else ExitReason.STOP_LOSS), be_used
            if tp_hit:
                return tp, b.timestamp, ExitReason.TAKE_PROFIT, be_used
        last = bars[-1]
        return last.close, last.timestamp, ExitReason.END_OF_DATA, be_used

    def _equity_curve(self, trades: list[dict]) -> pd.Series:
        import pandas as pd
        if not trades:
            return pd.Series(dtype=float)
        rs = [t["r_multiple"] for t in trades]
        # equity in R with $100 risk per trade
        eq = pd.Series(rs, dtype=float).cumsum() * 100.0 + 10000.0
        return eq
