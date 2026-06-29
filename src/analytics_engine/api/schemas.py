"""Pydantic response schemas for the analytics API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class MetricValue(BaseModel):
    metric_code: str
    period_start: date
    period_end: date
    value_numeric: float | None
    value_json: dict[str, Any] | None
    unit: str
    version: int
    computed_at: datetime | None = None


class MetricSummary(BaseModel):
    client_id: str
    vertical: str
    metrics: list[MetricValue]
    computed_at: datetime | None = None


class AlertResponse(BaseModel):
    alert_id: str
    detector_code: str
    severity: str
    title: str
    description: str
    evidence: list[dict[str, Any]]
    status: str
    created_at: datetime | None = None
    snoozed_until: datetime | None = None


class AlertListResponse(BaseModel):
    client_id: str
    alerts: list[AlertResponse]
    total: int


class AlertUpdateRequest(BaseModel):
    status: str  # acknowledged, resolved, snoozed
    snoozed_until: datetime | None = None


class PipelineRunResponse(BaseModel):
    run_id: str
    client_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    layer_reached: int | None
    vouchers_pulled: int | None
    metrics_computed: int | None
    alerts_raised: int | None
    error_message: str | None


class PipelineTriggerResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ClientProfileRequest(BaseModel):
    vertical: str
    fiscal_year_start_month: int = 4
    config_overrides: dict[str, Any] | None = None


class ClientProfileResponse(BaseModel):
    client_id: str
    vertical: str
    fiscal_year_start_month: int
    config_overrides: dict[str, Any] | None
