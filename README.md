# RVI Valuation Model

A private framework for tracking the fundamental value of **RVI — Robinhood
Ventures Fund I**, a closed-end fund that invests in late-stage private
companies. The goal is to estimate the underlying portfolio NAV per share and
compare it to the listed share price so you can judge whether the current
market price is reasonable.

> **Not investment advice.** This is a personal analytical tool. Inputs are
> estimates and will be wrong. Verify every number against primary sources
> (SEC filings, fund factsheets, primary funding round press releases) before
> using the output to size or change a position.

---

## Why RVI is hard to value

Most ETFs/CEFs hold liquid securities you can mark continuously. RVI holds
**private** companies — Databricks, etc. — whose "fair value" is reported by
the fund itself, typically quarterly via N-PORT filings, based on 409A
valuations and the most recent funding round. Several issues:

1. **Stale marks.** The fund's reported NAV may lag the market by 1–6 months.
   If a holding's secondary market has moved, the fund's mark won't reflect it
   until the next refresh.
2. **No real-time NAV.** Unlike an ETF, RVI's intraday price is pure
   supply/demand. It can decouple from underlying value by tens of percent.
3. **Premium/discount can be huge.** Retail-favored private-asset CEFs have
   historically traded at premiums of 50–800% to stated NAV (see Destiny Tech100
   / DXYZ in 2024). Those premiums compress sharply on (a) new share issuance,
   (b) updated quarterly marks, (c) an underlying IPO that exposes the gap.
4. **Concentration risk.** With ~10 holdings and one position (Databricks)
   above 20% of NAV, fund value is highly sensitive to single-name moves.

The model estimates an independent NAV using public secondary-market signals
and public-comparable multiples, then triangulates against the fund's own
reported marks.

---

## What the model does

For each holding, it estimates RVI's stake using up to three methods:

| Method | Formula | Use when |
| --- | --- | --- |
| **Last round** | `last_round_post_money × ownership_pct` | Recent (<6mo) primary round; conservative |
| **Secondary** | `last_round × (1 + secondary_premium) × (1 − illiquidity_discount) × ownership_pct` | Active Forge/EquityZen/Hiive data |
| **Public comp** | `revenue_ttm × peer_EV/Revenue × (1 − illiquidity_discount) × ownership_pct` | Cross-check against public peer multiples |

The three methods are blended using configurable weights (default
30 / 45 / 25). Per-holding blended stakes are summed, added to cash, less
liabilities and accrued fees, divided by shares outstanding → independent
**NAV/share**. Compared to market price → **premium/discount**.

Three NAV views are produced:

1. **Independent** — from your inputs and the methods above.
2. **Fund-reported marks** — straight sum of `fund_mark_M` from N-PORT.
3. **Implied from weights** — back-solves an implied portfolio NAV from each
   holding's reported `weight_pct` and your independent stake estimate
   (averaged across holdings). A sanity check that should agree with #1.

The output also shows a ±20% sensitivity per holding so you can see which
positions drive your NAV uncertainty.

---

## Usage

```bash
pip install -r requirements.txt
python value_rvi.py
```

To update inputs, edit `data/portfolio.yaml`. Re-run when:

- The fund publishes a new factsheet, N-PORT, or N-CSR (quarterly).
- A holding announces a new primary round.
- You spot a meaningful move in secondary market prints (Forge/EquityZen).
- You want to log the current state to `data/history.csv` for tracking.

Each run appends a row to `data/history.csv` with timestamp, market price,
NAV estimates, and premium/discount — so you can chart the premium-to-NAV
over time. Use `--no-log` to skip.

---

## Filling in inputs

Start with `data/portfolio.yaml`. The fund-level block (shares, cash, fees)
should come straight from filings. For each holding you need three pieces to
get *any* independent estimate:

1. **`rvi_ownership_pct`** — RVI's % of the company's fully-diluted shares.
   Compute as `fund_mark_M / (company_FMV_M)`. If the fund discloses a $ stake
   in N-PORT, that plus the company's last-round valuation gives you this.
2. **`last_round_valuation_B`** — most recent primary round, post-money.
3. **At least one of**: `secondary_premium_pct` (if you have current secondary
   data) or `public_comp_ev_to_revenue` + `company_revenue_ttm_B`.

If you only have `fund_mark_M` and `weight_pct`, the model still works — it
will just rely on fund marks rather than producing an independent estimate for
that holding.

Only **Databricks** is pre-filled (from the in-app screenshot, 23.24% as of
Jan 31, 2026). Fill the other nine from the fund's published holdings list.

### Where to find the inputs

| Input | Source |
| --- | --- |
| Shares outstanding, cash, liabilities, fees | Latest 10-Q / N-CSR on SEC EDGAR |
| Holdings list and `fund_mark_M` per holding | N-PORT filing (quarterly) |
| `weight_pct` | Fund factsheet / Robinhood app |
| `last_round_valuation_B`, date | TechCrunch, company press releases, PitchBook |
| `secondary_premium_pct` | Forge Global, EquityZen, Hiive marketplaces |
| `public_comp_ev_to_revenue` | NTM multiples for public peers (e.g. SNOW for Databricks) |
| `company_revenue_ttm_B` | Company press, earnings leaks, industry reports |

---

## How to read the output

```
VERDICT
  Independent NAV/share: $X.XX
  Market price:          $45.70
  Trading at +N.N% PREMIUM to estimated NAV.
```

Rules of thumb (not advice):

- **−20% to +10%** vs NAV: roughly in line with typical CEF behavior. The
  market is pricing in normal closed-end discount/premium dynamics.
- **+10% to +50%**: a real premium. Could be justified by access scarcity
  (RVI is one of the few retail vehicles for late-stage privates) but
  historically compresses.
- **+50% to +200%**: a speculative premium. The market price is no longer
  about the underlying — it's about flow. DXYZ-style. These compress fast,
  often >50% in days, when an event (IPO, share issuance, refreshed marks)
  forces re-pricing.
- **>+200%**: extreme. Treat with care regardless of conviction in holdings.

The **sensitivity table** tells you which holding's mark uncertainty matters
most. If Databricks is 23% of NAV and your DB valuation is ±25%, your
NAV/share is ±6% on that one holding alone.

---

## Limitations to be honest about

- **Ownership stakes are guessed**, not disclosed in real time. The fund
  reports a $ stake per holding in N-PORT; between filings you're
  extrapolating.
- **Public comps are imperfect** for AI-era privates. Databricks at AI infra
  multiples can look very different from Databricks at data warehouse
  multiples. The blend weights help, but don't substitute for judgment.
- **Secondary market prints are thin**. Single secondary trades can be
  unrepresentative; weight them lightly when volume is low.
- **The fund itself uses 409A-style valuations** which trail public market
  re-ratings. The "fund_marks" NAV is therefore systematically conservative
  in bull markets and systematically slow to mark down.

---

## Files

```
data/portfolio.yaml      ← edit this with current inputs
data/history.csv         ← auto-appended each run
valuation/model.py       ← Holding / Fund dataclasses + math
valuation/report.py      ← formatting and history logging
value_rvi.py             ← entry point
```
