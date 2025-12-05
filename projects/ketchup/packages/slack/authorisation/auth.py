"""
auth.py

This module contains the SlackAuth class, which is used to verify Slack signatures.
"""

import hashlib
import hmac
import time
from typing import Any, Dict, Optional

from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


class SlackAuth:
    """
    A class for handling Slack authentication logic, including signature verification.
    """

    def __init__(self, secrets_manager: SecretsManager) -> None:
        """
        Initialize SlackAuth with a SecretsManager instance.

        :param secrets_manager: The SecretsManager instance (required).
        """
        self._secrets_manager = secrets_manager
        self._slack_signing_secret: Optional[str] = None

    async def get_slack_signing_secret(self) -> Optional[str]:
        """
        Get the Slack signing secret, using cache if available.

        Uses the injected SecretsManager to fetch the main application secrets
        bundle and extracts the required key.

        :return: The retrieved Slack signing secret or None if retrieval fails
        """
        # Use the cached value if available
        if self._slack_signing_secret:
            return self._slack_signing_secret

        logger.info("Fetching Slack signing secret via SecretsManager.get_app_secrets()")
        try:
            # Use the injected secrets_manager instance and its method
            app_secrets = await self._secrets_manager.get_app_secrets()
            self._slack_signing_secret = app_secrets.get("SLACK_SIGNING_SECRET")
            if self._slack_signing_secret:
                logger.debug("Slack signing secret retrieved successfully.")
                return self._slack_signing_secret
            else:
                logger.error("SLACK_SIGNING_SECRET key not found in app secrets bundle.")
                return None
        except Exception as e:
            logger.error(
                "Failed to retrieve app secrets or signing secret key: %s",
                e,
                exc_info=True,
            )
            self._slack_signing_secret = None  # Ensure cache is None on error
            return None

    async def verify_slack_signature(self, headers: Dict[str, Any], raw_body_bytes: bytes) -> bool:
        """
        Verify the signature of an incoming Slack request.

        Args:
            headers: The headers from the incoming request.
            raw_body_bytes: The raw byte string of the request body.

        Returns:
            True if the signature is valid, False otherwise.
        """
        # Log entry point and received types/lengths for debugging
        #   logger.info("Entering verify_slack_signature")
        # logger.info("Headers type: %s, Keys: %s", type(headers), list(headers.keys()))
        # logger.info(
        #     "raw_body_bytes type: %s, length: %s",
        #     type(raw_body_bytes),
        #     len(raw_body_bytes),
        # )

        # Use lowercase keys matching AWS API Gateway event structure
        timestamp = headers.get("x-slack-request-timestamp")
        signature = headers.get("x-slack-signature")

        if not timestamp or not signature:
            logger.warning("Missing timestamp or signature in headers")
            return False

        # Check timestamp validity (within 5 minutes)
        try:
            if abs(time.time() - int(timestamp)) > 60 * 5:
                logger.warning("Timestamp validation failed: %s", timestamp)
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp format: %s", timestamp)
            return False

        try:
            signing_secret = await self.get_slack_signing_secret()
            if signing_secret is None:
                logger.error("Failed to retrieve Slack signing secret for verification.")
                return False

            logger.debug("Slack signature verification inputs:")
            logger.debug("x-slack-signature: %s", headers.get("x-slack-signature"))
            logger.debug(
                "x-slack-request-timestamp: %s",
                headers.get("x-slack-request-timestamp"),
            )
            sig_basestring = f"v0:{headers.get('x-slack-request-timestamp')}:{raw_body_bytes.decode('utf-8', errors='replace')}"

            my_signature = (
                "v0="
                + hmac.new(
                    signing_secret.encode("utf-8"),
                    sig_basestring.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
            )
        except Exception as e:
            logger.error(
                "Error generating signature for verification: %s",
                e,
                exc_info=True,
            )
            return False

        is_valid = hmac.compare_digest(my_signature, signature)
        if not is_valid:
            logger.warning(
                "Signature mismatch. Calculated: %s, Received: %s",
                my_signature,
                signature,
            )
        else:
            logger.debug("Slack signature verification successful")

        return is_valid
