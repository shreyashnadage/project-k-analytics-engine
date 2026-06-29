"""Health check endpoint."""

from fastapi import APIRouter

from analytics_engine import __version__
from analytics_engine.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version=__version__)
