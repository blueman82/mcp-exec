"""
user_ops.py

This module contains the SlackUserOps class, which is used to manage Slack user operations.
"""

import asyncio
from typing import Any, Dict, List, Optional

import orjson

from packages.core.constants import BATCH_SIZE
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import with_exponential_backoff
from packages.db.user_store import UserStore
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient

logger = setup_logger(__name__)


class SlackUserOps(SlackAsyncClient):
    """
    This class is responsible for Slack user operations like fetching user information.
    Relies on an injected UserStore.
    """

    def __init__(
        self,
        user_store: UserStore,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize the SlackUserOps with dependencies.

        Args:
            user_store: UserStore instance for database operations.
            slack_config: Pre-initialized SlackConfig instance (required).
            max_concurrent_requests: Maximum number of concurrent requests.
        """
        super().__init__(slack_config, max_concurrent_requests)

        # Store injected UserStore
        self.user_store = user_store
        self._user_cache: Dict[str, Dict[str, Any]] = {}  # In-memory cache for user info
        self._email_to_slack_cache: Dict[str, Optional[str]] = (
            {}
        )  # In-memory cache for email-to-Slack ID
        logger.info("SlackUserOps initialized with injected UserStore.")

    async def get_user_names(self, user_ids: List[str]) -> Dict[str, str]:
        """
        Get user names for a list of user IDs.

        Args:
            user_ids: List of user IDs to fetch names for

        Returns:
            Dictionary mapping user IDs to user names
        """
        if not user_ids:
            return {}

        # Filter out duplicates and invalid IDs
        valid_user_ids = list(set([uid for uid in user_ids if uid and isinstance(uid, str)]))

        # Initialize cache with existing in-memory cache entries
        user_cache: Dict[str, Dict[str, Any]] = {}  # Define type for local cache
        for uid in valid_user_ids:
            if uid in self._user_cache:
                user_cache[uid] = self._user_cache[uid]  # Copy existing dict

        # Identify which users we need to fetch (not in memory cache)
        missing_user_ids = [uid for uid in valid_user_ids if uid not in user_cache]

        if missing_user_ids:
            logger.info(
                "Fetching information for %s users not in memory cache",
                len(missing_user_ids),
            )

            # Step 1: Try to get users from DynamoDB
            db_users = await self.user_store.get_users(missing_user_ids)

            # Update cache with DB results
            for uid, name in db_users.items():
                user_info_dict = {
                    "user_id": uid,
                    "name": name,
                }  # Create consistent dict structure
                user_cache[uid] = user_info_dict
                self._user_cache[uid] = user_info_dict  # Update in-memory cache

            # Identify which users are still missing (not in DB)
            still_missing = [uid for uid in missing_user_ids if uid not in db_users]

            # Step 2: Fetch remaining users from Slack API
            if still_missing:
                logger.info("Fetching %s users from Slack API", len(still_missing))

                # Create list to store user data for DB updates
                new_user_data = []

                # Process users in batches to avoid rate limits
                for i in range(0, len(still_missing), BATCH_SIZE):
                    batch = still_missing[i : i + BATCH_SIZE]

                    # Use semaphore from base class for controlled concurrency
                    tasks = []
                    for uid in batch:
                        tasks.append(self._fetch_user_info_internal(uid))

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for idx, result in enumerate(results):
                        uid = batch[idx]
                        if isinstance(result, Exception):
                            logger.error(
                                "Failed to fetch user info for %s: %s",
                                uid,
                                str(result),
                            )
                            # Store fallback dict in cache
                            fallback_dict = {"user_id": uid, "name": uid}
                            user_cache[uid] = fallback_dict
                            self._user_cache[uid] = fallback_dict
                        elif result:  # result is the user dict from API
                            # Check if the result is a dict and not None
                            if not isinstance(result, dict):
                                msg = f"Expected dict, got {type(result)}"
                                logger.error(msg)
                                raise RuntimeError(msg)
                            # Extract name for DB storage (if needed, or store full dict)
                            name = (
                                result.get("profile", {}).get("real_name")
                                or result.get("name")
                                or uid
                            )
                            user_cache[uid] = result  # Store the full user dict
                            self._user_cache[uid] = result  # Store the full user dict
                            # Add data for DB batch store
                            new_user_data.append({"user_id": uid, "real_name": name})
                        else:  # Result is None (fetch failed)
                            logger.warning(
                                "Fetch returned None for user %s, using ID as fallback",
                                uid,
                            )
                            fallback_dict = {"user_id": uid, "name": uid}
                            user_cache[uid] = fallback_dict
                            self._user_cache[uid] = fallback_dict

                    # Add a small delay between batches
                    if i + BATCH_SIZE < len(still_missing):
                        await asyncio.sleep(1)

                # Store new users in DynamoDB for future lookups
                if new_user_data:
                    success, failure = await self.user_store.batch_store_users(new_user_data)
                    logger.info("Stored %s new users in DB (failed: %s)", success, failure)

        # Return map of user ID to user name, extracting from cache
        result_map: Dict[str, str] = {}
        for uid in user_ids:  # Iterate original list to preserve order/duplicates if needed
            cached_info = user_cache.get(uid)
            if cached_info:  # Should contain {"name": ...} or full user dict
                # Extract name, prioritizing real_name, then name, fallback to uid
                name = (
                    cached_info.get("profile", {}).get("real_name")
                    or cached_info.get("real_name")
                    or cached_info.get("name")
                    or uid
                )
                result_map[uid] = name
            else:
                result_map[uid] = uid  # Fallback if not found in cache at all
        return result_map

    async def get_user_usernames(self, user_ids: List[str]) -> Dict[str, str]:
        """
        Get usernames (not display names) for a list of user IDs.
        This method specifically returns the 'name' field from Slack user data,
        which is the username (e.g., 'harrison') rather than the display name.

        Args:
            user_ids: List of user IDs to fetch usernames for

        Returns:
            Dictionary mapping user IDs to usernames
        """
        if not user_ids:
            return {}

        # Use get_user_names to fetch all user data (it handles caching and DB lookups)
        # This populates the cache with full user info
        await self.get_user_names(user_ids)

        # Now extract usernames from the cache
        result_map: Dict[str, str] = {}
        for uid in user_ids:
            if uid in self._user_cache:
                cached_info = self._user_cache[uid]
                # Extract username (the 'name' field), fallback to uid
                username = cached_info.get("name") or uid
                result_map[uid] = username
                logger.info(
                    f"get_user_usernames: uid={uid}, cached_info.name={cached_info.get('name')}, username={username}"
                )
            else:
                # Fallback to user ID if not found
                result_map[uid] = uid
                logger.info(f"get_user_usernames: uid={uid} not in cache, using uid as fallback")

        return result_map

    @with_exponential_backoff()
    async def _fetch_user_info_internal(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch information for a single user from the Slack API.

        Args:
            user_id: The user ID to fetch information for

        Returns:
            Dictionary containing user info from Slack API or None if fetch fails.
        """
        url = f"{self.config.get_api_base_url()}/users.info"
        headers = self.config.get_headers()
        params = {"user": user_id}

        try:
            response = await self._make_api_request(url, "GET", headers, params)
            # Response is now a SafeResponse dict, parse the body
            data = orjson.loads(response["body"])

            if data.get("ok"):
                user = data.get("user", {})
                # Return the user sub-dictionary
                return user
            else:
                error = data.get("error", "Unknown error")
                logger.error("Error fetching user info for %s: %s", user_id, error)
                return None  # Return None on API error
        except Exception as e:
            logger.error("Error fetching user info for %s: %s", user_id, str(e))
            return None  # Return None on exception

    async def get_slack_id_by_email(self, email: str) -> Optional[str]:
        """
        Get Slack user ID for an email address using 3-level lookup:
        1. Memory cache
        2. DynamoDB cache
        3. Slack API (users.lookupByEmail)

        Results are cached permanently in DynamoDB (no TTL) for future lookups.

        Args:
            email: Email address to look up

        Returns:
            Slack user ID if found, None if not found or on error

        Architectural Notes:
            - Uses EMAIL_TO_SLACK#{email} as the DynamoDB partition key, following
              the established pattern of prefixed keys (USER#, CHANNEL#, etc.)
            - No TTL is applied as email-to-Slack mappings are stable (per design decision)
            - This is the first email-based lookup method; future features consuming
              this should follow the same cache-first pattern
        """
        if not email or not isinstance(email, str):
            logger.warning("get_slack_id_by_email called with invalid email: %s", email)
            return None

        email_lower = email.lower().strip()

        # Level 1: Check in-memory cache
        if email_lower in self._email_to_slack_cache:
            cached_value = self._email_to_slack_cache[email_lower]
            logger.debug("Email %s found in memory cache: %s", email_lower, cached_value)
            return cached_value

        # Level 2: Check DynamoDB cache
        try:
            db_result = await self.user_store.get_email_to_slack_mapping(email_lower)
            if db_result is not None:
                # Found in DynamoDB - update memory cache and return
                self._email_to_slack_cache[email_lower] = db_result
                logger.info("Email %s found in DynamoDB cache: %s", email_lower, db_result)
                return db_result
        except Exception as e:
            logger.error("Error checking DynamoDB cache for email %s: %s", email_lower, str(e))
            # Continue to Slack API lookup

        # Level 3: Fetch from Slack API
        logger.info("Fetching Slack ID for email %s from API", email_lower)
        slack_user_id = await self._fetch_slack_id_by_email_internal(email_lower)

        if slack_user_id:
            # Cache in memory
            self._email_to_slack_cache[email_lower] = slack_user_id

            # Cache in DynamoDB (fire and forget, don't block on this)
            try:
                await self.user_store.store_email_to_slack_mapping(email_lower, slack_user_id)
                logger.info(
                    "Stored email-to-Slack mapping for %s -> %s in DynamoDB",
                    email_lower,
                    slack_user_id,
                )
            except Exception as e:
                logger.error("Failed to store email-to-Slack mapping in DynamoDB: %s", str(e))
                # Don't fail the lookup - we have the result

        return slack_user_id

    @with_exponential_backoff(max_retries=3)
    async def _fetch_slack_id_by_email_internal(self, email: str) -> Optional[str]:
        """
        Fetch Slack user ID for an email from the Slack API.

        Uses Slack's users.lookupByEmail endpoint.

        Args:
            email: Email address to look up

        Returns:
            Slack user ID if found, None if not found or on error
        """
        url = f"{self.config.get_api_base_url()}/users.lookupByEmail"
        headers = self.config.get_headers()
        params = {"email": email}

        try:
            response = await self._make_api_request(url, "GET", headers, params)
            # Response is a SafeResponse dict, parse the body
            data = orjson.loads(response["body"])

            if data.get("ok"):
                user = data.get("user", {})
                slack_user_id = user.get("id")
                if slack_user_id:
                    logger.info("Found Slack user ID %s for email %s", slack_user_id, email)
                    return slack_user_id
                else:
                    logger.warning("Slack API returned ok but no user ID for email %s", email)
                    return None
            else:
                error = data.get("error", "Unknown error")
                # "users_not_found" is a normal case when email doesn't match
                if error == "users_not_found":
                    logger.info("No Slack user found for email %s", email)
                else:
                    logger.error("Error looking up Slack user by email %s: %s", email, error)
                return None
        except Exception as e:
            logger.error("Exception looking up Slack user by email %s: %s", email, str(e))
            return None
