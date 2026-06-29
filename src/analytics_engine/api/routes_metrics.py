"""Metrics API routes."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analytics_engine.api.deps import get_db, resolve_client_id
from analytics_engine.api.schemas import MetricSummary, MetricValue
from analytics_engine.db.models import ClientProfile, MetricSnapshot

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])


@router.get("/{client_id}/summary", response_model=MetricSummary)
async def metric_summary(
    client_id: str,
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter_by(client_id=client_id).first()
    vertical = profile.vertical if profile else "trading"

    snapshots = (
        db.query(MetricSnapshot)
        .filter_by(client_id=client_id)
        .order_by(MetricSnapshot.period_end.desc())
        .limit(50)
        .all()
    )

    seen = set()
    metrics = []
    for s in snapshots:
        if s.metric_code in seen:
            continue
        seen.add(s.metric_code)
        metrics.append(MetricValue(
            metric_code=s.metric_code,
            period_start=s.period_start,
            period_end=s.period_end,
            value_numeric=s.value_numeric,
            value_json=s.value_json,
            unit=s.unit,
            version=s.version,
            computed_at=s.computed_at,
        ))

    return MetricSummary(
        client_id=client_id,
        vertical=vertical,
        metrics=metrics,
        computed_at=metrics[0].computed_at if metrics else None,
    )


@router.get("/{client_id}/{metric_code}", response_model=list[MetricValue])
async def metric_history(
    client_id: str,
    metric_code: str,
    from_date: date = Query(default=None),
    to_date: date = Query(default=None),
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    if from_date is None:
        from_date = date.today() - timedelta(days=365)
    if to_date is None:
        to_date = date.today()

    snapshots = (
        db.query(MetricSnapshot)
        .filter_by(client_id=client_id, metric_code=metric_code)
        .filter(MetricSnapshot.period_end >= from_date)
        .filter(MetricSnapshot.period_end <= to_date)
        .order_by(MetricSnapshot.period_end.desc())
        .all()
    )

    return [
        MetricValue(
            metric_code=s.metric_code,
            period_start=s.period_start,
            period_end=s.period_end,
            value_numeric=s.value_numeric,
            value_json=s.value_json,
            unit=s.unit,
            version=s.version,
            computed_at=s.computed_at,
        )
        for s in snapshots
    ]
