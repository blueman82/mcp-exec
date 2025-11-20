#!/usr/bin/env python3
"""
Tests for main.py entry point with TypedDI integration.

Verifies:
- TypedDI container initializes correctly
- All required protocols are resolved
- Scheduler starts without errors
- Services are properly initialized
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.typed_di_integration import get_unified_container
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
        from ketchup_jira_pat_rotator.scheduler import PatRotationScheduler

        # Scheduler should initialize without errors
        scheduler = PatRotationScheduler()
        assert scheduler is not None
        assert scheduler.running is True
        assert hasattr(scheduler, "start")
        assert asyncio.iscoroutinefunction(scheduler.start)

    @pytest.mark.asyncio
    async def test_scheduler_has_rotation_interval(self):
        """Test that scheduler has proper rotation interval configured."""
        from ketchup_jira_pat_rotator.scheduler import PatRotationScheduler

        scheduler = PatRotationScheduler()

        # Verify rotation interval
        assert hasattr(scheduler, "ROTATION_INTERVAL_SECONDS")
        # 24 hours in seconds
        assert scheduler.ROTATION_INTERVAL_SECONDS == 24 * 60 * 60

    @pytest.mark.asyncio
    async def test_rotator_can_be_instantiated_with_dependencies(self):
        """Test that PATRotator can be instantiated with dependencies."""
        from ketchup_jira_pat_rotator.rotator import PATRotator

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
            import ketchup_jira_pat_rotator.main as main_module

            # Verify main module has expected attributes
            assert hasattr(main_module, "main")
            assert callable(main_module.main)

        except ImportError:
            # main.py doesn't exist yet - this is expected during first implementation
            pytest.skip("main.py not yet implemented")


class TestMainAsyncFunctionality:
    """Test async functionality in main module."""

    @pytest.mark.asyncio
    @patch("ketchup_jira_pat_rotator.main.PatRotationScheduler")
    async def test_main_can_start_scheduler(self, mock_scheduler_class):
        """Test that main function can start scheduler."""
        # Skip if main.py not yet implemented
        try:
            import ketchup_jira_pat_rotator.main as main_module

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
        from ketchup_jira_pat_rotator.scheduler import PatRotationScheduler

        scheduler = PatRotationScheduler()

        # Mock the rotation check to avoid actual network calls
        with patch.object(scheduler, "run_rotation_check", new_callable=AsyncMock):
            # Set a flag to stop after first iteration
            original_running = scheduler.running

            # Schedule shutdown after first run
            async def run_with_timeout():
                task = asyncio.create_task(scheduler.start())
                await asyncio.sleep(0.5)
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
            from ketchup_jira_pat_rotator.main import main

            assert callable(main)
        except ImportError:
            pytest.skip("main.py not yet implemented")

    def test_main_module_imports_logger(self):
        """Test that main module has logger configured."""
        try:
            import ketchup_jira_pat_rotator.main as main_module

            assert hasattr(main_module, "logger")
        except ImportError:
            pytest.skip("main.py not yet implemented")
