"""PaperBroker: simulates fills at requested price, tracks positions/pnl in memory."""
from __future__ import annotations

from orb_engine.broker.mock import MockBroker
from orb_engine.core.types import SymbolInfo


class PaperBroker(MockBroker):
    name = "paper"

    def __init__(self, balance: float = 10000.0, infos: dict[str, SymbolInfo] | None = None):
        super().__init__(balance, infos)
