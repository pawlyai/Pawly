"""
Admin endpoints (placeholder for future use).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
async def admin_ping() -> dict:
    return {"message": "pong"}
