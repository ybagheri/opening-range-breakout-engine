"""Broker interface — strategy depends on this, never on MT5 directly."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from orb_engine.core.types import OrderRequest, OrderResult, Position, SymbolInfo


class Broker(ABC):
    name: str = "base"

    @abstractmethod
    def connect(self) -> bool: ...
    @abstractmethod
    def is_connected(self) -> bool: ...
    @abstractmethod
    def account_balance(self) -> float: ...
    @abstractmethod
    def symbol_info(self, symbol: str) -> SymbolInfo | None: ...
    @abstractmethod
    def ensure_symbol(self, symbol: str) -> bool: ...
    @abstractmethod
    def current_price(self, symbol: str) -> tuple[float, float]: ...  # bid, ask
    @abstractmethod
    def spread_points(self, symbol: str) -> float: ...
    @abstractmethod
    def place_market_order(self, req: OrderRequest) -> OrderResult: ...
    @abstractmethod
    def modify_position_sltp(self, ticket: int, sl: float, tp: float) -> bool: ...
    @abstractmethod
    def close_position(self, ticket: int) -> bool: ...
    @abstractmethod
    def open_positions(self, magic: int | None = None, symbol: str | None = None) -> list[Position]: ...
    def get_rates(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        raise NotImplementedError
