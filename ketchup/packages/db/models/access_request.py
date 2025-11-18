"""
access_request.py

Model for access request items in DynamoDB.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AccessRequest:
    """Model for access request items in DynamoDB."""

    # Required fields
    user_id: str
    user_name: str
    request_timestamp: float  # epoch seconds
    status: str  # 'pending', 'approved', 'rejected', 'expired'

    # Optional fields
    user_email: Optional[str] = None
    reason_for_access: Optional[str] = None
    decided_by_id: Optional[str] = None
    decided_by_name: Optional[str] = None
    decision_timestamp: Optional[float] = None
    rejection_reason: Optional[str] = None

    # Slack message tracking
    channel_ts: Optional[str] = None  # Message timestamp in access channel
    response_url: Optional[str] = None  # For updating the message

    # Metadata
    request_metadata: Dict[str, Any] = field(default_factory=dict)

    # Auto-calculated fields
    ttl: Optional[int] = None

    def __post_init__(self):
        """Calculate TTL if not provided."""
        if self.ttl is None:
            from packages.core.constants import ACCESS_REQUEST_TTL_HOURS

            self.ttl = int(time.time() + (ACCESS_REQUEST_TTL_HOURS * 3600))

    def to_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            "PK": {"S": f"USER#{self.user_id}"},
            "SK": {"S": f"ACCESS_REQUEST#{self.request_timestamp}"},
            "user_id": {"S": self.user_id},
            "user_name": {"S": self.user_name},
            "request_timestamp": {"N": str(self.request_timestamp)},
            "status": {"S": self.status},
            "ttl": {"N": str(self.ttl)},
        }

        # Add optional string fields
        if self.user_email is not None:
            item["user_email"] = {"S": self.user_email}
        if self.reason_for_access is not None:
            item["reason_for_access"] = {"S": self.reason_for_access}
        if self.decided_by_id is not None:
            item["decided_by_id"] = {"S": self.decided_by_id}
        if self.decided_by_name is not None:
            item["decided_by_name"] = {"S": self.decided_by_name}
        if self.rejection_reason is not None:
            item["rejection_reason"] = {"S": self.rejection_reason}
        if self.channel_ts is not None:
            item["channel_ts"] = {"S": self.channel_ts}
        if self.response_url is not None:
            item["response_url"] = {"S": self.response_url}

        # Add optional numeric fields
        if self.decision_timestamp is not None:
            item["decision_timestamp"] = {"N": str(self.decision_timestamp)}

        # Add metadata if not empty
        if self.request_metadata:
            item["request_metadata"] = {"S": json.dumps(self.request_metadata)}

        return item

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> "AccessRequest":
        """Create instance from DynamoDB item."""
        # Handle both formats - with and without type descriptors
        # Check for required fields first
        if "user_id" not in item:
            raise ValueError("Missing required field: user_id")
        if "user_name" not in item:
            raise ValueError("Missing required field: user_name")
        if "request_timestamp" not in item:
            raise ValueError("Missing required field: request_timestamp")
        if "status" not in item:
            raise ValueError("Missing required field: status")

        user_id = (
            item["user_id"].get("S")
            if isinstance(item.get("user_id"), dict)
            else item["user_id"]
        )
        user_name = (
            item["user_name"].get("S")
            if isinstance(item.get("user_name"), dict)
            else item["user_name"]
        )
        request_timestamp = (
            float(item["request_timestamp"].get("N"))
            if isinstance(item.get("request_timestamp"), dict)
            else item["request_timestamp"]
        )
        status = (
            item["status"].get("S")
            if isinstance(item.get("status"), dict)
            else item["status"]
        )

        # Handle optional user_email
        user_email = None
        if "user_email" in item:
            user_email = (
                item["user_email"].get("S")
                if isinstance(item.get("user_email"), dict)
                else item.get("user_email")
            )

        # Handle optional fields
        ttl = None
        if "ttl" in item:
            ttl = (
                int(item["ttl"].get("N"))
                if isinstance(item["ttl"], dict)
                else item.get("ttl")
            )

        reason_for_access = None
        if "reason_for_access" in item:
            reason_for_access = (
                item["reason_for_access"].get("S")
                if isinstance(item["reason_for_access"], dict)
                else item.get("reason_for_access")
            )

        decided_by_id = None
        if "decided_by_id" in item:
            decided_by_id = (
                item["decided_by_id"].get("S")
                if isinstance(item["decided_by_id"], dict)
                else item.get("decided_by_id")
            )

        decided_by_name = None
        if "decided_by_name" in item:
            decided_by_name = (
                item["decided_by_name"].get("S")
                if isinstance(item["decided_by_name"], dict)
                else item.get("decided_by_name")
            )

        decision_timestamp = None
        if "decision_timestamp" in item:
            decision_timestamp = (
                float(item["decision_timestamp"].get("N"))
                if isinstance(item["decision_timestamp"], dict)
                else item.get("decision_timestamp")
            )

        rejection_reason = None
        if "rejection_reason" in item:
            rejection_reason = (
                item["rejection_reason"].get("S")
                if isinstance(item["rejection_reason"], dict)
                else item.get("rejection_reason")
            )

        channel_ts = None
        if "channel_ts" in item:
            channel_ts = (
                item["channel_ts"].get("S")
                if isinstance(item["channel_ts"], dict)
                else item.get("channel_ts")
            )

        response_url = None
        if "response_url" in item:
            response_url = (
                item["response_url"].get("S")
                if isinstance(item["response_url"], dict)
                else item.get("response_url")
            )

        request_metadata = {}
        if "request_metadata" in item:
            metadata_str = (
                item["request_metadata"].get("S")
                if isinstance(item["request_metadata"], dict)
                else item.get("request_metadata")
            )
            if metadata_str:
                try:
                    request_metadata = (
                        json.loads(metadata_str)
                        if isinstance(metadata_str, str)
                        else metadata_str
                    )
                except (json.JSONDecodeError, TypeError):
                    request_metadata = {}

        return cls(
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            request_timestamp=request_timestamp,
            status=status,
            ttl=ttl,
            reason_for_access=reason_for_access,
            decided_by_id=decided_by_id,
            decided_by_name=decided_by_name,
            decision_timestamp=decision_timestamp,
            rejection_reason=rejection_reason,
            channel_ts=channel_ts,
            response_url=response_url,
            request_metadata=request_metadata,
        )
