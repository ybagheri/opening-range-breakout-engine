"""Core shared types — broker-independent."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SignalType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_SIGNAL = "NO_SIGNAL"


class ExitReason(str, Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    FORCE_CLOSE = "FORCE_CLOSE"
    END_OF_DATA = "END_OF_DATA"
    MANUAL = "MANUAL"
    BREAKEVEN_STOP = "BREAKEVEN_STOP"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    REVERSAL_BLOCKED = "REVERSAL_BLOCKED"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    DRY_RUN = "DRY_RUN"


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime  # timezone-aware, market time
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Bar.timestamp must be timezone-aware")


@dataclass(frozen=True)
class OpeningRange:
    symbol: str
    session_date: str  # YYYY-MM-DD in market tz
    start: datetime
    end: datetime
    high: float
    low: float

    @property
    def width(self) -> float:
        return self.high - self.low

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def is_valid(self) -> bool:
        return self.high > self.low and self.width > 0


@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    session_date: str
    signal_type: SignalType
    signal_time: datetime
    price: float
    or_high: float
    or_low: float
    reason: str = ""
    atr: float | None = None  # known at signal-bar close; required iff SL mode is atr


@dataclass
class OrderRequest:
    symbol: str
    direction: Direction
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    magic: int
    strategy: str
    session_date: str
    comment: str = ""
    deviation_points: int = 20


@dataclass
class OrderResult:
    status: OrderStatus
    ticket: int | None = None
    filled_price: float | None = None
    message: str = ""
    retcode: int | None = None
    request: OrderRequest | None = None


@dataclass
class Position:
    ticket: int
    symbol: str
    direction: Direction
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    magic: int
    strategy: str
    session_date: str
    open_time: datetime | None = None


@dataclass
class SymbolInfo:
    symbol: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    trade_allowed: bool = True
    spread_points: float = 0.0
    stop_level_points: int = 0


@dataclass
class CompletedTrade:
    trade_id: str
    symbol: str
    direction: Direction
    session_date: str
    or_high: float
    or_low: float
    signal_time: datetime | None
    entry_time: datetime | None
    entry_price: float
    stop_price: float
    target_price: float
    volume: float
    risk_pct: float
    risk_amount: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: ExitReason | None = None
    gross_pnl: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    net_pnl: float = 0.0
    r_multiple: float = 0.0
    breakeven_used: bool = False
    config_hash: str = ""
    extra: dict = field(default_factory=dict)
