"""Admin routes — pipeline triggers, client profile management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from analytics_engine.api.deps import get_config_loader, get_db
from analytics_engine.api.schemas import (
    ClientProfileRequest,
    ClientProfileResponse,
    PipelineRunResponse,
    PipelineTriggerResponse,
)
from analytics_engine.db.engine import get_duck
from analytics_engine.db.models import ClientProfile, PipelineRun
from analytics_engine.db.session import create_session
from analytics_engine.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _run_pipeline(client_id: str):
    try:
        config = get_config_loader()
        orchestrator = PipelineOrchestrator(
            session_factory=create_session,
            duck_factory=get_duck,
            config_loader=config,
        )
        orchestrator.run_for_client(client_id)
    except Exception:
        logger.exception("Background pipeline failed for client %s", client_id)


@router.post("/pipeline/{client_id}/trigger", response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    client_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(_run_pipeline, client_id)
    return PipelineTriggerResponse(
        run_id="queued",
        status="queued",
        message=f"Pipeline triggered for client {client_id}",
    )


@router.get("/pipeline/{client_id}/runs", response_model=list[PipelineRunResponse])
async def pipeline_runs(
    client_id: str,
    db: Session = Depends(get_db),
):
    runs = (
        db.query(PipelineRun)
        .filter_by(client_id=client_id)
        .order_by(PipelineRun.started_at.desc())
        .limit(20)
        .all()
    )
    return [
        PipelineRunResponse(
            run_id=r.run_id,
            client_id=r.client_id,
            started_at=r.started_at,
            finished_at=r.finished_at,
            status=r.status,
            layer_reached=r.layer_reached,
            vouchers_pulled=r.vouchers_pulled,
            metrics_computed=r.metrics_computed,
            alerts_raised=r.alerts_raised,
            error_message=r.error_message,
        )
        for r in runs
    ]


@router.put("/clients/{client_id}/profile", response_model=ClientProfileResponse)
async def upsert_profile(
    client_id: str,
    body: ClientProfileRequest,
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter_by(client_id=client_id).first()
    if profile:
        profile.vertical = body.vertical
        profile.fiscal_year_start_month = body.fiscal_year_start_month
        profile.config_overrides = body.config_overrides
    else:
        profile = ClientProfile(
            client_id=client_id,
            vertical=body.vertical,
            fiscal_year_start_month=body.fiscal_year_start_month,
            config_overrides=body.config_overrides,
        )
        db.add(profile)

    db.commit()
    return ClientProfileResponse(
        client_id=profile.client_id,
        vertical=profile.vertical,
        fiscal_year_start_month=profile.fiscal_year_start_month,
        config_overrides=profile.config_overrides,
    )
