"""Liquidity shortfall detector — fires when cash runway is dangerously low."""

from __future__ import annotations

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import Alert, Evidence, MetricResult
from analytics_engine.detectors.base import detector_registry


@detector_registry.register
class LiquidityShortfallDetector:
    code = "liquidity_shortfall"

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]:
        burn = metrics.get("cash_flow.burn_rate")
        if not burn or not burn.value_json:
            return []

        runway_days = burn.value_json.get("runway_days")
        if runway_days is None:
            return []

        params = config.parameters
        critical_days = params.get("critical_runway_days", 15)
        warning_days = params.get("warning_runway_days", 30)

        if runway_days > warning_days:
            return []

        severity = "critical" if runway_days <= critical_days else "warning"
        cash_on_hand = burn.value_json.get("cash_on_hand_paise", 0)
        monthly_burn = burn.value_json.get("monthly_burn_paise", 0)

        return [Alert(
            detector_code=self.code,
            severity=severity,
            title=f"Cash runway is only {int(runway_days)} days",
            description=(
                f"At your current spending rate, your cash reserves will last about "
                f"{int(runway_days)} days. You may need to arrange additional funds soon."
            ),
            evidence=[
                Evidence("metric", "cash_flow.burn_rate", "Cash on hand", cash_on_hand),
                Evidence("metric", "cash_flow.burn_rate", "Monthly outflow", monthly_burn),
                Evidence("metric", "cash_flow.burn_rate", "Runway days", runway_days),
            ],
            suggested_action=(
                "Review upcoming payments and consider delaying non-critical expenses. "
                "Explore short-term credit options like overdraft or cash credit."
            ),
        )]
