"""
user_store.py

This module contains the UserStore class for DynamoDB operations with user data.
"""

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError

from packages.core.logging import setup_logger
from packages.db.batch_write_utils import batch_write_items_with_retries
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

logger = setup_logger(__name__)


class UserStore:
    """
    Service for interacting with DynamoDB for user-related operations using an async client.
    """

    def __init__(self, client: DynamoDBAsyncClient, table_name: str):
        """
        Initialize the UserStore with an async client.

        Args:
            client: An initialized DynamoDBAsyncClient instance.
            table_name: The DynamoDB table name.
        """
        self.client = client
        self.table_name = table_name

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from DynamoDB asynchronously.

        Args:
            user_id: The Slack user ID to retrieve

        Returns:
            User information dictionary or None if not found
        """
        logger.info("Getting user information for user ID: %s", user_id)
        key = {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "METADATA"}}

        try:
            # Use injected async client and await the call
            response = await self.client.get_item(key, table_name=self.table_name)

            item = response.get("Item")
            if item:
                logger.info("Found user information in DynamoDB for user ID: %s", user_id)

                # Create a normalized user dict
                user_dict = {
                    "user_id": user_id,
                    "real_name": item.get("real_name", {}).get("S"),
                    "updated_at": item.get("updated_at", {}).get("N"),
                    "authorized": item.get("authorized", {}).get("BOOL", False),
                }

                # Add features if present
                if "features" in item:
                    features_map = item["features"].get("M", {})
                    user_dict["features"] = self._parse_features_from_dynamodb(features_map)

                # Add preferences if present
                if "preferences" in item:
                    preferences_map = item["preferences"].get("M", {})
                    user_dict["preferences"] = self._parse_preferences_from_dynamodb(
                        preferences_map
                    )

                return user_dict
            else:
                logger.info("No user found in DynamoDB for user ID: %s", user_id)
                return None
        except ClientError as e:
            # Handle client errors (like ResourceNotFound)
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(
                "DynamoDB error fetching user %s: %s - %s",
                user_id,
                error_code,
                error_message,
            )
            return None
        except Exception as e:
            # Catch any unexpected errors with the DB operation
            logger.error("Unexpected error getting user %s: %s", user_id, str(e))
            return None

    async def store_user(
        self, user_data: Dict[str, Any], authorized: Optional[bool] = None
    ) -> bool:
        """
        Store user information in DynamoDB asynchronously.

        Args:
            user_data: Dictionary with user info (must include 'user_id' and 'real_name')
            authorized: Optional authorization status to set (True/False)

        Returns:
            True if operation succeeded, False otherwise
        """
        if not user_data.get("user_id"):
            logger.error("Cannot store user without user_id")
            return False

        logger.info("Storing user information for user ID: %s", user_data["user_id"])

        try:
            # Build the item with base data
            item = {
                "PK": {"S": f"USER#{user_data['user_id']}"},
                "SK": {"S": "METADATA"},
                "real_name": {"S": user_data.get("real_name", "Unknown User")},
                "updated_at": {"N": str(int(time.time()))},
            }

            # Add authorized flag if provided as parameter or in user_data
            if authorized is not None:
                item["authorized"] = {"BOOL": authorized}
            elif "authorized" in user_data:
                item["authorized"] = {"BOOL": user_data["authorized"]}

            # Add features if they exist
            if "features" in user_data:
                features_map = self._convert_features_to_dynamodb(user_data["features"])
                item["features"] = {"M": features_map}

            # Add preferences if they exist
            if "preferences" in user_data:
                preferences_map = self._convert_preferences_to_dynamodb(user_data["preferences"])
                item["preferences"] = {"M": preferences_map}

            # Use injected async client and await the call
            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info(
                "Successfully stored user information for user ID: %s",
                user_data["user_id"],
            )
            return True
        except Exception as e:
            logger.error("Error storing user %s: %s", user_data.get("user_id"), str(e))
            return False

    async def set_user_authorization(
        self, user_id: str, authorized: bool, real_name: Optional[str] = None
    ) -> bool:
        """
        Set user authorization status.

        Args:
            user_id: The user ID to update
            authorized: The authorization status to set
            real_name: Optional real name to update

        Returns:
            True if the update was successful, False otherwise
        """
        logger.info("Setting authorization for user %s to %s", user_id, authorized)

        # Get existing user to preserve other attributes
        existing_user = await self.get_user(user_id)
        user_data = {"user_id": user_id}

        if existing_user:
            # Preserve existing values
            user_data.update(existing_user)

        # Set or override authorization
        user_data["authorized"] = authorized

        if real_name is not None:
            user_data["real_name"] = real_name

        return await self.store_user(user_data)

    async def set_user_feature(self, user_id: str, feature_name: str, value: bool) -> bool:
        """
        Set a feature flag for a user.

        Args:
            user_id: The user ID to update
            feature_name: The name of the feature to set
            value: The value to set for the feature

        Returns:
            True if the update was successful, False otherwise
        """
        logger.info(f"Setting feature {feature_name}={value} for user {user_id}")

        # Get existing user to preserve other attributes
        existing_user = await self.get_user(user_id)
        if not existing_user:
            logger.warning(f"Cannot set feature for non-existent user: {user_id}")
            return False

        # Initialize or update features dict
        features = existing_user.get("features", {})
        features[feature_name] = value

        # Update user with new features
        existing_user["features"] = features

        return await self.store_user(existing_user)

    async def get_user_feature(self, user_id: str, feature_name: str) -> Optional[bool]:
        """
        Get a feature flag value for a user.

        Args:
            user_id: The user ID to query
            feature_name: The name of the feature to get

        Returns:
            The feature flag value, or None if not set
        """
        logger.info(f"Getting feature {feature_name} for user {user_id}")

        user = await self.get_user(user_id)
        if not user:
            return None

        features = user.get("features", {})
        return features.get(feature_name)

    async def get_users_with_feature(
        self, feature_name: str, value: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all users with a specific feature flag value.

        Args:
            feature_name: The name of the feature to query
            value: The feature value to match (default is True)

        Returns:
            List of user dictionaries with the matching feature flag value
        """
        logger.info(f"Getting all users with feature {feature_name}={value}")

        try:
            # This is a scan operation, which should be used carefully in production
            # For a large user base, consider using a GSI on features or other optimizations
            underlying_client = await self.client._get_client()

            filter_expression = "SK = :sk AND attribute_exists(features.#feature_name) AND features.#feature_name = :value"
            response = await underlying_client.scan(
                TableName=self.table_name,
                FilterExpression=filter_expression,
                ExpressionAttributeNames={"#feature_name": feature_name},
                ExpressionAttributeValues={
                    ":sk": {"S": "METADATA"},
                    ":value": {"BOOL": value},
                },
                ProjectionExpression="PK, real_name, features",
            )

            # Process results
            users = []
            for item in response.get("Items", []):
                # Extract user_id from PK (format: USER#<user_id>)
                pk = item.get("PK", {}).get("S", "")
                user_id = pk.replace("USER#", "") if pk.startswith("USER#") else ""

                if user_id:
                    user_dict = {
                        "user_id": user_id,
                        "real_name": item.get("real_name", {}).get("S", "Unknown"),
                    }

                    # Add features if present
                    if "features" in item:
                        features_map = item["features"].get("M", {})
                        user_dict["features"] = self._parse_features_from_dynamodb(features_map)

                    users.append(user_dict)

            # Handle pagination if needed
            while "LastEvaluatedKey" in response:
                response = await underlying_client.scan(
                    TableName=self.table_name,
                    FilterExpression=filter_expression,
                    ExpressionAttributeNames={"#feature_name": feature_name},
                    ExpressionAttributeValues={
                        ":sk": {"S": "METADATA"},
                        ":value": {"BOOL": value},
                    },
                    ProjectionExpression="PK, real_name, features",
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )

                for item in response.get("Items", []):
                    pk = item.get("PK", {}).get("S", "")
                    user_id = pk.replace("USER#", "") if pk.startswith("USER#") else ""

                    if user_id:
                        user_dict = {
                            "user_id": user_id,
                            "real_name": item.get("real_name", {}).get("S", "Unknown"),
                        }

                        # Add features if present
                        if "features" in item:
                            features_map = item["features"].get("M", {})
                            user_dict["features"] = self._parse_features_from_dynamodb(features_map)

                        users.append(user_dict)

            return users
        except Exception as e:
            logger.error(f"Error getting users with feature {feature_name}: {e}")
            return []

    async def get_users(self, user_ids: List[str]) -> Dict[str, str]:
        """
        Get multiple users from DynamoDB asynchronously.

        Args:
            user_ids: List of Slack user IDs to retrieve

        Returns:
            Dictionary mapping user IDs to real names
        """
        if not user_ids:
            return {}

        logger.info("Getting user information for %s users", len(user_ids))

        try:
            user_cache = {}
            batch_size = 100  # DynamoDB batch get limit

            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i : i + batch_size]
                keys = [
                    {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "METADATA"}}
                    for user_id in batch
                    if user_id and isinstance(user_id, str)
                ]

                if not keys:
                    continue

                # Get the underlying aioboto3 client
                underlying_client = await self.client._get_client()

                # Use the underlying client to make the batch_get_item call
                request_items = {self.table_name: {"Keys": keys}}
                response = await underlying_client.batch_get_item(RequestItems=request_items)

                items = response.get("Responses", {}).get(self.table_name, [])
                for item in items:
                    user_id = item.get("PK", {}).get("S", "").replace("USER#", "")
                    # Assuming response format is low-level DynamoDB JSON
                    real_name = item.get("real_name", {}).get("S", user_id)
                    user_cache[user_id] = real_name

                # Handle unprocessed keys if the async client provides them
                unprocessed_keys = response.get("UnprocessedKeys", {}).get(self.table_name)
                if unprocessed_keys:
                    logger.warning("Unprocessed keys found: %s", unprocessed_keys)
                    # Implement retry logic for unprocessed keys if needed

            return user_cache

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error("DynamoDB error getting users: %s - %s", error_code, error_message)
            return {}
        except Exception as e:
            # Catch specific exceptions if DynamoDBAsyncClient defines them
            logger.error("Unexpected error getting users: %s", str(e))
            return {}

    async def batch_store_users(self, user_data: List[Dict[str, str]]) -> Tuple[int, int]:
        """
        Store multiple users in DynamoDB using async batch operations.

        Args:
            user_data: List of dictionaries containing user data with 'user_id' and 'real_name' keys

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not user_data:
            return 0, 0

        logger.info("Batch storing %s users", len(user_data))
        timestamp = int(time.time())
        put_requests = [
            {
                "PutRequest": {
                    "Item": {
                        "PK": {"S": f"USER#{item['user_id']}"},
                        "SK": {"S": "METADATA"},
                        "real_name": {"S": item["real_name"]},
                        "updated_at": {"N": str(timestamp)},
                    }
                }
            }
            for item in user_data
        ]
        return await batch_write_items_with_retries(
            client=self.client,
            table_name=self.table_name,
            put_requests=put_requests,
        )

    async def store_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """
        Stores or updates user preferences in DynamoDB.

        Args:
            user_id: The Slack user ID.
            preferences: A dictionary containing user preferences.
        """
        logger.info("Attempting to store preferences for user ID: %s", user_id)

        # Retrieve existing user data to preserve real_name
        existing_user_data = await self.get_user(user_id)
        real_name = existing_user_data.get("real_name") if existing_user_data else "Unknown User"

        item = {
            "PK": {"S": f"USER#{user_id}"},
            "SK": {"S": "METADATA"},
            "real_name": {"S": real_name},
            "preferences": {"M": self._convert_preferences_to_dynamodb(preferences)},
            "updated_at": {"N": str(Decimal(time.time()))},
        }

        # Preserve features if they exist
        if existing_user_data and "features" in existing_user_data:
            features_map = self._convert_features_to_dynamodb(existing_user_data["features"])
            item["features"] = {"M": features_map}

        # Preserve authorized flag if it exists
        if existing_user_data and "authorized" in existing_user_data:
            item["authorized"] = {"BOOL": existing_user_data["authorized"]}

        try:
            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info("Successfully stored preferences for user ID: %s", user_id)
        except Exception as e:
            logger.error("Unexpected error storing user preferences: %s", str(e))

    def _convert_preferences_to_dynamodb(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a preferences dictionary to DynamoDB format.

        Args:
            preferences: Dictionary of user preferences

        Returns:
            Dict in DynamoDB format
        """
        preferences_map = {}

        # Convert product_focus (list of strings)
        if "product_focus" in preferences:
            product_focus_list = [{"S": product} for product in preferences["product_focus"]]
            preferences_map["product_focus"] = {"L": product_focus_list}

        # Convert detail_level (string)
        if "detail_level" in preferences:
            preferences_map["detail_level"] = {"S": preferences["detail_level"]}

        # Convert time_window (string)
        if "time_window" in preferences:
            preferences_map["time_window"] = {"S": preferences["time_window"]}

        # Convert include_in_summary (list of strings)
        if "include_in_summary" in preferences:
            include_list = [{"S": item} for item in preferences["include_in_summary"]]
            preferences_map["include_in_summary"] = {"L": include_list}

        # Convert join_notifications_enabled (string)
        if "join_notifications_enabled" in preferences:
            preferences_map["join_notifications_enabled"] = {
                "S": preferences["join_notifications_enabled"]
            }

        return preferences_map

    def _convert_features_to_dynamodb(
        self, features: Dict[str, bool]
    ) -> Dict[str, Dict[str, bool]]:
        """
        Convert a features dictionary to DynamoDB format.

        Args:
            features: Dictionary of user feature flags

        Returns:
            Dict in DynamoDB format
        """
        features_map = {}

        # Convert each boolean feature
        for feature_name, value in features.items():
            features_map[feature_name] = {"BOOL": value}

        return features_map

    def _parse_features_from_dynamodb(
        self, features_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, bool]:
        """
        Parse features from DynamoDB format to standard dictionary.

        Args:
            features_map: Features in DynamoDB format

        Returns:
            Dictionary of feature name to boolean value
        """
        features = {}

        # Convert each DynamoDB feature to a standard boolean
        for feature_name, value_dict in features_map.items():
            if "BOOL" in value_dict:
                features[feature_name] = value_dict["BOOL"]

        return features

    def _parse_preferences_from_dynamodb(
        self, preferences_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Parse preferences from DynamoDB format to standard dictionary.

        Args:
            preferences_map: Preferences in DynamoDB format

        Returns:
            Dictionary of preferences in standard format
        """
        preferences = {}

        # Convert product_focus (list of strings)
        if "product_focus" in preferences_map:
            product_focus_list = preferences_map["product_focus"].get("L", [])
            preferences["product_focus"] = [
                item.get("S", "") for item in product_focus_list if "S" in item
            ]

        # Convert detail_level (string)
        if "detail_level" in preferences_map:
            preferences["detail_level"] = preferences_map["detail_level"].get("S", "balanced")

        # Convert time_window (string)
        if "time_window" in preferences_map:
            preferences["time_window"] = preferences_map["time_window"].get("S", "past_24_hours")

        # Convert include_in_summary (list of strings)
        if "include_in_summary" in preferences_map:
            include_list = preferences_map["include_in_summary"].get("L", [])
            preferences["include_in_summary"] = [
                item.get("S", "") for item in include_list if "S" in item
            ]

        # Convert join_notifications_enabled (string)
        if "join_notifications_enabled" in preferences_map:
            preferences["join_notifications_enabled"] = preferences_map[
                "join_notifications_enabled"
            ].get("S", "enabled")

        return preferences

    async def is_user_authorized(self, user_id: str) -> bool:
        """
        Check if a user is authorized based on database record.

        Args:
            user_id: Slack user ID to check

        Returns:
            True if user has authorized=True in DB, False otherwise
        """
        try:
            user = await self.get_user(user_id)
            if user:
                # Check for authorized field (default to False if not present)
                return user.get("authorized", False)
            return False
        except Exception as e:
            logger.error(f"Error checking user authorization: {e}")
            return False

    async def get_channel_feature(self, channel_id: str, feature_name: str) -> Optional[bool]:
        """
        Get a feature flag value for a channel.

        Args:
            channel_id: Slack channel ID
            feature_name: Name of the feature (e.g., 'status_updater_enabled')

        Returns:
            Feature value or None if not found
        """
        try:
            response = await self.client.get_item(
                key={"PK": {"S": f"CHANNEL#{channel_id}"}, "SK": {"S": "CSO_DETAILS"}},
                table_name=self.table_name,
            )

            if response.get("Item"):
                features = response["Item"].get("features", {}).get("M", {})
                feature_value = features.get(feature_name, {}).get("BOOL")
                return feature_value

            return None
        except Exception as e:
            logger.error(f"Error getting channel feature {feature_name}: {e}")
            return None

    async def set_channel_feature(self, channel_id: str, feature_name: str, value: bool) -> bool:
        """
        Set a feature flag value for a channel.

        Args:
            channel_id: Slack channel ID
            feature_name: Name of the feature
            value: Feature value

        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to update the nested attribute first
            try:
                await self.client.update_item(
                    key={
                        "PK": {"S": f"CHANNEL#{channel_id}"},
                        "SK": {"S": "CSO_DETAILS"},
                    },
                    update_expression="SET features.#feature = :value",
                    expression_attribute_names={"#feature": feature_name},
                    expression_attribute_values={":value": {"BOOL": value}},
                    condition_expression="attribute_exists(features)",
                    table_name=self.table_name,
                )
                return True
            except Exception as e:
                if "ConditionalCheckFailedException" in str(e) or "ValidationException" in str(e):
                    # Features doesn't exist, create it
                    await self.client.update_item(
                        key={
                            "PK": {"S": f"CHANNEL#{channel_id}"},
                            "SK": {"S": "CSO_DETAILS"},
                        },
                        update_expression="SET features = :features",
                        expression_attribute_values={
                            ":features": {"M": {feature_name: {"BOOL": value}}}
                        },
                        table_name=self.table_name,
                    )
                    return True
                else:
                    raise e
        except Exception as e:
            logger.error(f"Error setting channel feature {feature_name}: {e}")
            return False

    async def get_channels_with_feature(self, feature_name: str, value: bool) -> List[str]:
        """
        Get all channels that have a specific feature enabled.

        Args:
            feature_name: Name of the feature to check
            value: Feature value to match

        Returns:
            List of channel IDs (e.g., ['C1234567890', 'C0987654321'])
        """
        logger.info(f"Getting all channels with feature {feature_name}={value}")

        try:
            underlying_client = await self.client._get_client()

            # Scan for all CSO_DETAILS items with the feature
            filter_expression = "begins_with(PK, :pk_prefix) AND SK = :sk AND attribute_exists(features.#feature_name) AND features.#feature_name = :value"

            response = await underlying_client.scan(
                TableName=self.table_name,
                FilterExpression=filter_expression,
                ExpressionAttributeNames={"#feature_name": feature_name},
                ExpressionAttributeValues={
                    ":pk_prefix": {"S": "CHANNEL#"},
                    ":sk": {"S": "CSO_DETAILS"},
                    ":value": {"BOOL": value},
                },
                ProjectionExpression="PK",
            )

            # Extract channel IDs from the results
            channel_ids = []
            for item in response.get("Items", []):
                pk = item.get("PK", {}).get("S", "")
                if pk.startswith("CHANNEL#"):
                    channel_id = pk.replace("CHANNEL#", "")
                    if channel_id:
                        channel_ids.append(channel_id)

            # Handle pagination if needed
            while "LastEvaluatedKey" in response:
                response = await underlying_client.scan(
                    TableName=self.table_name,
                    FilterExpression=filter_expression,
                    ExpressionAttributeNames={"#feature_name": feature_name},
                    ExpressionAttributeValues={
                        ":pk_prefix": {"S": "CHANNEL#"},
                        ":sk": {"S": "CSO_DETAILS"},
                        ":value": {"BOOL": value},
                    },
                    ProjectionExpression="PK",
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )

                for item in response.get("Items", []):
                    pk = item.get("PK", {}).get("S", "")
                    if pk.startswith("CHANNEL#"):
                        channel_id = pk.replace("CHANNEL#", "")
                        if channel_id:
                            channel_ids.append(channel_id)

            logger.info(f"Found {len(channel_ids)} channels with feature {feature_name}={value}")
            return channel_ids

        except Exception as e:
            logger.error(f"Error getting channels with feature {feature_name}: {e}")
            return []

    async def get_email_to_slack_mapping(self, email: str) -> Optional[str]:
        """
        Get cached Slack user ID for an email address from DynamoDB.

        Uses the EMAIL_TO_SLACK#{email} partition key pattern, consistent with
        other entity types (USER#, CHANNEL#, etc.).

        Args:
            email: Email address to look up (should be lowercase)

        Returns:
            Slack user ID if found in cache, None otherwise
        """
        logger.debug("Looking up email-to-Slack mapping for: %s", email)
        key = {"PK": {"S": f"EMAIL_TO_SLACK#{email}"}, "SK": {"S": "METADATA"}}

        try:
            response = await self.client.get_item(key, table_name=self.table_name)
            item = response.get("Item")

            if item:
                slack_user_id = item.get("slack_user_id", {}).get("S")
                if slack_user_id:
                    logger.info(
                        "Found cached email-to-Slack mapping: %s -> %s", email, slack_user_id
                    )
                    return slack_user_id

            logger.debug("No email-to-Slack mapping found for: %s", email)
            return None

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(
                "DynamoDB error fetching email mapping %s: %s - %s",
                email,
                error_code,
                error_message,
            )
            return None
        except Exception as e:
            logger.error("Unexpected error getting email mapping %s: %s", email, str(e))
            return None

    async def store_email_to_slack_mapping(self, email: str, slack_user_id: str) -> bool:
        """
        Store email-to-Slack user ID mapping in DynamoDB.

        Uses the EMAIL_TO_SLACK#{email} partition key pattern. No TTL is applied
        as email-to-Slack mappings are considered stable per design decision.

        Args:
            email: Email address (should be lowercase)
            slack_user_id: The Slack user ID to cache

        Returns:
            True if stored successfully, False otherwise
        """
        logger.info("Storing email-to-Slack mapping: %s -> %s", email, slack_user_id)

        try:
            item = {
                "PK": {"S": f"EMAIL_TO_SLACK#{email}"},
                "SK": {"S": "METADATA"},
                "slack_user_id": {"S": slack_user_id},
                "cached_at": {"S": datetime.now(timezone.utc).isoformat()},
            }

            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info("Successfully stored email-to-Slack mapping for: %s", email)
            return True

        except Exception as e:
            logger.error("Error storing email-to-Slack mapping for %s: %s", email, str(e))
            return False
