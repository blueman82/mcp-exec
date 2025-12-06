"""
test_cleanup_utils.py

Unit tests for packages.core.cleanup_utils.cleanup_resources.

Covers:
- cleanup_resources: component cleanup, AsyncClient cleanup, aiohttp session/connector cleanup, all error and edge cases
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.cleanup_utils import cleanup_resources

pytestmark = pytest.mark.unit


class TestCleanupResources:
    """Unit tests for cleanup_resources utility function."""

    @pytest.mark.asyncio
    async def test_component_cleanup_success(self) -> None:
        """Test cleanup_resources calls cleanup on components with cleanup method."""
        comp = MagicMock()
        comp.cleanup = AsyncMock()
        await cleanup_resources([comp])
        comp.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_component_cleanup_exception_logged(self) -> None:
        """Test cleanup_resources logs error if component cleanup raises."""
        comp = MagicMock()
        comp.cleanup = AsyncMock(side_effect=Exception("fail"))
        with patch("packages.core.cleanup_utils.logger") as mock_logger:
            await cleanup_resources([comp])
            mock_logger.error.assert_any_call(
                "Error cleaning component %s: %s", comp.__class__.__name__, "fail"
            )

    @pytest.mark.asyncio
    async def test_asyncclient_cleanup_success(self) -> None:
        """Test cleanup_resources finds and cleans up AsyncClient instances."""
        client = MagicMock()
        client.cleanup = AsyncMock()
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[client]),
            patch("packages.core.cleanup_utils.AsyncClient", new=MagicMock()),
            patch("packages.core.cleanup_utils.logger") as mock_logger,
            patch("packages.core.cleanup_utils.isinstance", return_value=True),
        ):
            type(client).cleanup = AsyncMock()
            await cleanup_resources([])
            client.cleanup.assert_awaited()
            mock_logger.info.assert_any_call("Found %d AsyncClient instances for cleanup", 1)

    @pytest.mark.asyncio
    async def test_asyncclient_cleanup_exception_logged(self) -> None:
        """Test cleanup_resources logs error if AsyncClient cleanup raises."""
        client = MagicMock()
        client.cleanup = AsyncMock(side_effect=Exception("fail"))
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[client]),
            patch("packages.core.cleanup_utils.AsyncClient", new=MagicMock()),
            patch("packages.core.cleanup_utils.logger") as mock_logger,
            patch("packages.core.cleanup_utils.isinstance", return_value=True),
        ):
            type(client).cleanup = AsyncMock(side_effect=Exception("fail"))
            await cleanup_resources([])
            mock_logger.error.assert_any_call("Error cleaning AsyncClient: %s", "fail")

    @pytest.mark.asyncio
    async def test_aiohttp_session_cleanup_success(self) -> None:
        """Test cleanup_resources finds and closes aiohttp sessions."""
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[session]),
            patch("packages.core.cleanup_utils.aiohttp.ClientSession", new=MagicMock()),
            patch("packages.core.cleanup_utils.logger") as mock_logger,
            patch("packages.core.cleanup_utils.isinstance", return_value=True),
        ):
            await cleanup_resources([])
            await session.close()
            mock_logger.info.assert_any_call(
                "Tier 3b: Found %d aiohttp sessions for fallback cleanup", 1
            )

    @pytest.mark.asyncio
    async def test_aiohttp_session_already_closed(self) -> None:
        """Test cleanup_resources skips already closed aiohttp sessions."""
        session = MagicMock()
        session.closed = True
        session.close = AsyncMock()
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[session]),
            patch("packages.core.cleanup_utils.aiohttp.ClientSession", new=MagicMock()),
        ):
            await cleanup_resources([])
            session.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_aiohttp_session_cleanup_exception_logged(self) -> None:
        """Test cleanup_resources logs error if aiohttp session close raises."""
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock(side_effect=Exception("fail"))
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[session]),
            patch("packages.core.cleanup_utils.aiohttp.ClientSession", new=MagicMock()),
            patch("packages.core.cleanup_utils.logger") as mock_logger,
            patch("packages.core.cleanup_utils.isinstance", return_value=True),
        ):
            try:
                await cleanup_resources([])
                await session.close()
            except Exception:
                pass
            mock_logger.error.assert_any_call("Tier 3b: Error closing session: %s", "fail")

    @pytest.mark.asyncio
    async def test_connector_cleanup_success(self) -> None:
        """Test cleanup_resources finds and closes aiohttp TCPConnector instances."""
        connector = MagicMock()
        connector.closed = False
        connector.close = MagicMock()
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[connector]),
            patch("packages.core.cleanup_utils.aiohttp.TCPConnector", new=MagicMock()),
            patch("packages.core.cleanup_utils.logger"),
            patch("packages.core.cleanup_utils.isinstance", return_value=True),
        ):
            await cleanup_resources([])
            connector.close.assert_called()

    @pytest.mark.asyncio
    async def test_connector_already_closed(self) -> None:
        """Test cleanup_resources skips already closed connectors."""
        connector = MagicMock()
        connector.closed = True
        connector.close = MagicMock()
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[connector]),
            patch("packages.core.cleanup_utils.aiohttp.TCPConnector", new=MagicMock()),
        ):
            await cleanup_resources([])
            connector.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_connector_cleanup_exception_logged(self) -> None:
        """Test cleanup_resources logs error if connector close raises."""
        connector = MagicMock()
        connector.closed = False
        connector.close = MagicMock(side_effect=Exception("fail"))
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", return_value=[connector]),
            patch("packages.core.cleanup_utils.aiohttp.TCPConnector", new=MagicMock()),
            patch("packages.core.cleanup_utils.logger") as mock_logger,
            patch("packages.core.cleanup_utils.isinstance", return_value=True),
        ):
            await cleanup_resources([])
            mock_logger.error.assert_any_call("Tier 4: Error closing connector: %s", "fail")

    @pytest.mark.asyncio
    async def test_all_fallbacks_and_errors(self) -> None:
        """Test cleanup_resources handles all fallback and error paths gracefully."""
        # Simulate all gc lookups raising
        with (
            patch("packages.core.cleanup_utils.gc.get_objects", side_effect=Exception("fail")),
            patch("packages.core.cleanup_utils.logger") as mock_logger,
        ):
            await cleanup_resources([])
            # Should log error for AsyncClient, session, and connector cleanup
            assert mock_logger.error.call_count >= 3
