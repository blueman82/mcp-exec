"""
sqs_client.py

AWS SQS client for sending and receiving event messages.
"""

import json
from typing import Any, Dict, List

import boto3

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class SQSClient:
    """Client for interacting with AWS SQS."""

    def __init__(self, queue_url: str, region: str = "eu-west-1"):
        """
        Initialize SQS client.

        Args:
            queue_url: The URL of the SQS queue
            region: AWS region (default: eu-west-1)
        """
        self.queue_url = queue_url
        self.client = boto3.client("sqs", region_name=region)

    async def send_message(self, message_body: Dict[str, Any]) -> bool:
        """
        Send message to SQS queue.

        Args:
            message_body: Dictionary containing the message data

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            response = self.client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    "event_type": {
                        "StringValue": message_body.get("event_type", "unknown"),
                        "DataType": "String",
                    },
                    "service": {
                        "StringValue": message_body.get("service", "unknown"),
                        "DataType": "String",
                    },
                },
            )
            logger.info(
                f"Sent SQS message: {response['MessageId']} for event: {message_body.get('event_type')}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send SQS message: {e}")
            return False

    async def receive_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Receive messages from queue.

        Args:
            max_messages: Maximum number of messages to receive (1-10)

        Returns:
            List of message dictionaries
        """
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=20,  # Long polling
                MessageAttributeNames=["All"],
            )
            return response.get("Messages", [])
        except Exception as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            return []

    async def delete_message(self, receipt_handle: str) -> bool:
        """
        Delete processed message from queue.

        Args:
            receipt_handle: The receipt handle of the message to delete

        Returns:
            True if message was deleted successfully, False otherwise
        """
        try:
            self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)
            return True
        except Exception as e:
            logger.error(f"Failed to delete SQS message: {e}")
            return False

    def get_queue_depth(self) -> int:
        """
        Get approximate number of messages in queue.

        Returns:
            Number of messages in queue, or -1 if error
        """
        try:
            response = self.client.get_queue_attributes(
                QueueUrl=self.queue_url, AttributeNames=["ApproximateNumberOfMessages"]
            )
            return int(response["Attributes"]["ApproximateNumberOfMessages"])
        except Exception as e:
            logger.error(f"Failed to get queue depth: {e}")
            return -1
