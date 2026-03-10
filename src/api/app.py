"""
FastAPI application factory.
"""

from fastapi import FastAPI

from src.api.routes import admin, health


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pawly API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.include_router(health.router)
    app.include_router(admin.router)

    return app
