"""Helper: python scripts/run_backtest.py --data-glob 'data/*.csv'"""
import sys

sys.path.insert(0, "src")
from orb_engine.cli import main

main(["backtest", "--data-glob", "data/*.csv"])
