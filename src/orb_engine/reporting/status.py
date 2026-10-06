"""Live status snapshot + stdlib HTTP server (no new dependencies).

`build_snapshot` gathers everything an operator needs at a glance without
exposing secrets: config hash (never credentials), connectivity, per-symbol OR
state, open strategy positions, and daily guard counters. The `status` CLI
command prints it, or serves it as JSON + a minimal auto-refreshing HTML page
for local monitoring next to the terminal.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from orb_engine._version import __version__


def build_snapshot(engine) -> dict:
    """engine: ORBEngine. Pure read-only assembly; never touches credentials."""
    s = engine.s
    broker = engine.broker
    try:
        connected = broker.is_connected()
    except Exception:  # noqa: BLE001 - status must never crash on broker faults
        connected = False
    try:
        balance = broker.account_balance() if connected else None
    except Exception:  # noqa: BLE001 - status must never crash on broker faults
        balance = None
    try:
        positions = broker.open_positions(magic=s.magic)
    except Exception:  # noqa: BLE001 - status must never crash on broker faults
        positions = []
    symbols = []
    for sym in s.symbols:
        orng = engine.strategy.get_or(sym)
        day = None
        try:
            day = engine.sessions.session_date(datetime.now(timezone.utc))
        except Exception:  # noqa: BLE001 - status must never crash on clock faults
            day = None
        guard = engine.tm.guard.day(day) if day else None
        symbols.append({
            "symbol": sym,
            "or_high": orng.high if orng else None,
            "or_low": orng.low if orng else None,
            "or_width": orng.width if orng else None,
            "trades_today": (guard.per_symbol.get(sym, 0) if guard else 0),
        })
    return {
        "strategy": "ORB_ENGINE",
        "version": __version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "config_hash": s.config_hash(),
        "dry_run": s.dry_run,
        "paper_mode": s.paper_mode,
        "broker": getattr(broker, "name", "?"),
        "connected": connected,
        "balance": balance,
        "open_positions": [
            {"ticket": p.ticket, "symbol": p.symbol, "direction": p.direction.value,
             "volume": p.volume, "entry": p.entry_price, "sl": p.stop_loss,
             "tp": p.take_profit} for p in positions
        ],
        "symbols": symbols,
    }


def snapshot_json(engine) -> str:
    return json.dumps(build_snapshot(engine), indent=2, default=str)


def snapshot_html(engine) -> str:
    snap = build_snapshot(engine)
    rows = "\n".join(
        f"<tr><td>{html.escape(str(x['symbol']))}</td>"
        f"<td>{x['or_high']}</td><td>{x['or_low']}</td>"
        f"<td>{x['trades_today']}</td></tr>" for x in snap["symbols"])
    poss = "\n".join(
        f"<tr><td>{p['ticket']}</td><td>{html.escape(p['symbol'])}</td>"
        f"<td>{p['direction']}</td><td>{p['volume']}</td>"
        f"<td>{p['entry']}</td><td>{p['sl']}</td><td>{p['tp']}</td></tr>"
        for p in snap["open_positions"]) or "<tr><td colspan=7>none</td></tr>"
    return (
        f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="15"><title>ORB Engine status</title></head><body>
<h1>ORB Engine <small>{html.escape(snap['version'])} · {html.escape(snap['config_hash'])} · """
        f"""dry_run={snap['dry_run']}</small></h1>
<p>broker={html.escape(str(snap['broker']))} connected={snap['connected']} """
        f"""balance={snap['balance']} generated={html.escape(snap['generated_utc'])}</p>
<h2>Symbols</h2><table border="1"><tr><th>symbol</th><th>OR high</th><th>OR low</th>
<th>trades today</th></tr>{rows}</table>
<h2>Open positions</h2><table border="1"><tr><th>ticket</th><th>symbol</th><th>dir</th>
<th>vol</th><th>entry</th><th>sl</th><th>tp</th></tr>{poss}</table>
</body></html>"""
    )


def serve(engine, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Blocking local status server. Binds loopback by default — never expose
    an unauthenticated trading-status page beyond localhost."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep stdout for engine logs
            pass

        def do_GET(self):
            if self.path == "/status.json":
                body, ctype = snapshot_json(engine), "application/json"
            else:
                body, ctype = snapshot_html(engine), "text/html; charset=utf-8"
            raw = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    HTTPServer((host, port), Handler).serve_forever()
