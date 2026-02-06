"""Asyncpg connection pool management.

This module provides functions for managing the asyncpg database connection pool
used throughout the Bravo application.
"""

import asyncpg
import structlog

from bravo.config import DatabaseSettings

logger = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(settings: DatabaseSettings) -> asyncpg.Pool:
    """Initialize the database connection pool.

    Args:
        settings: Database configuration settings.

    Returns:
        The initialized asyncpg connection pool.
    """
    global _pool

    if _pool is not None:
        return _pool

    logger.info(
        "initializing_database_pool",
        host=settings.host,
        port=settings.port,
        database=settings.name,
        min_size=settings.min_pool_size,
        max_size=settings.max_pool_size,
    )

    _pool = await asyncpg.create_pool(
        host=settings.host,
        port=settings.port,
        database=settings.name,
        user=settings.user,
        password=settings.password,
        min_size=settings.min_pool_size,
        max_size=settings.max_pool_size,
    )

    logger.info("database_pool_initialized")
    return _pool


def get_pool() -> asyncpg.Pool:
    """Get the current database connection pool.

    Returns:
        The current asyncpg connection pool.

    Raises:
        RuntimeError: If the pool has not been initialized.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def close_pool() -> None:
    """Close the database connection pool.

    Safely closes the pool if it exists, setting the global reference to None.
    """
    global _pool

    if _pool is not None:
        logger.info("closing_database_pool")
        await _pool.close()
        _pool = None
        logger.info("database_pool_closed")
