"""
FastAPI application factory.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import admin, chat, health, miniapp


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pawly API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # Allow the Telegram Mini App (hosted on GitHub Pages) to POST to this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://pawlyai.github.io",
            "https://api.pawly.app",
        ],
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(chat.router)
    app.include_router(miniapp.router)

    return app
