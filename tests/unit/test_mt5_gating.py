"""Unit test for the integration gate: without opt-in, live tests must skip, not fail."""


def test_terminal_gate_closed_by_default(monkeypatch):
    monkeypatch.delenv("MT5_RUN_LIVE_TESTS", raising=False)
    from tests.integration.test_mt5_terminal import terminal_available
    assert terminal_available() is False
