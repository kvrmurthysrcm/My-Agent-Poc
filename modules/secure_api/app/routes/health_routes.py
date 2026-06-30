from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@router.get("/health/details")
async def health_details() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "UP",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
