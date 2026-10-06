"""ORBStrategy: orchestrates OR + breakout + entry-window gating. No broker calls."""
from __future__ import annotations

from orb_engine.config.settings import Settings
from orb_engine.core.sessions import SessionConfig, SessionManager
from orb_engine.core.types import Bar, OpeningRange, SignalType, TradeSignal
from orb_engine.strategy.breakout import BreakoutDetector
from orb_engine.strategy.filters import VolumeFilter
from orb_engine.strategy.opening_range import OpeningRangeBuilder
from orb_engine.utils.time_utils import combine_market_time


class ORBStrategy:
    def __init__(self, settings: Settings):
        self.s = settings
        self.sessions = SessionManager(SessionConfig(
            timezone=settings.timezone, or_start=settings.or_start, or_end=settings.or_end,
            trading_start=settings.trading_start, trading_end=settings.trading_end,
            force_close_time=settings.force_close_time, allow_overnight=settings.allow_overnight))
        self.builder = OpeningRangeBuilder()
        vol = VolumeFilter(settings.volume_min_rvol if settings.volume_filter_enabled else 0.0)
        self.detector = BreakoutDetector(settings.breakout_buffer_points,
                                         settings.breakout_buffer_pct_of_or,
                                         settings.breakout_require_close, vol)
        self._or: dict[str, OpeningRange | None] = {}
        self._or_mean_volume: dict[str, float | None] = {}
        self._signalled: set[str] = set()  # (symbol, session_date) with signal already emitted

    def reset_day(self) -> None:
        self._or.clear()
        self._or_mean_volume.clear()
        self._signalled.clear()

    def get_or(self, symbol: str) -> OpeningRange | None:
        return self._or.get(symbol)

    def update_or(self, bars: list[Bar], symbol: str, session_date: str) -> OpeningRange | None:
        ors = combine_market_time(session_date, self.s.or_start, self.s.timezone)
        ore = combine_market_time(session_date, self.s.or_end, self.s.timezone)
        orng, valid = self.builder.build(bars, symbol, session_date, ors, ore)
        mean_vol = self.mean_volume(bars, symbol, ors, ore) if valid.ok else None
        self.set_or(symbol, orng if valid.ok else None, mean_vol)
        return self._or[symbol]

    def set_or(self, symbol: str, orng: OpeningRange | None,
               mean_volume: float | None = None) -> None:
        """Register a ready OR plus its mean formation volume (for the volume filter)."""
        self._or[symbol] = orng
        self._or_mean_volume[symbol] = mean_volume

    @staticmethod
    def mean_volume(bars: list[Bar], symbol: str, or_start, or_end) -> float | None:
        vols = [b.volume for b in bars if b.symbol == symbol and or_start <= b.timestamp < or_end]
        if not vols:
            return None
        return sum(vols) / len(vols)

    def on_bar(self, bar: Bar) -> TradeSignal:
        mkt = self.sessions.market_now(bar.timestamp)
        sess = self.sessions.session_date(bar.timestamp)
        orng = self._or.get(bar.symbol)
        if orng is None or not orng.is_valid:
            return TradeSignal(bar.symbol, sess, SignalType.NO_SIGNAL, bar.timestamp,
                               bar.close, float("nan"), float("nan"), "OR not ready/invalid")
        # OR formation bars themselves must not trigger
        ore = combine_market_time(sess, self.s.or_end, self.s.timezone)
        if not (ore <= mkt):
            return TradeSignal(bar.symbol, sess, SignalType.NO_SIGNAL, bar.timestamp,
                               bar.close, orng.high, orng.low,
                               "bar inside OR formation window")
        if not self.sessions.in_entry_window(bar.timestamp):
            return TradeSignal(bar.symbol, sess, SignalType.NO_SIGNAL, bar.timestamp,
                               bar.close, orng.high, orng.low, "outside entry window")
        # one signal per symbol-day by default is enforced by TradeManager; here we still
        # emit but mark repeated — TradeManager decides. Keep detector pure:
        sig = self.detector.detect(bar, orng, sess, self._or_mean_volume.get(bar.symbol))
        return sig
