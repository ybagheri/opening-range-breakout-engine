"""MT5Broker — thin adapter over the MetaTrader5 Python package.

Python-only execution: no EA, no chart attachment. All trading via Mt5 API.
On non-Windows / no-terminal environments, methods raise a clear error and the
engine must run in DRY_RUN / paper mode.
"""
from __future__ import annotations

import logging

from orb_engine.broker.base import Broker
from orb_engine.core.types import (
    Direction,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    SymbolInfo,
)

log = logging.getLogger(__name__)

try:  # optional dependency
    import MetaTrader5 as mt5  # type: ignore
    _MT5_AVAILABLE = True
except Exception:  # noqa: BLE001 - optional platform-specific dependency
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False


class MT5Broker(Broker):
    name = "mt5"

    def __init__(self, login: int | str = "", password: str = "", server: str = "",
                 path: str = "", magic: int = 20240101, deviation: int = 20):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.magic = magic
        self.deviation = deviation
        self._connected = False

    # -- connection -----------------------------------------------------
    def connect(self) -> bool:
        if not _MT5_AVAILABLE:
            log.error("MetaTrader5 package not available; use DRY_RUN/paper mode")
            return False
        kwargs: dict = {}
        if self.path:
            kwargs["path"] = self.path
        if not mt5.initialize(**kwargs):
            log.error("MT5 initialize failed: %s", mt5.last_error())
            return False
        if self.login:
            try:
                login = int(self.login)
            except ValueError:
                login = self.login  # type: ignore
            if not mt5.login(login, password=self.password, server=self.server):
                log.error("MT5 login failed: %s", mt5.last_error())
                mt5.shutdown()
                return False
        acc = mt5.account_info()
        if acc is None:
            log.error("MT5 account_info unavailable")
            return False
        self._connected = True
        log.info("MT5 connected: %s balance=%s", acc.server, acc.balance)
        return True

    def is_connected(self) -> bool:
        return self._connected

    def account_balance(self) -> float:
        acc = mt5.account_info()
        if acc is None:
            raise RuntimeError("MT5 account_info unavailable")
        return float(acc.balance)

    # -- symbols ---------------------------------------------------------
    def ensure_symbol(self, symbol: str) -> bool:
        info = mt5.symbol_info(symbol)
        if info is None:
            log.error("MT5 symbol not found: %s", symbol)
            return False
        if not info.visible and not mt5.symbol_select(symbol, True):
            log.error("MT5 symbol_select failed: %s", symbol)
            return False
        return True

    def symbol_info(self, symbol: str) -> SymbolInfo | None:
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        tick = mt5.symbol_info_tick(symbol)
        spread = float(tick.ask - tick.bid) / info.point if tick and info.point else 0.0
        trade_allowed = info.trade_mode in (
            getattr(mt5, "SYMBOL_TRADE_MODE_FULL", 4),
            getattr(mt5, "SYMBOL_TRADE_MODE_LONGONLY", 2),
            getattr(mt5, "SYMBOL_TRADE_MODE_SHORTONLY", 3),
        )
        return SymbolInfo(symbol, info.digits, info.point, info.trade_tick_size,
                          info.trade_tick_value, info.trade_contract_size,
                          info.volume_min, info.volume_max, info.volume_step,
                          trade_allowed, spread_points=spread,
                          stop_level_points=int(getattr(info, "trade_stops_level", 0)))

    def current_price(self, symbol: str) -> tuple[float, float]:
        t = mt5.symbol_info_tick(symbol)
        if t is None:
            raise RuntimeError(f"no tick for {symbol}")
        return float(t.bid), float(t.ask)

    def spread_points(self, symbol: str) -> float:
        info = self.symbol_info(symbol)
        return info.spread_points if info else float("inf")

    # -- orders -----------------------------------------------------------
    def place_market_order(self, req: OrderRequest) -> OrderResult:
        bid, ask = self.current_price(req.symbol)
        price = ask if req.direction == Direction.LONG else bid
        otype = mt5.ORDER_TYPE_BUY if req.direction == Direction.LONG else mt5.ORDER_TYPE_SELL
        mt5_req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": req.volume,
            "type": otype,
            "price": price,
            "sl": req.stop_loss,
            "tp": req.take_profit,
            "deviation": self.deviation,
            "magic": req.magic,
            "comment": req.comment or req.strategy,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(mt5_req)
        if res is None:
            return OrderResult(OrderStatus.REJECTED, message=f"order_send None: {mt5.last_error()}", request=req)
        msg = f"retcode={res.retcode} ticket={res.order} price={res.price} comment={res.comment}"
        if res.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
            return OrderResult(OrderStatus.FILLED, int(res.order), float(res.price), msg, int(res.retcode), req)
        return OrderResult(OrderStatus.REJECTED, message=msg, retcode=int(res.retcode), request=req)

    def modify_position_sltp(self, ticket: int, sl: float, tp: float) -> bool:
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        p = positions[0]
        req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "symbol": p.symbol,
               "sl": sl, "tp": tp, "magic": p.magic}
        res = mt5.order_send(req)
        return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, ticket: int) -> bool:
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        p = positions[0]
        tick = mt5.symbol_info_tick(p.symbol)
        if tick is None:
            return False
        otype = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
        req = {"action": mt5.TRADE_ACTION_DEAL, "position": ticket, "symbol": p.symbol,
               "volume": p.volume, "type": otype, "price": price,
               "deviation": self.deviation, "magic": p.magic, "comment": "ORB close"}
        res = mt5.order_send(req)
        return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

    def open_positions(self, magic=None, symbol=None) -> list[Position]:
        raw = mt5.positions_get() or []
        out: list[Position] = []
        for p in raw:
            if magic is not None and p.magic != magic:
                continue
            if symbol is not None and p.symbol != symbol:
                continue
            d = Direction.LONG if p.type == mt5.POSITION_TYPE_BUY else Direction.SHORT
            out.append(Position(int(p.ticket), p.symbol, d, float(p.volume), float(p.price_open),
                                float(p.sl), float(p.tp), int(p.magic), str(p.comment),
                                session_date="", open_time=None))
        return out

    def get_rates(self, symbol: str, timeframe: str = "M5", count: int = 5000):
        import pandas as pd
        tf = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
              "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1}.get(timeframe, mt5.TIMEFRAME_M5)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            raise RuntimeError(f"copy_rates failed for {symbol}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"time": "t", "tick_volume": "volume"})
        df = df.set_index("t")[["open", "high", "low", "close", "volume"]]
        return df
