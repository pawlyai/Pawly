"""
FastAPI application factory.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import admin, chat, health, miniapp


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pawly API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type", "ngrok-skip-browser-warning"],
    )

    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(chat.router)
    app.include_router(miniapp.router)

    # Serve mini app static files from /miniapp/
    miniapp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "miniapp")
    miniapp_dir = os.path.abspath(miniapp_dir)
    if os.path.isdir(miniapp_dir):
        app.mount("/miniapp", StaticFiles(directory=miniapp_dir, html=True), name="miniapp")

    return app
