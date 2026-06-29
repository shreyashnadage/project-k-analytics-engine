"""Payable cliff detector — fires when large payments are bunched together."""

from __future__ import annotations

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import Alert, Evidence, MetricResult
from analytics_engine.detectors.base import detector_registry


@detector_registry.register
class PayableCliffDetector:
    code = "payable_cliff"

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]:
        aging = metrics.get("payables.aging_buckets")
        burn = metrics.get("cash_flow.burn_rate")
        if not aging or not aging.value_json:
            return []

        buckets = aging.value_json
        # Short-term payables due within 30 days
        due_soon = buckets.get("0-30", 0)

        cash_on_hand = 0
        if burn and burn.value_json:
            cash_on_hand = burn.value_json.get("cash_on_hand_paise", 0)

        if cash_on_hand == 0 or due_soon == 0:
            return []

        coverage_ratio = cash_on_hand / due_soon
        params = config.parameters
        critical_ratio = params.get("critical_coverage_ratio", 0.5)
        warning_ratio = params.get("warning_coverage_ratio", 1.0)

        if coverage_ratio > warning_ratio:
            return []

        severity = "critical" if coverage_ratio <= critical_ratio else "warning"

        return [Alert(
            detector_code=self.code,
            severity=severity,
            title=f"Upcoming payments exceed your available cash by {(1/coverage_ratio - 1)*100:.0f}%",
            description=(
                "Payments due in the next 30 days are larger than your current cash reserves. "
                "You may face difficulty paying suppliers on time."
            ),
            evidence=[
                Evidence("metric", "payables.aging_buckets", "Payables due within 30 days (paise)", due_soon),
                Evidence("metric", "cash_flow.burn_rate", "Cash on hand (paise)", cash_on_hand),
                Evidence("computed", "payable_cliff", "Coverage ratio", f"{coverage_ratio:.2f}x"),
            ],
            suggested_action=(
                "Negotiate extended payment terms with your suppliers. "
                "Accelerate collections from your debtors or consider a short-term credit facility."
            ),
        )]
