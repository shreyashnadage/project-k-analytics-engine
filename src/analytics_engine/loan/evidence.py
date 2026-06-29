"""Evidence chain builder — traces loan recommendations back to source data."""

from __future__ import annotations

from analytics_engine.core.amount import paise_to_lakhs
from analytics_engine.core.types import EligibilityResult, Evidence, MetricResult


def build_evidence_chain(
    product_code: str,
    amount_paise: int,
    metrics: dict[str, MetricResult],
    eligibility_results: list[EligibilityResult],
) -> list[Evidence]:
    chain = []

    chain.append(Evidence(
        source_type="computation",
        source_id=f"loan.{product_code}",
        description=f"Recommended amount: {paise_to_lakhs(amount_paise)}",
        value=amount_paise,
    ))

    for er in eligibility_results:
        chain.append(Evidence(
            source_type="eligibility",
            source_id=er.rule_code,
            description=f"{er.rule_name}: {'PASS' if er.passed else 'FAIL'} — {er.detail}",
            value=er.passed,
        ))

    # Link to key supporting metrics
    supporting = ["revenue.monthly_trend", "working_capital.net_working_capital",
                   "receivables.dso", "receivables.aging_buckets", "cash_flow.net_operating"]
    for code in supporting:
        m = metrics.get(code)
        if m and m.value_numeric is not None:
            chain.append(Evidence(
                source_type="metric",
                source_id=code,
                description=f"{code} = {m.value_numeric}",
                value=m.value_numeric,
            ))

    return chain
