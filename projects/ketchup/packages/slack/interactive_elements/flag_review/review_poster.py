"""
review_poster.py

Handles review posting and summary generation for flag review functionality.
Provides specialized methods for creating review blocks, posting summaries,
and managing review-related messages.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.slack.interactive_elements.flag_review.flag_types import REVIEW_CHANNEL_ID

logger = setup_logger(__name__)


class ReviewPoster:
    """Handles review posting and summary operations."""

    def __init__(self, dependency_container):
        """Initialize the review poster with dependency injection container.

        Args:
            dependency_container: TypedDI container for dependency access.
        """
        self.container = dependency_container

    @property
    def posting_handler(self):
        """Get posting handler from dependency container."""
        return self.container.get_posting_handler()

    async def post_review_summary(
        self,
        channel_id: str,
        flag_count: int,
        acknowledged_count: int,
        replied_count: int,
        period: str = "week",
    ) -> bool:
        """Post a summary of review activity.

        Args:
            channel_id: Channel to post summary to.
            flag_count: Number of flags raised.
            acknowledged_count: Number of flags acknowledged.
            replied_count: Number of flags replied to.
            period: Time period for the summary.

        Returns:
            True if posted successfully, False otherwise.
        """
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Flag Review Summary - This {period.capitalize()}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Flags Raised:*\n{flag_count}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Acknowledged:*\n{acknowledged_count}",
                        },
                        {"type": "mrkdwn", "text": f"*Replied:*\n{replied_count}"},
                        {
                            "type": "mrkdwn",
                            "text": (
                                f"*Resolution Rate:*\n{((acknowledged_count + replied_count) / flag_count * 100):.1f}%"
                                if flag_count > 0
                                else "N/A"
                            ),
                        },
                    ],
                },
            ]

            result = await self.posting_handler.post_message(
                channel_id=channel_id,
                message=f"Flag review summary for this {period}",
                blocks=blocks,
            )

            return result.get("ok", False)

        except Exception as e:
            logger.error(f"Error posting review summary: {e}")
            return False

    def format_review_message(
        self,
        feedback_text: str,
        user_id: str,
        channel_id: str,
        timestamp: str,
        include_actions: bool = True,
    ) -> str:
        """Format a review message for display.

        Args:
            feedback_text: The feedback text.
            user_id: ID of the user who submitted feedback.
            channel_id: Channel where feedback was submitted.
            timestamp: Timestamp of the feedback.
            include_actions: Whether to include action buttons.

        Returns:
            Formatted message string.
        """
        formatted = f"*Feedback from <@{user_id}>*\n"
        formatted += f"Channel: <#{channel_id}>\n"
        formatted += f"Time: {timestamp}\n\n"
        formatted += f"_{feedback_text}_"

        if include_actions:
            formatted += "\n\n_Use the buttons below to acknowledge or reply._"

        return formatted

    def create_flag_review_blocks(
        self,
        channel_id: str,
        user_id: str,
        user_name: str,
        feedback_text: str,
        validation_issues: List[str],
        time_str: str,
        message_ts: Optional[str] = None,
        status_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Create message blocks for flag review.

        Args:
            channel_id: Channel ID.
            user_id: User ID.
            user_name: User name.
            feedback_text: Feedback text.
            validation_issues: Validation issues.
            time_str: Time string.
            message_ts: Message timestamp (optional).
            status_text: Status text (optional).

        Returns:
            List of message blocks.
        """
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Status Flagged for Review"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Channel:*\n<#{channel_id}>"},
                    {"type": "mrkdwn", "text": f"*Flagged by:*\n<@{user_id}>"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{time_str}"},
                ],
            },
        ]

        # Add message link if available
        if message_ts:
            link = f"https://adobe.enterprise.slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"
            blocks[1]["fields"].insert(1, {"type": "mrkdwn", "text": f"*Message:*\n<{link}|View>"})

        # Add status text if available
        if status_text:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Status Text:*\n```{status_text[:500]}```",
                    },
                }
            )

        # Add feedback
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Feedback:*\n{feedback_text}"},
            }
        )

        # Add validation issues if any
        if validation_issues:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"⚠️ Validation notes: {', '.join(validation_issues)}",
                        }
                    ],
                }
            )

        # Add action buttons
        if message_ts:
            acknowledge_value = f"{channel_id}|{message_ts}|{user_id}"
            reply_value = f"{channel_id}|{message_ts}|{user_id}"
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Acknowledge"},
                            "style": "primary",
                            "action_id": "acknowledge_feedback",
                            "value": acknowledge_value,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "💬 Reply"},
                            "action_id": "reply_to_feedback",
                            "value": reply_value,
                        },
                    ],
                }
            )

        return blocks

    async def post_review_to_channel(
        self,
        channel_id: str,
        review_data: Dict[str, Any],
        post_to_review_channel: bool = True,
    ) -> Optional[str]:
        """Post a review to the specified channel.

        Args:
            channel_id: Channel to post to.
            review_data: Review data containing all necessary information.
            post_to_review_channel: Whether to also post to the review channel.

        Returns:
            Message timestamp if successful, None otherwise.
        """
        try:
            # Extract review data
            user_id = review_data.get("user_id")
            user_name = review_data.get("user_name", "Unknown User")
            feedback_text = review_data.get("feedback_text", "")
            validation_issues = review_data.get("validation_issues", [])
            message_ts = review_data.get("message_ts")
            status_text = review_data.get("status_text")

            # Format time
            flag_time = datetime.now(timezone.utc)
            time_str = flag_time.strftime("%H:%M")

            # Create blocks
            blocks = self.create_flag_review_blocks(
                channel_id=channel_id,
                user_id=user_id,
                user_name=user_name,
                feedback_text=feedback_text,
                validation_issues=validation_issues,
                time_str=time_str,
                message_ts=message_ts,
                status_text=status_text,
            )

            # Post to specified channel
            result = await self.posting_handler.post_message(
                channel_id=channel_id,
                message=f"Flag review from {user_name}",
                blocks=blocks,
            )

            if result.get("ok") and post_to_review_channel and channel_id != REVIEW_CHANNEL_ID:
                # Also post to the review channel
                await self.posting_handler.post_message(
                    channel_id=REVIEW_CHANNEL_ID,
                    message=f"Flag review from {user_name} in <#{channel_id}>",
                    blocks=blocks,
                )

            return result.get("ts") if result.get("ok") else None

        except Exception as e:
            logger.error(f"Error posting review to channel: {e}")
            return None

    async def generate_weekly_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate a weekly review report.

        Args:
            start_date: Start date for the report.
            end_date: End date for the report.

        Returns:
            Dictionary containing report data.
        """
        # This would typically query the database for statistics
        return {
            "period": f"{start_date.date()} to {end_date.date()}",
            "total_flags": 0,
            "acknowledged": 0,
            "replied": 0,
            "pending": 0,
            "top_channels": [],
            "top_flaggers": [],
            "average_resolution_time": "N/A",
        }

    def create_review_trend_blocks(self, trend_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create blocks showing review trends.

        Args:
            trend_data: Dictionary containing trend information.

        Returns:
            List of Slack blocks for trend display.
        """
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Review Trends"},
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*This Week:*\n{trend_data.get('this_week', 0)} flags",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Last Week:*\n{trend_data.get('last_week', 0)} flags",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Change:*\n{trend_data.get('change_percent', 0):+.1f}%",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Avg Response:*\n{trend_data.get('avg_response_time', 'N/A')}",
                    },
                ],
            },
        ]

        return blocks
