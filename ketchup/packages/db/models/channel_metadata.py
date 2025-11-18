"""
channel_metadata.py

This module contains the ChannelMetadata data class for channel metadata.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChannelMetadata:
    """
    Data class representing metadata for a Slack channel.

    This class encapsulates all metadata associated with a channel to provide
    a more structured approach to storing and retrieving channel data.

    Attributes:
        channel_id: The unique identifier of the Slack channel
        channel_name: The name of the Slack channel
        archived: Whether the channel is archived
        date_created_epoch: Optional creation timestamp
        custom_fields: Optional dictionary of additional metadata fields
        jira_report_status: Status of JIRA report posting (PENDING, PROCESSING, PROCESSED, FAILED, SKIPPED)
        jira_report_timestamp: Timestamp when JIRA report was posted
    """

    channel_id: str
    channel_name: str
    archived: bool = False
    date_created_epoch: Optional[int] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    jira_report_status: str = "PENDING"
    jira_report_timestamp: Optional[int] = None

    def to_item(self) -> Dict[str, Any]:
        """
        Convert metadata to DynamoDB item format with proper type descriptors.

        Returns:
            Dictionary formatted for DynamoDB storage with type information
        """
        # Create item with proper DynamoDB type descriptors
        item = {
            "PK": {"S": f"CHANNEL#{self.channel_id}"},
            "SK": {"S": "CSO_DETAILS"},
            "channel_id": {"S": self.channel_id},
            "channel_name": {"S": self.channel_name},
            "archived": {"BOOL": self.archived},
            "timestamp": {"N": str(int(time.time()))},
            "jira_report_status": {"S": self.jira_report_status},
        }

        # Add creation date if available
        if self.date_created_epoch is not None:
            item["created_at"] = {"N": str(self.date_created_epoch)}
        else:
            item["created_at"] = {"N": "0"}

        # Add JIRA report timestamp if available
        if self.jira_report_timestamp is not None:
            item["jira_report_timestamp"] = {"N": str(self.jira_report_timestamp)}

        # Include archived_at if not present
        if "archived_at" not in self.custom_fields:
            item["archived_at"] = {"N": "0"}

        # Add custom fields with appropriate type descriptors
        if self.custom_fields:
            for key, value in self.custom_fields.items():
                if key == "archived_at" and isinstance(value, int):
                    item["archived_at"] = {"N": str(value)}
                elif key == "created_at" and isinstance(value, int):
                    item["created_at"] = {"N": str(value)}
                elif key == "customer_name" and isinstance(value, str):
                    item["customer_name"] = {"S": value}
                elif key == "jira_ticket" and isinstance(value, str):
                    item["jira_ticket"] = {"S": value}
                elif key == "product" and isinstance(value, str):
                    item["product"] = {"S": value}
                elif isinstance(value, str):
                    item[key] = {"S": value}
                elif isinstance(value, bool):
                    item[key] = {"BOOL": value}
                elif isinstance(value, (int, float)):
                    item[key] = {"N": str(value)}
                # Handle other types as needed

        # Ensure required fields exist
        if "customer_name" not in item:
            item["customer_name"] = {"S": "NOT YET AVAILABLE"}
        if "jira_ticket" not in item:
            item["jira_ticket"] = {"S": "NOT YET AVAILABLE"}
        if "product" not in item:
            item["product"] = {"S": "unknown"}

        return item
