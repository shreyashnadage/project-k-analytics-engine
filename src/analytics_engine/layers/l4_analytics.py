"""Layer 4: Analytics — compute enabled metrics against DuckDB staging marts."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import duckdb
from sqlalchemy.orm import Session

from analytics_engine.core.config import ConfigLoader
from analytics_engine.core.types import MetricResult
from analytics_engine.db.models import MetricSnapshot
from analytics_engine.metrics import MetricContext, metric_registry
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class L4Analytics:
    def __init__(self, session: Session, config_loader: ConfigLoader):
        self._session = session
        self._config = config_loader

    def execute(self, ctx: PipelineContext, duck: duckdb.DuckDBPyConnection) -> None:
        profile = ctx.profile
        if profile is None:
            logger.warning("No profile for client %s, skipping analytics", ctx.client_id)
            return

        # Default period: last 6 months ending today
        period_end = date.today()
        period_start = period_end - timedelta(days=180)

        metric_ctx = MetricContext(period_start=period_start, period_end=period_end)

        enabled_metrics = metric_registry.get_enabled(profile.metrics_enabled)
        logger.info(
            "L4 computing %d metrics for client %s (%s)",
            len(enabled_metrics), ctx.client_id, profile.name,
        )

        for metric in enabled_metrics:
            try:
                results = metric.compute(duck, metric_ctx)
                for result in results:
                    self._persist_metric(ctx, result)
                    ctx.metric_results[result.metric_code] = result
                ctx.metrics_computed += len(results)
            except Exception:
                logger.exception("Failed to compute metric %s for client %s", metric.code, ctx.client_id)

        self._session.commit()
        logger.info("L4 persisted %d metric snapshots for client %s", ctx.metrics_computed, ctx.client_id)

    def _persist_metric(self, ctx: PipelineContext, result: MetricResult) -> None:
        # Check for existing snapshot with same dedup key
        existing = (
            self._session.query(MetricSnapshot)
            .filter_by(
                client_id=ctx.client_id,
                metric_code=result.metric_code,
                period_end=result.period_end,
                version=result.version,
            )
            .first()
        )

        if existing:
            existing.value_numeric = result.value_numeric
            existing.value_json = result.value_json
            existing.unit = result.unit
            existing.computed_at = datetime.now(timezone.utc)
            existing.pipeline_run_id = ctx.run_id
            existing.period_start = result.period_start
        else:
            snapshot = MetricSnapshot(
                client_id=ctx.client_id,
                metric_code=result.metric_code,
                period_start=result.period_start,
                period_end=result.period_end,
                value_numeric=result.value_numeric,
                value_json=result.value_json,
                unit=result.unit,
                pipeline_run_id=ctx.run_id,
                version=result.version,
            )
            self._session.add(snapshot)
