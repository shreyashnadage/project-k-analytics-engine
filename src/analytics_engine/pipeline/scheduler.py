"""Batch scheduler — runs pipelines on config-driven intervals per client plan tier."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from analytics_engine.core.config import ConfigLoader
from analytics_engine.db.engine import get_duck
from analytics_engine.db.models import ClientProfile
from analytics_engine.db.session import create_session
from analytics_engine.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class PipelineScheduler:
    def __init__(self, config_loader: ConfigLoader):
        self._config = config_loader
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        scheduling = self._config.get_scheduling_config()
        plan_intervals = scheduling.get("plan_intervals", {})
        default_minutes = plan_intervals.get("basic", {}).get("interval_minutes", 120)

        # Schedule a master job that discovers clients and runs their pipelines
        self._scheduler.add_job(
            self._run_all_clients,
            "interval",
            minutes=default_minutes,
            id="master_pipeline",
            name="Master Pipeline Runner",
            max_instances=1,
        )
        self._scheduler.start()
        logger.info("Scheduler started with %d-minute interval", default_minutes)

    def stop(self) -> None:
        self._scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    def _run_all_clients(self) -> None:
        session = create_session()
        try:
            profiles = session.query(ClientProfile).all()
            client_ids = [p.client_id for p in profiles]
        finally:
            session.close()

        if not client_ids:
            logger.info("No client profiles configured, skipping batch run")
            return

        orchestrator = PipelineOrchestrator(
            session_factory=create_session,
            duck_factory=get_duck,
            config_loader=self._config,
        )

        for client_id in client_ids:
            try:
                orchestrator.run_for_client(client_id)
            except Exception:
                logger.exception("Pipeline failed for client %s", client_id)
