"""Loan recommendation API routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from analytics_engine.api.deps import get_db, resolve_client_id
from analytics_engine.db.models import LoanRecommendation

router = APIRouter(prefix="/v1/loan", tags=["loan"])


class LoanRecoResponse(BaseModel):
    reco_id: str
    product_type: str
    recommended_amount_paise: int
    confidence: str
    rationale: str
    status: str
    valid_until: date
    created_at: datetime | None = None


class LoanRecoDetailResponse(LoanRecoResponse):
    evidence: list[dict[str, Any]]
    eligibility: list[dict[str, Any]]


@router.get("/{client_id}/recommendations", response_model=list[LoanRecoResponse])
async def list_recommendations(
    client_id: str,
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    recos = (
        db.query(LoanRecommendation)
        .filter_by(client_id=client_id, status="active")
        .order_by(LoanRecommendation.created_at.desc())
        .all()
    )

    return [
        LoanRecoResponse(
            reco_id=r.reco_id,
            product_type=r.product_type,
            recommended_amount_paise=r.recommended_amount_paise,
            confidence=r.confidence,
            rationale=r.rationale,
            status=r.status,
            valid_until=r.valid_until,
            created_at=r.created_at,
        )
        for r in recos
    ]


@router.get("/{client_id}/recommendations/{reco_id}/evidence", response_model=LoanRecoDetailResponse)
async def recommendation_evidence(
    client_id: str,
    reco_id: str,
    _caller: str = Depends(resolve_client_id),
    db: Session = Depends(get_db),
):
    reco = (
        db.query(LoanRecommendation)
        .filter_by(reco_id=reco_id, client_id=client_id)
        .first()
    )
    if not reco:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return LoanRecoDetailResponse(
        reco_id=reco.reco_id,
        product_type=reco.product_type,
        recommended_amount_paise=reco.recommended_amount_paise,
        confidence=reco.confidence,
        rationale=reco.rationale,
        status=reco.status,
        valid_until=reco.valid_until,
        created_at=reco.created_at,
        evidence=reco.evidence_json or [],
        eligibility=reco.eligibility_json or [],
    )
