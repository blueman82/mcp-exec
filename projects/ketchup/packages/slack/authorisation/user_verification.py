"""
user_verification.py

Database-backed user authorization with Slack user ID seed list.
"""

from packages.core.logging import setup_logger
from packages.db.user_store import UserStore
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


class UserVerifier:
    """
    Database-backed user verification using Slack user IDs.

    Authorization flow:
    1. Check if user exists in seed list from secrets (source of truth)
    2. If in seed list, ensure DB is updated to reflect authorization
    3. If not in seed list, ensure DB is updated to revoke authorization
    4. Return authorization status based on secrets
    """

    def __init__(self, user_store: UserStore, user_ops: SlackUserOps, secrets_manager):
        """
        Initialize UserVerifier with database and secrets manager.

        Args:
            user_store: Database store for user data
            user_ops: Slack operations for fetching user info
            secrets_manager: Secrets manager for fetching authorized users
        """
        self.user_store = user_store
        self.user_ops = user_ops
        self.secrets_manager = secrets_manager
        logger.info("UserVerifier initialized with secrets manager")

    async def validate_user_id(self, user_id: str) -> bool:
        """
        Check if user is authorized using secrets-first approach.

        Args:
            user_id: Slack user ID to validate

        Returns:
            True if authorized, False otherwise
        """
        logger.info(f"Validating authorization for user ID: {user_id}")

        try:
            # Step 1: ALWAYS check Secrets Manager first (source of truth)
            # Fetch fresh list from secrets manager instead of using cached value
            authorised_slack_user_ids = await self.secrets_manager.get_authorised_slack_user_ids()
            if user_id not in authorised_slack_user_ids:
                logger.info(f"User {user_id} is not in authorized seed list from secrets")

                # Update DB to reflect removal from secrets
                existing_user = await self.user_store.get_user(user_id)
                if existing_user and existing_user.get("authorized", False):
                    logger.info(f"Revoking database authorization for {user_id}")
                    await self.user_store.set_user_authorization(
                        user_id=user_id,
                        authorized=False,
                        real_name=existing_user.get("real_name"),
                    )

                return False

            # Step 2: User IS in the authorized list - ensure DB is updated
            logger.info(f"User {user_id} found in authorized seed list")

            # Check if user exists in DB
            existing_user = await self.user_store.get_user(user_id)

            if not existing_user:
                # Fetch user info from Slack and store
                logger.info(f"User {user_id} not in DB, fetching from Slack")
                user_info = await self.user_ops._fetch_user_info_internal(user_id)
                if user_info:
                    real_name = (
                        user_info.get("profile", {}).get("real_name")
                        or user_info.get("real_name")
                        or user_info.get("name")
                        or user_id
                    )
                    # Store new user with authorization
                    await self.user_store.store_user(
                        {"user_id": user_id, "real_name": real_name, "authorized": True}
                    )
                else:
                    logger.warning(f"Could not fetch user info from Slack for {user_id}")
                    # Still authorize but with minimal info
                    await self.user_store.store_user(
                        {"user_id": user_id, "real_name": user_id, "authorized": True}
                    )

            elif not existing_user.get("authorized", False):
                # User exists but not authorized - update authorization
                logger.info(f"Updating authorization for {user_id} in database")
                success = await self.user_store.set_user_authorization(
                    user_id=user_id,
                    authorized=True,
                    real_name=existing_user.get("real_name", user_id),
                )

                if not success:
                    logger.error(f"Failed to update authorization for user {user_id}")
                    # Still return True as they are in secrets (source of truth)

            logger.info(f"User {user_id} is authorized (from secrets)")
            return True

        except Exception as e:
            logger.error(f"Error validating user {user_id}: {e}")
            return False

    def validate_user(self, user_name: str) -> bool:
        """
        Legacy method for backward compatibility.
        This should not be used - use validate_user_id instead.
        """
        logger.warning(f"Legacy validate_user called with username: {user_name}")
        return False
