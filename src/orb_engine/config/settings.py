"""Externalized configuration: .env + structured validation. No secrets in code."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "")
    if v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_float(name: str, default: float) -> float:
    v = os.getenv(name, "")
    if v == "":
        return default
    return float(v)


def _get_int(name: str, default: int) -> int:
    v = os.getenv(name, "")
    if v == "":
        return default
    return int(v)


@dataclass
class Settings:
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""
    symbols: tuple[str, ...] = ("US30", "US500", "US100")
    magic: int = 20240101
    deviation_points: int = 20
    timezone: str = "America/New_York"
    or_start: str = "09:30"
    or_end: str = "09:45"
    trading_start: str = "09:45"
    trading_end: str = "11:30"
    force_close_time: str = ""
    allow_overnight: bool = False
    risk_per_trade_percent: float = 0.5
    max_trades_per_symbol_per_day: int = 1
    max_total_trades_per_day: int = 3
    max_daily_loss_percent: float = 2.0
    stop_loss_mode: str = "opposite"
    stop_loss_value: float = 1.0
    take_profit_mode: str = "risk_reward"
    take_profit_value: float = 2.0
    risk_reward: float = 2.0
    breakout_buffer_points: float = 0.0
    breakout_buffer_pct_of_or: float = 0.0
    breakout_require_close: bool = False
    breakeven_enabled: bool = True
    breakeven_trigger_r: float = 1.0
    breakeven_buffer_points: float = 0.0
    max_spread_points: float = 0.0
    dry_run: bool = True
    paper_mode: bool = True
    backtest_spread_points: float = 2.0
    backtest_slippage_points: float = 1.0
    backtest_commission: float = 0.0
    intrabar_policy: str = "conservative"
    state_db: str = "data/orb_state.sqlite"
    journal_db: str = "data/orb_journal.sqlite"
    log_level: str = "INFO"
    point_overrides: dict[str, float] = field(default_factory=dict)

    def config_hash(self) -> str:
        payload = json.dumps(self.public_dict(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def public_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if "password" not in k}
        d["symbols"] = list(self.symbols)
        return d


def _parse_point_overrides(raw: str) -> dict[str, float]:
    """Parse e.g. "US30:1.0,US500:0.25" into {symbol: point}. Empty -> {}."""
    out: dict[str, float] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"POINT_OVERRIDES entry must be SYMBOL:point, got {part!r}")
        sym, val = part.split(":", 1)
        out[sym.strip().upper()] = float(val)
    return out


def load_settings() -> Settings:
    syms = [s.strip() for s in _get("MT5_SYMBOLS", "US30,US500,US100").split(",") if s.strip()]
    return Settings(
        mt5_login=_get("MT5_LOGIN"),
        mt5_password=_get("MT5_PASSWORD"),
        mt5_server=_get("MT5_SERVER"),
        mt5_path=_get("MT5_PATH"),
        symbols=tuple(syms),
        magic=_get_int("MT5_MAGIC", 20240101),
        deviation_points=_get_int("MT5_DEVIATION_POINTS", 20),
        timezone=_get("TIMEZONE", "America/New_York") or "America/New_York",
        or_start=_get("OR_START_TIME", "09:30"),
        or_end=_get("OR_END_TIME", "09:45"),
        trading_start=_get("TRADING_START_TIME", "09:45"),
        trading_end=_get("TRADING_END_TIME", "11:30"),
        force_close_time=_get("FORCE_CLOSE_TIME", ""),
        allow_overnight=_get_bool("ALLOW_OVERNIGHT", False),
        risk_per_trade_percent=_get_float("RISK_PER_TRADE_PERCENT", 0.5),
        max_trades_per_symbol_per_day=_get_int("MAX_TRADES_PER_SYMBOL_PER_DAY", 1),
        max_total_trades_per_day=_get_int("MAX_TOTAL_TRADES_PER_DAY", 3),
        max_daily_loss_percent=_get_float("MAX_DAILY_LOSS_PERCENT", 2.0),
        stop_loss_mode=_get("STOP_LOSS_MODE", "opposite").lower(),
        stop_loss_value=_get_float("STOP_LOSS_VALUE", 1.0),
        take_profit_mode=_get("TAKE_PROFIT_MODE", "risk_reward").lower(),
        take_profit_value=_get_float("TAKE_PROFIT_VALUE", 2.0),
        risk_reward=_get_float("RISK_REWARD", 2.0),
        breakout_buffer_points=_get_float("BREAKOUT_BUFFER_POINTS", 0.0),
        breakout_buffer_pct_of_or=_get_float("BREAKOUT_BUFFER_PCT_OF_OR", 0.0),
        breakout_require_close=_get_bool("BREAKOUT_REQUIRE_CLOSE", False),
        breakeven_enabled=_get_bool("BREAK_EVEN_ENABLED", True),
        breakeven_trigger_r=_get_float("BREAK_EVEN_TRIGGER_R", 1.0),
        breakeven_buffer_points=_get_float("BREAK_EVEN_BUFFER_POINTS", 0.0),
        max_spread_points=_get_float("MAX_SPREAD_POINTS", 0.0),
        dry_run=_get_bool("DRY_RUN", True),
        paper_mode=_get_bool("PAPER_MODE", True),
        backtest_spread_points=_get_float("BACKTEST_SPREAD_POINTS", 2.0),
        backtest_slippage_points=_get_float("BACKTEST_SLIPPAGE_POINTS", 1.0),
        backtest_commission=_get_float("BACKTEST_COMMISSION_PER_TRADE", 0.0),
        intrabar_policy=_get("BACKTEST_INTRA_BAR_POLICY", "conservative").lower(),
        state_db=_get("STATE_DB_PATH", "data/orb_state.sqlite"),
        journal_db=_get("JOURNAL_DB_PATH", "data/orb_journal.sqlite"),
        log_level=_get("LOG_LEVEL", "INFO") or "INFO",
        point_overrides=_parse_point_overrides(_get("POINT_OVERRIDES", "")),
    )


def validate_settings(s: Settings) -> list[str]:
    """Return list of error strings; empty means valid."""
    from orb_engine.utils.time_utils import parse_hhmm
    errors: list[str] = []
    if not s.symbols:
        errors.append("MT5_SYMBOLS must contain at least one symbol")
    if not (0 < s.risk_per_trade_percent <= 5):
        errors.append(f"RISK_PER_TRADE_PERCENT must be in (0, 5], got {s.risk_per_trade_percent}")
    if s.risk_reward <= 0:
        errors.append(f"RISK_REWARD must be > 0, got {s.risk_reward}")
    if s.stop_loss_mode not in ("opposite", "or_width_multiple", "fixed_points", "percent", "atr"):
        errors.append(f"Unknown STOP_LOSS_MODE: {s.stop_loss_mode}")
    if s.take_profit_mode not in ("risk_reward", "or_width_multiple", "fixed_points"):
        errors.append(f"Unknown TAKE_PROFIT_MODE: {s.take_profit_mode}")
    try:
        ors, ore = parse_hhmm(s.or_start), parse_hhmm(s.or_end)
        ts, te = parse_hhmm(s.trading_start), parse_hhmm(s.trading_end)
        if (ore.hour, ore.minute) <= (ors.hour, ors.minute):
            errors.append("OR_END_TIME must be after OR_START_TIME")
        if (te.hour, te.minute) <= (ts.hour, ts.minute):
            errors.append("TRADING_END_TIME must be after TRADING_START_TIME")
    except ValueError as e:
        errors.append(f"Invalid time format: {e}")
    if s.max_trades_per_symbol_per_day < 1:
        errors.append("MAX_TRADES_PER_SYMBOL_PER_DAY must be >= 1")
    if s.intrabar_policy not in ("conservative", "optimistic", "stop_first", "target_first"):
        errors.append(f"Unknown intrabar policy: {s.intrabar_policy}")
    for sym, pt in s.point_overrides.items():
        if pt <= 0:
            errors.append(f"POINT_OVERRIDES {sym}: point must be > 0")
    return errors
