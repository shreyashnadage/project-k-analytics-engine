"""Layer 5: Insight — generate plain-language insights from metric results."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from analytics_engine.db.models import Insight
from analytics_engine.insights.engine import InsightEngine
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class L5Insight:
    def __init__(self, session: Session, insight_engine: InsightEngine | None = None):
        self._session = session
        self._engine = insight_engine or InsightEngine()

    def execute(self, ctx: PipelineContext) -> None:
        if not ctx.metric_results:
            return

        outputs = self._engine.generate(ctx.metric_results)
        logger.info("L5 generated %d insights for client %s", len(outputs), ctx.client_id)

        period_end = date.today()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        for out in outputs:
            # Avoid duplicate insights for same metric/period
            existing = (
                self._session.query(Insight)
                .filter_by(client_id=ctx.client_id, metric_code=out.metric_code, period_end=period_end)
                .first()
            )
            if existing:
                existing.severity = out.severity
                existing.title = out.title
                existing.body = out.body
                existing.data_json = out.data
                existing.expires_at = expires_at
                existing.is_read = False
            else:
                insight = Insight(
                    client_id=ctx.client_id,
                    metric_code=out.metric_code,
                    category=out.category,
                    severity=out.severity,
                    title=out.title,
                    body=out.body,
                    data_json=out.data,
                    period_end=period_end,
                    expires_at=expires_at,
                )
                self._session.add(insight)

            ctx.insights_generated += 1

        self._session.commit()
