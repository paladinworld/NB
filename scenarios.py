"""What-if scenarios for RVI. Run: python scenarios.py"""

from valuation.model import load_fund


def shock(fund, name_to_multiplier: dict[str, float]) -> tuple[float, float]:
    """Apply per-holding multipliers to blended values and return new NAV/share + delta vs base."""
    base_nav = fund.nav_from_independent_M()
    base_nav_ps = base_nav / fund.shares_outstanding_M

    delta_M = 0.0
    for h in fund.holdings:
        if h.name in name_to_multiplier:
            v = h.blended_value_M(fund.valuation_weights)
            if v is None:
                continue
            delta_M += v * (name_to_multiplier[h.name] - 1.0)

    new_nav = base_nav + delta_M
    new_nav_ps = new_nav / fund.shares_outstanding_M
    return new_nav_ps, new_nav_ps - base_nav_ps


def main():
    fund = load_fund("data/portfolio.yaml")
    base_nav_ps = fund.nav_per_share("independent")
    px = fund.market_price

    print(f"Base independent NAV/share: ${base_nav_ps:,.2f}")
    print(f"Market price:               ${px:,.2f}")
    print(f"Base premium/discount:      {(px-base_nav_ps)/base_nav_ps*100:+.2f}%\n")

    scenarios = [
        # User's questions, against the actual holdings:
        ("OpenAI $852B → $1T (+17%)",
            {"OpenAI": 1.17}),
        ("Stripe +30% from investment round",
            {"Stripe": 1.30}),
        ("Both: OpenAI +17% AND Stripe +30%",
            {"OpenAI": 1.17, "Stripe": 1.30}),
        ("OpenAI $852B → $1.2T (+41%)",
            {"OpenAI": 1.41}),
        # Other bull / bear scenarios:
        ("Databricks IPO pop (+50%)",
            {"Databricks": 1.50}),
        ("All fintechs +30% (Revolut + Airwallex + Ramp + Stripe)",
            {"Revolut": 1.30, "Airwallex": 1.30, "Ramp": 1.30, "Stripe": 1.30}),
        ("Bull: every private holding +40%",
            {h.name: 1.40 for h in fund.holdings}),
        ("Bear: every private holding −25%",
            {h.name: 0.75 for h in fund.holdings}),
        ("Mercor 10x (AI-leader narrative)",
            {"Mercor": 10.0}),
    ]

    print(f"{'Scenario':<55} {'NAV/sh':>9} {'Δ NAV':>8} {'Mkt vs NAV':>11}")
    print("-" * 86)
    for label, shocks in scenarios:
        new_nav_ps, delta = shock(fund, shocks)
        premium = (px - new_nav_ps) / new_nav_ps * 100
        print(f"{label:<55} ${new_nav_ps:>7,.2f} {delta:+8,.2f} {premium:+10.2f}%")


if __name__ == "__main__":
    main()
