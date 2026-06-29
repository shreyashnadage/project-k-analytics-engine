"""FastAPI dependencies — session, config, auth."""

from __future__ import annotations

from functools import lru_cache
from typing import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from analytics_engine.core.config import ConfigLoader
from analytics_engine.db.public_models import DeviceRegistration
from analytics_engine.db.session import create_session


def get_db() -> Generator[Session, None, None]:
    session = create_session()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def get_config_loader() -> ConfigLoader:
    return ConfigLoader()


async def resolve_client_id(
    x_api_key: str = Header(...),
    db: Session = Depends(get_db),
) -> str:
    device = (
        db.query(DeviceRegistration)
        .filter_by(api_key=x_api_key, status="active")
        .first()
    )
    if not device:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return device.client_id
