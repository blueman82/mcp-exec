"""Bravo FastAPI application entry point.

This module defines the FastAPI application factory, lifespan management,
and the main entry point for running the API server.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI

from bravo import __version__
from bravo.api import admin, assignees, health, nudge, polling, tickets
from bravo.config import get_settings
from bravo.db import close_pool, init_pool

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Args:
        _app: The FastAPI application instance (unused but required by signature).

    Yields:
        None during the application's active lifetime.
    """
    settings = get_settings()

    logger.info("starting_bravo", version=__version__)

    await init_pool(settings.database)

    yield

    await close_pool()
    logger.info("bravo_shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application with all routers registered.
    """
    settings = get_settings()

    app = FastAPI(
        title="Bravo API",
        description="Bravo - Championing Our Data - Jira hygiene nudge system",
        version=__version__,
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.include_router(health.router, tags=["Health"])
    app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    app.include_router(polling.router, prefix="/polling", tags=["Polling"])
    app.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
    app.include_router(nudge.router, prefix="/nudge", tags=["Nudge"])
    app.include_router(assignees.router, prefix="/assignees", tags=["Admin"])

    return app


app = create_app()


def main() -> None:
    """Run the application with uvicorn.

    Starts the uvicorn server with configuration from settings.
    """
    settings = get_settings()
    uvicorn.run(
        "bravo.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
