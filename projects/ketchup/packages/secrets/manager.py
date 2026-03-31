"""
manager.py

This module provides a class-based approach to retrieving and managing secrets
from AWS Secrets Manager.
"""

import json
import time

import aioboto3  # type: ignore[import-untyped]

from packages.core.constants import AWS_REGION, AWS_SECRET_NAME

# import boto3
from packages.core.logging import setup_logger

# Set up module logger
logger = setup_logger(__name__)


class SecretsManager:
    """
    A class to manage retrieval of secrets from AWS Secrets Manager.

    This class provides both synchronous and asynchronous methods for retrieving
    secrets from AWS Secrets Manager. It also includes convenience methods for
    retrieving specific application secrets.
    """

    # Secret names
    APP_SECRETS_NAME = AWS_SECRET_NAME

    def __init__(self, region_name=AWS_REGION):
        """
        Initialize the SecretsManager with the AWS region.

        :param region_name: The AWS region name to use for AWS clients.
        """
        self.region_name = region_name
        self._secrets_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._cache_timestamp = 0

    async def get_secret_async(self, secret_name):
        """
        Retrieve a secret from AWS Secrets Manager asynchronously.

        :param secret_name: The name of the secret to retrieve.
        :return: A dictionary containing the secret information.
        :raises Exception: If the secret cannot be retrieved.
        """
        start_message = "Starting get_secret_async function."
        logger.info(start_message)

        # Create a new session and client for AWS Secrets Manager
        # Use AWS profile from environment if available
        import os

        profile_name = os.environ.get("AWS_PROFILE")
        session = (
            aioboto3.Session(profile_name=profile_name) if profile_name else aioboto3.Session()
        )
        async with session.client(
            service_name="secretsmanager", region_name=self.region_name
        ) as client:
            try:
                # Attempt to get the secret value from AWS Secrets Manager
                get_secret_value_response = await client.get_secret_value(SecretId=secret_name)
                # If the secret is stored as a string, parse it as JSON and return the dictionary
                if "SecretString" in get_secret_value_response:
                    return json.loads(get_secret_value_response["SecretString"])
                # If SecretString is missing, raise KeyError
                raise KeyError("SecretString not found in secret value response")
            except Exception as e:
                logger.error("Unable to retrieve secret asynchronously: %s", e)
                raise

    async def get_app_secrets(self):
        """
        Retrieve all application secrets from AWS Secrets Manager with caching.

        :return: A dictionary containing all application secrets.
        :raises Exception: If the secrets cannot be retrieved.
        """
        current_time = time.time()

        # Check if we have a valid cache
        if self._secrets_cache and (current_time - self._cache_timestamp) < self._cache_ttl:
            logger.info(
                "Returning cached secrets (age: %.1f seconds)",
                current_time - self._cache_timestamp,
            )
            return self._secrets_cache

        start_message = "Starting get_app_secrets function."
        logger.info(start_message)

        try:
            secrets_async = await self.get_secret_async(self.APP_SECRETS_NAME)
            logger.info("Application secrets retrieved successfully from AWS Secrets Manager.")
        except Exception as e:
            logger.error("Failed to retrieve application secrets: %s", e)
            raise

        # Map the secrets to expected keys
        try:
            # Helper function to parse JSON-encoded strings
            def parse_json_field(value, default=None):
                """Parse a JSON-encoded string field, returning default if parsing fails."""
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON field: {value}")
                        return default
                return value if value is not None else default

            secrets_dict = {
                "SLACK_SIGNING_SECRET": secrets_async["slack_signing_secret"],
                "SLACK_API_TOKEN": secrets_async["slack_api_token"],
                "SLACK_USER_API_TOKEN": secrets_async["slack_user_api_token"],
                "APP_BOT_USER_ID": secrets_async["slack_bot_app_id"],
                "EXIGENCE_USER_ID": secrets_async["exigence_user_id"],
                "AZURE_OPENAI_LB_API_KEY": secrets_async["azure_openai_lb_api_key"],
                "BOT_SLACK_USER_ID": secrets_async["bot_slack_user_id"],
                # New IMS and iPaaS secrets
                "IMS_CLIENT_ID": secrets_async.get("ims_client_id", "ketchup_prod"),
                "IMS_CLIENT_SECRET": secrets_async.get("ims_client_secret", ""),
                "IMS_CODE": secrets_async.get("ims_code", ""),
                "IPAAS_USERNAME": secrets_async.get("ipaas_username", "ketchup"),
                "IPAAS_PASSWORD": secrets_async.get("ipaas_password", ""),
                "IPAAS_API_KEY": secrets_async.get("ipaas_api_key", ""),
                "IMS_ACCESS_TOKEN": secrets_async.get("ims_access_token", ""),
                "IMS_REFRESH_TOKEN": secrets_async.get("ims_refresh_token", ""),
                "IMS_TOKEN_EXPIRES_AT": secrets_async.get("ims_token_expires_at", 0),
                # Usage stats admin users - parse JSON-encoded string
                "USAGE_STATS_ADMIN_USERS": parse_json_field(
                    secrets_async.get("usage_stats_admin_users"), default=[]
                ),
                # Authorized Slack user IDs - parse JSON-encoded string
                "AUTHORISED_SLACK_USER_IDS": parse_json_field(
                    secrets_async.get("authorised_slack_user_ids"), default=[]
                ),
                # Authorized LDAP usernames backup - parse JSON-encoded string
                "AUTHORISED_USERS_LDAP_BACKUP": parse_json_field(
                    secrets_async.get("authorised_users_ldap_backup"), default=[]
                ),
                "SLACK_WEBHOOK_URL": secrets_async.get("slack_webhook_url", ""),
            }

            # Update cache
            self._secrets_cache = secrets_dict
            self._cache_timestamp = current_time
            logger.info("Secrets cache updated")

            return secrets_dict
        except Exception as e:
            logger.error("Failed to retrieve application secrets: %s", e)
            raise

    # Specific async secret getter methods
    async def get_slack_signing_secret(self):
        """Get the Slack signing secret asynchronously."""
        start_message = "Starting get_slack_signing_secret function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["SLACK_SIGNING_SECRET"]

    async def get_authorised_users(self):
        """Get the list of authorised users asynchronously."""
        start_message = "Starting get_authorised_users function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["AUTHORISED_USERS"]

    async def get_slack_api_token_async(self):
        """Get the Slack API token asynchronously."""
        start_message = "Starting get_slack_api_token_async function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["SLACK_API_TOKEN"]

    async def get_slack_user_api_token(self):
        """Get the Slack user API token asynchronously."""
        start_message = "Starting get_slack_user_api_token function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["SLACK_USER_API_TOKEN"]

    async def get_exigence_user_id_async(self):
        """Get the exigence user ID asynchronously."""
        start_message = "Starting get_exigence_user_id_async function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["EXIGENCE_USER_ID"]

    async def get_azure_openai_lb_api_key(self):
        """Get the Azure OpenAI LB API key asynchronously."""
        start_message = "Starting get_azure_openai_lb_api_key function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["AZURE_OPENAI_LB_API_KEY"]

    async def get_new_relic_api_key(self):
        """Get the New Relic API key asynchronously."""
        logger.info("Starting get_new_relic_api_key function.")
        secrets = await self.get_app_secrets()
        return secrets["NEW_RELIC_API_KEY"]

    async def get_new_relic_account_id(self):
        """Get the New Relic account ID asynchronously."""
        logger.info("Starting get_new_relic_account_id function.")
        secrets = await self.get_app_secrets()
        return secrets["NEW_RELIC_ACCOUNT_ID"]

    async def get_bot_slack_user_id_async(self):
        """Get the bot Slack user ID asynchronously."""
        start_message = "Starting get_bot_slack_user_id_async function."
        logger.info(start_message)

        secrets = await self.get_app_secrets()
        return secrets["BOT_SLACK_USER_ID"]

    async def get_authorised_slack_user_ids(self):
        """Get the list of authorised Slack user IDs asynchronously.

        This method bypasses the cache to ensure authorization checks
        always use the most current data from AWS Secrets Manager.
        """
        logger.info("Starting get_authorised_slack_user_ids function.")

        # Bypass cache for authorization lists - always fetch fresh
        try:
            secrets_async = await self.get_secret_async(self.APP_SECRETS_NAME)
            logger.info("Fetched fresh authorization list from AWS Secrets Manager.")

            # Parse the JSON-encoded list
            if isinstance(secrets_async.get("authorised_slack_user_ids"), str):
                try:
                    return json.loads(secrets_async["authorised_slack_user_ids"])
                except json.JSONDecodeError:
                    logger.warning("Failed to parse authorised_slack_user_ids JSON")
                    return []
            return secrets_async.get("authorised_slack_user_ids", [])
        except Exception as e:
            logger.error("Failed to retrieve authorised user IDs: %s", e)
            # Fall back to cached version if fetch fails
            secrets = await self.get_app_secrets()
            return secrets["AUTHORISED_SLACK_USER_IDS"]

    async def get_authorised_users_ldap_backup(self):
        """Get the list of authorised LDAP usernames asynchronously.

        This method bypasses the cache to ensure authorization checks
        always use the most current data from AWS Secrets Manager.
        """
        logger.info("Starting get_authorised_users_ldap_backup function.")

        # Bypass cache for authorization lists - always fetch fresh
        try:
            secrets_async = await self.get_secret_async(self.APP_SECRETS_NAME)
            logger.info("Fetched fresh LDAP backup list from AWS Secrets Manager.")

            # Parse the JSON-encoded list
            if isinstance(secrets_async.get("authorised_users_ldap_backup"), str):
                try:
                    return json.loads(secrets_async["authorised_users_ldap_backup"])
                except json.JSONDecodeError:
                    logger.warning("Failed to parse authorised_users_ldap_backup JSON")
                    return []
            return secrets_async.get("authorised_users_ldap_backup", [])
        except Exception as e:
            logger.error("Failed to retrieve LDAP backup user list: %s", e)
            # Fall back to cached version if fetch fails
            secrets = await self.get_app_secrets()
            return secrets["AUTHORISED_USERS_LDAP_BACKUP"]

    async def get_slack_webhook_url(self):
        """Get the Slack webhook URL asynchronously."""
        secrets = await self.get_app_secrets()
        return secrets.get("SLACK_WEBHOOK_URL", "")

    async def update_secret(self, updates: dict) -> None:
        """
        Update specific values within the application secret.

        This method retrieves the current secret, updates specified values,
        and writes the updated secret back to AWS Secrets Manager.

        Args:
            updates: Dictionary of key-value pairs to update in the secret

        Raises:
            Exception: If the secret cannot be updated
        """
        logger.info("Starting update_secret function with %d updates", len(updates))

        # Use AWS profile from environment if available
        import os

        profile_name = os.environ.get("AWS_PROFILE")
        session = (
            aioboto3.Session(profile_name=profile_name) if profile_name else aioboto3.Session()
        )
        async with session.client(
            service_name="secretsmanager", region_name=self.region_name
        ) as client:
            try:
                # First, get the current secret
                get_response = await client.get_secret_value(SecretId=self.APP_SECRETS_NAME)

                if "SecretString" not in get_response:
                    raise KeyError("SecretString not found in secret value response")

                # Parse current secret
                current_secret = json.loads(get_response["SecretString"])

                # Update with new values
                for key, value in updates.items():
                    current_secret[key] = value
                    logger.info("Updated %s in secret", key)

                # Write back the updated secret
                await client.update_secret(
                    SecretId=self.APP_SECRETS_NAME,
                    SecretString=json.dumps(current_secret),
                )

                logger.info(
                    "Successfully updated %d values in AWS Secrets Manager",
                    len(updates),
                )

            except Exception as e:
                logger.error("Failed to update secret: %s", e)
                raise

    async def add_authorized_user(self, user_id: str) -> bool:
        """
        Add a user to the authorized users list.

        This method safely adds a user ID to the AUTHORISED_SLACK_USER_IDS list,
        ensuring no duplicates and preserving the existing list.

        Args:
            user_id: The Slack user ID to add

        Returns:
            bool: True if user was added, False if already existed

        Raises:
            Exception: If the update fails
        """
        logger.info("Starting add_authorized_user for user: %s", user_id)

        try:
            # Get current authorized users
            current_users = await self.get_authorised_slack_user_ids()

            # Check if user already exists
            if user_id in current_users:
                logger.info("User %s already in authorized list", user_id)
                return False

            # Add the new user
            updated_users = current_users.copy()
            updated_users.append(user_id)

            # Update the secret with JSON-encoded list
            await self.update_secret({"authorised_slack_user_ids": json.dumps(updated_users)})

            # Invalidate cache to force refresh on next access
            self._secrets_cache = {}
            self._cache_timestamp = 0

            logger.info("Successfully added user %s to authorized list", user_id)
            return True

        except Exception as e:
            logger.error("Failed to add authorized user %s: %s", user_id, e)
            raise

    async def add_authorized_user_with_ldap(self, user_id: str, ldap_username: str) -> bool:
        """
        Add a user to both the authorized Slack users list and LDAP backup list.

        This method safely adds a user ID to the AUTHORISED_SLACK_USER_IDS list
        and their LDAP username to the AUTHORISED_USERS_LDAP_BACKUP list,
        ensuring no duplicates and preserving the existing lists.

        Args:
            user_id: The Slack user ID to add
            ldap_username: The LDAP username to add

        Returns:
            bool: True if user was added, False if already existed in both lists

        Raises:
            Exception: If the update fails
        """
        logger.info(
            "Starting add_authorized_user_with_ldap for user: %s, ldap: %s",
            user_id,
            ldap_username,
        )

        try:
            # Get current lists
            current_slack_users = await self.get_authorised_slack_user_ids()
            current_ldap_users = await self.get_authorised_users_ldap_backup()

            # Check if user already exists in both lists
            slack_exists = user_id in current_slack_users
            ldap_exists = ldap_username in current_ldap_users

            if slack_exists and ldap_exists:
                logger.info(
                    "User %s (ldap: %s) already in both authorized lists",
                    user_id,
                    ldap_username,
                )
                return False

            # Update lists
            updated_slack_users = current_slack_users.copy()
            updated_ldap_users = current_ldap_users.copy()

            if not slack_exists:
                updated_slack_users.append(user_id)
            if not ldap_exists:
                updated_ldap_users.append(ldap_username)

            # Update the secret with both JSON-encoded lists
            await self.update_secret(
                {
                    "authorised_slack_user_ids": json.dumps(updated_slack_users),
                    "authorised_users_ldap_backup": json.dumps(updated_ldap_users),
                }
            )

            # Invalidate cache to force refresh on next access
            self._secrets_cache = {}
            self._cache_timestamp = 0

            logger.info(
                "Successfully added user %s (ldap: %s) to authorized lists",
                user_id,
                ldap_username,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to add authorized user %s (ldap: %s): %s",
                user_id,
                ldap_username,
                e,
            )
            raise

    async def remove_authorized_user(self, user_id: str) -> bool:
        """
        Remove a user from the authorized users list.

        This method safely removes a user ID from the AUTHORISED_SLACK_USER_IDS list,
        preserving the existing list.

        Args:
            user_id: The Slack user ID to remove

        Returns:
            bool: True if user was removed, False if didn't exist

        Raises:
            Exception: If the update fails
        """
        logger.info("Starting remove_authorized_user for user: %s", user_id)

        try:
            # Get current authorized users
            current_users = await self.get_authorised_slack_user_ids()

            # Check if user exists
            if user_id not in current_users:
                logger.info("User %s not in authorized list", user_id)
                return False

            # Remove the user
            updated_users = current_users.copy()
            updated_users.remove(user_id)

            # Update the secret with JSON-encoded list
            await self.update_secret({"authorised_slack_user_ids": json.dumps(updated_users)})

            # Invalidate cache to force refresh on next access
            self._secrets_cache = {}
            self._cache_timestamp = 0

            logger.info("Successfully removed user %s from authorized list", user_id)
            return True

        except Exception as e:
            logger.error("Failed to remove authorized user %s: %s", user_id, e)
            raise

    async def remove_authorized_user_with_ldap(self, user_id: str, ldap_username: str) -> bool:
        """
        Remove a user from both the authorized Slack users list and LDAP backup list.

        This method safely removes a user ID from the AUTHORISED_SLACK_USER_IDS list
        and their LDAP username from the AUTHORISED_USERS_LDAP_BACKUP list,
        preserving the existing lists.

        Args:
            user_id: The Slack user ID to remove
            ldap_username: The LDAP username to remove

        Returns:
            bool: True if user was removed, False if didn't exist in either list

        Raises:
            Exception: If the update fails
        """
        logger.info(
            "Starting remove_authorized_user_with_ldap for user: %s, ldap: %s",
            user_id,
            ldap_username,
        )

        try:
            # Get current lists
            current_slack_users = await self.get_authorised_slack_user_ids()
            current_ldap_users = await self.get_authorised_users_ldap_backup()

            # Check if user exists in either list
            slack_exists = user_id in current_slack_users
            ldap_exists = ldap_username in current_ldap_users

            if not slack_exists and not ldap_exists:
                logger.info(
                    "User %s (ldap: %s) not in either authorized list",
                    user_id,
                    ldap_username,
                )
                return False

            # Update lists
            updated_slack_users = current_slack_users.copy()
            updated_ldap_users = current_ldap_users.copy()

            if slack_exists:
                updated_slack_users.remove(user_id)
            if ldap_exists:
                updated_ldap_users.remove(ldap_username)

            # Update the secret with both JSON-encoded lists
            await self.update_secret(
                {
                    "authorised_slack_user_ids": json.dumps(updated_slack_users),
                    "authorised_users_ldap_backup": json.dumps(updated_ldap_users),
                }
            )

            # Invalidate cache to force refresh on next access
            self._secrets_cache = {}
            self._cache_timestamp = 0

            logger.info(
                "Successfully removed user %s (ldap: %s) from authorized lists",
                user_id,
                ldap_username,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to remove authorized user %s (ldap: %s): %s",
                user_id,
                ldap_username,
                e,
            )
            raise
