"""Pretty-print a valuation report for a Fund and append a history row."""

import csv
import os
from datetime import datetime
from typing import Optional

from tabulate import tabulate

from .model import Fund, Holding


def _fmt_M(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"${v:,.1f}M"


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%"


def _holding_rows(fund: Fund):
    weights = fund.valuation_weights
    rows = []
    for h in fund.holdings:
        rows.append([
            h.name,
            f"{h.weight_pct:.2f}%" if h.weight_pct is not None else "—",
            _fmt_M(h.fund_mark_M),
            _fmt_M(h.value_last_round_M()),
            _fmt_M(h.value_secondary_M()),
            _fmt_M(h.value_public_comp_M()),
            _fmt_M(h.blended_value_M(weights)),
        ])
    return rows


def render(fund: Fund) -> str:
    out = []
    out.append("=" * 78)
    out.append(f"{fund.ticker} — {fund.name}")
    out.append(f"Price ${fund.market_price:,.2f} as of {fund.price_as_of}    "
               f"Market cap ${fund.market_cap_M():,.1f}M    "
               f"Shares {fund.shares_outstanding_M:,.3f}M")
    out.append("=" * 78)
    out.append("")

    out.append("HOLDINGS — fair value estimates ($M, RVI's stake)")
    out.append(tabulate(
        _holding_rows(fund),
        headers=["Holding", "Weight", "Fund mark", "Last round", "Secondary", "Public comp", "Blended"],
        tablefmt="simple",
    ))
    out.append("")

    # NAV summary across sources
    nav_indep_ps = fund.nav_per_share("independent")
    nav_marks_ps = fund.nav_per_share("fund_marks")
    nav_rep_ps = fund.nav_per_share("reported_weights")

    summary = [
        ["Independent estimate (blended methods)",
         _fmt_M(fund.nav_from_independent_M()),
         f"${nav_indep_ps:,.2f}" if nav_indep_ps else "—",
         _fmt_pct(fund.premium_discount_pct("independent"))],
        ["Fund-reported marks (N-PORT)",
         _fmt_M(fund.nav_from_fund_marks_M()),
         f"${nav_marks_ps:,.2f}" if nav_marks_ps else "—",
         _fmt_pct(fund.premium_discount_pct("fund_marks"))],
        ["Implied from reported weights (sanity)",
         _fmt_M(fund.nav_from_reported_weights_M()),
         f"${nav_rep_ps:,.2f}" if nav_rep_ps else "—",
         _fmt_pct(fund.premium_discount_pct("reported_weights"))],
    ]
    out.append("NAV SUMMARY")
    out.append(tabulate(
        summary,
        headers=["Source", "Portfolio NAV", "NAV / share", "Mkt vs NAV"],
        tablefmt="simple",
    ))
    out.append("")

    # Sensitivity: ±20% on each holding's blended value
    sens_rows = []
    base_nav = fund.nav_from_independent_M()
    if base_nav:
        for h in fund.holdings:
            v = h.blended_value_M(fund.valuation_weights)
            if v is None:
                continue
            down = (base_nav - 0.20 * v) / fund.shares_outstanding_M
            up = (base_nav + 0.20 * v) / fund.shares_outstanding_M
            sens_rows.append([
                h.name,
                _fmt_M(v),
                f"${down:,.2f}",
                f"${up:,.2f}",
            ])
        if sens_rows:
            out.append("SENSITIVITY — NAV/share if each holding's value moves ±20%")
            out.append(tabulate(
                sens_rows,
                headers=["Holding", "Current stake", "NAV/share if −20%", "NAV/share if +20%"],
                tablefmt="simple",
            ))
            out.append("")

    # Verdict
    pd_indep = fund.premium_discount_pct("independent")
    out.append("VERDICT")
    if pd_indep is None:
        out.append("  Not enough inputs to compute an independent NAV.")
        out.append("  Fill in rvi_ownership_pct and last_round_valuation_B for more holdings.")
    else:
        nav_ps = fund.nav_per_share("independent")
        out.append(f"  Independent NAV/share: ${nav_ps:,.2f}")
        out.append(f"  Market price:          ${fund.market_price:,.2f}")
        if pd_indep > 0:
            out.append(f"  Trading at {pd_indep:+.1f}% PREMIUM to estimated NAV.")
        else:
            out.append(f"  Trading at {pd_indep:+.1f}% DISCOUNT to estimated NAV.")
        out.append("")
        out.append("  Context: closed-end funds typically trade between a 10% discount and")
        out.append("  a 20% premium to NAV. Private-asset CEFs with retail demand can spike")
        out.append("  to >50% premiums (e.g. DXYZ traded at 800%+ premium in 2024). Premiums")
        out.append("  this large tend to compress — usually fast — once new shares are issued")
        out.append("  or marks are refreshed in N-PORT filings.")

    out.append("")
    out.append("Inputs are estimates. Verify each input from primary sources before acting.")
    return "\n".join(out)


def append_history(fund: Fund, history_path: str) -> None:
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    new_file = not os.path.exists(history_path)
    with open(history_path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow([
                "timestamp",
                "price_as_of",
                "market_price",
                "shares_outstanding_M",
                "market_cap_M",
                "nav_independent_M",
                "nav_per_share_independent",
                "premium_discount_pct_independent",
                "nav_fund_marks_M",
                "nav_per_share_fund_marks",
                "premium_discount_pct_fund_marks",
            ])
        w.writerow([
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            fund.price_as_of,
            fund.market_price,
            fund.shares_outstanding_M,
            round(fund.market_cap_M(), 2),
            round(fund.nav_from_independent_M(), 2),
            round(fund.nav_per_share("independent"), 4) if fund.nav_per_share("independent") else "",
            round(fund.premium_discount_pct("independent"), 3) if fund.premium_discount_pct("independent") is not None else "",
            round(fund.nav_from_fund_marks_M(), 2),
            round(fund.nav_per_share("fund_marks"), 4) if fund.nav_per_share("fund_marks") else "",
            round(fund.premium_discount_pct("fund_marks"), 3) if fund.premium_discount_pct("fund_marks") is not None else "",
        ])
