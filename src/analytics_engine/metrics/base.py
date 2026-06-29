"""Metric framework — protocol, registry, and computation context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

import duckdb

from analytics_engine.core.registry import Registry
from analytics_engine.core.types import MetricResult


@dataclass
class MetricContext:
    period_start: date
    period_end: date

    @property
    def days_in_period(self) -> int:
        return (self.period_end - self.period_start).days or 1


@runtime_checkable
class MetricProtocol(Protocol):
    code: str
    version: int

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        ...


metric_registry: Registry[MetricProtocol] = Registry("metric")
