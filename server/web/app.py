"""
FastAPI application factory.
Creates the app, mounts static files, and registers all routers.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.web.routes.session import router as session_router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """
    Build and return the configured FastAPI application.

    Returns:
        A ready-to-serve FastAPI instance.
    """
    app = FastAPI(
        title="PRESCRIPTION — Web Dashboard",
        description=(
            "AI-powered voice medical prescription assistant. "
            "REST API for the web frontend."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Allow local browser dev servers on common ports
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000",
                       "http://127.0.0.1:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routes
    app.include_router(session_router)

    # Serve the SPA from /
    if _STATIC_DIR.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(_STATIC_DIR), html=True),
            name="static",
        )

    return app


# Module-level app instance for uvicorn
app = create_app()


def run() -> None:
    """
    Entry point called by the `prescription-web` CLI script.
    Starts uvicorn on 0.0.0.0:8000 with auto-reload for development.
    """
    uvicorn.run(
        "server.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["server"],
    )


if __name__ == "__main__":
    run()
