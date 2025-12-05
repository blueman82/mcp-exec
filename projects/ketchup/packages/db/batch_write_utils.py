"""
batch_write_utils.py

Shared utility for DynamoDB batch write operations with retries and error handling.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def batch_write_items_with_retries(
    client: Any,
    table_name: str,
    put_requests: List[Dict[str, Any]],
    batch_size: int = 25,
    max_retries: int = 5,
    throttle_success: float = 0.5,
    throttle_failure: float = 1.0,
    get_underlying_client: Optional[Callable[[], Any]] = None,
) -> Tuple[int, int]:
    """
    Perform batch write operations to DynamoDB with retries for unprocessed items.

    Args:
        client: The DynamoDBAsyncClient or similar (must provide _get_client if get_underlying_client is None).
        table_name: The DynamoDB table name.
        put_requests: List of PutRequest dicts for DynamoDB.
        batch_size: Max items per batch (default 25 for DynamoDB).
        max_retries: Max number of retries for unprocessed items.
        throttle_success: Sleep time (seconds) between successful batches.
        throttle_failure: Sleep time (seconds) after batches with unprocessed items.
        get_underlying_client: Optional function to get the underlying aioboto3 client.

    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0
    total = len(put_requests)

    for i in range(0, total, batch_size):
        batch = put_requests[i : i + batch_size]
        request_items = {table_name: batch}
        retries = 0
        unprocessed = batch
        while unprocessed and retries <= max_retries:
            try:
                # Get the underlying client if needed
                if get_underlying_client:
                    underlying_client = await get_underlying_client()
                else:
                    underlying_client = await client._get_client()
                response = await underlying_client.batch_write_item(RequestItems=request_items)
                unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])
                current_success = len(batch) - len(unprocessed)
                current_failure = len(unprocessed)
                success_count += current_success
                failure_count += current_failure
                if unprocessed:
                    logger.warning(
                        "%s items were unprocessed in the batch (retry %s/%s): %s",
                        len(unprocessed),
                        retries + 1,
                        max_retries,
                        unprocessed,
                    )
                    request_items = {table_name: unprocessed}
                    retries += 1
                    await asyncio.sleep(throttle_failure)
                else:
                    await asyncio.sleep(throttle_success)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", "Unknown error")
                logger.error(
                    "DynamoDB error in batch_write_items_with_retries: %s - %s",
                    error_code,
                    error_message,
                )
                failure_count += len(unprocessed)
                break
            except Exception as e:
                logger.error(
                    "Unexpected error in batch_write_items_with_retries: %s",
                    str(e),
                    exc_info=True,
                )
                failure_count += len(unprocessed)
                break
    logger.info(
        "Batch write complete: %s successful, %s failed (max_retries=%s)",
        success_count,
        failure_count,
        max_retries,
    )
    return success_count, failure_count
