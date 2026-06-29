"""Sales decline detector — fires when revenue is trending downward."""

from __future__ import annotations

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import Alert, Evidence, MetricResult
from analytics_engine.detectors.base import detector_registry


@detector_registry.register
class SalesDeclineDetector:
    code = "sales_decline"

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]:
        mom = metrics.get("revenue.mom_growth")
        if not mom or not mom.value_json:
            return []

        series = mom.value_json.get("growth_series", [])
        params = config.parameters
        lookback = params.get("lookback_months", 3)
        critical_decline_pct = params.get("critical_decline_pct", -20)
        warning_decline_pct = params.get("warning_decline_pct", -10)

        if len(series) < lookback:
            return []

        recent = series[-lookback:]
        valid_growths = [e["growth_pct"] for e in recent if e.get("growth_pct") is not None]
        if not valid_growths:
            return []

        avg_growth = sum(valid_growths) / len(valid_growths)
        consecutive_declines = sum(1 for g in valid_growths if g < 0)

        if avg_growth > warning_decline_pct:
            return []

        severity = "critical" if avg_growth <= critical_decline_pct else "warning"

        return [Alert(
            detector_code=self.code,
            severity=severity,
            title=f"Sales have declined {abs(avg_growth):.0f}% on average over the last {lookback} months",
            description=(
                f"Your revenue has been falling consistently. "
                f"{consecutive_declines} out of the last {lookback} months showed negative growth."
            ),
            evidence=[
                Evidence("metric", "revenue.mom_growth", "Average monthly growth", f"{avg_growth:.1f}%"),
                Evidence("metric", "revenue.mom_growth", "Consecutive declining months", consecutive_declines),
                Evidence("metric", "revenue.mom_growth", "Recent growth data",
                         [{"month": e["month"], "growth": e["growth_pct"]} for e in recent]),
            ],
            suggested_action=(
                "Analyze which products or customers are driving the decline. "
                "Consider promotional offers or expanding to new customer segments."
            ),
        )]
