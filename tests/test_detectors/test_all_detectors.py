"""Tests for all detector evaluations."""

from __future__ import annotations

from datetime import date

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import MetricResult
from analytics_engine.detectors import detector_registry


def _make_metric(code, value_numeric=None, value_json=None, unit="days"):
    return MetricResult(
        metric_code=code,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 6, 30),
        value_numeric=value_numeric,
        value_json=value_json,
        unit=unit,
        version=1,
    )


def _make_config(params: dict) -> DetectorConfig:
    return DetectorConfig(
        code="test",
        name="Test Detector",
        description="Test",
        parameters=params,
        severity_rules={},
    )


class TestDetectorRegistry:
    def test_all_detectors_registered(self):
        codes = detector_registry.all_codes()
        assert "liquidity_shortfall" in codes
        assert "concentration_risk" in codes
        assert "aging_deterioration" in codes
        assert "payable_cliff" in codes
        assert "sales_decline" in codes
        assert "ccc_stretch" in codes


class TestLiquidityShortfall:
    def test_critical_when_runway_low(self):
        detector = detector_registry.get("liquidity_shortfall")
        metrics = {
            "cash_flow.burn_rate": _make_metric("cash_flow.burn_rate", value_json={
                "runway_days": 10, "cash_on_hand_paise": 100000, "monthly_burn_paise": 300000,
            }),
        }
        config = _make_config({"critical_runway_days": 15, "warning_runway_days": 30})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_warning_when_runway_moderate(self):
        detector = detector_registry.get("liquidity_shortfall")
        metrics = {
            "cash_flow.burn_rate": _make_metric("cash_flow.burn_rate", value_json={
                "runway_days": 25, "cash_on_hand_paise": 500000, "monthly_burn_paise": 200000,
            }),
        }
        config = _make_config({"critical_runway_days": 15, "warning_runway_days": 30})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    def test_no_alert_when_runway_healthy(self):
        detector = detector_registry.get("liquidity_shortfall")
        metrics = {
            "cash_flow.burn_rate": _make_metric("cash_flow.burn_rate", value_json={
                "runway_days": 60, "cash_on_hand_paise": 1000000, "monthly_burn_paise": 200000,
            }),
        }
        config = _make_config({"critical_runway_days": 15, "warning_runway_days": 30})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 0


class TestConcentrationRisk:
    def test_critical_when_concentrated(self):
        detector = detector_registry.get("concentration_risk")
        metrics = {
            "receivables.concentration": _make_metric("receivables.concentration", value_json={
                "top_3_pct": 85,
                "top_parties": [
                    {"party": "Big Corp", "percentage": 60, "total_paise": 6000000, "voucher_count": 10},
                    {"party": "Mid Corp", "percentage": 15, "total_paise": 1500000, "voucher_count": 5},
                    {"party": "Small Corp", "percentage": 10, "total_paise": 1000000, "voucher_count": 3},
                ],
            }),
        }
        config = _make_config({"critical_top3_pct": 80, "warning_top3_pct": 60})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_no_alert_when_diversified(self):
        detector = detector_registry.get("concentration_risk")
        metrics = {
            "receivables.concentration": _make_metric("receivables.concentration", value_json={
                "top_3_pct": 40,
                "top_parties": [{"party": "A", "percentage": 15, "total_paise": 1500000, "voucher_count": 3}],
            }),
        }
        config = _make_config({"critical_top3_pct": 80, "warning_top3_pct": 60})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 0


class TestAgingDeterioration:
    def test_critical_overdue(self):
        detector = detector_registry.get("aging_deterioration")
        metrics = {
            "receivables.aging_buckets": _make_metric("receivables.aging_buckets", value_json={
                "0-30": 100, "31-60": 50, "61-90": 30, "91-180": 200, "180+": 150, "total": 530,
            }),
        }
        config = _make_config({"critical_overdue_pct": 30, "warning_overdue_pct": 15})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        # (200 + 150) / 530 = 66% > 30%
        assert alerts[0].severity == "critical"


class TestPayableCliff:
    def test_critical_when_cash_short(self):
        detector = detector_registry.get("payable_cliff")
        metrics = {
            "payables.aging_buckets": _make_metric("payables.aging_buckets", value_json={
                "0-30": 1000000, "31-60": 500000, "61-90": 0, "91-180": 0, "180+": 0, "total": 1500000,
            }),
            "cash_flow.burn_rate": _make_metric("cash_flow.burn_rate", value_json={
                "cash_on_hand_paise": 400000, "monthly_burn_paise": 500000, "runway_days": 24,
            }),
        }
        config = _make_config({"critical_coverage_ratio": 0.5, "warning_coverage_ratio": 1.0})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"


class TestSalesDecline:
    def test_warning_on_decline(self):
        detector = detector_registry.get("sales_decline")
        metrics = {
            "revenue.mom_growth": _make_metric("revenue.mom_growth", value_json={
                "growth_series": [
                    {"month": "2025-04", "growth_pct": -12},
                    {"month": "2025-05", "growth_pct": -8},
                    {"month": "2025-06", "growth_pct": -15},
                ],
            }),
        }
        config = _make_config({"lookback_months": 3, "critical_decline_pct": -20, "warning_decline_pct": -10})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    def test_no_alert_when_growing(self):
        detector = detector_registry.get("sales_decline")
        metrics = {
            "revenue.mom_growth": _make_metric("revenue.mom_growth", value_json={
                "growth_series": [
                    {"month": "2025-04", "growth_pct": 5},
                    {"month": "2025-05", "growth_pct": 10},
                    {"month": "2025-06", "growth_pct": 8},
                ],
            }),
        }
        config = _make_config({"lookback_months": 3, "critical_decline_pct": -20, "warning_decline_pct": -10})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 0


class TestCCCStretch:
    def test_critical_when_ccc_high(self):
        detector = detector_registry.get("ccc_stretch")
        metrics = {
            "ccc.cash_conversion_cycle": _make_metric("ccc.cash_conversion_cycle", value_json={
                "ccc": 100, "dso": 60, "dpo": 20, "dio": 60,
            }),
        }
        config = _make_config({"critical_ccc_days": 90, "warning_ccc_days": 60})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_no_alert_when_ccc_normal(self):
        detector = detector_registry.get("ccc_stretch")
        metrics = {
            "ccc.cash_conversion_cycle": _make_metric("ccc.cash_conversion_cycle", value_json={
                "ccc": 45, "dso": 30, "dpo": 15, "dio": 30,
            }),
        }
        config = _make_config({"critical_ccc_days": 90, "warning_ccc_days": 60})
        alerts = detector.evaluate(metrics, {}, config)
        assert len(alerts) == 0
