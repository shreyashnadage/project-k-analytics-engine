"""Metric library — import all modules to trigger @registry.register decorators."""

from analytics_engine.metrics import (
    cash_flow,  # noqa: F401
    ccc,  # noqa: F401
    inventory,  # noqa: F401
    payables,  # noqa: F401
    receivables,  # noqa: F401
    revenue,  # noqa: F401
    working_capital,  # noqa: F401
)
from analytics_engine.metrics.base import MetricContext, MetricProtocol, metric_registry

__all__ = ["metric_registry", "MetricContext", "MetricProtocol"]
