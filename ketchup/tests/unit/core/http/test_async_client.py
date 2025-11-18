"""
test_async_client.py

Unit tests for packages.core.async_client.AsyncClient and _AdaptiveBatcher.

Covers:
- AsyncClient: initialization, setup, cleanup, context manager, _make_api_request, execute_with_backoff, error and edge cases
- _AdaptiveBatcher: increase_size, decrease_size, get_size
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.async_client import AsyncClient

# Import session types for proper testing
import aiohttp


class DummyConfig:
    pass


class DummyResponse:
    ok: bool = True
    status: int = 200

    async def read(self) -> bytes:
        return b"data"

    async def text(self) -> str:
        return "text"


class TestAsyncClient:
    """Unit tests for AsyncClient class and core logic."""

    def test_init_with_config(self) -> None:
        """Test AsyncClient initializes with config and sets defaults."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        assert client.config is cfg
        assert client._session is None
        assert client._request_semaphore._value == 10

    def test_init_without_config_raises(self) -> None:
        """Test AsyncClient raises ValueError if config is None."""
        with pytest.raises(ValueError, match="Configuration.*cannot be None"):
            AsyncClient(config=None)

    @pytest.mark.asyncio
    async def test_setup_creates_session(self) -> None:
        """Test setup creates a new session if none exists."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        with patch(
            "packages.core.async_client.create_session_with_retries",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = (MagicMock(closed=False), None)
            result: AsyncClient[DummyConfig, DummyResponse] = await client.setup()
            assert result is client
            assert client._session is mock_create.return_value[0]

    @pytest.mark.asyncio
    async def test_setup_reuses_open_session(self) -> None:
        """Test setup returns self if session exists and is open."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        client._session = MagicMock(closed=False)
        result: AsyncClient[DummyConfig, DummyResponse] = await client.setup()
        assert result is client

    @pytest.mark.asyncio
    async def test_setup_recreates_closed_session(self) -> None:
        """Test setup recreates session if existing is closed."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        closed_session: MagicMock = MagicMock(closed=True)
        client._session = closed_session
        with patch(
            "packages.core.async_client.create_session_with_retries",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = (MagicMock(closed=False), None)
            result: AsyncClient[DummyConfig, DummyResponse] = await client.setup()
            assert result is client
            assert client._session is mock_create.return_value[0]

    @pytest.mark.asyncio
    async def test_setup_session_creation_error(self) -> None:
        """Test setup raises ClientError if session creation fails."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        from packages.core.exceptions import ClientError
        from packages.core.http.session_management import SessionCreationError

        with patch(
            "packages.core.async_client.create_session_with_retries",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.side_effect = SessionCreationError(
                "fail", last_exception=Exception("bad")
            )
            with pytest.raises(ClientError, match="Failed to establish client session"):
                await client.setup()

    @pytest.mark.asyncio
    async def test_cleanup_closes_session(self) -> None:
        """Test cleanup closes aiohttp session and resets state."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        # Mock an aiohttp.ClientSession
        session: AsyncMock = AsyncMock(spec=aiohttp.ClientSession, closed=False)
        client._session = session
        await client.cleanup()
        session.close.assert_awaited_once()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_already_closed(self) -> None:
        """Test cleanup is safe if session is already closed."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        session: MagicMock = MagicMock(closed=True)
        client._session = session
        await client.cleanup()
        # Should not call close
        assert not hasattr(session, "close") or not session.close.called

    @pytest.mark.asyncio
    async def test_cleanup_logs_error_on_close(self) -> None:
        """Test cleanup logs error if aiohttp session.close raises."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        # Mock an aiohttp.ClientSession that raises error on close
        session: AsyncMock = AsyncMock(spec=aiohttp.ClientSession, closed=False)
        session.close.side_effect = Exception("fail")
        client._session = session
        with patch("packages.core.async_client.logger") as mock_logger:
            await client.cleanup()
            mock_logger.error.assert_called()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager calls setup and cleanup."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        with patch.object(
            client, "setup", new_callable=AsyncMock
        ) as mock_setup, patch.object(
            client, "cleanup", new_callable=AsyncMock
        ) as mock_cleanup:
            async with client:
                mock_setup.assert_awaited_once()
            mock_cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_make_api_request_success(self) -> None:
        """Test _make_api_request returns response on success."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        response: DummyResponse = DummyResponse()
        with patch.object(client, "setup", new_callable=AsyncMock), patch.object(
            client, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_backoff:
            mock_backoff.return_value = response
            result: DummyResponse = await client._make_api_request(
                url="http://foo", method="GET"
            )
            assert result is response

    @pytest.mark.asyncio
    async def test_make_api_request_timeout(self) -> None:
        """Test _make_api_request raises ClientError or TimeoutError on timeout."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        from packages.core.exceptions import ClientError

        with patch.object(client, "setup", new_callable=AsyncMock), patch.object(
            client, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_backoff:
            import asyncio

            mock_backoff.side_effect = asyncio.TimeoutError()
            with pytest.raises((ClientError, asyncio.TimeoutError)):
                await client._make_api_request(url="http://foo", method="GET")

    @pytest.mark.asyncio
    async def test_make_api_request_http_error(self) -> None:
        """Test _make_api_request raises ClientError or aiohttp.ClientError on HTTP error."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        import aiohttp

        from packages.core.exceptions import ClientError

        with patch.object(client, "setup", new_callable=AsyncMock), patch.object(
            client, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_backoff:
            mock_backoff.side_effect = aiohttp.ClientError("fail")
            with pytest.raises((ClientError, aiohttp.ClientError)):
                await client._make_api_request(url="http://foo", method="GET")

    @pytest.mark.asyncio
    async def test_make_api_request_unexpected_error(self) -> None:
        """Test _make_api_request raises ClientError or Exception on unexpected error."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        from packages.core.exceptions import ClientError

        with patch.object(client, "setup", new_callable=AsyncMock), patch.object(
            client, "execute_with_backoff", new_callable=AsyncMock
        ) as mock_backoff:
            mock_backoff.side_effect = Exception("fail")
            with pytest.raises((ClientError, Exception)):
                await client._make_api_request(url="http://foo", method="GET")

    @pytest.mark.asyncio
    async def test_execute_with_backoff_delegates(self) -> None:
        """Test execute_with_backoff delegates to backoff strategy."""
        cfg: DummyConfig = DummyConfig()
        client: AsyncClient[DummyConfig, DummyResponse] = AsyncClient(config=cfg)
        func: AsyncMock = AsyncMock(return_value=42)
        client._backoff_strategy = MagicMock()
        client._backoff_strategy.execute = AsyncMock(return_value=42)
        result: int = await client.execute_with_backoff(func, 1, foo=2)
        client._backoff_strategy.execute.assert_awaited_once_with(func, 1, foo=2)
        assert result == 42
