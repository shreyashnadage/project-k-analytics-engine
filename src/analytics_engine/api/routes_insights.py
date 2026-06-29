"""Insights API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from analytics_engine.api.deps import get_db, resolve_client_id
from analytics_engine.db.models import Insight

router = APIRouter(prefix="/v1/insights", tags=["insights"])


class InsightResponse(BaseModel):
    insight_id: str
    metric_code: str
    category: str
    severity: str
    title: str
    body: str
    data: dict[str, Any] | None
    is_read: bool
    created_at: datetime | None = None
    expires_at: datetime | None = None


class InsightListResponse(BaseModel):
    client_id: str
    insights: list[InsightResponse]
    total: int


@router.get("/{client_id}", response_model=InsightListResponse)
async def list_insights(
    client_id: str,
    category: str = Query(default=None),
    severity: str = Query(default=None),
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    query = db.query(Insight).filter_by(client_id=client_id)

    if category:
        query = query.filter_by(category=category)
    if severity:
        query = query.filter_by(severity=severity)

    insights = query.order_by(Insight.created_at.desc()).limit(50).all()

    return InsightListResponse(
        client_id=client_id,
        insights=[
            InsightResponse(
                insight_id=i.insight_id,
                metric_code=i.metric_code,
                category=i.category,
                severity=i.severity,
                title=i.title,
                body=i.body,
                data=i.data_json,
                is_read=i.is_read or False,
                created_at=i.created_at,
                expires_at=i.expires_at,
            )
            for i in insights
        ],
        total=len(insights),
    )


@router.patch("/{client_id}/{insight_id}/read")
async def mark_read(
    client_id: str,
    insight_id: str,
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    insight = db.query(Insight).filter_by(insight_id=insight_id, client_id=client_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_read = True
    insight.read_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}
