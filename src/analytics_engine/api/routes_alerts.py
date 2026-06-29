"""Alerts API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analytics_engine.api.deps import get_db, resolve_client_id
from analytics_engine.api.schemas import AlertListResponse, AlertResponse, AlertUpdateRequest
from analytics_engine.db.models import AlertRecord

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.get("/{client_id}", response_model=AlertListResponse)
async def list_alerts(
    client_id: str,
    status: str = Query(default="open"),
    detector: str = Query(default=None),
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    query = db.query(AlertRecord).filter_by(client_id=client_id)

    if status != "all":
        query = query.filter_by(status=status)
    if detector:
        query = query.filter_by(detector_code=detector)

    alerts = query.order_by(AlertRecord.created_at.desc()).limit(100).all()

    return AlertListResponse(
        client_id=client_id,
        alerts=[
            AlertResponse(
                alert_id=a.alert_id,
                detector_code=a.detector_code,
                severity=a.severity,
                title=a.title,
                description=a.description,
                evidence=a.evidence_json or [],
                status=a.status,
                created_at=a.created_at,
                snoozed_until=a.snoozed_until,
            )
            for a in alerts
        ],
        total=len(alerts),
    )


@router.patch("/{client_id}/{alert_id}", response_model=AlertResponse)
async def update_alert(
    client_id: str,
    alert_id: str,
    body: AlertUpdateRequest,
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    alert = (
        db.query(AlertRecord)
        .filter_by(alert_id=alert_id, client_id=client_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if body.status not in ("acknowledged", "resolved", "snoozed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    alert.status = body.status
    if body.status == "resolved":
        alert.resolved_at = datetime.now(timezone.utc)
    if body.status == "snoozed" and body.snoozed_until:
        alert.snoozed_until = body.snoozed_until

    db.commit()

    return AlertResponse(
        alert_id=alert.alert_id,
        detector_code=alert.detector_code,
        severity=alert.severity,
        title=alert.title,
        description=alert.description,
        evidence=alert.evidence_json or [],
        status=alert.status,
        created_at=alert.created_at,
        snoozed_until=alert.snoozed_until,
    )
