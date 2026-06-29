"""Per-pipeline-run state bag passed through all layers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from analytics_engine.core.config import VerticalProfile
from analytics_engine.core.types import MetricResult


@dataclass
class SyncStats:
    vouchers_pulled: int = 0
    ledgers_pulled: int = 0
    groups_pulled: int = 0
    stock_items_pulled: int = 0

    @property
    def total(self) -> int:
        return self.vouchers_pulled + self.ledgers_pulled + self.groups_pulled + self.stock_items_pulled


@dataclass
class PipelineContext:
    client_id: str
    tenant_ids: list[str]
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Resolved config
    vertical: str = "trading"
    profile: VerticalProfile | None = None

    # Per-layer results
    sync_stats: SyncStats = field(default_factory=SyncStats)
    metric_results: dict[str, MetricResult] = field(default_factory=dict)
    metric_history: dict[str, list[MetricResult]] = field(default_factory=dict)
    alerts_raised: int = 0
    insights_generated: int = 0
    metrics_computed: int = 0

    # Layer status tracking
    current_layer: int = 0
    error: str | None = None
