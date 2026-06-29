"""Shared domain types used across the analytics engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end


@dataclass(frozen=True)
class AgingBucketConfig:
    boundaries_days: list[int]
    labels: list[str]


@dataclass
class MetricResult:
    metric_code: str
    period_start: date
    period_end: date
    value_numeric: float | None
    value_json: dict[str, Any] | None
    unit: str  # 'days', 'ratio', 'inr_paise', 'percent'
    version: int = 1


@dataclass
class Evidence:
    source_type: str  # 'voucher', 'ledger', 'metric'
    source_id: str
    description: str
    value: Any = None


@dataclass
class Alert:
    detector_code: str
    severity: str  # 'warning', 'critical'
    title: str
    description: str
    evidence: list[Evidence] = field(default_factory=list)
    suggested_action: str | None = None


@dataclass
class LoanRequirement:
    product_type: str
    recommended_amount_paise: int
    confidence: str  # 'high', 'medium', 'low'
    rationale: str
    evidence_chain: list[Evidence] = field(default_factory=list)
    eligibility_results: list[EligibilityResult] = field(default_factory=list)
    valid_until: date | None = None


@dataclass
class EligibilityResult:
    rule_code: str
    rule_name: str
    passed: bool
    detail: str
    weight: float = 0.0


@dataclass
class ClientContext:
    client_id: str
    tenant_ids: list[str]
    vertical: str = "trading"
    fiscal_year_start_month: int = 4
    config_overrides: dict[str, Any] | None = None
