"""
access_request_operations.py

Operations for managing access requests in DynamoDB using scan-based queries (no GSI).
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple

from botocore.exceptions import ClientError

from packages.core.constants import (
    ACCESS_REQUEST_RATE_LIMIT_PER_HOUR,
    ACCESS_REQUEST_STATUS,
)
from packages.core.logging import setup_logger
from packages.core.time_utils import convert_timestamp_to_utc
from packages.db.models.access_request import AccessRequest
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


class AccessRequestOperations(BaseOperations):
    """Operations for managing access requests in DynamoDB (scan-based, no GSI)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 900  # 15 minutes
        self._cache_lock = asyncio.Lock()
        self._batch_scan_enabled = True

    async def create_request_with_validation(
        self, request: AccessRequest
    ) -> Tuple[bool, str, Optional[AccessRequest]]:
        """
        Create an access request with rate limiting and duplicate checking.

        Returns:
            Tuple of (success, message, created_request)
        """
        try:
            # Check rate limit
            rate_limit_ok, rate_limit_msg = await self._check_and_update_rate_limit(
                request.user_id
            )
            if not rate_limit_ok:
                return False, rate_limit_msg, None

            # Check for existing pending request (using cached scan)
            existing = await self._get_pending_request_cached(request.user_id)
            if existing:
                time_str = convert_timestamp_to_utc(existing.request_timestamp)
                return (
                    False,
                    f"You already have a pending request from {time_str}",
                    existing,
                )

            # Create the request
            item = request.to_item()
            await self.client.put_item(item=item, table_name=self.table_name)

            # Invalidate cache since we added a new pending request
            self.invalidate_cache()

            logger.info(
                "Created access request",
                extra={
                    "user_id": request.user_id,
                    "user_name": request.user_name,
                    "timestamp": request.request_timestamp,
                },
            )

            return True, "Access request created successfully", request

        except Exception as e:
            logger.error(f"Error creating access request: {e}")
            return False, "Failed to create access request. Please try again.", None

    async def get_pending_request(self, user_id: str) -> Optional[AccessRequest]:
        """Get pending access request for a user using scan (no GSI available)."""
        try:
            # Use scan with filter since GSI is not available
            response = await self.client.scan(
                table_name=self.table_name,
                filter_expression="#status = :pending AND user_id = :user_id",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={
                    ":pending": {"S": ACCESS_REQUEST_STATUS["PENDING"]},
                    ":user_id": {"S": user_id},
                },
                limit=100,  # Reasonable limit for scan
            )

            items = response.get("Items", [])
            if items:
                # Verify TTL hasn't expired
                item = items[0]
                ttl_value = (
                    item.get("ttl", {}).get("N", "0")
                    if isinstance(item.get("ttl"), dict)
                    else item.get("ttl", 0)
                )
                if float(ttl_value) > time.time():
                    return AccessRequest.from_item(item)
                else:
                    # Mark as expired
                    timestamp_value = (
                        float(item["request_timestamp"].get("N"))
                        if isinstance(item["request_timestamp"], dict)
                        else item["request_timestamp"]
                    )
                    await self._update_request_status(
                        user_id, timestamp_value, ACCESS_REQUEST_STATUS["EXPIRED"]
                    )

            return None

        except Exception as e:
            logger.error(f"Error getting pending request: {e}")
            return None

    async def update_request_decision(
        self,
        user_id: str,
        request_timestamp: float,
        decision: str,
        decided_by_id: str,
        decided_by_name: str,
        rejection_reason: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Update request with decision (approve/reject).
        Uses conditional update to prevent race conditions.
        """
        try:
            update_expr = """
                SET #status = :new_status,
                    decided_by_id = :decided_by_id,
                    decided_by_name = :decided_by_name,
                    decision_timestamp = :decision_timestamp
            """

            expr_values = {
                ":new_status": {"S": decision},
                ":decided_by_id": {"S": decided_by_id},
                ":decided_by_name": {"S": decided_by_name},
                ":decision_timestamp": {"N": str(time.time())},
                ":pending": {"S": ACCESS_REQUEST_STATUS["PENDING"]},
            }

            if rejection_reason:
                update_expr += ", rejection_reason = :rejection_reason"
                expr_values[":rejection_reason"] = {"S": rejection_reason}

            # Conditional update - only if still pending
            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"ACCESS_REQUEST#{request_timestamp}"},
                },
                update_expression=update_expr,
                expression_attribute_names={"#status": "status"},
                expression_attribute_values=expr_values,
                condition_expression="#status = :pending",
            )

            # Invalidate cache since status changed
            self.invalidate_cache()

            return True, "Request updated successfully"

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Get current status
                current = await self._get_request(user_id, request_timestamp)
                if current:
                    decided_time = convert_timestamp_to_utc(current.decision_timestamp)
                    return (
                        False,
                        f"This request was already {current.status} by {current.decided_by_name} at {decided_time}",
                    )
                return False, "Request not found or already processed"

            logger.error(f"Error updating request decision: {e}")
            return False, "Failed to update request"

    async def _check_and_update_rate_limit(self, user_id: str) -> Tuple[bool, str]:
        """Check and update rate limit for user."""
        try:
            rate_limit_key = {
                "PK": {"S": f"RATE_LIMIT#{user_id}"},
                "SK": {"S": "ACCESS_REQUEST"},
            }

            # Try to increment counter with conditional check
            await self.client.update_item(
                table_name=self.table_name,
                key=rate_limit_key,
                update_expression="SET request_count = if_not_exists(request_count, :zero) + :inc, #ttl = :ttl",
                expression_attribute_names={"#ttl": "ttl"},
                expression_attribute_values={
                    ":inc": {"N": "1"},
                    ":zero": {"N": "0"},
                    ":ttl": {"N": str(int(time.time() + 3600))},  # 1 hour TTL
                    ":limit": {"N": str(ACCESS_REQUEST_RATE_LIMIT_PER_HOUR)},
                },
                condition_expression="attribute_not_exists(request_count) OR request_count < :limit",
            )

            return True, "Rate limit check passed"

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Rate limit exceeded
                return (
                    False,
                    f"Too many requests. You can make up to {ACCESS_REQUEST_RATE_LIMIT_PER_HOUR} requests per hour.",
                )

            logger.error(f"Rate limit check error: {e}")
            # Fail open - allow request if rate limit check fails
            return True, "Rate limit check passed"

    async def get_all_pending_requests(self) -> List[AccessRequest]:
        """Get all pending requests for admin dashboard using scan (no GSI available)."""
        try:
            response = await self.client.scan(
                table_name=self.table_name,
                filter_expression="#status = :pending",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={
                    ":pending": {"S": ACCESS_REQUEST_STATUS["PENDING"]}
                },
                limit=500,  # Reasonable limit for admin operations
            )

            requests = []
            current_time = time.time()

            for item in response.get("Items", []):
                try:
                    # Check if this is an access request item by verifying SK pattern
                    if "SK" in item:
                        sk_value = (
                            item["SK"].get("S")
                            if isinstance(item.get("SK"), dict)
                            else item.get("SK")
                        )
                        if not sk_value or not sk_value.startswith("ACCESS_REQUEST#"):
                            # Skip non-access-request items
                            continue

                    ttl_value = (
                        item.get("ttl", {}).get("N", "0")
                        if isinstance(item.get("ttl"), dict)
                        else item.get("ttl", 0)
                    )
                    if float(ttl_value) > current_time:
                        requests.append(AccessRequest.from_item(item))
                except Exception as e:
                    # Log at ERROR level with item details for debugging
                    logger.error(
                        f"Error processing access request item in get_all_pending_requests: {e}"
                    )
                    logger.error(f"Item keys present: {list(item.keys())}")
                    if "SK" in item:
                        sk_value = (
                            item["SK"].get("S")
                            if isinstance(item.get("SK"), dict)
                            else item.get("SK")
                        )
                        logger.error(f"Item SK: {sk_value}")
                    # Skip this item and continue with others
                    continue

            return sorted(requests, key=lambda x: x.request_timestamp)

        except Exception as e:
            logger.error(f"Error getting all pending requests: {e}")
            return []

    async def _get_pending_request_cached(
        self, user_id: str
    ) -> Optional[AccessRequest]:
        """Get pending request for user using cached results (15-minute TTL)."""
        await self._ensure_cache_fresh()
        return self._pending_cache.get(user_id)

    async def check_batch_requests(
        self, user_ids: List[str]
    ) -> Dict[str, Optional[AccessRequest]]:
        """Check multiple users for pending requests in a single operation."""
        await self._ensure_cache_fresh()
        return {user_id: self._pending_cache.get(user_id) for user_id in user_ids}

    async def _ensure_cache_fresh(self):
        """Ensure cache is fresh, refresh if expired."""
        async with self._cache_lock:
            current_time = time.time()

            # Check if cache is valid (15 minutes)
            if (
                self._pending_cache is None
                or current_time - self._cache_timestamp > self._cache_ttl
            ):

                # Refresh cache with all pending requests
                logger.info("Refreshing pending requests cache (15-minute interval)")
                all_pending = await self._scan_all_pending_requests()
                self._pending_cache = {req.user_id: req for req in all_pending}
                self._cache_timestamp = current_time

                logger.info(
                    f"Cache refreshed with {len(self._pending_cache)} pending requests"
                )

    async def _scan_all_pending_requests(self) -> List[AccessRequest]:
        """Scan for all pending requests (internal method for caching)."""
        try:
            response = await self.client.scan(
                table_name=self.table_name,
                filter_expression="#status = :pending",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={
                    ":pending": {"S": ACCESS_REQUEST_STATUS["PENDING"]}
                },
            )

            requests = []
            current_time = time.time()

            for item in response.get("Items", []):
                try:
                    # Check if this is an access request item by verifying SK pattern
                    if "SK" in item:
                        sk_value = (
                            item["SK"].get("S")
                            if isinstance(item.get("SK"), dict)
                            else item.get("SK")
                        )
                        if not sk_value or not sk_value.startswith("ACCESS_REQUEST#"):
                            # Skip non-access-request items
                            continue

                    ttl_value = (
                        item.get("ttl", {}).get("N", "0")
                        if isinstance(item.get("ttl"), dict)
                        else item.get("ttl", 0)
                    )
                    if float(ttl_value) > current_time:
                        requests.append(AccessRequest.from_item(item))
                except Exception as e:
                    # Log at ERROR level with item details for debugging
                    logger.error(f"Error processing access request item: {e}")
                    logger.error(f"Item keys present: {list(item.keys())}")
                    if "PK" in item:
                        pk_value = (
                            item["PK"].get("S")
                            if isinstance(item.get("PK"), dict)
                            else item.get("PK")
                        )
                        logger.error(f"Item PK: {pk_value}")
                    if "SK" in item:
                        sk_value = (
                            item["SK"].get("S")
                            if isinstance(item.get("SK"), dict)
                            else item.get("SK")
                        )
                        logger.error(f"Item SK: {sk_value}")
                    # Skip this item and continue with others
                    continue

            logger.info(f"Scanned and found {len(requests)} pending requests")
            return requests

        except Exception as e:
            logger.error(f"Error scanning pending requests: {e}")
            return []

    def invalidate_cache(self):
        """Invalidate the pending requests cache."""
        self._pending_cache = None
        self._cache_timestamp = 0

    async def _get_request(
        self, user_id: str, request_timestamp: float
    ) -> Optional[AccessRequest]:
        """Get a specific access request by user_id and timestamp."""
        try:
            response = await self.client.get_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"ACCESS_REQUEST#{request_timestamp}"},
                },
            )

            item = response.get("Item")
            if item:
                return AccessRequest.from_item(item)
            return None

        except Exception as e:
            logger.error(f"Error getting request: {e}")
            return None

    async def _update_request_status(
        self, user_id: str, request_timestamp: float, new_status: str
    ) -> bool:
        """Update the status of a request (internal method)."""
        try:
            await self.client.update_item(
                table_name=self.table_name,
                key={
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"ACCESS_REQUEST#{request_timestamp}"},
                },
                update_expression="SET #status = :new_status",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={":new_status": {"S": new_status}},
            )
            return True
        except Exception as e:
            logger.error(f"Error updating request status: {e}")
            return False
