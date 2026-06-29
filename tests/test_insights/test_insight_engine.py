"""Tests for the insight engine — template loading and generation."""

from datetime import date

from analytics_engine.core.types import MetricResult
from analytics_engine.insights.engine import InsightEngine


def _metric(code, value_numeric=None, value_json=None):
    return MetricResult(
        metric_code=code, period_start=date(2025, 1, 1), period_end=date(2025, 6, 30),
        value_numeric=value_numeric, value_json=value_json, unit="days", version=1,
    )


class TestInsightEngine:
    def test_loads_templates(self):
        engine = InsightEngine()
        assert len(engine._templates) > 0

    def test_generates_dso_critical(self):
        engine = InsightEngine()
        metrics = {
            "receivables.dso": _metric("receivables.dso", value_numeric=100),
        }
        insights = engine.generate(metrics)
        dso_insights = [i for i in insights if i.metric_code == "receivables.dso"]
        assert len(dso_insights) == 1
        assert dso_insights[0].severity == "critical"
        assert "100" in dso_insights[0].body

    def test_generates_dso_info_when_healthy(self):
        engine = InsightEngine()
        metrics = {
            "receivables.dso": _metric("receivables.dso", value_numeric=25),
        }
        insights = engine.generate(metrics)
        dso_insights = [i for i in insights if i.metric_code == "receivables.dso"]
        assert len(dso_insights) == 1
        assert dso_insights[0].severity == "info"

    def test_negative_cash_flow_critical(self):
        engine = InsightEngine()
        metrics = {
            "cash_flow.net_operating": _metric("cash_flow.net_operating", value_numeric=-500000),
        }
        insights = engine.generate(metrics)
        cf_insights = [i for i in insights if i.metric_code == "cash_flow.net_operating"]
        assert len(cf_insights) == 1
        assert cf_insights[0].severity == "critical"

    def test_burn_rate_warning(self):
        engine = InsightEngine()
        metrics = {
            "cash_flow.burn_rate": _metric("cash_flow.burn_rate", value_numeric=45,
                                           value_json={"runway_days": 45, "cash_on_hand_paise": 9000000,
                                                       "monthly_burn_paise": 6000000}),
        }
        insights = engine.generate(metrics)
        burn_insights = [i for i in insights if i.metric_code == "cash_flow.burn_rate"]
        assert len(burn_insights) == 1
        assert burn_insights[0].severity == "warning"

    def test_no_insight_for_missing_metric(self):
        engine = InsightEngine()
        insights = engine.generate({})
        assert len(insights) == 0

    def test_concentration_critical(self):
        engine = InsightEngine()
        metrics = {
            "receivables.concentration": _metric(
                "receivables.concentration", value_numeric=75,
                value_json={"top_3_pct": 75, "top_parties": [], "total_paise": 1000000},
            ),
        }
        insights = engine.generate(metrics)
        conc = [i for i in insights if i.metric_code == "receivables.concentration"]
        assert len(conc) == 1
        assert conc[0].severity == "critical"
