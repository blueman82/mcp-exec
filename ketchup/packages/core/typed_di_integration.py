"""
TypedServiceRegistry Integration

Pure TypedDI integration layer - legacy DI has been fully removed.
All services now use protocol-based type resolution.
"""

import time
from typing import Optional

from packages.core.logging import setup_logger
from .typed_di import TypedServiceRegistry

logger = setup_logger(__name__)

# Global instance
_typed_registry: Optional[TypedServiceRegistry] = None




async def _run_startup_smoke_checks(registry: TypedServiceRegistry) -> bool:
    """
    Run startup smoke checks to validate essential services before going live.

    Tests only the 6 essential services that are initialized during startup.
    Compatibility bridge tests (Tests 7-9) are deferred to post-initialization
    to avoid deadlocks during the startup sequence.
    Returns True if all checks pass, False if any fail.
    """
    logger.info(
        "Running TypedDI startup smoke checks for essential services + critical service chain validation"
    )

    try:
        # Import only the 6 essential services that are initialized at startup
        # These match the services registered in _register_essential_services_with_protocols()
        from packages.db.config.dynamodb_config import DynamoDBConfig
        from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
        from packages.db.dynamodb_store import DynamoDBStore
        from packages.secrets.manager import SecretsManager
        from packages.slack.config.slack_config import SlackConfig
        from packages.slack.messages.posting import SlackPostingHandler

        # Test 1: Resolve SecretsManager
        try:
            secrets_manager = await registry.aget(SecretsManager)
            if secrets_manager is None:
                logger.error("Smoke check failed: SecretsManager resolved to None")
                return False
            logger.debug("✓ SecretsManager smoke check passed")
        except Exception as e:
            logger.error(f"Smoke check failed: SecretsManager resolution error: {e}")
            return False

        # Test 2: Resolve SlackConfig
        try:
            slack_config = await registry.aget(SlackConfig)
            if slack_config is None:
                logger.error("Smoke check failed: SlackConfig resolved to None")
                return False
            logger.debug("✓ SlackConfig smoke check passed")
        except Exception as e:
            logger.error(f"Smoke check failed: SlackConfig resolution error: {e}")
            return False

        # Test 3: Resolve SlackPostingHandler
        try:
            slack_posting_handler = await registry.aget(SlackPostingHandler)
            if slack_posting_handler is None:
                logger.error("Smoke check failed: SlackPostingHandler resolved to None")
                return False
            logger.debug("✓ SlackPostingHandler smoke check passed")
        except Exception as e:
            logger.error(
                f"Smoke check failed: SlackPostingHandler resolution error: {e}"
            )
            return False

        # Test 4: Resolve DynamoDBConfig
        try:
            dynamodb_config = await registry.aget(DynamoDBConfig)
            if dynamodb_config is None:
                logger.error("Smoke check failed: DynamoDBConfig resolved to None")
                return False
            logger.debug("✓ DynamoDBConfig smoke check passed")
        except Exception as e:
            logger.error(f"Smoke check failed: DynamoDBConfig resolution error: {e}")
            return False

        # Test 5: Resolve DynamoDBAsyncClient
        try:
            dynamodb_client = await registry.aget(DynamoDBAsyncClient)
            if dynamodb_client is None:
                logger.error("Smoke check failed: DynamoDBAsyncClient resolved to None")
                return False
            logger.debug("✓ DynamoDBAsyncClient smoke check passed")
        except Exception as e:
            logger.error(
                f"Smoke check failed: DynamoDBAsyncClient resolution error: {e}"
            )
            return False

        # Test 6: Resolve DynamoDBStore
        try:
            dynamodb_store = await registry.aget(DynamoDBStore)
            if dynamodb_store is None:
                logger.error("Smoke check failed: DynamoDBStore resolved to None")
                return False
            logger.debug("✓ DynamoDBStore smoke check passed")
        except Exception as e:
            logger.error(f"Smoke check failed: DynamoDBStore resolution error: {e}")
            return False

        # NOTE: Tests 7-9 (compatibility bridge tests) removed to prevent deadlock
        # These tests accessed the compatibility bridge during initialization,
        # causing circular dependencies. They should be run post-initialization
        # as a separate validation step if needed.

        logger.info(
            "All TypedDI startup smoke checks passed successfully (6 essential services)"
        )
        return True

    except ImportError as e:
        logger.error(f"Smoke check failed: Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"Smoke check failed: Unexpected error: {e}")
        return False




def get_typed_registry() -> TypedServiceRegistry:
    """
    Get the global TypedServiceRegistry instance.
    
    Returns:
        TypedServiceRegistry: The global registry instance
        
    Raises:
        RuntimeError: If registry not initialized
    """
    if _typed_registry is None:
        raise RuntimeError(
            "TypedServiceRegistry not initialized. "
            "Call get_unified_container() first to initialize the registry."
        )
    return _typed_registry


async def get_unified_container() -> TypedServiceRegistry:
    """
    Get the TypedServiceRegistry directly (legacy DI removed).

    Returns:
        TypedServiceRegistry: The initialized registry instance
    """
    global _typed_registry

    if _typed_registry is None:
        logger.info("Initializing TypedServiceRegistry")
        _typed_registry = TypedServiceRegistry()

        # Register all services
        from .typed_di.service_registrations import register_all_services
        register_all_services(_typed_registry)

        # Initialize all services
        logger.info("Running TypedDI initialize_all()")
        init_start = time.perf_counter()
        await _typed_registry.initialize_all()
        init_duration = time.perf_counter() - init_start
        logger.info("TypedDI initialize_all() completed in %.2fs", init_duration)

        # Run startup smoke checks
        logger.info("Running TypedDI startup smoke checks")
        if not await _run_startup_smoke_checks(_typed_registry):
            logger.error("TypedDI startup smoke checks failed")
            raise RuntimeError("TypedDI initialization failed smoke checks")

        # Freeze registry after smoke checks pass
        _typed_registry.freeze_after_init()
        logger.info("TypedServiceRegistry initialized successfully with smoke checks passed")

    return _typed_registry


async def cleanup_unified_container() -> None:
    """Clean up the TypedServiceRegistry."""
    global _typed_registry
    logger.info("Cleaning up TypedServiceRegistry")
    _typed_registry = None


# Backward compatibility functions
async def get_container() -> TypedServiceRegistry:
    """
    Get the global TypedServiceRegistry instance.

    Maintained for backward compatibility.
    """
    return await get_unified_container()


async def cleanup_container() -> None:
    """Clean up the global TypedServiceRegistry instance."""
    await cleanup_unified_container()
