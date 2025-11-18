"""
feedback_operations.py

This module contains operations for feedback management in DynamoDB.
"""

from typing import Any, Dict, cast

from packages.core.logging import setup_logger
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


class FeedbackOperations(BaseOperations):
    """Operations for feedback management in DynamoDB."""

    async def store_feedback(self, feedback_item: Dict[str, Any]) -> bool:
        """
        Store feedback item in DynamoDB.

        Args:
            feedback_item: Dictionary containing feedback information

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Storing feedback in DynamoDB")

            # Convert the plain Python dictionary to DynamoDB format
            dynamodb_item = self._format_for_dynamodb(feedback_item)

            await self.client.put_item(item=dynamodb_item, table_name=self.table_name)
            logger.info("Successfully stored feedback")
            return True
        except Exception as e:
            logger.error("Error storing feedback: %s", str(e))
            return False

    def _format_for_dynamodb(self, item: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Convert a plain Python dictionary to DynamoDB format.

        Args:
            item: Plain Python dictionary

        Returns:
            Dictionary in DynamoDB format
        """
        dynamodb_item: Dict[str, Dict[str, Any]] = {}

        for key, value in item.items():
            if isinstance(value, str):
                dynamodb_item[key] = {"S": value}
            elif isinstance(value, int):
                dynamodb_item[key] = {"N": str(value)}
            elif isinstance(value, float):
                dynamodb_item[key] = {"N": str(value)}
            elif isinstance(value, bool):
                dynamodb_item[key] = cast(Any, {"BOOL": value})  # type: ignore[dict-item]
            elif value is None:
                dynamodb_item[key] = cast(Any, {"NULL": True})  # type: ignore[dict-item]
            elif isinstance(value, list):
                formatted_list = []
                for item_in_list in value:
                    if isinstance(item_in_list, str):
                        formatted_list.append({"S": item_in_list})
                    elif isinstance(item_in_list, (int, float)):
                        formatted_list.append({"N": str(item_in_list)})
                    elif isinstance(item_in_list, bool):
                        formatted_list.append({"BOOL": item_in_list})
                    elif item_in_list is None:
                        formatted_list.append({"NULL": True})
                    elif isinstance(item_in_list, list):
                        logger.warning(
                            "Nested list found during DynamoDB formatting, converting to string: %s",
                            str(item_in_list)[:100],
                        )
                        formatted_list.append({"S": str(item_in_list)})
                    elif isinstance(item_in_list, dict):
                        formatted_list.append(
                            {"M": self._format_for_dynamodb(item_in_list)}
                        )
                    else:
                        formatted_list.append({"S": str(item_in_list)})
                dynamodb_item[key] = cast(Any, {"L": formatted_list})
            elif isinstance(value, dict):
                dynamodb_item[key] = cast(Any, {"M": self._format_for_dynamodb(value)})  # type: ignore[dict-item]
            else:
                dynamodb_item[key] = {"S": str(value)}

        return dynamodb_item

    async def cleanup_channel_feedback_data(self, channel_id: str) -> bool:
        """
        Clean up all feedback flag data for a channel when it's archived.

        Args:
            channel_id: The channel ID to clean up feedback data for

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # 1. Query all FEEDBACK items for this channel
            feedback_result = await self.client.query(
                table_name=self.table_name,
                key_condition_expression="PK = :pk",
                expression_attribute_values={":pk": {"S": f"FEEDBACK#{channel_id}"}},
            )

            # 2. Query all MESSAGE flag status items for this channel
            message_result = await self.client.query(
                table_name=self.table_name,
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": {"S": f"MESSAGE#{channel_id}"},
                    ":sk_prefix": {"S": "FLAG_STATUS#"},
                },
            )

            # Combine results from both queries
            items = feedback_result.get("Items", []) + message_result.get("Items", [])
            if not items:
                logger.info(f"No feedback flag data found for channel {channel_id}")
                return True

            # Delete items in batches
            for i in range(0, len(items), 25):  # DynamoDB batch limit
                batch = items[i : i + 25]
                delete_requests = []

                for item in batch:
                    delete_requests.append(
                        {
                            "DeleteRequest": {
                                "Key": {"PK": item.get("PK"), "SK": item.get("SK")}
                            }
                        }
                    )

                if delete_requests:
                    # Execute batch delete using the underlying client
                    underlying_client = await self.client._get_client()
                    response = await underlying_client.batch_write_item(
                        RequestItems={self.table_name: delete_requests}
                    )

                    # Handle any unprocessed items
                    unprocessed = response.get("UnprocessedItems", {}).get(
                        self.table_name, []
                    )
                    if unprocessed:
                        logger.warning(
                            f"Failed to delete {len(unprocessed)} feedback flag records"
                        )

            logger.info(
                f"Deleted {len(items)} feedback flag records for channel {channel_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error cleaning up feedback data for channel {channel_id}: {e}"
            )
            return False

    async def cleanup(self) -> None:
        """
        Clean up any resources used by this operations instance.

        FeedbackOperations implementation delegates to the parent BaseOperations cleanup.
        """
        logger.info("Cleaning up FeedbackOperations instance")
        await super().cleanup()
