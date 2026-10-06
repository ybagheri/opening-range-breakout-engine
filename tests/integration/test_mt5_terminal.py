"""MT5 terminal integration tests — run ONLY against a real demo terminal.

Gating (all must hold, otherwise the whole module SKIPS, never fails):
  1. env MT5_RUN_LIVE_TESTS=1 (explicit opt-in; CI never sets it by accident),
  2. `import MetaTrader5` succeeds (Windows + package installed),
  3. MT5Broker.connect() reaches a terminal (logged-in demo account).

Hard safety rules for this module:
  - NEVER call place_market_order / close_position / modify_position_sltp.
  - Execution is exercised exclusively through the DRY_RUN path.
  - Tests never close, modify, or open anything; read-only + dry-run only.

Enable on a Windows machine with a demo terminal:
    set MT5_RUN_LIVE_TESTS=1
    pytest tests/integration/test_mt5_terminal.py -v
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.mt5


def terminal_available() -> bool:
    """True only when live-terminal tests are explicitly enabled AND reachable."""
    if os.getenv("MT5_RUN_LIVE_TESTS") != "1":
        return False
    try:
        import MetaTrader5  # noqa: F401
    except ImportError:
        return False
    return True


def _settings():
    from orb_engine.config.settings import load_settings, validate_settings
    s = load_settings()
    errs = validate_settings(s)
    assert not errs, f"invalid config: {errs}"
    # Force dry-run: this module must be physically incapable of live trading.
    s.dry_run = True
    return s


@pytest.fixture(scope="module")
def broker():
    if not terminal_available():
        pytest.skip("MT5 terminal tests need MT5_RUN_LIVE_TESTS=1 + MetaTrader5 + terminal")
    from orb_engine.broker.mt5_broker import MT5Broker
    s = _settings()
    b = MT5Broker(s.mt5_login, s.mt5_password, s.mt5_server, s.mt5_path,
                  s.magic, s.deviation_points)
    if not b.connect():
        pytest.skip("MT5 terminal not reachable (start terminal / check credentials)")
    yield b


@pytest.fixture(scope="module")
def symbol(broker):
    from orb_engine.config.settings import load_settings
    syms = load_settings().symbols
    assert syms, "MT5_SYMBOLS empty"
    return os.getenv("MT5_TEST_SYMBOL", syms[0])


def test_terminal_connection_and_account(broker):
    assert broker.is_connected()
    assert broker.account_balance() > 0


def test_symbol_validation(broker, symbol):
    assert broker.ensure_symbol(symbol), f"symbol not usable: {symbol}"
    info = broker.symbol_info(symbol)
    assert info is not None
    assert info.point > 0 and info.tick_size > 0 and info.tick_value > 0
    assert info.contract_size > 0
    assert 0 < info.volume_min <= info.volume_max and info.volume_step > 0
    assert info.trade_allowed, f"{symbol} not tradeable"


def test_market_data_and_ticks(broker, symbol):
    bid, ask = broker.current_price(symbol)
    assert 0 < bid <= ask, f"invalid quote bid={bid} ask={ask}"
    df = broker.get_rates(symbol, "M5", 50)
    assert not df.empty
    assert {"open", "high", "low", "close"}.issubset(df.columns)
    from orb_engine.data.validation import validate_ohlc
    assert validate_ohlc(df) == []


def test_dry_run_pipeline_end_to_end(broker, symbol, tmp_path_factory):
    """Full live path (real specs, sizing, SL/TP) with zero order submission."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from orb_engine.core.types import SignalType, TradeSignal
    from orb_engine.execution.trade_manager import TradeManager
    s = _settings()
    tm = TradeManager(s, broker, state=None)
    # entry at live ask with a symmetric ±10 price-unit OR shell so SL distance
    # is positive on any instrument; TradeManager still validates everything.
    ask = broker.current_price(symbol)[1]
    sig = TradeSignal(symbol, "2099-01-01", SignalType.LONG,
                      datetime(2099, 1, 1, 10, 0, tzinfo=ZoneInfo("America/New_York")),
                      ask, ask + 10.0, ask - 10.0, "integration-probe")
    res = tm.handle_signal(sig, broker.account_balance())
    assert res["action"] in ("dry_run", "ignore")  # ignore only for guard reasons
    if res["action"] == "dry_run":
        assert res["size"].volume > 0 and res["size"].expected_max_loss > 0
    assert isinstance(broker.open_positions(magic=s.magic, symbol=symbol), list)


def test_strategy_identity_isolates_own_positions(broker):
    # Must not fail on accounts with manual/other-EA positions; filter is by magic.
    mine = broker.open_positions(magic=123456789)
    assert isinstance(mine, list)
