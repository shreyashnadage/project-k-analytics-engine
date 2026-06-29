"""Detector framework — protocol, registry, and evaluation context."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from analytics_engine.core.config import DetectorConfig
from analytics_engine.core.registry import Registry
from analytics_engine.core.types import Alert, MetricResult


@runtime_checkable
class DetectorProtocol(Protocol):
    code: str

    def evaluate(
        self,
        metrics: dict[str, MetricResult],
        history: dict[str, list[MetricResult]],
        config: DetectorConfig,
    ) -> list[Alert]: ...


detector_registry: Registry[DetectorProtocol] = Registry("detector")
