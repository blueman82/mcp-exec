"""Async IMS token manager built on top of the shared AsyncClient."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import orjson

from packages.core.async_client import AsyncClient
from packages.core.exceptions import ClientError
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


@dataclass
class IMSTokenManagerConfig:
    """Configuration container for the async IMS token manager."""

    secrets_manager: SecretsManager
    ims_base_url: str = "https://ims-na1.adobelogin.com"

    def as_dict(self) -> Dict[str, Any]:
        """Return config values as a dictionary.

        Returns:
            Dict[str, Any]: Mapping of configuration fields for logging.
        """

        return {
            "ims_base_url": self.ims_base_url,
        }


class AsyncIMSTokenManager(AsyncClient[IMSTokenManagerConfig, Dict[str, Any]]):
    """Manage IMS authentication tokens using shared httpx session handling."""

    def __init__(
        self,
        secrets_manager: SecretsManager,
        ims_base_url: str = "https://ims-na1.adobelogin.com",
        max_concurrent_requests: int = 2,
        request_timeout: int = 30,
    ) -> None:
        """Initialise the token manager with AsyncClient infrastructure.

        Args:
            secrets_manager: Secrets manager providing IMS credentials and tokens.
            ims_base_url: Base URL for IMS token endpoints.
            max_concurrent_requests: Maximum concurrent HTTP requests.
            request_timeout: Request timeout in seconds.
        """
        logger.info(
            "Initializing AsyncIMSTokenManager (NEW ASYNC IMPLEMENTATION) with ims_base_url=%s, "
            "max_concurrent_requests=%d, request_timeout=%d",
            ims_base_url,
            max_concurrent_requests,
            request_timeout,
        )
        config = IMSTokenManagerConfig(
            secrets_manager=secrets_manager,
            ims_base_url=ims_base_url.rstrip("/"),
        )
        super().__init__(
            config=config,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
        )
        self._token_cache: Dict[str, Any] = {}
        logger.info(
            "AsyncIMSTokenManager initialization complete - ready for httpx-based IMS token operations"
        )

    @property
    def secrets_manager(self) -> SecretsManager:
        """Expose the secrets manager from the configuration.

        Returns:
            SecretsManager: The secrets manager instance.
        """

        return self.config.secrets_manager

    @property
    def ims_base_url(self) -> str:
        """Base URL for IMS token endpoints.

        Returns:
            str: Normalised IMS base URL without trailing slash.
        """

        return self.config.ims_base_url

    async def get_valid_token(self) -> str:
        """Return a valid IMS access token, refreshing when necessary.

        Returns:
            str: Active IMS access token suitable for authenticated calls.
        """

        logger.info("Checking IMS token validity")
        cached_token = self.get_cached_token()
        if cached_token:
            logger.info("Using cached IMS token")
            return cached_token

        secrets = await self.secrets_manager.get_app_secrets()

        expires_at = int(secrets.get("IMS_TOKEN_EXPIRES_AT", 0))
        current_time = time.time()

        if expires_at > current_time + 300:
            logger.info("IMS token is still valid")
            return secrets["IMS_ACCESS_TOKEN"]

        logger.info("IMS token expired or expiring soon, refreshing…")
        return await self._refresh_token()

    async def _refresh_token(self) -> str:
        """Refresh the IMS token using the stored refresh token.

        Returns:
            str: Newly refreshed access token.

        Raises:
            Exception: If the refresh fails and no fallback is available.
        """

        secrets = await self.secrets_manager.get_app_secrets()
        refresh_token = secrets.get("IMS_REFRESH_TOKEN")

        if not refresh_token:
            logger.warning("No refresh token available, attempting initial authentication")
            return await self._initial_authentication()

        payload = {
            "client_id": secrets["IMS_CLIENT_ID"],
            "client_secret": secrets["IMS_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = await self._make_api_request(
                url=f"{self.ims_base_url}/ims/token/v4",
                method="POST",
                data=payload,
            )
        except ClientError as exc:
            logger.error("Network error during token refresh: %s", exc)
            raise Exception(f"Failed to refresh IMS token: {exc}") from exc

        if response["status"] != 200:
            error_text = response["body"].decode(errors="ignore")
            logger.error("IMS token refresh failed: %s - %s", response["status"], error_text)

            if response["status"] == 400:
                logger.info("Refresh token invalid, attempting initial authentication")
                return await self._initial_authentication()

            raise Exception(f"IMS token refresh failed: {response['status']}")

        result = self._parse_json(response)
        await self._update_tokens(result)
        logger.info("IMS token refreshed successfully")
        return result["access_token"]

    async def _initial_authentication(self) -> str:
        """Perform a fresh IMS authentication using the authorization code.

        Returns:
            str: Newly issued access token from IMS.

        Raises:
            Exception: If the IMS service rejects the authentication request.
        """

        secrets = await self.secrets_manager.get_app_secrets()
        payload = {
            "client_id": secrets["IMS_CLIENT_ID"],
            "client_secret": secrets["IMS_CLIENT_SECRET"],
            "code": secrets["IMS_CODE"],
            "grant_type": "authorization_code",
        }

        try:
            response = await self._make_api_request(
                url=f"{self.ims_base_url}/ims/token/v4",
                method="POST",
                data=payload,
            )
        except ClientError as exc:
            logger.error("Network error during initial authentication: %s", exc)
            raise Exception(f"Failed to authenticate with IMS: {exc}") from exc

        if response["status"] != 200:
            error_text = response["body"].decode(errors="ignore")
            logger.error(
                "IMS initial authentication failed: %s - %s",
                response["status"],
                error_text,
            )
            raise Exception(f"IMS authentication failed: {response['status']}")

        result = self._parse_json(response)
        await self._update_tokens(result)
        logger.info("IMS initial authentication successful")
        return result["access_token"]

    async def _update_tokens(self, token_response: Dict[str, Any]) -> None:
        """Persist refreshed tokens and update the in-memory cache.

        Args:
            token_response: Token payload returned by IMS API.
        """

        expires_in = token_response.get("expires_in", 3600)
        expires_at = int(time.time() + expires_in)

        self._token_cache = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response.get("refresh_token", ""),
            "expires_at": expires_at,
        }

        logger.info("Tokens updated, expires at: %s", expires_at)

        try:
            await self.secrets_manager.update_secret(
                {
                    "ims_access_token": token_response["access_token"],
                    "ims_refresh_token": token_response.get("refresh_token", ""),
                    "ims_token_expires_at": str(expires_at),
                }
            )
            logger.info("Successfully updated IMS tokens in AWS Secrets Manager")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to update tokens in AWS Secrets Manager: %s", exc)

    def get_cached_token(self) -> Optional[str]:
        """Return a cached token if it remains valid for at least five minutes.

        Returns:
            Optional[str]: Cached access token or ``None`` if missing/expired.
        """

        if not self._token_cache:
            return None

        expires_at = self._token_cache.get("expires_at", 0)
        if expires_at > time.time() + 300:
            return self._token_cache.get("access_token")

        return None

    @staticmethod
    def _parse_json(response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a SafeResponse body into JSON, raising on decode errors.

        Args:
            response: SafeResponse-like mapping returned by AsyncClient.

        Returns:
            Dict[str, Any]: Parsed JSON payload.

        Raises:
            Exception: If the response body is not valid JSON.
        """

        try:
            return orjson.loads(response["body"])
        except orjson.JSONDecodeError as exc:  # pragma: no cover - unexpected path
            logger.error("Failed to parse IMS response body: %s", exc)
            raise Exception("Invalid IMS response payload") from exc
