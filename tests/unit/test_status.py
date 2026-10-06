"""v1.6.0 tests: status snapshot content, secrecy, HTTP round-trip."""
import json
import urllib.request

from orb_engine.broker.paper import PaperBroker
from orb_engine.config.settings import Settings
from orb_engine.core.types import SymbolInfo
from orb_engine.execution.engine import ORBEngine
from orb_engine.reporting import status as st


def _eng(tmp_path, symbols=("US30",)):
    s = Settings(symbols=symbols, state_db=str(tmp_path / "s.db"),
                 journal_db=str(tmp_path / "j.db"), mt5_password="super-secret")
    infos = {sym: SymbolInfo(sym, 2, 0.01, 0.01, 1.0, 1, 0.01, 100, 0.01) for sym in symbols}
    return ORBEngine(s, PaperBroker(10000.0, infos))


def test_snapshot_structure_and_no_secrets(tmp_path):
    snap = st.build_snapshot(_eng(tmp_path))
    assert snap["strategy"] == "ORB_ENGINE" and snap["config_hash"]
    assert snap["connected"] and snap["balance"] == 10000.0
    assert [x["symbol"] for x in snap["symbols"]] == ["US30"]
    blob = json.dumps(snap)
    assert "super-secret" not in blob and "password" not in blob.lower()


def test_html_escapes_symbol_names(tmp_path):
    snap_html = st.snapshot_html(_eng(tmp_path, symbols=("<b>X</b>",)))
    assert "<b>X</b>" not in snap_html and "&lt;b&gt;" in snap_html


def test_http_round_trip(tmp_path):
    import socket
    import threading as th
    import time

    eng = _eng(tmp_path)

    def free_port():
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    port = free_port()
    th.Thread(target=st.serve, args=(eng, "127.0.0.1", port), daemon=True).start()
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/status.json",
                                        timeout=2) as r:
                data = json.loads(r.read())
            break
        except OSError:
            time.sleep(0.1)
    assert data["strategy"] == "ORB_ENGINE"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        page = r.read().decode()
    assert "ORB Engine" in page
