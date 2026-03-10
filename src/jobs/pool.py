"""
ARQ pool singleton — used by handlers to enqueue background jobs without
importing the heavy worker module.
"""

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        logger.info("ARQ pool created")
    return _arq_pool


async def close_arq_pool() -> None:
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None
        logger.info("ARQ pool closed")
