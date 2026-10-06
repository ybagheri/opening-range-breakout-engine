"""Daily loss / trade-count guards (per-symbol and portfolio)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DailyState:
    date: str
    trades: int = 0
    per_symbol: dict[str, int] = field(default_factory=dict)
    realized_pnl: float = 0.0
    blocked: bool = False


class DailyRiskGuard:
    def __init__(self, max_trades_symbol: int = 1, max_trades_total: int = 3,
                 max_daily_loss_pct: float = 2.0):
        self.max_trades_symbol = max_trades_symbol
        self.max_trades_total = max_trades_total
        self.max_daily_loss_pct = max_daily_loss_pct
        self._days: dict[str, DailyState] = {}

    def day(self, date: str) -> DailyState:
        return self._days.setdefault(date, DailyState(date))

    def can_open(self, date: str, symbol: str, balance: float) -> tuple[bool, str]:
        st = self.day(date)
        if st.per_symbol.get(symbol, 0) >= self.max_trades_symbol:
            return False, "max trades per symbol reached"
        if st.trades >= self.max_trades_total:
            return False, "max total trades reached"
        if (self.max_daily_loss_pct > 0 and balance > 0
                and st.realized_pnl <= -(self.max_daily_loss_pct / 100.0) * balance):
            return False, "daily loss limit reached"
        return True, ""

    def record_fill(self, date: str, symbol: str) -> None:
        st = self.day(date)
        st.trades += 1
        st.per_symbol[symbol] = st.per_symbol.get(symbol, 0) + 1

    def record_pnl(self, date: str, pnl: float) -> None:
        self.day(date).realized_pnl += pnl
