"""
distributed_lock.py

Distributed lock implementation using DynamoDB for preventing race conditions
in access request approvals.
"""

import time
import uuid
from contextlib import asynccontextmanager

from botocore.exceptions import ClientError

from packages.core.constants import ACCESS_REQUEST_LOCK_TIMEOUT
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class DistributedLock:
    """
    Distributed lock using DynamoDB conditional writes.
    Prevents race conditions when multiple approvers click simultaneously.
    """

    def __init__(self, dynamodb_client, table_name):
        """
        Initialize the distributed lock.

        Args:
            dynamodb_client: DynamoDB async client
            table_name: DynamoDB table name
        """
        self.client = dynamodb_client
        self.table_name = table_name
        self._lock_prefix = "LOCK#"
        self._owner_id = str(uuid.uuid4())  # Unique ID for this instance

    @asynccontextmanager
    async def acquire_lock(self, resource_id: str, timeout_seconds: int = None):
        """
        Acquire a distributed lock for a resource.

        Args:
            resource_id: The resource to lock (e.g., "ACCESS_REQUEST#U123#12345.678")
            timeout_seconds: Lock timeout in seconds (defaults to ACCESS_REQUEST_LOCK_TIMEOUT)

        Yields:
            bool: True if lock was acquired, False otherwise
        """
        if timeout_seconds is None:
            timeout_seconds = ACCESS_REQUEST_LOCK_TIMEOUT

        lock_key = f"{self._lock_prefix}{resource_id}"
        acquired = False

        try:
            # Try to acquire lock
            acquired = await self._try_acquire_lock(lock_key, timeout_seconds)
            yield acquired
        finally:
            # Always try to release the lock if we acquired it
            if acquired:
                await self._release_lock(lock_key)

    async def _try_acquire_lock(self, lock_key: str, timeout_seconds: int) -> bool:
        """
        Try to acquire a lock using conditional put.

        Args:
            lock_key: The lock key in DynamoDB
            timeout_seconds: Lock timeout in seconds

        Returns:
            bool: True if lock was acquired, False otherwise
        """
        current_time = int(time.time())
        expiry_time = current_time + timeout_seconds

        try:
            # Try to create lock with conditional check
            await self.client.put_item(
                item={
                    "PK": {"S": lock_key},
                    "SK": {"S": "LOCK"},
                    "owner_id": {"S": self._owner_id},
                    "acquired_at": {"N": str(current_time)},
                    "expires_at": {"N": str(expiry_time)},
                    "ttl": {"N": str(expiry_time + 3600)},  # Clean up after 1 hour
                },
                table_name=self.table_name,
                condition_expression="attribute_not_exists(PK)",
            )

            logger.info(f"Lock acquired: {lock_key}")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Lock already exists, check if it's expired
                return await self._try_steal_expired_lock(lock_key, timeout_seconds)
            else:
                logger.error(f"Error acquiring lock: {e}")
                return False

    async def _try_steal_expired_lock(
        self, lock_key: str, timeout_seconds: int
    ) -> bool:
        """
        Try to steal an expired lock.

        Args:
            lock_key: The lock key in DynamoDB
            timeout_seconds: Lock timeout in seconds

        Returns:
            bool: True if lock was stolen, False otherwise
        """
        try:
            # Get current lock
            response = await self.client.get_item(
                key={"PK": {"S": lock_key}, "SK": {"S": "LOCK"}},
                table_name=self.table_name,
            )

            item = response.get("Item")
            if not item:
                # Lock disappeared, try to acquire again
                return await self._try_acquire_lock(lock_key, timeout_seconds)

            # Check if lock is expired
            current_time = int(time.time())
            expires_at = int(item.get("expires_at", {}).get("N", "0"))

            if current_time > expires_at:
                # Lock is expired, try to steal it
                old_owner = item.get("owner_id", {}).get("S", "")

                try:
                    await self.client.update_item(
                        key={"PK": {"S": lock_key}, "SK": {"S": "LOCK"}},
                        update_expression="SET owner_id = :new_owner, acquired_at = :now, expires_at = :expires",
                        expression_attribute_values={
                            ":new_owner": {"S": self._owner_id},
                            ":now": {"N": str(current_time)},
                            ":expires": {"N": str(current_time + timeout_seconds)},
                            ":old_owner": {"S": old_owner},
                            ":old_expires": {"N": str(expires_at)},
                        },
                        condition_expression="owner_id = :old_owner AND expires_at = :old_expires",
                        table_name=self.table_name,
                    )

                    logger.info(f"Stole expired lock: {lock_key} from {old_owner}")
                    return True

                except ClientError as e:
                    if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                        # Someone else stole it first
                        logger.info(f"Failed to steal expired lock: {lock_key}")
                        return False
                    raise

            return False

        except Exception as e:
            logger.error(f"Error checking expired lock: {e}")
            return False

    async def _release_lock(self, lock_key: str):
        """
        Release a lock we own.

        Args:
            lock_key: The lock key in DynamoDB
        """
        try:
            await self.client.delete_item(
                key={"PK": {"S": lock_key}, "SK": {"S": "LOCK"}},
                condition_expression="owner_id = :owner",
                expression_attribute_values={":owner": {"S": self._owner_id}},
                table_name=self.table_name,
            )

            logger.info(f"Lock released: {lock_key}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # We don't own this lock anymore (expired and stolen)
                logger.warning(f"Tried to release lock we don't own: {lock_key}")
            else:
                logger.error(f"Error releasing lock: {e}")
