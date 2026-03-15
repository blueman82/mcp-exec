"""
Test Container Passthrough Pattern

Validates that all refactored services correctly implement the container passthrough
pattern, allowing for:
1. Accepting an optional container parameter
2. Using provided container instead of creating a new one
3. Backward compatibility when called without arguments
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.typed_di.registry import TypedServiceRegistry
from packages.slack.channel_events.models import ProcessingResult

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_container():
    """
    Create a mock TypedServiceRegistry with necessary protocols.

    This fixture returns a mock container that can be passed to the refactored
    functions to verify they use the provided container instead of creating one.
    """
    container = MagicMock(spec=TypedServiceRegistry)
    container.aget = AsyncMock()
    container.is_initialized = MagicMock(return_value=True)
    return container


@pytest.fixture
def mock_dynamodb_store():
    """Mock DynamoDB store for service tests."""
    mock = AsyncMock()
    mock.client = MagicMock()
    mock.table_name = "test_table"
    mock.channel_ops = AsyncMock()
    mock.store_maintenance_cache = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_secrets_manager():
    """Mock SecretsManager for service tests."""
    return AsyncMock()


@pytest.fixture
def mock_soap_client():
    """Mock SOAP client for maintenance fetcher tests."""
    mock = AsyncMock()
    mock.fetch_maintenance_data = AsyncMock(return_value=[{"id": 1}])
    return mock


# ============================================================================
# Signature Verification Tests
# ============================================================================


class TestFunctionSignatures:
    """Verify all refactored functions have the correct container parameter signature."""

    def test_maintenance_fetcher_signature(self):
        """Verify fetch_and_store_maintenance_data has container: Optional[TypedServiceRegistry] = None."""
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )

        sig = inspect.signature(fetch_and_store_maintenance_data)

        # Verify container parameter exists
        assert "container" in sig.parameters, "container parameter missing"

        # Verify it has Optional default of None
        container_param = sig.parameters["container"]
        assert container_param.default is None, "container default should be None"

    def test_status_updater_signature(self):
        """Verify run_auto_status has container: Optional[TypedServiceRegistry] = None."""
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        sig = inspect.signature(run_auto_status)

        # Verify container parameter exists
        assert "container" in sig.parameters, "container parameter missing"

        # Verify it has Optional default of None
        container_param = sig.parameters["container"]
        assert container_param.default is None, "container default should be None"

    def test_metadata_processor_signature(self):
        """Verify process_channels has container: Optional[TypedServiceRegistry] = None."""
        from ketchup_unified_scheduler.services.metadata.processor import process_channels

        sig = inspect.signature(process_channels)

        # Verify container parameter exists
        assert "container" in sig.parameters, "container parameter missing"

        # Verify it has Optional default of None
        container_param = sig.parameters["container"]
        assert container_param.default is None, "container default should be None"

    def test_jira_reporter_signature(self):
        """Verify run_reporting_cycle has container: Optional[TypedServiceRegistry] = None."""
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle

        sig = inspect.signature(run_reporting_cycle)

        # Verify container parameter exists
        assert "container" in sig.parameters, "container parameter missing"

        # Verify it has Optional default of None
        container_param = sig.parameters["container"]
        assert container_param.default is None, "container default should be None"


# ============================================================================
# Maintenance Fetcher Passthrough Tests
# ============================================================================


class TestMaintenanceFetcherPassthrough:
    """Test container passthrough for maintenance_fetcher service."""

    @pytest.mark.asyncio
    async def test_accepts_container_parameter(self, mock_container):
        """Test that fetch_and_store_maintenance_data accepts container parameter."""
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )

        # Verify function can be called with container parameter (even if it returns early due to feature flag)
        with patch.dict("os.environ", {"KETCHUP_MAINTENANCE_FETCHER_ENABLED": "false"}):
            result = await fetch_and_store_maintenance_data(container=mock_container)
            assert result == {"status": "disabled"}

    @pytest.mark.asyncio
    async def test_uses_provided_container(
        self, mock_container, mock_dynamodb_store, mock_soap_client
    ):
        """Test that provided container is used instead of get_unified_container."""
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )

        # Setup mock container to return required services
        mock_container.aget = AsyncMock(side_effect=[mock_soap_client, mock_dynamodb_store])

        with patch.dict("os.environ", {"KETCHUP_MAINTENANCE_FETCHER_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.maintenance.fetcher.get_unified_container"
            ) as mock_get_container:
                await fetch_and_store_maintenance_data(container=mock_container)

                # get_unified_container should NOT be called when container is provided
                mock_get_container.assert_not_called()

    @pytest.mark.asyncio
    async def test_backward_compatible_without_container(self):
        """Test that function works when called without container argument."""
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )

        # With feature disabled, function should return early without needing container
        with patch.dict("os.environ", {"KETCHUP_MAINTENANCE_FETCHER_ENABLED": "false"}):
            result = await fetch_and_store_maintenance_data()
            assert result == {"status": "disabled"}

    @pytest.mark.asyncio
    async def test_creates_container_when_none_provided(self):
        """Test that get_unified_container is called when container=None."""
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )

        mock_container = AsyncMock()
        mock_container.aget = AsyncMock(
            side_effect=Exception("Expected - testing container creation")
        )

        with patch.dict("os.environ", {"KETCHUP_MAINTENANCE_FETCHER_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.maintenance.fetcher.get_unified_container",
                return_value=mock_container,
            ) as mock_get_container:
                # Call will fail when trying to aget, but we just need to verify get_unified_container was called
                try:
                    await fetch_and_store_maintenance_data()
                except Exception:
                    pass

                # get_unified_container SHOULD be called when no container provided
                mock_get_container.assert_called_once()


# ============================================================================
# Status Updater Passthrough Tests
# ============================================================================


class TestStatusUpdaterPassthrough:
    """Test container passthrough for status_updater service."""

    @pytest.mark.asyncio
    async def test_accepts_container_parameter(self, mock_container):
        """Test that run_auto_status accepts container parameter."""
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        # Setup mock to raise early to avoid full execution
        mock_container.aget = AsyncMock(side_effect=Exception("Test - early exit"))

        with pytest.raises(Exception, match="Test - early exit"):
            await run_auto_status(container=mock_container)

    @pytest.mark.asyncio
    async def test_uses_provided_container(self, mock_container, mock_dynamodb_store):
        """Test that provided container is used instead of get_unified_container."""
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        # Setup mock container
        mock_container.aget = AsyncMock(return_value=mock_dynamodb_store)

        with patch(
            "ketchup_unified_scheduler.services.status.processor.get_unified_container"
        ) as mock_get_container:
            with patch(
                "ketchup_unified_scheduler.services.status.processor.DistributedLock"
            ) as mock_lock:
                # Make lock acquisition fail to exit early
                mock_lock_instance = AsyncMock()
                mock_lock_instance.acquire_lock = MagicMock(
                    return_value=AsyncMock(
                        __aenter__=AsyncMock(return_value=False),
                        __aexit__=AsyncMock(return_value=None),
                    )
                )
                mock_lock.return_value = mock_lock_instance

                await run_auto_status(container=mock_container)

                # get_unified_container should NOT be called when container is provided
                mock_get_container.assert_not_called()

    @pytest.mark.asyncio
    async def test_backward_compatible_without_container(self):
        """Test that function works when called without container argument."""
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        mock_container = AsyncMock()
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        with patch(
            "ketchup_unified_scheduler.services.status.processor.get_unified_container",
            return_value=mock_container,
        ):
            # Function should call get_unified_container when no container provided
            with pytest.raises(Exception, match="Test exit"):
                await run_auto_status()

    @pytest.mark.asyncio
    async def test_creates_container_when_none_provided(self):
        """Test that get_unified_container is called when container=None."""
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        mock_container = AsyncMock()
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        with patch(
            "ketchup_unified_scheduler.services.status.processor.get_unified_container",
            return_value=mock_container,
        ) as mock_get_container:
            try:
                await run_auto_status()
            except Exception:
                pass

            # get_unified_container SHOULD be called when no container provided
            mock_get_container.assert_called_once()


# ============================================================================
# Metadata Updater Passthrough Tests
# ============================================================================


class TestMetadataUpdaterPassthrough:
    """Test container passthrough for metadata_updater service."""

    @pytest.mark.asyncio
    async def test_accepts_container_parameter(self, mock_container):
        """Test that process_channels accepts container parameter."""
        from ketchup_unified_scheduler.services.metadata.processor import process_channels

        # Setup mock container
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        result = await process_channels(container=mock_container)
        # Should return error response due to exception
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_uses_provided_container(self, mock_container, mock_secrets_manager):
        """Test that provided container is used instead of get_unified_container."""
        from ketchup_unified_scheduler.services.metadata.processor import process_channels

        # Setup mock container to return required dependencies
        mock_container.aget = AsyncMock(return_value=mock_secrets_manager)

        with patch(
            "ketchup_unified_scheduler.services.metadata.processor.get_unified_container"
        ) as mock_get_container:
            with patch(
                "ketchup_unified_scheduler.services.metadata.processor.create_channel_metadata_updater"
            ) as mock_create_updater:
                # Mock updater to avoid full execution
                mock_updater = AsyncMock()
                mock_updater.initialize = AsyncMock()
                mock_updater.scan_for_incomplete_metadata = AsyncMock(return_value=[])
                mock_updater.cleanup_clients = AsyncMock()
                mock_create_updater.return_value = mock_updater

                await process_channels(container=mock_container)

                # get_unified_container should NOT be called when container is provided
                mock_get_container.assert_not_called()

    @pytest.mark.asyncio
    async def test_backward_compatible_without_container(self):
        """Test that function works when called without container argument."""
        from ketchup_unified_scheduler.services.metadata.processor import process_channels

        mock_container = AsyncMock()
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        with patch(
            "ketchup_unified_scheduler.services.metadata.processor.get_unified_container",
            return_value=mock_container,
        ):
            result = await process_channels()
            # Should return error due to exception
            assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_creates_container_when_none_provided(self):
        """Test that get_unified_container is called when container=None."""
        from ketchup_unified_scheduler.services.metadata.processor import process_channels

        mock_container = AsyncMock()
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        with patch(
            "ketchup_unified_scheduler.services.metadata.processor.get_unified_container",
            return_value=mock_container,
        ) as mock_get_container:
            await process_channels()

            # get_unified_container SHOULD be called when no container provided
            mock_get_container.assert_called_once()


# ============================================================================
# JIRA Reporter Passthrough Tests
# ============================================================================


class TestJiraReporterPassthrough:
    """Test container passthrough for jira_reporter service."""

    @pytest.mark.asyncio
    async def test_accepts_container_parameter(self, mock_container):
        """Test that run_reporting_cycle accepts container parameter."""
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle

        # Setup mock container to raise early to avoid full execution
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        # FeatureFlags is imported locally inside run_reporting_cycle, so patch at source
        with patch(
            "packages.core.config.feature_flags.FeatureFlags.is_jira_reporter_enabled",
            return_value=True,
        ):
            # Function should accept container and use it
            await run_reporting_cycle(container=mock_container)
            # Function catches exceptions internally, so no assertion on raise

    @pytest.mark.asyncio
    async def test_uses_provided_container(self, mock_container, mock_dynamodb_store):
        """Test that provided container is used instead of get_unified_container."""
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle

        # Setup mock container
        mock_container.aget = AsyncMock(return_value=mock_dynamodb_store)

        # FeatureFlags is imported locally inside run_reporting_cycle, so patch at source
        with patch(
            "packages.core.config.feature_flags.FeatureFlags.is_jira_reporter_enabled",
            return_value=False,
        ):
            with patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.get_unified_container"
            ) as mock_get_container:
                await run_reporting_cycle(container=mock_container)

                # get_unified_container should NOT be called when container is provided
                mock_get_container.assert_not_called()

    @pytest.mark.asyncio
    async def test_backward_compatible_without_container(self):
        """Test that function works when called without container argument."""
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle

        # FeatureFlags is imported locally inside run_reporting_cycle, so patch at source
        with patch(
            "packages.core.config.feature_flags.FeatureFlags.is_jira_reporter_enabled",
            return_value=False,
        ):
            # Should work without container argument (will exit early due to feature flag)
            await run_reporting_cycle()

    @pytest.mark.asyncio
    async def test_creates_container_when_none_provided(self):
        """Test that get_unified_container is called when container=None."""
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle

        mock_container = AsyncMock()
        mock_container.aget = AsyncMock(side_effect=Exception("Test exit"))

        # FeatureFlags is imported locally inside run_reporting_cycle, so patch at source
        with patch(
            "packages.core.config.feature_flags.FeatureFlags.is_jira_reporter_enabled",
            return_value=True,
        ):
            with patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.get_unified_container",
                return_value=mock_container,
            ) as mock_get_container:
                await run_reporting_cycle()

                # get_unified_container SHOULD be called when no container provided
                mock_get_container.assert_called_once()


# ============================================================================
# Integration Tests - All Services
# ============================================================================


class TestAllServicesPassthroughPattern:
    """Integration tests verifying consistent passthrough pattern across all services."""

    def test_all_functions_have_consistent_signature(self):
        """Verify all refactored functions have consistent container parameter."""
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )
        from ketchup_unified_scheduler.services.metadata.processor import process_channels
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        functions = [
            fetch_and_store_maintenance_data,
            run_auto_status,
            process_channels,
            run_reporting_cycle,
        ]

        for func in functions:
            sig = inspect.signature(func)
            assert "container" in sig.parameters, f"{func.__name__} missing container param"

            container_param = sig.parameters["container"]
            assert (
                container_param.default is None
            ), f"{func.__name__} container param should default to None"

            # Verify annotation includes Optional or TypedServiceRegistry
            annotation = container_param.annotation
            annotation_str = str(annotation)
            assert (
                "TypedServiceRegistry" in annotation_str
                or "Optional" in annotation_str
                or annotation == inspect.Parameter.empty
            ), f"{func.__name__} container param should be Optional[TypedServiceRegistry]"

    @pytest.mark.asyncio
    async def test_dependency_verification_script(self):
        """
        Run the dependency verification script from the task description.

        This test verifies that all refactored functions have the container parameter
        as specified in the PHASE 0 verification step.
        """
        from ketchup_unified_scheduler.services.jira_reporter.service import run_reporting_cycle
        from ketchup_unified_scheduler.services.maintenance.fetcher import (
            fetch_and_store_maintenance_data,
        )
        from ketchup_unified_scheduler.services.metadata.processor import process_channels
        from ketchup_unified_scheduler.services.status.processor import run_auto_status

        functions = [
            fetch_and_store_maintenance_data,
            run_auto_status,
            process_channels,
            run_reporting_cycle,
        ]

        for func in functions:
            sig = inspect.signature(func)
            assert "container" in sig.parameters, f"{func.__name__} missing container param"
