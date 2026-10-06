"""PaperBroker: fills at the *quoted* bid/ask (never the idealized signal price),
so spread cost vs. the signal is explicit in every fill record."""
from __future__ import annotations

from orb_engine.broker.mock import MockBroker
from orb_engine.core.types import (
    Direction,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    SymbolInfo,
)


class PaperBroker(MockBroker):
    name = "paper"

    def __init__(self, balance: float = 10000.0, infos: dict[str, SymbolInfo] | None = None):
        super().__init__(balance, infos)
        self.quotes: dict[str, tuple[float, float]] = {}
        self.fills: list[dict] = []

    def set_quote(self, symbol: str, bid: float, ask: float) -> None:
        self.quotes[symbol] = (bid, ask)

    def current_price(self, symbol: str) -> tuple[float, float]:
        if symbol in self.quotes:
            return self.quotes[symbol]
        return super().current_price(symbol)

    def place_market_order(self, req: OrderRequest) -> OrderResult:
        bid, ask = self.current_price(req.symbol)
        fill = ask if req.direction == Direction.LONG else bid
        slip = (fill - req.entry_price) * (1 if req.direction == Direction.LONG else -1)
        self.orders_sent.append(req)
        self._ticket += 1
        self._positions.append(Position(self._ticket, req.symbol, req.direction, req.volume,
                                        fill, req.stop_loss, req.take_profit, req.magic,
                                        req.strategy, req.session_date))
        self.fills.append({"ticket": self._ticket, "requested": req.entry_price,
                           "filled": fill, "slippage": slip})
        return OrderResult(OrderStatus.FILLED, self._ticket, fill,
                           f"paper fill slip={slip:.5f}", 10009, req)
