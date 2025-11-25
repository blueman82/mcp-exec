"""
slack_config.py

This module provides a SlackConfig class for storing and accessing
Slack-related configuration values securely loaded from SecretsManager.
"""

from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)


class SlackConfig:
    """
    A configuration class for managing Slack API credentials and settings.
    Credentials are now loaded per instance via SecretsManager.
    """

    def __init__(self, secrets_manager: SecretsManager, api_token: str, headers: dict):
        """
        Initialize SlackConfig using the provided SecretsManager instance and token/headers.

        Args:
            secrets_manager: An instance of SecretsManager.
            api_token: The Slack API token.
            headers: The headers dict for Slack API requests.
        """
        self.secrets_manager = secrets_manager
        self.api_token: str = api_token
        self.headers: dict = headers
        self.api_base_url: str = "https://slack.com/api"
        logger.info("SlackConfig initialized with instance-specific token.")

    @classmethod
    async def create(cls, secrets_manager: SecretsManager) -> "SlackConfig":
        """
        Async factory for SlackConfig.
        """
        try:
            api_token = await secrets_manager.get_slack_api_token_async()
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            return cls(secrets_manager, api_token, headers)
        except Exception as e:
            logger.error("Error initializing SlackConfig: %s", e)
            raise

    def get_headers(self) -> dict:
        """Returns headers initialized for this specific instance."""
        if not self.headers:
            raise RuntimeError("SlackConfig headers were not properly initialized.")
        return self.headers

    def get_api_base_url(self) -> str:
        """Returns the base URL configured for this instance."""
        return self.api_base_url
