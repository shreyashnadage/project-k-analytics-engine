"""Tests for loan eligibility rules."""

from datetime import date

from analytics_engine.core.types import MetricResult
from analytics_engine.loan.rules import evaluate_rule


def _metric(code, value_numeric=None, value_json=None):
    return MetricResult(
        metric_code=code, period_start=date(2025, 1, 1), period_end=date(2025, 6, 30),
        value_numeric=value_numeric, value_json=value_json, unit="days", version=1,
    )


class TestMinRevenue:
    def test_passes_above_threshold(self):
        metrics = {"revenue.monthly_trend": _metric("revenue.monthly_trend", value_json={"total_paise": 100_000_000})}
        result = evaluate_rule({"rule": "min_revenue_6m", "threshold_paise": 50_000_000, "weight": 0.3}, metrics, 0)
        assert result.passed is True

    def test_fails_below_threshold(self):
        metrics = {"revenue.monthly_trend": _metric("revenue.monthly_trend", value_json={"total_paise": 30_000_000})}
        result = evaluate_rule({"rule": "min_revenue_6m", "threshold_paise": 50_000_000, "weight": 0.3}, metrics, 0)
        assert result.passed is False


class TestPositiveNWC:
    def test_passes_when_positive(self):
        m = _metric("working_capital.net_working_capital", value_json={"nwc_paise": 5_000_000})
        metrics = {"working_capital.net_working_capital": m}
        result = evaluate_rule({"rule": "positive_nwc", "weight": 0.2}, metrics, 0)
        assert result.passed is True

    def test_fails_when_negative(self):
        m = _metric("working_capital.net_working_capital", value_json={"nwc_paise": -1_000_000})
        metrics = {"working_capital.net_working_capital": m}
        result = evaluate_rule({"rule": "positive_nwc", "weight": 0.2}, metrics, 0)
        assert result.passed is False


class TestDSOReasonable:
    def test_passes_within_limit(self):
        metrics = {"receivables.dso": _metric("receivables.dso", value_numeric=45)}
        result = evaluate_rule({"rule": "dso_reasonable", "max_days": 90, "weight": 0.2}, metrics, 0)
        assert result.passed is True

    def test_fails_over_limit(self):
        metrics = {"receivables.dso": _metric("receivables.dso", value_numeric=120)}
        result = evaluate_rule({"rule": "dso_reasonable", "max_days": 90, "weight": 0.2}, metrics, 0)
        assert result.passed is False


class TestNoCriticalAlerts:
    def test_passes_with_no_alerts(self):
        result = evaluate_rule({"rule": "no_critical_alerts", "weight": 0.3}, {}, 0)
        assert result.passed is True

    def test_fails_with_alerts(self):
        result = evaluate_rule({"rule": "no_critical_alerts", "weight": 0.3}, {}, 3)
        assert result.passed is False


class TestDebtorQuality:
    def test_passes_low_overdue(self):
        metrics = {"receivables.aging_buckets": _metric("receivables.aging_buckets", value_json={
            "0-30": 700, "31-60": 200, "61-90": 50, "91-180": 30, "180+": 20, "total": 1000,
        })}
        result = evaluate_rule({"rule": "debtor_quality", "max_overdue_pct": 30, "weight": 0.3}, metrics, 0)
        assert result.passed is True

    def test_fails_high_overdue(self):
        metrics = {"receivables.aging_buckets": _metric("receivables.aging_buckets", value_json={
            "0-30": 200, "31-60": 100, "61-90": 100, "91-180": 300, "180+": 300, "total": 1000,
        })}
        result = evaluate_rule({"rule": "debtor_quality", "max_overdue_pct": 30, "weight": 0.3}, metrics, 0)
        assert result.passed is False
