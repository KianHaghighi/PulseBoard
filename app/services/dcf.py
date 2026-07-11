"""
Simplified DCF scenario engine.

Deliberately approximates unlevered FCF as NOPAT (EBIT * (1 - tax_rate)),
i.e. assumes capex roughly offsets D&A and working-capital changes are
negligible. This keeps the assumption set to the five inputs that move a
valuation the most (revenue growth, EBIT margin, tax rate, WACC, terminal
growth) instead of requiring a full capex/D&A/NWC build. Not a substitute
for the uploaded model's full DCF — it's a quick "what if" tool.

Mirrored in JS in app/templates/portfolio/analysis_view.html for the live
slider preview; keep both in sync if this changes.
"""


def run_dcf(
    base_revenue: float,
    revenue_growth: float,
    ebit_margin: float,
    tax_rate: float,
    wacc: float,
    terminal_growth: float,
    shares_outstanding: float | None = None,
    years: int = 5,
) -> dict | None:
    """Returns {"enterprise_value": ..., "implied_price": ... or None} in the
    same units as base_revenue (e.g. $M), or None for degenerate inputs."""
    if wacc <= terminal_growth:
        return None

    pv_sum = 0.0
    revenue = base_revenue
    fcff = 0.0
    for t in range(1, years + 1):
        revenue = revenue * (1 + revenue_growth)
        fcff = revenue * ebit_margin * (1 - tax_rate)
        pv_sum += fcff / (1 + wacc) ** t

    terminal_value = fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** years

    enterprise_value = pv_sum + pv_terminal
    implied_price = (
        enterprise_value / shares_outstanding
        if shares_outstanding and shares_outstanding > 0
        else None
    )

    return {"enterprise_value": enterprise_value, "implied_price": implied_price}


def derive_base_defaults(model: dict) -> dict:
    """Derive starting scenario assumptions from a parsed valuation model
    (app/services/portfolio_analyzer.parse_valuation_model)."""
    revenue = model.get("revenue") or []
    valid = [(i, v) for i, v in enumerate(revenue) if v is not None]

    if len(valid) >= 2:
        (i0, v0), (i1, v1) = valid[0], valid[-1]
        n_years = i1 - i0
        growth = (v1 / v0) ** (1 / n_years) - 1 if n_years > 0 and v0 > 0 else 0.05
    else:
        growth = 0.05

    base_revenue = valid[-1][1] if valid else None

    margins = [v for v in (model.get("ebit_margin") or []) if v is not None]
    ebit_margin = margins[-1] if margins else 0.15

    return {
        "base_revenue": base_revenue,
        "revenue_growth_rate": round(growth, 4),
        "ebit_margin": round(ebit_margin, 4),
        "tax_rate": 0.21,
        "wacc": model.get("wacc") or 0.10,
        "terminal_growth_rate": model.get("terminal_growth_rate") or 0.025,
    }
