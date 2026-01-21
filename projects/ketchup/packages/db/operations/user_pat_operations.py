"""
User PAT Operations for storing and retrieving JIRA Personal Access Tokens.

This module provides operations for storing user PATs in DynamoDB with
automatic TTL-based expiry (1 hour). The PAT is obfuscated using base64
encoding - actual security is provided by IAM policies on the DynamoDB table.

Key Schema:
- PK: USER#{slack_user_id}
- SK: JIRA_PAT
- ttl: Unix timestamp for auto-deletion (1 hour from creation)
"""

import base64
import time
from typing import Optional

from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)

# TTL for PAT storage (1 hour in seconds)
PAT_TTL_SECONDS = 3600

# Sort key for PAT records
SK_JIRA_PAT = "JIRA_PAT"


class UserPATOperations(BaseOperations):
    """Service for storing and retrieving user JIRA PATs.

    PATs are stored with a 1-hour TTL and automatically deleted by DynamoDB
    after expiry. The PAT value is base64 encoded for obfuscation.

    Key Schema:
    - PK: USER#{slack_user_id}
    - SK: JIRA_PAT
    """

    def __init__(self, client: DynamoDBAsyncClient, table_name: str) -> None:
        """Initialize the UserPATOperations.

        Args:
            client: DynamoDBAsyncClient for database access.
            table_name: The DynamoDB table name.
        """
        super().__init__(client, table_name)
        logger.info("UserPATOperations initialized with table: %s", table_name)

    def _make_pk(self, user_id: str) -> str:
        """Generate the partition key for a user's PAT record.

        Args:
            user_id: The Slack user ID

        Returns:
            The formatted partition key.
        """
        return f"USER#{user_id}"

    def _encode_pat(self, pat: str) -> str:
        """Encode PAT for storage (base64 obfuscation).

        Args:
            pat: The plain text PAT

        Returns:
            Base64 encoded PAT
        """
        return base64.b64encode(pat.encode("utf-8")).decode("utf-8")

    def _decode_pat(self, encoded_pat: str) -> str:
        """Decode PAT from storage.

        Args:
            encoded_pat: Base64 encoded PAT

        Returns:
            Plain text PAT
        """
        return base64.b64decode(encoded_pat.encode("utf-8")).decode("utf-8")

    async def store_pat(self, user_id: str, pat: str) -> None:
        """Store a user's JIRA PAT with 1-hour TTL.

        Args:
            user_id: The Slack user ID
            pat: The JIRA Personal Access Token
        """
        logger.info("Storing PAT for user: %s", user_id)

        current_time = int(time.time())
        ttl = current_time + PAT_TTL_SECONDS

        item = {
            "PK": {"S": self._make_pk(user_id)},
            "SK": {"S": SK_JIRA_PAT},
            "encoded_pat": {"S": self._encode_pat(pat)},
            "created_at": {"N": str(current_time)},
            "ttl": {"N": str(ttl)},
        }

        try:
            await self.client.put_item(item=item, table_name=self.table_name)
            logger.info("Stored PAT for user %s (expires in 1 hour)", user_id)
        except Exception as e:
            logger.error("Error storing PAT for user %s: %s", user_id, e)
            raise

    async def get_pat(self, user_id: str) -> Optional[str]:
        """Retrieve a user's JIRA PAT if not expired.

        Args:
            user_id: The Slack user ID

        Returns:
            The PAT if found and not expired, None otherwise.
        """
        logger.debug("Getting PAT for user: %s", user_id)

        try:
            key = {
                "PK": {"S": self._make_pk(user_id)},
                "SK": {"S": SK_JIRA_PAT},
            }

            response = await self.client.get_item(key=key, table_name=self.table_name)

            item = response.get("Item")
            if not item:
                logger.debug("No PAT found for user: %s", user_id)
                return None

            # Check if TTL has expired (DynamoDB TTL deletion is eventual)
            ttl = int(item.get("ttl", {}).get("N", "0"))
            if ttl > 0 and int(time.time()) > ttl:
                logger.debug("PAT expired for user: %s", user_id)
                return None

            encoded_pat = item.get("encoded_pat", {}).get("S")
            if not encoded_pat:
                logger.warning("PAT record exists but no encoded_pat for user: %s", user_id)
                return None

            return self._decode_pat(encoded_pat)

        except Exception as e:
            logger.error("Error getting PAT for user %s: %s", user_id, e)
            return None

    async def delete_pat(self, user_id: str) -> None:
        """Delete a user's stored PAT.

        Args:
            user_id: The Slack user ID
        """
        logger.info("Deleting PAT for user: %s", user_id)

        try:
            key = {
                "PK": {"S": self._make_pk(user_id)},
                "SK": {"S": SK_JIRA_PAT},
            }

            await self.client.delete_item(key=key, table_name=self.table_name)
            logger.info("Deleted PAT for user: %s", user_id)

        except Exception as e:
            logger.error("Error deleting PAT for user %s: %s", user_id, e)
            raise

    async def has_valid_pat(self, user_id: str) -> bool:
        """Check if a user has a valid (non-expired) PAT stored.

        Args:
            user_id: The Slack user ID

        Returns:
            True if user has a valid PAT, False otherwise.
        """
        pat = await self.get_pat(user_id)
        return pat is not None

    async def get_pat_expiry_minutes(self, user_id: str) -> Optional[int]:
        """Get the remaining minutes until PAT expires.

        Args:
            user_id: The Slack user ID

        Returns:
            Minutes remaining until expiry, or None if no valid PAT.
        """
        try:
            key = {
                "PK": {"S": self._make_pk(user_id)},
                "SK": {"S": SK_JIRA_PAT},
            }

            response = await self.client.get_item(key=key, table_name=self.table_name)

            item = response.get("Item")
            if not item:
                return None

            ttl = int(item.get("ttl", {}).get("N", "0"))
            if ttl <= 0:
                return None

            remaining_seconds = ttl - int(time.time())
            if remaining_seconds <= 0:
                return None

            return max(1, remaining_seconds // 60)  # At least 1 minute if valid

        except Exception as e:
            logger.error("Error getting PAT expiry for user %s: %s", user_id, e)
            return None
