#!/usr/bin/env python3
"""Compute and print RVI's estimated NAV and premium/discount to market price.

Usage:
  python value_rvi.py [--portfolio data/portfolio.yaml] [--no-log]
"""

import argparse

from valuation.model import load_fund
from valuation.report import render, append_history


def main() -> None:
    ap = argparse.ArgumentParser(description="RVI portfolio NAV estimator")
    ap.add_argument("--portfolio", default="data/portfolio.yaml")
    ap.add_argument("--history", default="data/history.csv")
    ap.add_argument("--no-log", action="store_true",
                    help="Skip appending a row to data/history.csv")
    args = ap.parse_args()

    fund = load_fund(args.portfolio)
    print(render(fund))
    if not args.no_log:
        append_history(fund, args.history)


if __name__ == "__main__":
    main()
