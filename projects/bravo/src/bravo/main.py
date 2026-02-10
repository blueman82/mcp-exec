"""Bravo FastAPI application entry point.

This module defines the FastAPI application factory, lifespan management,
and the main entry point for running the API server.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI

from bravo import __version__
from bravo.api import admin, assignees, health, nudge, polling, tickets
from bravo.config import LOG_FILE, get_settings, load_settings
from bravo.container import create_container
from bravo.db import close_pool, init_pool


def configure_logging(log_level: str) -> None:
    """Configure structlog with JSON output to stdout and file.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE))
    except OSError:
        pass  # Skip file handler if /var/log is not writable

    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=handlers,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        None during the application's active lifetime.
    """
    settings = await load_settings()

    logger.info("starting_bravo", version=__version__)

    await init_pool(settings.database)

    container = create_container(settings)
    await container.initialize_all()
    app.state.container = container

    yield

    await app.state.container.shutdown_all()
    await close_pool()
    logger.info("bravo_shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application with all routers registered.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

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
