"""Access validation using Secrets Manager whitelist."""

import structlog

from asksplunk.secrets import SecretsManager

logger = structlog.get_logger()


class AccessValidator:
    """Validates user access against authorized whitelist.

    Uses SecretsManager to fetch the list of authorized Slack user IDs.
    Authorization checks always bypass cache to ensure freshness.

    Attributes:
        secrets_manager: SecretsManager instance for fetching authorized users
    """

    def __init__(self, secrets_manager: SecretsManager) -> None:
        """Initialize AccessValidator with SecretsManager.

        Args:
            secrets_manager: SecretsManager instance (must be within async context)
        """
        self.secrets_manager = secrets_manager

    async def is_authorized(self, user_id: str) -> bool:
        """Check if user_id is in the authorized list.

        Args:
            user_id: Slack user ID to check (e.g., "W7MGASQ2K")

        Returns:
            True if user is authorized, False otherwise
        """
        authorized_ids = await self.secrets_manager.get_authorised_slack_user_ids()
        is_auth = user_id in authorized_ids
        if not is_auth:
            logger.info("unauthorized_user", user=user_id)
        return is_auth
