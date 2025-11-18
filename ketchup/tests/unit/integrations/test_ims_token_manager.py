"""Unit tests for the async IMS token manager built on AsyncClient."""

import time
from unittest.mock import AsyncMock

import pytest

from packages.core.exceptions import ClientError
from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager

pytestmark = pytest.mark.unit


class TestAsyncIMSTokenManager:
    """Test coverage for AsyncIMSTokenManager behaviour."""

    @pytest.fixture()
    def mock_secrets_manager(self):
        """Provide a mock SecretsManager implementation."""

        secrets_manager = AsyncMock()
        secrets_manager.get_app_secrets = AsyncMock(
            return_value={
                "IMS_CLIENT_ID": "test_client",
                "IMS_CLIENT_SECRET": "test_secret",
                "IMS_CODE": "test_code",
                "IMS_ACCESS_TOKEN": "valid_token",
                "IMS_REFRESH_TOKEN": "refresh_token",
                "IMS_TOKEN_EXPIRES_AT": time.time() + 3600,
            }
        )
        secrets_manager.update_secret = AsyncMock()
        return secrets_manager

    @pytest.fixture()
    def manager(self, mock_secrets_manager):
        """Create a manager instance for tests."""

        mgr = AsyncIMSTokenManager(secrets_manager=mock_secrets_manager)
        return mgr

    @pytest.mark.asyncio
    async def test_get_valid_token_not_expired(self, manager, mock_secrets_manager):
        """Ensure cached token is returned when still valid."""

        token = await manager.get_valid_token()

        assert token == "valid_token"
        mock_secrets_manager.get_app_secrets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_valid_token_expired(self, manager, mock_secrets_manager, mocker):
        """Verify refresh is triggered when token is expired."""

        mock_secrets_manager.get_app_secrets.return_value["IMS_TOKEN_EXPIRES_AT"] = (
            time.time() - 100
        )

        mocker.patch.object(
            manager, "_refresh_token", AsyncMock(return_value="new_token")
        )

        token = await manager.get_valid_token()

        assert token == "new_token"
        manager._refresh_token.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_get_valid_token_near_expiry(self, manager, mock_secrets_manager, mocker):
        """Confirm refresh when token is inside five-minute buffer."""

        mock_secrets_manager.get_app_secrets.return_value["IMS_TOKEN_EXPIRES_AT"] = (
            time.time() + 120
        )

        mocker.patch.object(
            manager, "_refresh_token", AsyncMock(return_value="buffer_refresh")
        )

        token = await manager.get_valid_token()

        assert token == "buffer_refresh"
        manager._refresh_token.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, manager, mocker):
        """Successful refresh should parse response and update cache."""

        mocker.patch.object(
            manager,
            "_make_api_request",
            AsyncMock(
                return_value={
                    "status": 200,
                    "headers": {},
                    "body": b'{"access_token": "new", "refresh_token": "new_r", "expires_in": 3600}',
                    "content_type": "application/json",
                    "url": "https://ims-na1.adobelogin.com/ims/token/v4",
                }
            ),
        )
        mock_update = mocker.patch.object(manager, "_update_tokens", AsyncMock())

        token = await manager._refresh_token()

        assert token == "new"
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_refresh_triggers_initial_auth(self, manager, mocker):
        """400 response should fall back to initial authentication."""

        mocker.patch.object(
            manager,
            "_make_api_request",
            AsyncMock(
                return_value={
                    "status": 400,
                    "headers": {},
                    "body": b"Invalid refresh token",
                    "content_type": "text/plain",
                    "url": "https://example",
                }
            ),
        )
        mock_auth = mocker.patch.object(
            manager, "_initial_authentication", AsyncMock(return_value="fresh")
        )

        token = await manager._refresh_token()

        assert token == "fresh"
        mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_network_error(self, manager, mocker):
        """ClientError raises wrapped exception."""

        mocker.patch.object(
            manager,
            "_make_api_request",
            AsyncMock(side_effect=ClientError("failure")),
        )

        with pytest.raises(Exception) as exc:
            await manager._refresh_token()

        assert "Failed to refresh IMS token" in str(exc.value)

    @pytest.mark.asyncio
    async def test_initial_authentication_success(self, manager, mocker):
        """Initial auth should update tokens and return access token."""

        mocker.patch.object(
            manager,
            "_make_api_request",
            AsyncMock(
                return_value={
                    "status": 200,
                    "headers": {},
                    "body": b'{"access_token": "init", "refresh_token": "init_r", "expires_in": 3600}',
                    "content_type": "application/json",
                    "url": "https://ims-na1.adobelogin.com/ims/token/v4",
                }
            ),
        )
        mock_update = mocker.patch.object(manager, "_update_tokens", AsyncMock())

        token = await manager._initial_authentication()

        assert token == "init"
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_initial_authentication_failure(self, manager, mocker):
        """Non-200 initial auth response raises exception."""

        mocker.patch.object(
            manager,
            "_make_api_request",
            AsyncMock(
                return_value={
                    "status": 401,
                    "headers": {},
                    "body": b"Invalid",
                    "content_type": "text/plain",
                    "url": "https://example",
                }
            ),
        )

        with pytest.raises(Exception) as exc:
            await manager._initial_authentication()

        assert "IMS authentication failed: 401" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_tokens_persists_cache(self, manager, mocker, mock_secrets_manager):
        """Ensure tokens cached and secrets manager updated."""

        mocker.patch("time.time", return_value=1000)

        await manager._update_tokens(
            {
                "access_token": "updated",
                "refresh_token": "updated_r",
                "expires_in": 7200,
            }
        )

        assert manager._token_cache["access_token"] == "updated"
        assert manager._token_cache["expires_at"] == 1000 + 7200
        mock_secrets_manager.update_secret.assert_called_once()

    def test_get_cached_token_valid(self, manager):
        """Return cached token when still valid."""

        manager._token_cache = {
            "access_token": "cached",
            "expires_at": time.time() + 400,
        }

        assert manager.get_cached_token() == "cached"

    def test_get_cached_token_expired(self, manager):
        """Expired cached token returns None."""

        manager._token_cache = {
            "access_token": "stale",
            "expires_at": time.time() - 10,
        }

        assert manager.get_cached_token() is None

    def test_get_cached_token_empty(self, manager):
        """Empty cache returns None."""

        manager._token_cache = {}

        assert manager.get_cached_token() is None
