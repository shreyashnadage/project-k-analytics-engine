"""Top-level pipeline runner — executes 6 layers for a single client."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

import duckdb
from sqlalchemy.orm import Session

from analytics_engine.core.config import ConfigLoader
from analytics_engine.db.models import ClientProfile, PipelineRun
from analytics_engine.db.public_models import SyncRecord
from analytics_engine.layers.l1_sync import L1Sync
from analytics_engine.layers.l2_normalize import L2Normalize
from analytics_engine.layers.l3_staging import L3Staging
from analytics_engine.layers.l4_analytics import L4Analytics
from analytics_engine.layers.l5_insight import L5Insight
from analytics_engine.layers.l6_action import L6Action
from analytics_engine.loan.engine import LoanEngine
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        duck_factory: Callable[[], duckdb.DuckDBPyConnection],
        config_loader: ConfigLoader,
    ):
        self._session_factory = session_factory
        self._duck_factory = duck_factory
        self._config = config_loader

    def run_for_client(self, client_id: str) -> PipelineContext:
        session = self._session_factory()
        try:
            ctx = self._build_context(session, client_id)
            self._record_run_start(session, ctx)

            # Layer 1: Sync
            ctx.current_layer = 1
            self._update_layer_progress(session, ctx)
            l1 = L1Sync(session)
            l1.execute(ctx)
            if ctx.sync_stats.total == 0:
                self._record_run_end(session, ctx, "skipped")
                logger.info("Pipeline %s: no new data for client %s", ctx.run_id, client_id)
                return ctx

            # Layer 2: Normalize
            ctx.current_layer = 2
            self._update_layer_progress(session, ctx)
            l2 = L2Normalize(session, self._config)
            l2.execute(ctx)

            # Layer 3: Stage into DuckDB
            ctx.current_layer = 3
            self._update_layer_progress(session, ctx)
            duck = self._duck_factory()
            l3 = L3Staging(session)
            l3.execute(ctx, duck)

            # Layer 4: Compute metrics
            ctx.current_layer = 4
            self._update_layer_progress(session, ctx)
            l4 = L4Analytics(session, self._config)
            l4.execute(ctx, duck)

            duck.close()

            # Layer 5: Generate insights
            ctx.current_layer = 5
            self._update_layer_progress(session, ctx)
            l5 = L5Insight(session)
            l5.execute(ctx)

            # Layer 6: Run detectors, raise alerts
            ctx.current_layer = 6
            self._update_layer_progress(session, ctx)
            l6 = L6Action(session, self._config)
            l6.execute(ctx)

            # Loan recommendations
            ctx.current_layer = 7
            self._update_layer_progress(session, ctx)
            loan_engine = LoanEngine(session, self._config)
            loan_engine.evaluate(ctx)

            self._record_run_end(session, ctx, "success")
            logger.info(
                "Pipeline %s: completed for client %s — %d records synced, %d metrics computed",
                ctx.run_id, client_id, ctx.sync_stats.total, ctx.metrics_computed,
            )
            return ctx

        except Exception as e:
            ctx.error = str(e)
            logger.exception("Pipeline %s failed at layer %d", ctx.run_id, ctx.current_layer)
            self._record_run_end(session, ctx, "failed")
            raise
        finally:
            session.close()

    def _build_context(self, session: Session, client_id: str) -> PipelineContext:
        # Resolve tenant_ids from sync_records
        tenant_rows = (
            session.query(SyncRecord.tenant_id)
            .filter(SyncRecord.client_id == client_id)
            .filter(SyncRecord.tenant_id.isnot(None))
            .distinct()
            .all()
        )
        tenant_ids = [r[0] for r in tenant_rows]

        # If no sync_records yet, tenant_id == client_id (backend convention)
        if not tenant_ids:
            tenant_ids = [client_id]

        # Load client profile
        profile_row = session.query(ClientProfile).filter_by(client_id=client_id).first()
        vertical = profile_row.vertical if profile_row else "trading"
        overrides = profile_row.config_overrides if profile_row else None

        profile = self._config.resolve_client_config(vertical, overrides)

        return PipelineContext(
            client_id=client_id,
            tenant_ids=tenant_ids,
            vertical=vertical,
            profile=profile,
        )

    def _update_layer_progress(self, session: Session, ctx: PipelineContext) -> None:
        run = session.query(PipelineRun).filter_by(run_id=ctx.run_id).first()
        if run:
            run.layer_reached = ctx.current_layer
            run.vouchers_pulled = ctx.sync_stats.vouchers_pulled
            run.metrics_computed = ctx.metrics_computed
            run.alerts_raised = ctx.alerts_raised
            session.commit()

    def _record_run_start(self, session: Session, ctx: PipelineContext) -> None:
        run = PipelineRun(
            run_id=ctx.run_id,
            client_id=ctx.client_id,
            started_at=ctx.started_at,
            status="running",
        )
        session.add(run)
        session.commit()

    def _record_run_end(self, session: Session, ctx: PipelineContext, status: str) -> None:
        run = session.query(PipelineRun).filter_by(run_id=ctx.run_id).first()
        if run:
            run.status = status
            run.finished_at = datetime.now(timezone.utc)
            run.layer_reached = ctx.current_layer
            run.vouchers_pulled = ctx.sync_stats.vouchers_pulled
            run.metrics_computed = ctx.metrics_computed
            run.alerts_raised = ctx.alerts_raised
            run.error_message = ctx.error
            session.commit()
