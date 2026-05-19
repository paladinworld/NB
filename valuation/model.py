"""Core valuation model for RVI (Robinhood Ventures Fund I).

The fund holds private companies. The model estimates each holding's fair
value via up to three independent methods, blends them, sums to a portfolio
NAV, and compares NAV/share to the listed share price to surface premium
or discount."""

from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class Holding:
    name: str
    weight_pct: Optional[float] = None
    fund_mark_M: Optional[float] = None
    rvi_ownership_pct: Optional[float] = None
    last_round_valuation_B: Optional[float] = None
    last_round_date: Optional[str] = None
    secondary_premium_pct: float = 0.0
    illiquidity_discount_pct: float = 20.0
    public_comp_ev_to_revenue: Optional[float] = None
    company_revenue_ttm_B: Optional[float] = None
    notes: str = ""

    def value_last_round_M(self) -> Optional[float]:
        if self.last_round_valuation_B is None or self.rvi_ownership_pct is None:
            return None
        return self.last_round_valuation_B * 1000.0 * (self.rvi_ownership_pct / 100.0)

    def value_secondary_M(self) -> Optional[float]:
        base = self.value_last_round_M()
        if base is None:
            return None
        gross = base * (1.0 + self.secondary_premium_pct / 100.0)
        return gross * (1.0 - self.illiquidity_discount_pct / 100.0)

    def value_public_comp_M(self) -> Optional[float]:
        if (
            self.public_comp_ev_to_revenue is None
            or self.company_revenue_ttm_B is None
            or self.rvi_ownership_pct is None
        ):
            return None
        company_ev_M = (
            self.public_comp_ev_to_revenue * self.company_revenue_ttm_B * 1000.0
        )
        stake_M = company_ev_M * (self.rvi_ownership_pct / 100.0)
        return stake_M * (1.0 - self.illiquidity_discount_pct / 100.0)

    def blended_value_M(self, weights: dict) -> Optional[float]:
        candidates = [
            (self.value_last_round_M(), weights.get("last_round", 0.0)),
            (self.value_secondary_M(), weights.get("secondary", 0.0)),
            (self.value_public_comp_M(), weights.get("public_comp", 0.0)),
        ]
        valid = [(v, w) for v, w in candidates if v is not None and w > 0]
        if not valid:
            return None
        total_w = sum(w for _, w in valid)
        return sum(v * w for v, w in valid) / total_w

    def best_estimate_M(self, weights: dict) -> Optional[float]:
        """Independent estimate if computable, otherwise the fund's own mark."""
        b = self.blended_value_M(weights)
        if b is not None:
            return b
        return self.fund_mark_M


@dataclass
class Fund:
    ticker: str
    name: str
    inception_date: str
    ipo_raise_M: float
    ipo_price: float
    shares_outstanding_M: float
    market_price: float
    price_as_of: str
    cash_and_equivalents_M: float = 0.0
    other_liabilities_M: float = 0.0
    accrued_mgmt_fee_M: float = 0.0
    management_fee_pct: float = 2.0
    valuation_weights: dict = field(
        default_factory=lambda: {"last_round": 0.3, "secondary": 0.45, "public_comp": 0.25}
    )
    holdings: list = field(default_factory=list)

    # ---- NAV computations ----

    def nav_from_fund_marks_M(self) -> float:
        portfolio = sum(h.fund_mark_M or 0.0 for h in self.holdings)
        return (
            portfolio
            + self.cash_and_equivalents_M
            - self.other_liabilities_M
            - self.accrued_mgmt_fee_M
        )

    def nav_from_independent_M(self) -> float:
        portfolio = 0.0
        for h in self.holdings:
            v = h.best_estimate_M(self.valuation_weights)
            if v is not None:
                portfolio += v
        return (
            portfolio
            + self.cash_and_equivalents_M
            - self.other_liabilities_M
            - self.accrued_mgmt_fee_M
        )

    def nav_from_reported_weights_M(self) -> Optional[float]:
        """Back out implied portfolio NAV from any single holding with both a
        weight_pct and an independent fair-value estimate.

        If Databricks is reported as 23.24% of fund NAV and we independently
        estimate the Databricks stake at $X, then implied portfolio NAV = X / 0.2324.
        Useful as a sanity check: averages across all holdings with the data."""
        implied = []
        for h in self.holdings:
            if h.weight_pct is None or h.weight_pct <= 0:
                continue
            v = h.blended_value_M(self.valuation_weights)
            if v is None:
                continue
            implied.append(v / (h.weight_pct / 100.0))
        if not implied:
            return None
        return sum(implied) / len(implied)

    def nav_per_share(self, source: str = "independent") -> Optional[float]:
        if source == "independent":
            nav = self.nav_from_independent_M()
        elif source == "fund_marks":
            nav = self.nav_from_fund_marks_M()
        elif source == "reported_weights":
            nav = self.nav_from_reported_weights_M()
            if nav is None:
                return None
            nav += self.cash_and_equivalents_M - self.other_liabilities_M - self.accrued_mgmt_fee_M
        else:
            raise ValueError(f"unknown NAV source: {source}")
        return nav / self.shares_outstanding_M

    def market_cap_M(self) -> float:
        return self.shares_outstanding_M * self.market_price

    def premium_discount_pct(self, source: str = "independent") -> Optional[float]:
        nav_ps = self.nav_per_share(source)
        if nav_ps is None or nav_ps == 0:
            return None
        return (self.market_price - nav_ps) / nav_ps * 100.0


# ---- Loader ----

def _holding_from_dict(d: dict) -> Holding:
    return Holding(
        name=d.get("name", "UNKNOWN"),
        weight_pct=d.get("weight_pct"),
        fund_mark_M=d.get("fund_mark_M"),
        rvi_ownership_pct=d.get("rvi_ownership_pct"),
        last_round_valuation_B=d.get("last_round_valuation_B"),
        last_round_date=d.get("last_round_date"),
        secondary_premium_pct=d.get("secondary_premium_pct", 0.0) or 0.0,
        illiquidity_discount_pct=d.get("illiquidity_discount_pct", 20.0) or 20.0,
        public_comp_ev_to_revenue=d.get("public_comp_ev_to_revenue"),
        company_revenue_ttm_B=d.get("company_revenue_ttm_B"),
        notes=d.get("notes", "") or "",
    )


def load_fund(path: str) -> Fund:
    with open(path) as f:
        raw = yaml.safe_load(f)
    fund_data = raw["fund"]
    weights = raw.get("valuation_weights", {})
    holdings = [_holding_from_dict(h) for h in raw.get("holdings", [])]
    return Fund(
        ticker=fund_data["ticker"],
        name=fund_data["name"],
        inception_date=str(fund_data.get("inception_date", "")),
        ipo_raise_M=fund_data["ipo_raise_M"],
        ipo_price=fund_data["ipo_price"],
        shares_outstanding_M=fund_data["shares_outstanding_M"],
        market_price=fund_data["market_price"],
        price_as_of=str(fund_data.get("price_as_of", "")),
        cash_and_equivalents_M=fund_data.get("cash_and_equivalents_M", 0.0) or 0.0,
        other_liabilities_M=fund_data.get("other_liabilities_M", 0.0) or 0.0,
        accrued_mgmt_fee_M=fund_data.get("accrued_mgmt_fee_M", 0.0) or 0.0,
        management_fee_pct=fund_data.get("management_fee_pct", 2.0),
        valuation_weights=weights or {"last_round": 0.3, "secondary": 0.45, "public_comp": 0.25},
        holdings=holdings,
    )
