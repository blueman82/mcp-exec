"""Async IMS/MCP feature flag helpers."""

from __future__ import annotations

import functools
import os

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class MCPFeatureFlags:
    """Typed helpers for controlling async IMS/MCP rollout."""

    _ASYNC_ENV_VAR = "KETCHUP_USE_ASYNC_MCP"

    @classmethod
    @functools.lru_cache(maxsize=1)
    def use_async_clients(cls) -> bool:
        """Return True when the async IMS/MCP clients should be used."""

        use_async = os.environ.get(cls._ASYNC_ENV_VAR, "false").lower() == "true"
        logger.info(
            "MCPFeatureFlags.use_async_clients() = %s (env: %s=%s)",
            use_async,
            cls._ASYNC_ENV_VAR,
            os.environ.get(cls._ASYNC_ENV_VAR, "not set"),
        )
        return use_async

    @classmethod
    def reset_cache(cls) -> None:
        """Clear cached flag values (useful for tests changing env)."""

        cls.use_async_clients.cache_clear()
