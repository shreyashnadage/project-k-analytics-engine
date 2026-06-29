"""Aging deterioration detector — fires when overdue receivables are growing."""

from __future__ import annotations

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import Alert, Evidence, MetricResult
from analytics_engine.detectors.base import detector_registry


@detector_registry.register
class AgingDeteriorationDetector:
    code = "aging_deterioration"

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]:
        aging = metrics.get("receivables.aging_buckets")
        if not aging or not aging.value_json:
            return []

        buckets = aging.value_json
        total = buckets.get("total", 0)
        if total == 0:
            return []

        overdue_90_plus = buckets.get("91-180", 0) + buckets.get("180+", 0)
        overdue_pct = overdue_90_plus * 100.0 / total

        params = config.parameters
        critical_pct = params.get("critical_overdue_pct", 30)
        warning_pct = params.get("warning_overdue_pct", 15)

        if overdue_pct < warning_pct:
            return []

        severity = "critical" if overdue_pct >= critical_pct else "warning"

        return [Alert(
            detector_code=self.code,
            severity=severity,
            title=f"{overdue_pct:.0f}% of your receivables are overdue by 90+ days",
            description=(
                "A significant portion of money owed to you is severely overdue. "
                "This increases the risk of bad debts and strains your working capital."
            ),
            evidence=[
                Evidence("metric", "receivables.aging_buckets", "Overdue 90+ days (paise)", overdue_90_plus),
                Evidence("metric", "receivables.aging_buckets", "Total receivables (paise)", total),
                Evidence("metric", "receivables.aging_buckets", "Overdue percentage", f"{overdue_pct:.1f}%"),
            ],
            suggested_action=(
                "Follow up urgently with customers who owe you for 90+ days. "
                "Consider offering early payment discounts for future invoices to improve collection speed."
            ),
        )]
