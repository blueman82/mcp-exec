"""message_services.py

Consolidated message processing services for flag review functionality.
Provides centralized message handling, formatting, validation, and transformation
services that were previously scattered across multiple modules.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class MessageFormattingService:
    """Handles message formatting and text processing utilities."""

    def __init__(self):
        """Initialize the message formatting service."""
        pass

    def format_timestamp(self, timestamp: Optional[str] = None) -> str:
        """Format timestamp for display in messages."""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%H:%M")
            except ValueError:
                logger.warning(f"Invalid timestamp format: {timestamp}")
        return datetime.now(timezone.utc).strftime("%H:%M")

    def format_user_mention(self, user_id: str) -> str:
        """Format user ID as Slack mention."""
        return f"<@{user_id}>"

    def format_channel_mention(self, channel_id: str) -> str:
        """Format channel ID as Slack mention."""
        return f"<#{channel_id}>"

    def format_message_link(
        self, channel_id: str, message_ts: str, link_text: str = "View"
    ) -> str:
        """Format message link for Slack."""
        ts_no_dot = message_ts.replace('.', '')
        url = f"https://adobe.enterprise.slack.com/archives/{channel_id}/p{ts_no_dot}"
        return f"<{url}|{link_text}>"

    def truncate_text(self, text: str, max_length: int = 500) -> str:
        """Truncate text with ellipsis if too long."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."


class MessageValidationService:
    """Handles message validation and parsing utilities."""

    def __init__(self):
        """Initialize the message validation service."""
        pass

    def validate_message_content(self, content: str) -> Tuple[bool, List[str]]:
        """Validate message content for safety and format."""
        issues = []
        if not content or not content.strip():
            issues.append("Empty content")
            return False, issues
        if len(content) > 3000:
            issues.append("Content too long")
        # Check for potentially harmful content
        harmful_patterns = ['<script', 'javascript:', 'data:text/html']
        for pattern in harmful_patterns:
            if pattern.lower() in content.lower():
                issues.append(f"Potentially harmful content: {pattern}")
        return len(issues) == 0, issues

    def parse_action_value(self, action_value: str) -> Dict[str, str]:
        """Parse action value from button clicks."""
        try:
            parts = action_value.split('|')
            return {
                'primary': parts[0] if parts else '',
                'secondary': parts[1] if len(parts) > 1 else '',
                'tertiary': parts[2] if len(parts) > 2 else '',
                'quaternary': parts[3] if len(parts) > 3 else ''
            }
        except Exception as e:
            logger.error(f"Error parsing action value: {e}")
            return {'primary': action_value, 'secondary': '', 'tertiary': '', 'quaternary': ''}

    def extract_metadata_from_modal(self, modal_view: Dict[str, Any]) -> Dict[str, str]:
        """Extract metadata from modal private_metadata field."""
        try:
            private_metadata = modal_view.get('private_metadata', '')
            parts = private_metadata.split('|')
            return {
                'channel_id': parts[0] if parts else '',
                'message_ts': parts[1] if len(parts) > 1 else '',
                'user_id': parts[2] if len(parts) > 2 else '',
                'flag_id': parts[3] if len(parts) > 3 else ''
            }
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {'channel_id': '', 'message_ts': '', 'user_id': '', 'flag_id': ''}


class MessageTransformationService:
    """Handles message transformation and preparation utilities."""

    def __init__(self):
        """Initialize the message transformation service."""
        pass

    def prepare_flag_context(
        self,
        channel_id: str,
        user_id: str,
        feedback_text: str,
        message_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Prepare context data for flag operations."""
        return {
            'channel_id': channel_id,
            'user_id': user_id,
            'feedback_text': feedback_text,
            'message_ts': message_ts,
            'flag_id': f"{channel_id}_{message_ts or 'no_ts'}_{user_id}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'display_time': self._format_display_time()
        }

    def prepare_notification_data(
        self,
        recipient_id: str,
        message_type: str,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare notification data for sending."""
        return {
            'recipient_id': recipient_id,
            'message_type': message_type,
            'context': context_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'notification_id': f"{recipient_id}_{message_type}_{int(datetime.now().timestamp())}"
        }

    def transform_blocks_for_update(
        self,
        original_blocks: List[Dict[str, Any]],
        update_type: str,
        update_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Transform message blocks for updates."""
        try:
            blocks = original_blocks.copy()
            # Add context block based on update type
            if update_type == "flagged":
                context_text = f"⚠️ Flagged for review by {update_data.get('user', 'Unknown')}"
            elif update_type == "acknowledged":
                context_text = f"✅ Acknowledged by {update_data.get('admin', 'Admin')}"
            elif update_type == "replied":
                context_text = f"💬 Reply sent by {update_data.get('admin', 'Admin')}"
            else:
                context_text = f"🔄 Updated: {update_type}"
            # Find or add context block
            context_block = {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": context_text}]
            }
            # Remove existing context blocks with flags
            blocks = [b for b in blocks if not self._is_flag_context_block(b)]
            blocks.append(context_block)
            return blocks
        except Exception as e:
            logger.error(f"Error transforming blocks: {e}")
            return original_blocks

    def _format_display_time(self) -> str:
        """Format current time for display."""
        return datetime.now(timezone.utc).strftime("%H:%M")

    def _is_flag_context_block(self, block: Dict[str, Any]) -> bool:
        """Check if block is a flag-related context block."""
        if block.get('type') != 'context':
            return False
            
        elements = block.get('elements', [])
        for element in elements:
            text = element.get('text', '')
            if any(flag in text for flag in ['Flagged', 'Acknowledged', 'Reply sent']):
                return True
        return False


class MessageQueueService:
    """Handles message queue processing and batch operations."""

    def __init__(self):
        """Initialize the message queue service."""
        self.pending_messages = []
        self.batch_size = 10

    def queue_message(self, message_data: Dict[str, Any]) -> None:
        """Add message to processing queue."""
        self.pending_messages.append({
            **message_data,
            'queued_at': datetime.now(timezone.utc).isoformat()
        })

    def get_pending_batch(self) -> List[Dict[str, Any]]:
        """Get a batch of pending messages for processing."""
        batch = self.pending_messages[:self.batch_size]
        self.pending_messages = self.pending_messages[self.batch_size:]
        return batch

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len(self.pending_messages)

    def clear_queue(self) -> int:
        """Clear all pending messages."""
        count = len(self.pending_messages)
        self.pending_messages.clear()
        return count


class MessageAnalyticsService:
    """Handles message analytics and tracking utilities."""

    def __init__(self):
        """Initialize the message analytics service."""
        self.message_stats = {
            'total_messages': 0,
            'successful_sends': 0,
            'failed_sends': 0,
            'updates': 0
        }

    def track_message_sent(self, success: bool) -> None:
        """Track a message send attempt."""
        self.message_stats['total_messages'] += 1
        if success:
            self.message_stats['successful_sends'] += 1
        else:
            self.message_stats['failed_sends'] += 1

    def track_message_update(self) -> None:
        """Track a message update operation."""
        self.message_stats['updates'] += 1

    def get_success_rate(self) -> float:
        """Calculate message send success rate."""
        total = self.message_stats['total_messages']
        if total == 0:
            return 0.0
        return (self.message_stats['successful_sends'] / total) * 100

    def get_stats_summary(self) -> Dict[str, Union[int, float]]:
        """Get comprehensive statistics summary."""
        return {
            **self.message_stats,
            'success_rate': self.get_success_rate()
        }

    def reset_stats(self) -> None:
        """Reset all statistics counters."""
        self.message_stats = {
            'total_messages': 0,
            'successful_sends': 0,
            'failed_sends': 0,
            'updates': 0
        }


class MessageOrchestratorService:
    """Main orchestrator for all message services."""

    def __init__(self):
        """Initialize the message orchestrator with all services."""
        self.formatting = MessageFormattingService()
        self.validation = MessageValidationService()
        self.transformation = MessageTransformationService()
        self.queue = MessageQueueService()
        self.analytics = MessageAnalyticsService()

    def get_formatting_service(self) -> MessageFormattingService:
        """Get the formatting service instance."""
        return self.formatting

    def get_validation_service(self) -> MessageValidationService:
        """Get the validation service instance."""
        return self.validation

    def get_transformation_service(self) -> MessageTransformationService:
        """Get the transformation service instance."""
        return self.transformation

    def get_queue_service(self) -> MessageQueueService:
        """Get the queue service instance."""
        return self.queue

    def get_analytics_service(self) -> MessageAnalyticsService:
        """Get the analytics service instance."""
        return self.analytics


# Factory function for service creation
def create_message_services() -> MessageOrchestratorService:
    """Create and return a configured message services orchestrator.
    
    Returns:
        Configured MessageOrchestratorService instance.
    """
    return MessageOrchestratorService()
