"""In-memory MockBroker for unit tests."""
from __future__ import annotations

from orb_engine.broker.base import Broker
from orb_engine.core.types import (
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    SymbolInfo,
)


class MockBroker(Broker):
    name = "mock"

    def __init__(self, balance: float = 10000.0, infos: dict[str, SymbolInfo] | None = None):
        self._balance = balance
        self._infos = infos or {}
        self._positions: list[Position] = []
        self._ticket = 1000
        self.orders_sent: list[OrderRequest] = []

    def connect(self) -> bool:
        return True

    def is_connected(self) -> bool:
        return True

    def account_balance(self) -> float:
        return self._balance

    def symbol_info(self, symbol: str) -> SymbolInfo | None:
        return self._infos.get(symbol)

    def ensure_symbol(self, symbol: str) -> bool:
        return symbol in self._infos

    def current_price(self, symbol: str) -> tuple[float, float]:
        return 100.0, 100.02

    def spread_points(self, symbol: str) -> float:
        return 2.0

    def place_market_order(self, req: OrderRequest) -> OrderResult:
        self.orders_sent.append(req)
        self._ticket += 1
        pos = Position(self._ticket, req.symbol,
                       req.direction, req.volume, req.entry_price,
                       req.stop_loss, req.take_profit, req.magic, req.strategy,
                       req.session_date)
        self._positions.append(pos)
        return OrderResult(OrderStatus.FILLED, self._ticket, req.entry_price, "mock fill", 10009, req)

    def modify_position_sltp(self, ticket: int, sl: float, tp: float) -> bool:
        for p in self._positions:
            if p.ticket == ticket:
                p.stop_loss, p.take_profit = sl, tp
                return True
        return False

    def close_position(self, ticket: int) -> bool:
        before = len(self._positions)
        self._positions = [p for p in self._positions if p.ticket != ticket]
        return len(self._positions) < before

    def open_positions(self, magic=None, symbol=None) -> list[Position]:
        out = self._positions
        if magic is not None:
            out = [p for p in out if p.magic == magic]
        if symbol is not None:
            out = [p for p in out if p.symbol == symbol]
        return list(out)
