"""Eligibility rule implementations for loan products."""

from __future__ import annotations

from analytics_engine.core.types import EligibilityResult, MetricResult


def evaluate_rule(
    rule_def: dict,
    metrics: dict[str, MetricResult],
    alerts_raised: int,
) -> EligibilityResult:
    rule_code = rule_def["rule"]
    weight = rule_def.get("weight", 0.25)
    evaluator = _RULE_MAP.get(rule_code)
    if not evaluator:
        return EligibilityResult(
            rule_code=rule_code, rule_name=rule_code,
            passed=False, detail=f"Unknown rule: {rule_code}", weight=weight,
        )
    return evaluator(rule_def, metrics, alerts_raised, weight)


def _min_revenue_6m(rule_def, metrics, alerts_raised, weight) -> EligibilityResult:
    trend = metrics.get("revenue.monthly_trend")
    if not trend or not trend.value_json:
        return EligibilityResult("min_revenue_6m", "Minimum 6-month revenue", False, "Revenue data unavailable", weight)

    total = trend.value_json.get("total_paise", 0)
    threshold = rule_def.get("threshold_paise", 50_000_000)
    passed = total >= threshold
    detail = f"6-month revenue: {total} paise (threshold: {threshold})"
    return EligibilityResult("min_revenue_6m", "Minimum 6-month revenue", passed, detail, weight)


def _positive_nwc(rule_def, metrics, alerts_raised, weight) -> EligibilityResult:
    nwc = metrics.get("working_capital.net_working_capital")
    if not nwc or not nwc.value_json:
        return EligibilityResult("positive_nwc", "Positive net working capital", False, "NWC data unavailable", weight)

    nwc_paise = nwc.value_json.get("nwc_paise", 0)
    passed = nwc_paise > 0
    detail = f"Net working capital: {nwc_paise} paise"
    return EligibilityResult("positive_nwc", "Positive net working capital", passed, detail, weight)


def _dso_reasonable(rule_def, metrics, alerts_raised, weight) -> EligibilityResult:
    dso = metrics.get("receivables.dso")
    if not dso or dso.value_numeric is None:
        return EligibilityResult("dso_reasonable", "Reasonable collection period", False, "DSO unavailable", weight)

    max_days = rule_def.get("max_days", 90)
    passed = dso.value_numeric <= max_days
    detail = f"DSO: {dso.value_numeric:.0f} days (max: {max_days})"
    return EligibilityResult("dso_reasonable", "Reasonable collection period", passed, detail, weight)


def _no_critical_alerts(rule_def, metrics, alerts_raised, weight) -> EligibilityResult:
    passed = alerts_raised == 0
    detail = f"{alerts_raised} critical alerts raised" if not passed else "No critical alerts"
    return EligibilityResult("no_critical_alerts", "No critical alerts", passed, detail, weight)


def _min_receivables(rule_def, metrics, alerts_raised, weight) -> EligibilityResult:
    aging = metrics.get("receivables.aging_buckets")
    if not aging or not aging.value_json:
        return EligibilityResult(
            "min_receivables", "Minimum receivables", False, "Receivables data unavailable", weight,
        )

    total = aging.value_json.get("total", 0)
    threshold = rule_def.get("threshold_paise", 20_000_000)
    passed = total >= threshold
    detail = f"Total receivables: {total} paise (threshold: {threshold})"
    return EligibilityResult("min_receivables", "Minimum receivables", passed, detail, weight)


def _debtor_quality(rule_def, metrics, alerts_raised, weight) -> EligibilityResult:
    aging = metrics.get("receivables.aging_buckets")
    if not aging or not aging.value_json:
        return EligibilityResult("debtor_quality", "Debtor quality", False, "Aging data unavailable", weight)

    buckets = aging.value_json
    total = buckets.get("total", 0)
    if total == 0:
        return EligibilityResult("debtor_quality", "Debtor quality", False, "No receivables", weight)

    overdue = buckets.get("91-180", 0) + buckets.get("180+", 0)
    overdue_pct = overdue * 100.0 / total
    max_pct = rule_def.get("max_overdue_pct", 30)
    passed = overdue_pct <= max_pct
    detail = f"Overdue 90+ days: {overdue_pct:.1f}% (max: {max_pct}%)"
    return EligibilityResult("debtor_quality", "Debtor quality", passed, detail, weight)


_RULE_MAP = {
    "min_revenue_6m": _min_revenue_6m,
    "positive_nwc": _positive_nwc,
    "dso_reasonable": _dso_reasonable,
    "no_critical_alerts": _no_critical_alerts,
    "min_receivables": _min_receivables,
    "debtor_quality": _debtor_quality,
}
