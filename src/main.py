"""
Entry point: starts the aiogram Telegram bot and FastAPI server concurrently.

Development:  long-polling + uvicorn
Production:   Telegram webhook mounted on FastAPI, uvicorn only
"""

import asyncio

import uvicorn
from fastapi import Request
from fastapi.responses import Response

from src.api.app import create_app
from src.bot.bot import create_bot
from src.config import settings
from src.db.engine import close_engine, init_engine
from src.db.redis import close_redis, init_redis
from src.jobs.pool import close_arq_pool
from src.utils.logger import configure_logging, get_logger

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main() -> None:
    logger.info("Starting Pawly", env=settings.node_env, port=settings.port)

    # Initialise shared resources
    await init_engine()
    await init_redis()

    # Build bot and dispatcher.
    # Production: token errors are hard failures — better to crash loudly than
    # run silently without Telegram.
    # Development: invalid/missing token skips the bot so the web API still works.
    bot = None
    dp = None
    try:
        bot, dp = await create_bot()
    except Exception as exc:
        if settings.node_env == "production":
            raise
        logger.warning("Telegram bot disabled (dev mode) — token invalid or missing", reason=str(exc))

    # Build FastAPI app
    fastapi_app = create_app()

    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level,
        loop="none",  # use the already-running asyncio loop
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        if settings.node_env == "production":
            # Set webhook and serve only uvicorn (Telegram pushes updates to us)
            webhook_url = (
                f"https://{settings.webhook_host}/webhook/{settings.telegram_bot_token}"
            )
            await bot.set_webhook(webhook_url, drop_pending_updates=True)  # type: ignore[union-attr]
            logger.info("webhook set", url=webhook_url)

            @fastapi_app.post(f"/webhook/{settings.telegram_bot_token}")
            async def telegram_webhook(request: Request) -> Response:
                from aiogram.types import Update
                body = await request.body()
                update = Update.model_validate_json(body)
                await dp.feed_update(bot, update)  # type: ignore[union-attr]
                return Response()

            await server.serve()
        else:
            if bot is not None and dp is not None:
                # Full dev mode: long-polling + uvicorn side-by-side
                await asyncio.gather(
                    dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
                    server.serve(),
                )
            else:
                # API-only dev mode: no valid bot token, web API still works
                logger.info("Running in API-only mode — POST /chat available, Telegram bot offline")
                await server.serve()
    finally:
        logger.info("Shutting down Pawly")
        if bot is not None:
            await bot.session.close()
        await close_arq_pool()
        await close_redis()
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
