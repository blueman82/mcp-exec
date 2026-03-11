"""
report_generator.py

Service for generating reports from channel data.
"""

import time
from typing import Any, Dict, List, Optional

from packages.ai.core.openai_handler import OpenAIHandler
from packages.core.config.feature_flags import FeatureFlags
from packages.core.constants import USE_PIPELINE_PROCESSING
from packages.core.logging import setup_logger
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps

from .archive_handler import JiraReporterArchiveHandler

logger = setup_logger(__name__)


class ReportGenerator:
    """Generates reports for channels using AI."""

    def __init__(
        self,
        openai_handler: OpenAIHandler,
        channel_msg_ops: SlackChannelMessageOps,
        archive_handler: Optional[JiraReporterArchiveHandler] = None,
    ):
        """
        Initialize the report generator.

        Args:
            openai_handler: Pre-initialized OpenAIHandler for AI integration
            channel_msg_ops: Operations for retrieving channel messages
            archive_handler: Optional handler for archived channels
        """
        self.openai_handler = openai_handler
        self.channel_msg_ops = channel_msg_ops
        self.archive_handler = archive_handler

    async def generate_report(
        self, channel_id: str, channel_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate a report for the specified channel.

        Args:
            channel_id: The Slack channel ID
            channel_metadata: Channel metadata from DynamoDB

        Returns:
            Report text or None if generation failed
        """
        channel_name = channel_metadata.get("channel_name", "Unknown")
        was_unarchived = False

        try:
            # Handle archived channels using archive_handler with bot membership logic
            if self.archive_handler:
                # Check if channel is archived and unarchive with bot membership
                is_archived = await self.archive_handler.is_channel_archived(channel_id)
                if is_archived:
                    logger.info(
                        f"Channel {channel_id} is archived, using archive handler to unarchive with bot membership"
                    )
                    was_unarchived = await self.archive_handler.temporarily_unarchive_channel(
                        channel_id
                    )
                    if not was_unarchived:
                        logger.error(
                            f"Failed to unarchive channel {channel_id} for report generation"
                        )
                        return None

            # Get channel messages - channel should now be unarchived with bot membership
            logger.info(f"Fetching messages for channel {channel_id} ({channel_name})")
            if USE_PIPELINE_PROCESSING:
                messages = await self.channel_msg_ops.fetch_channel_messages_collected(
                    channel_id=channel_id, limit=500  # Reasonable limit to avoid token issues
                )
            else:
                messages = await self.channel_msg_ops.fetch_channel_messages(
                    channel_id=channel_id, limit=500  # Reasonable limit to avoid token issues
                )

            if not messages:
                logger.warning(f"No messages found for channel {channel_id}")
                return None

            # Format the messages for AI consumption
            formatted_messages = self._format_messages_for_ai(messages)

            # Create the prompt for report generation
            prompt = self._create_report_prompt(
                formatted_messages=formatted_messages, channel_metadata=channel_metadata
            )

            # Generate the report using OpenAI
            messages = [{"role": "user", "content": prompt}]
            report_text = await self.openai_handler.execute_prompt(
                messages=messages, max_tokens=2000, temperature=0.3
            )

            if not report_text:
                logger.error(f"Failed to generate report for channel {channel_id}")
                return None

            # Format the report for JIRA
            jira_formatted_report = self._format_for_jira(report_text, channel_metadata)

            return jira_formatted_report

        except Exception as e:
            logger.error(f"Error generating report for channel {channel_id}: {str(e)}")
            return None

        finally:
            # Re-archive the channel if we unarchived it
            if was_unarchived and self.archive_handler:
                logger.info(f"Re-archiving channel {channel_id} after report generation")
                await self.archive_handler.rearchive_channel(channel_id)

    def _format_messages_for_ai(self, messages: List[str]) -> str:
        """Format channel messages for AI consumption."""
        # Messages are already formatted as strings, just join them
        return "\n".join(messages)

    def _create_report_prompt(
        self, formatted_messages: str, channel_metadata: Dict[str, Any]
    ) -> str:
        """Create an AI prompt for report generation."""
        customer = channel_metadata.get("customer_name", "")
        jira_ticket = channel_metadata.get("jira_ticket", "Unknown")
        channel_name = channel_metadata.get("channel_name", "Unknown")

        # Only include customer line if we have a valid customer name
        customer_line = (
            f"Customer: {customer}\n" if customer and customer != "NOT YET AVAILABLE" else ""
        )

        prompt = f"""<role>
You are an AI assistant specialized in summarizing incident response conversations from CSO (Customer Support Operations) war rooms. Your task is to extract key incident information from Slack messages and structure them into a comprehensive JIRA-formatted report.
</role>

<context>
Channel: {channel_name}
JIRA Ticket: {jira_ticket}
{customer_line.rstrip()}
</context>

<response_structure>
Generate a report with these nine sections in order. Use JIRA wiki formatting throughout:
- h3. Executive Summary — incident overview, current status, CSO Phase, business impact
- h3. People Involved — engineers listed with roles/contributions
- h3. Incident Timeline — key events chronologically (timestamps: DD-MMM-YYYY, HH:MM UTC)
- h3. Technical Analysis — root cause, systems affected, error patterns
- h3. Impact Assessment — customer impact, service availability, affected metrics
- h3. Resolution & Mitigation — actions taken, workarounds, fixes applied
- h3. JIRA Tickets & Work Done — related tickets with work summaries
- h3. Next Steps — pending actions, ongoing investigations, preventative measures
- h3. References — support tickets, documentation, case numbers

Within sections, use * for bullet points. Do not create subsections or nested headers.
</response_structure>

<data_source>
Slack channel messages (provided below):

{formatted_messages}
</data_source>

<formatting_rules>
✅ JIRA wiki syntax: h3. for headers, * for bullets, [link text|URL] for links
✅ Timestamps: DD-MMM-YYYY, HH:MM UTC format (e.g. 15-Mar-2026, 14:32 UTC)
✅ Attribute actions to people by name or Slack handle where possible
❌ Do not use Slack mrkdwn (* bold, _italic, etc.) — use JIRA wiki only
❌ Do not invent section headers or skip sections
</formatting_rules>

<constraints>
- Extract information only from the provided Slack messages. Never fabricate events or timestamps.
- If a section has no relevant information, write "Not specified" rather than leaving it blank.
- Keep language concise and factual. Focus on what happened, not speculation.
- Omit the Customer field from the report body if no valid customer name was provided.
- Preserve error messages, code snippets, and numeric values verbatim from source.
</constraints>

Analyse the provided Slack conversation above and generate the report now.
"""

        # Add JSON format instruction when structured output is enabled
        # Azure OpenAI API requires the word "json" in the prompt when using response_format: json_object
        if FeatureFlags.is_structured_json_output_enabled():
            prompt += """

IMPORTANT: Return your response as JSON with this exact structure:
{"response_text": "your complete JIRA-formatted report here"}

The response_text field should contain the full report using JIRA wiki formatting as specified above.
"""

        return prompt

    def _format_for_jira(self, report_text: str, channel_metadata: Dict[str, Any]) -> str:
        """Format the report for JIRA markdown."""
        customer = channel_metadata.get("customer_name", "")
        channel_name = channel_metadata.get("channel_name", "Unknown")
        channel_id = channel_metadata.get("channel_id", "Unknown")
        jira_ticket = channel_metadata.get("jira_ticket", "")

        # Only include customer line if we have a valid customer name
        customer_line = (
            f"*Customer*: {customer}\n" if customer and customer != "NOT YET AVAILABLE" else ""
        )

        # Include JIRA ticket if available
        jira_line = f"*JIRA Ticket*: {jira_ticket}\n" if jira_ticket else ""

        # Add header and context information
        header = f"""h2. Ketchup Automated Incident Report

*Channel*: {channel_name} (ID: {channel_id})
{customer_line}{jira_line}*Generated*: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}

----

{report_text}

----

_This report was automatically generated by Ketchup._
"""
        return header
