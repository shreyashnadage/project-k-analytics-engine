"""CCC stretch detector — fires when cash conversion cycle is elongating."""

from __future__ import annotations

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import Alert, Evidence, MetricResult
from analytics_engine.detectors.base import detector_registry


@detector_registry.register
class CCCStretchDetector:
    code = "ccc_stretch"

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]:
        ccc = metrics.get("ccc.cash_conversion_cycle")
        if not ccc or not ccc.value_json:
            return []

        ccc_days = ccc.value_json.get("ccc")
        if ccc_days is None:
            return []

        params = config.parameters
        critical_days = params.get("critical_ccc_days", 90)
        warning_days = params.get("warning_ccc_days", 60)

        if ccc_days < warning_days:
            return []

        severity = "critical" if ccc_days >= critical_days else "warning"
        dso = ccc.value_json.get("dso", 0)
        dpo = ccc.value_json.get("dpo", 0)
        dio = ccc.value_json.get("dio", 0)

        # Identify the biggest contributor
        components = {"collecting from customers (DSO)": dso, "holding inventory (DIO)": dio}
        biggest = max(components, key=lambda k: components[k] or 0)

        return [Alert(
            detector_code=self.code,
            severity=severity,
            title=f"Your cash cycle is {ccc_days:.0f} days — money is tied up too long",
            description=(
                f"It takes {ccc_days:.0f} days from when you pay suppliers to when you collect "
                f"from customers. The biggest delay is in {biggest}. "
                f"A shorter cycle means more cash available for your business."
            ),
            evidence=[
                Evidence("metric", "ccc.cash_conversion_cycle", "CCC", f"{ccc_days:.0f} days"),
                Evidence("metric", "ccc.cash_conversion_cycle", "DSO",
                         f"{dso:.0f}" if dso else "N/A"),
                Evidence("metric", "ccc.cash_conversion_cycle", "DPO",
                         f"{dpo:.0f}" if dpo else "N/A"),
                Evidence("metric", "ccc.cash_conversion_cycle", "DIO",
                         f"{dio:.0f}" if dio else "N/A"),
            ],
            suggested_action=(
                "Focus on reducing DSO by following up on collections, and negotiate better payment "
                "terms with suppliers to increase DPO. If inventory days are high, review stock levels."
            ),
        )]
