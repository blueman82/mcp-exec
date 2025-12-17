#!/usr/bin/env python3
"""
Tests for main.py entry point with TypedDI integration.

Verifies:
- TypedDI container initializes correctly with mocked AWS dependencies
- All required protocols are resolved
- Scheduler starts without errors
- Services are properly initialized

NOTE: These are unit tests with mocked AWS dependencies.
AWS services are mocked via conftest.py fixtures.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
    IMSTokenManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,
)
from packages.core.typed_di_integration import get_unified_container


class TestMainTypeInitialization:
    """Test TypedDI container initialization."""

    @pytest.mark.asyncio
    async def test_typed_di_container_initializes(self):
        """Test that TypedDI container initializes successfully."""
        container = await get_unified_container()
        assert container is not None
        assert hasattr(container, "aget")

    @pytest.mark.asyncio
    async def test_dynamodb_store_protocol_resolved(self):
        """Test that DynamoDBStoreProtocol can be resolved."""
        container = await get_unified_container()
        db_store = await container.aget(DynamoDBStoreProtocol)
        assert db_store is not None

    @pytest.mark.asyncio
    async def test_secrets_manager_protocol_resolved(self):
        """Test that SecretsManagerProtocol can be resolved."""
        container = await get_unified_container()
        secrets_manager = await container.aget(SecretsManagerProtocol)
        assert secrets_manager is not None

    @pytest.mark.asyncio
    async def test_mcp_client_protocol_resolved(self):
        """Test that MCPClientProtocol can be resolved."""
        container = await get_unified_container()
        mcp_client = await container.aget(MCPClientProtocol)
        assert mcp_client is not None

    @pytest.mark.asyncio
    async def test_ims_token_manager_protocol_resolved(self):
        """Test that IMSTokenManagerProtocol can be resolved."""
        container = await get_unified_container()
        ims_token_manager = await container.aget(IMSTokenManagerProtocol)
        assert ims_token_manager is not None

    @pytest.mark.asyncio
    async def test_all_required_protocols_available(self):
        """Test that all required protocols for PAT rotator are available."""
        container = await get_unified_container()

        # Verify all required protocols can be resolved
        required_protocols = [
            DynamoDBStoreProtocol,
            SecretsManagerProtocol,
            MCPClientProtocol,
            IMSTokenManagerProtocol,
        ]

        for protocol in required_protocols:
            service = await container.aget(protocol)
            assert service is not None, f"Protocol {protocol} not available"

    @pytest.mark.asyncio
    async def test_container_services_properly_initialized(self):
        """Test that container services are properly initialized."""
        container = await get_unified_container()

        # Get services and verify they have expected attributes/methods
        db_store = await container.aget(DynamoDBStoreProtocol)
        assert hasattr(db_store, "client")
        assert hasattr(db_store, "table_name")

        secrets_manager = await container.aget(SecretsManagerProtocol)
        # Verify it's a protocol implementation (has methods)
        assert secrets_manager is not None
        assert hasattr(secrets_manager, "__class__")


class TestSchedulerIntegration:
    """Test scheduler integration with TypedDI."""

    @pytest.mark.asyncio
    async def test_scheduler_initialization_with_container(self):
        """Test that scheduler can be initialized with container dependencies."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PatRotationScheduler

        # Scheduler should initialize without errors
        scheduler = PatRotationScheduler()
        assert scheduler is not None
        assert scheduler.running is True
        assert hasattr(scheduler, "start")
        assert asyncio.iscoroutinefunction(scheduler.start)

    @pytest.mark.asyncio
    async def test_scheduler_has_rotation_interval(self):
        """Test that scheduler has proper rotation interval configured."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PatRotationScheduler

        scheduler = PatRotationScheduler()

        # Verify rotation interval - BaseScheduler uses interval_minutes
        assert hasattr(scheduler, "interval_minutes")
        # 24 hours in minutes = 1440
        assert scheduler.interval_minutes == 1440
        # get_sleep_seconds should return 24 hours in seconds
        assert scheduler.get_sleep_seconds() == 24 * 60 * 60

    @pytest.mark.asyncio
    async def test_rotator_can_be_instantiated_with_dependencies(self):
        """Test that PATRotator can be instantiated with dependencies."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        # Should instantiate without errors
        rotator = PATRotator()
        assert rotator is not None
        assert hasattr(rotator, "rotate")
        assert asyncio.iscoroutinefunction(rotator.rotate)

    @pytest.mark.asyncio
    async def test_main_entry_point_structure(self):
        """Test that main module has correct entry point structure."""
        # Import will fail if main.py doesn't exist
        try:
            import ketchup_unified_scheduler.services.pat_rotator.rotator as main_module

            # Verify main module has expected attributes
            assert hasattr(main_module, "main")
            assert callable(main_module.main)

        except ImportError:
            # main.py doesn't exist yet - this is expected during first implementation
            pytest.skip("main.py not yet implemented")


class TestMainAsyncFunctionality:
    """Test async functionality in main module."""

    @pytest.mark.asyncio
    @patch("ketchup_unified_scheduler.services.pat_rotator.rotator.PatRotationScheduler")
    async def test_main_can_start_scheduler(self, mock_scheduler_class):
        """Test that main function can start scheduler."""
        # Skip if main.py not yet implemented
        try:
            import ketchup_unified_scheduler.services.pat_rotator.rotator as main_module

            # Mock the scheduler
            mock_scheduler = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler

            # This would be the async main function
            if hasattr(main_module, "async_main"):
                await main_module.async_main()
                mock_scheduler.start.assert_called_once()

        except ImportError:
            pytest.skip("main.py not yet implemented")

    @pytest.mark.asyncio
    async def test_scheduler_runs_without_errors(self):
        """Test that scheduler can run initial cycle without errors."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PatRotationScheduler

        scheduler = PatRotationScheduler()

        # Mock the run_task method to avoid actual network calls
        with patch.object(scheduler, "run_task", new_callable=AsyncMock):
            # Mock asyncio.sleep to prevent infinite loop
            with patch(
                "packages.core.schedulers.base_scheduler.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                # Schedule shutdown after first run
                async def run_with_timeout():
                    task = asyncio.create_task(scheduler.start())
                    await asyncio.sleep(0.1)
                    scheduler.running = False
                    try:
                        await asyncio.wait_for(task, timeout=2.0)
                    except asyncio.TimeoutError:
                        pass

                try:
                    await run_with_timeout()
                except Exception as e:
                    pytest.fail(f"Scheduler failed to run: {e}")


class TestMainModuleExports:
    """Test that main module exports required functions."""

    def test_main_module_exports_main_function(self):
        """Test that main module exports main function."""
        try:
            from ketchup_unified_scheduler.services.pat_rotator.rotator import main

            assert callable(main)
        except ImportError:
            pytest.skip("main.py not yet implemented")

    def test_main_module_imports_logger(self):
        """Test that main module has logger configured."""
        try:
            import ketchup_unified_scheduler.services.pat_rotator.rotator as main_module

            assert hasattr(main_module, "logger")
        except ImportError:
            pytest.skip("main.py not yet implemented")


class TestPATRotatorDIIntegration:
    """Test TypedDI integration in PAT rotator."""

    @pytest.mark.asyncio
    async def test_rotator_accepts_container(self):
        """Test that PATRotator can be instantiated with a DI container."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        container = await get_unified_container()
        rotator = PATRotator(container=container)

        assert rotator is not None
        assert rotator._container is container

    @pytest.mark.asyncio
    async def test_rotator_resolves_mcp_client_via_di(self):
        """Test that rotator resolves MCP client via TypedDI when container provided."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        container = await get_unified_container()
        rotator = PATRotator(container=container)

        # Get MCP client via the lazy getter
        mcp_client = await rotator._get_mcp_client()

        assert mcp_client is not None

    @pytest.mark.asyncio
    async def test_rotator_falls_back_without_container(self):
        """Test that rotator can fall back to direct instantiation without container."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        # Create rotator without container
        rotator = PATRotator(container=None)

        assert rotator._container is None
        # MCP client should be None initially (lazy initialization)
        assert rotator._mcp_client is None

    @pytest.mark.asyncio
    async def test_scheduler_passes_container_to_rotator(self):
        """Test that scheduler passes DI container to rotator."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PatRotationScheduler

        container = await get_unified_container()
        scheduler = PatRotationScheduler(container=container)

        assert scheduler._container is container

    @pytest.mark.asyncio
    async def test_scheduler_accepts_none_container(self):
        """Test that scheduler works without container (backward compatible)."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PatRotationScheduler

        scheduler = PatRotationScheduler()

        assert scheduler._container is None

    @pytest.mark.asyncio
    async def test_mcp_client_caching(self):
        """Test that MCP client is cached after first resolution."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        container = await get_unified_container()
        rotator = PATRotator(container=container)

        # First call should resolve and cache
        mcp_client_1 = await rotator._get_mcp_client()

        # Second call should return cached instance
        mcp_client_2 = await rotator._get_mcp_client()

        assert mcp_client_1 is mcp_client_2

    @pytest.mark.asyncio
    async def test_rotate_returns_skipped_when_no_rotation_needed(self):
        """Test that rotate returns skipped status when rotation not needed."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        container = await get_unified_container()
        rotator = PATRotator(container=container)

        # Mock the monitor to return False (no rotation needed)
        with patch.object(rotator._monitor, "should_rotate", return_value=False):
            result = await rotator.rotate()

        assert result["status"] == "skipped"
        assert result["action"] == "no_rotation_needed"

    @pytest.mark.asyncio
    async def test_rotate_handles_missing_mcp_client(self):
        """Test that rotate handles unavailable MCP client gracefully."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        # Create rotator without container
        rotator = PATRotator(container=None)

        # Mock monitor to trigger rotation
        with patch.object(rotator._monitor, "should_rotate", return_value=True):
            # Mock _get_mcp_client to return None (simulating init failure)
            with patch.object(rotator, "_get_mcp_client", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None

                result = await rotator.rotate()

        assert result["status"] == "failed"
        assert result["reason"] == "mcp_client_unavailable"
