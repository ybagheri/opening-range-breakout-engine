"""Report generator: config + metrics + reproducibility block."""
from __future__ import annotations

import datetime as dt
import json


def build_report(config: dict, metrics: dict, data_info: dict, out_md: str) -> str:
    lines = ["# ORB Backtest Report", "",
             f"Generated (UTC): {dt.datetime.now(dt.timezone.utc).isoformat()}", "",
             "## Configuration", "```json", json.dumps(config, indent=2, default=str), "```", "",
             "## Data & assumptions", "```json", json.dumps(data_info, indent=2, default=str), "```", "",
             "## Metrics", "```json", json.dumps(metrics, indent=2, default=str), "```", "",
             "> Backtested performance is not guaranteed future performance."]
    with open(out_md, "w") as f:
        f.write("\n".join(lines))
    return out_md
