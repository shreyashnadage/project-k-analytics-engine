"""Formatters for insight template rendering — amounts, dates, percentages."""

from __future__ import annotations

from analytics_engine.core.amount import paise_to_lakhs


def format_amount(paise: int | float | None) -> str:
    if paise is None:
        return "N/A"
    return paise_to_lakhs(int(paise))


def build_template_context(metric_code: str, value_numeric: float | None, value_json: dict | None) -> dict:
    """Build a context dict for template string formatting."""
    ctx = {}

    if value_numeric is not None:
        ctx["value"] = value_numeric

    if value_json:
        ctx.update(value_json)

    # Add formatted versions of common paise fields
    for key in ("cash_on_hand_paise", "monthly_burn_paise", "net_cf_paise",
                "nwc_paise", "total_paise", "current_assets_paise", "current_liabilities_paise"):
        if key in ctx:
            display_key = key.replace("_paise", "_formatted")
            ctx[display_key] = format_amount(ctx[key])

    # Special formatted_value for the primary numeric
    if value_numeric is not None:
        unit = _infer_unit(metric_code)
        if unit == "inr_paise":
            ctx["formatted_value"] = format_amount(value_numeric)
        elif unit == "days":
            ctx["formatted_value"] = f"{value_numeric:.0f} days"
        elif unit == "percent":
            ctx["formatted_value"] = f"{value_numeric:.1f}%"
        elif unit == "ratio":
            ctx["formatted_value"] = f"{value_numeric:.2f}"
        else:
            ctx["formatted_value"] = f"{value_numeric:.2f}"

    return ctx


def _infer_unit(metric_code: str) -> str:
    day_keywords = ("dso", "dpo", "dio", "burn_rate", "ccc")
    if any(k in metric_code for k in day_keywords):
        return "days"
    if "ratio" in metric_code or "current_ratio" in metric_code or "turnover" in metric_code:
        return "ratio"
    if "concentration" in metric_code or "growth" in metric_code:
        return "percent"
    if "cash_flow" in metric_code or "working_capital" in metric_code or "revenue" in metric_code:
        return "inr_paise"
    return "unknown"
