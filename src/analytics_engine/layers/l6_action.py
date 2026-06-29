"""Layer 6: Action — run enabled detectors, persist alerts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from analytics_engine.core.config import ConfigLoader
from analytics_engine.db.models import AlertRecord
from analytics_engine.detectors import detector_registry
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class L6Action:
    def __init__(self, session: Session, config_loader: ConfigLoader):
        self._session = session
        self._config = config_loader

    def execute(self, ctx: PipelineContext) -> None:
        profile = ctx.profile
        if profile is None:
            return

        enabled_detectors = detector_registry.get_enabled(profile.detectors_enabled)
        logger.info(
            "L6 running %d detectors for client %s",
            len(enabled_detectors), ctx.client_id,
        )

        for detector in enabled_detectors:
            try:
                det_config = self._config.get_detector_config(detector.code)
                if det_config is None:
                    continue

                cooldown_days = det_config.parameters.get("cooldown_days", 7)
                if self._in_cooldown(ctx.client_id, detector.code, cooldown_days):
                    logger.debug("Detector %s in cooldown for client %s", detector.code, ctx.client_id)
                    continue

                alerts = detector.evaluate(
                    metrics=ctx.metric_results,
                    history=ctx.metric_history,
                    config=det_config,
                )

                for alert in alerts:
                    self._persist_alert(ctx, alert)
                    ctx.alerts_raised += 1

            except Exception:
                logger.exception("Detector %s failed for client %s", detector.code, ctx.client_id)

        self._session.commit()
        logger.info("L6 raised %d alerts for client %s", ctx.alerts_raised, ctx.client_id)

    def _in_cooldown(self, client_id: str, detector_code: str, cooldown_days: int) -> bool:
        if cooldown_days <= 0:
            return False

        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        existing = (
            self._session.query(AlertRecord)
            .filter_by(client_id=client_id, detector_code=detector_code)
            .filter(AlertRecord.created_at >= cutoff)
            .first()
        )
        return existing is not None

    def _persist_alert(self, ctx: PipelineContext, alert) -> None:
        evidence_data = [
            {"source_type": e.source_type, "source_id": e.source_id,
             "description": e.description, "value": e.value}
            for e in alert.evidence
        ]

        record = AlertRecord(
            client_id=ctx.client_id,
            detector_code=alert.detector_code,
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
            evidence_json=evidence_data,
            pipeline_run_id=ctx.run_id,
        )
        self._session.add(record)
