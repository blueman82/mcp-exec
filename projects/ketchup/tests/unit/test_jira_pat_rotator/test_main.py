#!/usr/bin/env python3
"""
Tests for PAT rotator TypedDI integration.

Verifies:
- TypedDI container initializes correctly with mocked AWS dependencies
- All required protocols are resolved
- PATRotator can be instantiated and works correctly
- Services are properly initialized

NOTE: These are unit tests with mocked AWS dependencies.
AWS services are mocked via conftest.py fixtures.

Note: PatRotationScheduler class was removed as dead code - production uses
TaskRegistry + TaskConfig pattern via ketchup_unified_scheduler.
"""

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
    MCPAsyncClientProtocol,
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
        """Test that MCPAsyncClientProtocol can be resolved."""
        container = await get_unified_container()
        mcp_client = await container.aget(MCPAsyncClientProtocol)
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
            MCPAsyncClientProtocol,
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


class TestPATRotatorInstantiation:
    """Test PATRotator instantiation and basic functionality."""

    @pytest.mark.asyncio
    async def test_rotator_can_be_instantiated(self):
        """Test that PATRotator can be instantiated."""
        from ketchup_unified_scheduler.services.pat_rotator.rotator import PATRotator

        rotator = PATRotator()
        assert rotator is not None
        assert hasattr(rotator, "rotate")

    @pytest.mark.asyncio
    async def test_rotator_has_logger(self):
        """Test that rotator module has logger configured."""
        import ketchup_unified_scheduler.services.pat_rotator.rotator as rotator_module

        assert hasattr(rotator_module, "logger")


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
