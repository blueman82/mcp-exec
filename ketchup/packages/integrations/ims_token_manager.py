"""
ims_token_manager.py

Manages IMS (Identity Management System) token lifecycle including
authentication, refresh, and storage.
"""

import time
from typing import Any, Dict, Optional

import aiohttp

from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


class IMSTokenManager:
    """Manages IMS authentication tokens with automatic refresh."""

    def __init__(self, secrets_manager: SecretsManager):
        """
        Initialize the IMS Token Manager.

        Args:
            secrets_manager: SecretsManager instance for accessing credentials
        """
        self.secrets_manager = secrets_manager
        self._token_cache: Dict[str, Any] = {}
        self.ims_base_url = "https://ims-na1.adobelogin.com"

    async def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if needed.

        Returns:
            Valid IMS access token

        Raises:
            Exception: If token refresh fails
        """
        logger.info("Checking IMS token validity")
        secrets = await self.secrets_manager.get_app_secrets()

        # Check if token is still valid (with 5 minute buffer)
        expires_at = int(secrets.get("IMS_TOKEN_EXPIRES_AT", 0))
        current_time = time.time()

        if expires_at > current_time + 300:  # 5 min buffer
            logger.info("IMS token is still valid")
            return secrets["IMS_ACCESS_TOKEN"]

        logger.info("IMS token expired or expiring soon, refreshing...")
        return await self._refresh_token()

    async def _refresh_token(self) -> str:
        """
        Refresh the IMS token using refresh token.

        Returns:
            New access token

        Raises:
            Exception: If refresh fails
        """
        secrets = await self.secrets_manager.get_app_secrets()
        refresh_token = secrets.get("IMS_REFRESH_TOKEN")

        if not refresh_token:
            logger.warning(
                "No refresh token available, attempting initial authentication"
            )
            return await self._initial_authentication()

        async with aiohttp.ClientSession() as session:
            data = {
                "client_id": secrets["IMS_CLIENT_ID"],
                "client_secret": secrets["IMS_CLIENT_SECRET"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            try:
                async with session.post(
                    f"{self.ims_base_url}/ims/token/v4",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"IMS token refresh failed: {response.status} - {error_text}"
                        )

                        if response.status == 400:
                            # Invalid refresh token, try initial authentication
                            logger.info(
                                "Refresh token invalid, attempting initial authentication"
                            )
                            return await self._initial_authentication()

                        raise Exception(f"IMS token refresh failed: {response.status}")

                    result = await response.json()
                    await self._update_tokens(result)
                    logger.info("IMS token refreshed successfully")
                    return result["access_token"]

            except aiohttp.ClientError as e:
                logger.error(f"Network error during token refresh: {e}")
                raise Exception(f"Failed to refresh IMS token: {e}")

    async def _initial_authentication(self) -> str:
        """
        Perform initial authentication using authorization code.

        Returns:
            New access token

        Raises:
            Exception: If authentication fails
        """
        secrets = await self.secrets_manager.get_app_secrets()

        async with aiohttp.ClientSession() as session:
            data = {
                "client_id": secrets["IMS_CLIENT_ID"],
                "client_secret": secrets["IMS_CLIENT_SECRET"],
                "code": secrets["IMS_CODE"],
                "grant_type": "authorization_code",
            }

            try:
                async with session.post(
                    f"{self.ims_base_url}/ims/token/v4",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"IMS initial authentication failed: {response.status} - {error_text}"
                        )
                        raise Exception(f"IMS authentication failed: {response.status}")

                    result = await response.json()
                    await self._update_tokens(result)
                    logger.info("IMS initial authentication successful")
                    return result["access_token"]

            except aiohttp.ClientError as e:
                logger.error(f"Network error during initial authentication: {e}")
                raise Exception(f"Failed to authenticate with IMS: {e}")

    async def _update_tokens(self, token_response: Dict[str, Any]) -> None:
        """
        Update stored tokens with new values in AWS Secrets Manager.

        Args:
            token_response: Response from IMS token endpoint
        """
        # Calculate expiration time
        expires_in = token_response.get("expires_in", 3600)
        expires_at = int(time.time() + expires_in)

        # Cache tokens
        self._token_cache = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response.get("refresh_token", ""),
            "expires_at": expires_at,
        }

        logger.info(f"Tokens updated, expires at: {expires_at}")

        # Update AWS Secrets Manager
        try:
            await self.secrets_manager.update_secret(
                {
                    "ims_access_token": token_response["access_token"],
                    "ims_refresh_token": token_response.get("refresh_token", ""),
                    "ims_token_expires_at": str(
                        expires_at
                    ),  # Store as string for JSON compatibility
                }
            )
            logger.info("Successfully updated IMS tokens in AWS Secrets Manager")
        except Exception as e:
            logger.error(f"Failed to update tokens in AWS Secrets Manager: {e}")
            # Continue execution even if update fails - we have the tokens cached

    def get_cached_token(self) -> Optional[str]:
        """
        Get cached token if available and valid.

        Returns:
            Cached access token or None if not available/expired
        """
        if not self._token_cache:
            return None

        expires_at = self._token_cache.get("expires_at", 0)
        if expires_at > time.time() + 300:  # 5 min buffer
            return self._token_cache.get("access_token")

        return None
