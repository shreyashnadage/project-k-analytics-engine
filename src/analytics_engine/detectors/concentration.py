"""Concentration risk detector — fires when revenue depends too heavily on few customers."""

from __future__ import annotations

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.types import Alert, Evidence, MetricResult
from analytics_engine.detectors.base import detector_registry


@detector_registry.register
class ConcentrationRiskDetector:
    code = "concentration_risk"

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]:
        conc = metrics.get("receivables.concentration")
        if not conc or not conc.value_json:
            return []

        top_3_pct = conc.value_json.get("top_3_pct", 0)
        top_parties = conc.value_json.get("top_parties", [])

        params = config.parameters
        critical_pct = params.get("critical_top3_pct", 80)
        warning_pct = params.get("warning_top3_pct", 60)

        if top_3_pct < warning_pct:
            return []

        severity = "critical" if top_3_pct >= critical_pct else "warning"
        top_party = top_parties[0] if top_parties else {}

        return [Alert(
            detector_code=self.code,
            severity=severity,
            title=f"Top 3 customers account for {top_3_pct:.0f}% of your sales",
            description=(
                "Your business is heavily dependent on a few customers. "
                "If any of them delay payments or stop ordering, it could significantly "
                "impact your cash flow."
            ),
            evidence=[
                Evidence("metric", "receivables.concentration", "Top 3 customer share", f"{top_3_pct:.1f}%"),
                Evidence("metric", "receivables.concentration", "Largest customer",
                         f"{top_party.get('party', 'N/A')} ({top_party.get('percentage', 0):.1f}%)"),
            ],
            suggested_action=(
                "Try to diversify your customer base. Consider reaching out to new markets "
                "or offering trade credit to attract smaller but more numerous buyers."
            ),
        )]
