"""
GET /health — liveness / readiness probe.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.db.redis import get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    redis: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    try:
        await get_redis().ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"

    return HealthResponse(status="ok", redis=redis_status)
