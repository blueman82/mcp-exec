"""
test_session_keepalive.py

Unit tests for keep-alive connection tuning in session_management.py.

Covers:
- Session creation with keep-alive tuning enabled
- Session creation with keep-alive tuning disabled (legacy behavior)
- Custom keepalive_timeout and dns_cache_ttl values
- Feature flag integration
- TCPConnector configuration validation
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from packages.core.config.feature_flags import FeatureFlags
from packages.core.http.session_management import create_session_with_retries


class TestKeepAliveFeatureFlags:
    """Unit tests for keep-alive feature flag methods."""

    def test_is_keepalive_tuning_enabled_true(self) -> None:
        """Test is_keepalive_tuning_enabled returns True when env var is 'true'."""
        with patch.dict(os.environ, {"KETCHUP_KEEPALIVE_ENABLED": "true"}):
            assert FeatureFlags.is_keepalive_tuning_enabled() is True

    def test_is_keepalive_tuning_enabled_false(self) -> None:
        """Test is_keepalive_tuning_enabled returns False when env var is 'false'."""
        with patch.dict(os.environ, {"KETCHUP_KEEPALIVE_ENABLED": "false"}):
            assert FeatureFlags.is_keepalive_tuning_enabled() is False

    def test_is_keepalive_tuning_enabled_default(self) -> None:
        """Test is_keepalive_tuning_enabled returns False by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert FeatureFlags.is_keepalive_tuning_enabled() is False

    def test_get_keepalive_timeout_custom(self) -> None:
        """Test get_keepalive_timeout returns custom value from env var."""
        with patch.dict(os.environ, {"KETCHUP_KEEPALIVE_TIMEOUT": "120"}):
            assert FeatureFlags.get_keepalive_timeout() == 120

    def test_get_keepalive_timeout_default(self) -> None:
        """Test get_keepalive_timeout returns default 60 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            assert FeatureFlags.get_keepalive_timeout() == 60

    def test_get_dns_cache_ttl_custom(self) -> None:
        """Test get_dns_cache_ttl returns custom value from env var."""
        with patch.dict(os.environ, {"KETCHUP_DNS_CACHE_TTL": "600"}):
            assert FeatureFlags.get_dns_cache_ttl() == 600

    def test_get_dns_cache_ttl_default(self) -> None:
        """Test get_dns_cache_ttl returns default 300 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            assert FeatureFlags.get_dns_cache_ttl() == 300


class TestSessionKeepAliveEnabled:
    """Unit tests for session creation with keep-alive tuning enabled."""

    @pytest.mark.asyncio
    async def test_session_creation_with_keepalive_enabled(self) -> None:
        """Test create_session_with_retries creates session with keep-alive settings."""
        with (
            patch.dict(
                os.environ,
                {
                    "KETCHUP_KEEPALIVE_ENABLED": "true",
                    "KETCHUP_KEEPALIVE_TIMEOUT": "60",
                    "KETCHUP_DNS_CACHE_TTL": "300",
                },
            ),
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_connector = MagicMock()
            mock_connector_class.return_value = mock_connector

            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session_class.return_value = mock_session

                session, error = await create_session_with_retries(
                    client_name="test_client",
                    semaphore_limit=10,
                    request_timeout_total=60.0,
                )

                # Verify session was created successfully
                assert session is mock_session
                assert error is None

                # Verify TCPConnector was called with keep-alive settings
                mock_connector_class.assert_called_once_with(
                    limit=10,
                    ttl_dns_cache=300,
                    enable_cleanup_closed=True,
                    force_close=False,
                    keepalive_timeout=60,
                )

    @pytest.mark.asyncio
    async def test_session_creation_with_custom_timeout(self) -> None:
        """Test session creation with custom keep-alive timeout."""
        with (
            patch.dict(
                os.environ,
                {
                    "KETCHUP_KEEPALIVE_ENABLED": "true",
                    "KETCHUP_KEEPALIVE_TIMEOUT": "120",
                    "KETCHUP_DNS_CACHE_TTL": "300",
                },
            ),
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_connector = MagicMock()
            mock_connector_class.return_value = mock_connector

            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session_class.return_value = mock_session

                session, error = await create_session_with_retries(
                    client_name="test_client",
                    semaphore_limit=10,
                )

                assert session is mock_session
                assert error is None

                # Verify custom timeout was used
                mock_connector_class.assert_called_once_with(
                    limit=10,
                    ttl_dns_cache=300,
                    enable_cleanup_closed=True,
                    force_close=False,
                    keepalive_timeout=120,
                )

    @pytest.mark.asyncio
    async def test_session_creation_with_custom_dns_cache(self) -> None:
        """Test session creation with custom DNS cache TTL."""
        with (
            patch.dict(
                os.environ,
                {
                    "KETCHUP_KEEPALIVE_ENABLED": "true",
                    "KETCHUP_KEEPALIVE_TIMEOUT": "60",
                    "KETCHUP_DNS_CACHE_TTL": "600",
                },
            ),
            patch("aiohttp.TCPConnector") as mock_connector_class,
        ):
            mock_connector = MagicMock()
            mock_connector_class.return_value = mock_connector

            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session_class.return_value = mock_session

                session, error = await create_session_with_retries(
                    client_name="test_client",
                    semaphore_limit=10,
                )

                assert session is mock_session
                assert error is None

                # Verify custom DNS cache TTL was used
                mock_connector_class.assert_called_once_with(
                    limit=10,
                    ttl_dns_cache=600,
                    enable_cleanup_closed=True,
                    force_close=False,
                    keepalive_timeout=60,
                )


class TestSessionKeepAliveDisabled:
    """Unit tests for session creation with keep-alive tuning disabled (legacy)."""

    @pytest.mark.asyncio
    async def test_session_creation_with_keepalive_disabled(self) -> None:
        """Test create_session_with_retries uses legacy behavior when disabled."""
        with patch.dict(os.environ, {"KETCHUP_KEEPALIVE_ENABLED": "false"}):
            with patch("aiohttp.TCPConnector") as mock_connector_class:
                mock_connector = MagicMock()
                mock_connector_class.return_value = mock_connector

                with patch("aiohttp.ClientSession") as mock_session_class:
                    mock_session = MagicMock()
                    mock_session.closed = False
                    mock_session_class.return_value = mock_session

                    session, error = await create_session_with_retries(
                        client_name="test_client",
                        semaphore_limit=10,
                        request_timeout_total=60.0,
                    )

                    # Verify session was created successfully
                    assert session is mock_session
                    assert error is None

                    # Verify TCPConnector was called with legacy settings (no keep-alive params)
                    mock_connector_class.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_session_creation_default_disabled(self) -> None:
        """Test session creation defaults to legacy behavior when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("aiohttp.TCPConnector") as mock_connector_class:
                mock_connector = MagicMock()
                mock_connector_class.return_value = mock_connector

                with patch("aiohttp.ClientSession") as mock_session_class:
                    mock_session = MagicMock()
                    mock_session.closed = False
                    mock_session_class.return_value = mock_session

                    session, error = await create_session_with_retries(
                        client_name="test_client",
                        semaphore_limit=10,
                    )

                    assert session is mock_session
                    assert error is None

                    # Verify legacy behavior (no keep-alive settings)
                    mock_connector_class.assert_called_once_with(limit=10)


class TestSessionKeepAliveLogging:
    """Unit tests for keep-alive logging."""

    @pytest.mark.asyncio
    async def test_logging_when_keepalive_enabled(self) -> None:
        """Test appropriate logging when keep-alive is enabled."""
        with (
            patch.dict(
                os.environ,
                {
                    "KETCHUP_KEEPALIVE_ENABLED": "true",
                    "KETCHUP_KEEPALIVE_TIMEOUT": "60",
                    "KETCHUP_DNS_CACHE_TTL": "300",
                },
            ),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession") as mock_session_class,
            patch("logging.Logger.info") as mock_logger_info,
        ):
            mock_session = MagicMock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session

            session, error = await create_session_with_retries(
                client_name="test_client",
                semaphore_limit=10,
            )

            assert session is mock_session
            assert error is None

            # Verify logging was called with keep-alive info
            log_calls = [str(call) for call in mock_logger_info.call_args_list]
            assert any(
                "Keep-alive tuning enabled" in call or "timeout=" in call for call in log_calls
            )

    @pytest.mark.asyncio
    async def test_logging_when_keepalive_disabled(self) -> None:
        """Test appropriate logging when keep-alive is disabled."""
        with patch.dict(os.environ, {"KETCHUP_KEEPALIVE_ENABLED": "false"}):
            with (
                patch("aiohttp.TCPConnector"),
                patch("aiohttp.ClientSession") as mock_session_class,
                patch("logging.Logger.debug") as mock_logger_debug,
            ):
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session_class.return_value = mock_session

                session, error = await create_session_with_retries(
                    client_name="test_client",
                    semaphore_limit=10,
                )

                assert session is mock_session
                assert error is None

                # Verify logging was called with legacy info
                log_calls = [str(call) for call in mock_logger_debug.call_args_list]
                assert any("legacy" in call.lower() for call in log_calls)


class TestSessionKeepAliveBackwardCompatibility:
    """Unit tests verifying backward compatibility."""

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_env_vars(self) -> None:
        """Test session creation works without any keep-alive env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("aiohttp.TCPConnector") as mock_connector_class:
                mock_connector = MagicMock()
                mock_connector_class.return_value = mock_connector

                with patch("aiohttp.ClientSession") as mock_session_class:
                    mock_session = MagicMock()
                    mock_session.closed = False
                    mock_session_class.return_value = mock_session

                    # This should work exactly as before
                    session, error = await create_session_with_retries(
                        client_name="test_client",
                        semaphore_limit=5,
                        request_timeout_total=30.0,
                    )

                    assert session is mock_session
                    assert error is None
                    mock_connector_class.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_backward_compatibility_existing_parameters(self) -> None:
        """Test existing parameters still work as expected."""
        with patch.dict(os.environ, {"KETCHUP_KEEPALIVE_ENABLED": "false"}):
            with (
                patch("aiohttp.TCPConnector"),
                patch("aiohttp.ClientSession") as mock_session_class,
                patch("aiohttp.ClientTimeout") as mock_timeout,
            ):
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session_class.return_value = mock_session

                session, error = await create_session_with_retries(
                    client_name="legacy_client",
                    semaphore_limit=20,
                    request_timeout_total=90.0,
                    max_retries=3,
                    initial_delay=2.0,
                )

                assert session is mock_session
                assert error is None

                # Verify timeout was configured correctly
                mock_timeout.assert_called_once_with(total=90.0)
