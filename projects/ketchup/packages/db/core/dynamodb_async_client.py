"""
DynamoDB async client module.

This module provides an asynchronous client for DynamoDB operations.
"""

from typing import Any, Dict, Optional

import aioboto3  # type: ignore[import-untyped]

from packages.core.async_client import AsyncClient
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import with_exponential_backoff
from packages.db.config.dynamodb_config import DynamoDBConfig

logger = setup_logger(__name__)


class DynamoDBAsyncClient(AsyncClient[DynamoDBConfig, Dict[str, Any]]):
    """Specialized client for asynchronous DynamoDB operations."""

    def __init__(
        self,
        config: Optional[DynamoDBConfig] = None,
        max_concurrent_requests: int = 10,
    ) -> None:
        """Initialize the DynamoDB async client.

        Args:
            config: Configuration for DynamoDB
            max_concurrent_requests: Maximum number of concurrent requests
        """
        if not config:
            config = DynamoDBConfig()

        super().__init__(
            config=config,
            max_concurrent_requests=max_concurrent_requests,
        )
        self._client = None
        self._aioboto3_session = None
        self._client_cm = None  # Store the client context manager

    async def _get_client(self):
        """Get or initialize the DynamoDB client.

        Returns:
            Initialized DynamoDB client
        """
        try:
            # If client exists, try a simple test operation to verify it's still valid
            if self._client:
                try:
                    # Test if client is still valid with a simple operation
                    # This just checks the session without actually hitting DynamoDB
                    self._client._request_signer
                    return self._client
                except Exception as e:
                    # Session is closed or other error, clear the client to recreate it
                    logger.warning("DynamoDB client session invalid, recreating: %s", str(e))
                    await self.cleanup()

            # Initialize session and client if not already done
            if not self._aioboto3_session:
                self._aioboto3_session = aioboto3.Session()

            # Create client using the context manager properly
            client_cm = self._aioboto3_session.client(
                "dynamodb", region_name=self.config.get_region()
            )
            self._client = await client_cm.__aenter__()
            self._client_cm = client_cm  # Store the context manager for cleanup

            return self._client

        except Exception as e:
            # In case of any error, clean up and re-raise
            logger.error("Error creating DynamoDB client: %s", str(e))
            await self.cleanup()
            raise

    async def cleanup(self):
        """Cleanup resources thoroughly."""
        try:
            logger.info("Cleaning up DynamoDB async client resources")
            if self._client and self._client_cm:
                try:
                    await self._client_cm.__aexit__(None, None, None)
                except Exception as e:
                    logger.error("Error closing DynamoDB client: %s", str(e))
                finally:
                    self._client = None
                    self._client_cm = None
                    self._aioboto3_session = None
        except Exception as e:
            logger.error("Error during DynamoDB client cleanup: %s", str(e))

    @with_exponential_backoff()
    async def put_item(
        self,
        item: Dict[str, Any],
        condition_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Put an item into DynamoDB with retry logic.

        Args:
            item: Item to put into DynamoDB
            condition_expression: Optional condition expression
            expression_attribute_values: Optional expression attribute values
            table_name: Optional table name override

        Returns:
            Response from DynamoDB

        Raises:
            ClientError: If a DynamoDB error occurs
        """
        client = await self._get_client()

        params = {"TableName": table_name or self.config.get_table_name(), "Item": item}

        if condition_expression:
            params["ConditionExpression"] = condition_expression

        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values

        return await client.put_item(**params)

    @with_exponential_backoff()
    async def update_item(
        self,
        key: Dict[str, Any],
        update_expression: str,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        condition_expression: Optional[str] = None,
        table_name: Optional[str] = None,
        return_values: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an item in DynamoDB with retry logic.

        Args:
            key: Key of the item to update
            update_expression: Update expression
            expression_attribute_values: Optional expression attribute values
            expression_attribute_names: Optional expression attribute names
            condition_expression: Optional condition expression
            table_name: Optional table name override
            return_values: Optional return values specification (e.g., "ALL_NEW", "UPDATED_NEW")

        Returns:
            Response from DynamoDB

        Raises:
            ClientError: If a DynamoDB error occurs
        """
        client = await self._get_client()

        params = {
            "TableName": table_name or self.config.get_table_name(),
            "Key": key,
            "UpdateExpression": update_expression,
        }

        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values

        if expression_attribute_names:
            params["ExpressionAttributeNames"] = expression_attribute_names

        if condition_expression:
            params["ConditionExpression"] = condition_expression

        if return_values:
            params["ReturnValues"] = return_values

        return await client.update_item(**params)

    @with_exponential_backoff()
    async def delete_item(
        self,
        key: Dict[str, Any],
        condition_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete an item from DynamoDB with retry logic.

        Args:
            key: Key of the item to delete
            condition_expression: Optional condition expression
            expression_attribute_values: Optional expression attribute values
            table_name: Optional table name override

        Returns:
            Response from DynamoDB

        Raises:
            ClientError: If a DynamoDB error occurs
        """
        client = await self._get_client()

        params = {
            "TableName": table_name or self.config.get_table_name(),
            "Key": key,
        }

        if condition_expression:
            params["ConditionExpression"] = condition_expression

        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values

        return await client.delete_item(**params)

    @with_exponential_backoff()
    async def get_item(
        self,
        key: Dict[str, Any],
        table_name: Optional[str] = None,
        consistent_read: bool = False,
    ) -> Dict[str, Any]:
        """Get an item from DynamoDB with retry logic.

        Args:
            key: Key of the item to retrieve
            table_name: Optional table name override
            consistent_read: If True, use strongly consistent read

        Returns:
            Response from DynamoDB

        Raises:
            ClientError: If a DynamoDB error occurs
        """
        client = await self._get_client()

        params = {
            "TableName": table_name or self.config.get_table_name(),
            "Key": key,
        }

        if consistent_read:
            params["ConsistentRead"] = True

        return await client.get_item(**params)

    @with_exponential_backoff()
    async def scan(
        self,
        filter_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        table_name: Optional[str] = None,
        limit: Optional[int] = None,
        exclusive_start_key: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Scan items in DynamoDB with retry logic.

        Args:
            filter_expression: Optional filter expression
            expression_attribute_values: Optional expression attribute values (can be plain or DynamoDB format)
            expression_attribute_names: Optional expression attribute names
            table_name: Optional table name override
            limit: Optional maximum number of items to return
            exclusive_start_key: Optional key to start scan from

        Returns:
            Response from DynamoDB

        Raises:
            ClientError: If a DynamoDB error occurs
        """
        client = await self._get_client()

        params = {
            "TableName": table_name or self.config.get_table_name(),
        }

        if filter_expression:
            params["FilterExpression"] = filter_expression

        if expression_attribute_values:
            # Convert plain values to DynamoDB format if needed
            formatted_values = {}
            for key, value in expression_attribute_values.items():
                if isinstance(value, dict) and any(
                    k in value for k in ["S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"]
                ):
                    # Already in DynamoDB format
                    formatted_values[key] = value
                else:
                    # Convert to DynamoDB format
                    formatted_values[key] = self._convert_to_dynamodb_format(value)
            params["ExpressionAttributeValues"] = formatted_values  # type: ignore[assignment]

        if expression_attribute_names:
            params["ExpressionAttributeNames"] = expression_attribute_names  # type: ignore[assignment]

        if limit:
            params["Limit"] = limit  # type: ignore[assignment]

        if exclusive_start_key:
            params["ExclusiveStartKey"] = exclusive_start_key  # type: ignore[assignment]

        return await client.scan(**params)

    @with_exponential_backoff()
    async def query(
        self,
        key_condition_expression: str,
        expression_attribute_values: Dict[str, Any],
        filter_expression: Optional[str] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        table_name: Optional[str] = None,
        limit: Optional[int] = None,
        exclusive_start_key: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query items from DynamoDB with retry logic.

        Args:
            key_condition_expression: Key condition expression
            expression_attribute_values: Expression attribute values
            filter_expression: Optional filter expression
            expression_attribute_names: Optional expression attribute names
            table_name: Optional table name override
            limit: Optional maximum number of items to return
            exclusive_start_key: Optional key to start query from

        Returns:
            Response from DynamoDB

        Raises:
            ClientError: If a DynamoDB error occurs
        """
        client = await self._get_client()

        # Convert expression_attribute_values to DynamoDB format if needed
        formatted_values = {}
        for key, value in expression_attribute_values.items():
            if isinstance(value, dict) and any(
                k in value for k in ["S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"]
            ):
                # Already in DynamoDB format
                formatted_values[key] = value
            else:
                # Convert to DynamoDB format
                formatted_values[key] = self._convert_to_dynamodb_format(value)

        params = {
            "TableName": table_name or self.config.get_table_name(),
            "KeyConditionExpression": key_condition_expression,
            "ExpressionAttributeValues": formatted_values,
        }

        if filter_expression:
            params["FilterExpression"] = filter_expression

        if expression_attribute_names:
            params["ExpressionAttributeNames"] = expression_attribute_names

        if limit:
            params["Limit"] = limit  # type: ignore[assignment]

        if exclusive_start_key:
            params["ExclusiveStartKey"] = exclusive_start_key

        return await client.query(**params)

    def _convert_to_dynamodb_format(self, value: Any) -> Dict[str, Any]:
        """Convert a Python value to DynamoDB format.

        Args:
            value: Python value to convert

        Returns:
            DynamoDB formatted value
        """
        if value is None:
            return {"NULL": True}
        elif isinstance(value, bool):
            return {"BOOL": value}
        elif isinstance(value, str):
            return {"S": value}
        elif isinstance(value, (int, float)):
            return {"N": str(value)}
        elif isinstance(value, bytes):
            return {"B": value}
        elif isinstance(value, list):
            if not value:
                return {"L": []}
            # Check if it's a list of strings (SS), numbers (NS), or mixed (L)
            if all(isinstance(v, str) for v in value):
                return {"SS": value}
            elif all(isinstance(v, (int, float)) for v in value):
                return {"NS": [str(v) for v in value]}
            else:
                # Mixed list
                return {"L": [self._convert_to_dynamodb_format(v) for v in value]}
        elif isinstance(value, dict):
            # Map type
            return {"M": {k: self._convert_to_dynamodb_format(v) for k, v in value.items()}}
        else:
            # Default to string representation
            return {"S": str(value)}
