"""
metadata_extractor.py

This module contains the MetadataExtractor class that handles AI-related
functionality for extracting metadata from channel messages.
"""

import re
from typing import Dict, List

import orjson

from packages.ai.core.openai_handler import OpenAIHandler
from packages.ai.prompts.customer_extraction import get_customer_name_extraction_prompt
from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class MetadataExtractor:
    """Extracts metadata from channel messages using AI."""

    def __init__(self, ai_handler: OpenAIHandler):
        """Initialize with a pre-initialized AI handler dependency.

        Args:
            ai_handler: An initialized OpenAIHandler instance.
        """
        if not ai_handler:
            raise ValueError("An initialized OpenAIHandler instance is required.")
        self.ai_handler = ai_handler

        # Get the extraction prompt string directly during initialization
        self.extraction_prompt_text = get_customer_name_extraction_prompt()

    def format_messages_for_ai(self, messages: List[str]) -> str:
        """
        Format messages for AI processing.

        Args:
            messages: List of message strings
            max_messages: Maximum number of messages to include

        Returns:
            Formatted message string for AI processing
        """
        if not messages:
            return ""

        # Process messages in chronological order (oldest first)
        messages.sort()
        # Combine messages into a single string
        return "\n".join(messages)

    def parse_ai_response(self, response: str) -> Dict[str, str]:
        """
        Parse AI response to extract metadata.

        Args:
            response: Raw AI response string

        Returns:
            Dictionary with extracted customer_name and jira_ticket
        """
        logger.info("parse_ai_response: Received raw AI response: '%s'", response)

        default_response = {
            "customer_name": "NOT YET AVAILABLE",
            "jira_ticket": "NOT YET AVAILABLE",
        }

        if not response:
            logger.info(
                "parse_ai_response: Empty response received, returning default."
            )
            return default_response

        lines = response.strip().splitlines()
        logger.info("parse_ai_response: Lines from AI response: %s", lines)

        extracted_customer_name = lines[0].strip() if lines else "NOT YET AVAILABLE"
        logger.info(
            "parse_ai_response: Extracted customer_name: '%s'", extracted_customer_name
        )

        # Add validation for potential domain-based misidentification
        self._validate_customer_extraction(extracted_customer_name)

        clickable_ticket = "NOT YET AVAILABLE"

        if len(lines) > 1:
            ticket_line = lines[1].strip()
            logger.info(
                "parse_ai_response: Raw ticket_line from AI: '%s'", ticket_line
            )

            # 1. Check if already Slack-formatted
            if (
                ticket_line.startswith("<https://")
                and "|" in ticket_line
                and ticket_line.endswith(">")
            ):
                # Extract ID from Slack format <URL|ID>
                slack_match = re.match(r"<https?://[^|]+\|([^>]+)>", ticket_line)
                if slack_match:
                    clickable_ticket = slack_match.group(1).upper()
                    logger.info(
                        "parse_ai_response: Extracted ID from Slack format: '%s'",
                        clickable_ticket,
                    )
                else:
                    clickable_ticket = ticket_line
                    logger.info(
                        "parse_ai_response: Failed to extract from Slack format, kept as is: '%s'",
                        clickable_ticket,
                    )
            # 2. Check for Markdown format [Text](URL)
            elif (
                ticket_line.startswith("[")
                and "](" in ticket_line
                and ticket_line.endswith(")")
            ):
                match = re.match(
                    r"\[([^\]]+)\]\(([^)]+)\)", ticket_line
                )
                if match:
                    text_part = match.group(1)
                    url_part = match.group(2)
                    if "jira.corp.adobe.com/browse/" in url_part:
                        # Extract just the ticket ID
                        clickable_ticket = text_part.upper()
                        logger.info(
                            "parse_ai_response: Extracted ID from Markdown format: '%s'",
                            clickable_ticket,
                        )
                    else:  # Not a JIRA link in Markdown, keep as is
                        clickable_ticket = ticket_line
                        logger.info(
                            "parse_ai_response: Markdown link (not JIRA) kept as is: '%s'",
                            clickable_ticket,
                        )
                else:  # Malformed Markdown
                    clickable_ticket = ticket_line
                    logger.info(
                        "parse_ai_response: Malformed Markdown, kept as is: '%s'",
                        clickable_ticket,
                    )
            # 3. Check for plain JIRA URL
            elif "jira.corp.adobe.com/browse/" in ticket_line:
                ticket_id_from_url = ticket_line.split("jira.corp.adobe.com/browse/")[
                    -1
                ].strip()
                # Remove any trailing slashes or parameters
                ticket_id_from_url = ticket_id_from_url.split("/")[0].split("?")[0].upper()
                clickable_ticket = ticket_id_from_url
                logger.info(
                    "parse_ai_response: Extracted ID from URL: '%s'",
                    clickable_ticket,
                )
            # 4. Check for plain JIRA ID (e.g., CPGNREQ-12345)
            else:
                jira_id_pattern = r"^[A-Z]{2,10}-[0-9]{1,7}(?![0-9])$"
                if re.match(jira_id_pattern, ticket_line, re.IGNORECASE):
                    clickable_ticket = ticket_line.upper()
                    logger.info(
                        "parse_ai_response: Found plain JIRA ID: '%s'",
                        clickable_ticket,
                    )
                else:  # Fallback
                    clickable_ticket = ticket_line
                    logger.info(
                        "parse_ai_response: Ticket is raw text (fallback): '%s'",
                        clickable_ticket,
                    )
        else:
            logger.info("parse_ai_response: No second line found for JIRA ticket.")

        final_result = {
            "customer_name": extracted_customer_name,
            "jira_ticket": clickable_ticket,
        }
        logger.info("parse_ai_response: Final parsed result: %s", final_result)
        return final_result

    def _validate_customer_extraction(self, customer_name: str) -> None:
        """
        Log customer extraction for manual review when needed.

        Args:
            customer_name: The extracted customer name to validate
        """
        if customer_name == "NOT YET AVAILABLE":
            return

        # Check for potential domain-based misidentification
        if customer_name and customer_name.upper() in ['ADOBE', 'MICROSOFT']:
            logger.warning(f"Potential domain-based misidentification detected: {customer_name}")

        # Simply log the extraction for manual review
        # No automatic flagging since many legitimate customers could match patterns
        logger.info(
            "Customer extracted: '%s'. Manual review recommended if unexpected.",
            customer_name
        )

    async def extract_metadata_with_ai(
        self, channel_id: str, messages: List[str]
    ) -> Dict[str, str]:
        """Extract metadata using AI by calling the OpenAI handler."""
        if not messages:
            logger.warning(
                "No messages provided for channel %s to extract metadata.", channel_id
            )
            return {"customer_name": "ERROR", "jira_ticket": "ERROR"}

        # Ensure messages are formatted correctly for the AI prompt
        # If you have a specific formatter like self.format_messages_for_ai, use it.
        # For now, joining with newline as per previous logic for formatted_messages.
        formatted_messages = "\n".join(messages)

        try:
            response = await self.ai_handler.call_openai_endpoint(
                messages=[
                    {"role": "system", "content": self.extraction_prompt_text},
                    {"role": "user", "content": formatted_messages},
                ],
                user_id=None,
                incoming_channel=channel_id,
            )
            raw_content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            # Extract from JSON if structured output is enabled
            if FeatureFlags.is_structured_json_output_enabled():
                try:
                    data = orjson.loads(raw_content)
                    response_content = data.get("response_text", raw_content)
                    logger.info(
                        "Extracted text from JSON response (%d chars)", len(response_content)
                    )
                except orjson.JSONDecodeError as e:
                    logger.error(
                        "Failed to parse JSON response, falling back to raw content: %s", e
                    )
                    response_content = raw_content
            else:
                # Prose mode - use raw content as-is
                response_content = raw_content

            # *** THIS IS THE KEY CHANGE: Call parse_ai_response here ***
            parsed_metadata = self.parse_ai_response(response_content)

            # Updated log message to reflect that parsed_metadata is being used
            logger.info(
                "Processed AI response for channel %s - Customer: '%s', JIRA: '%s'",
                channel_id,
                parsed_metadata.get("customer_name"),
                parsed_metadata.get("jira_ticket"),
            )
            return parsed_metadata

        except Exception as e:
            logger.error(
                "AI metadata extraction failed for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return {
                "customer_name": "NOT YET AVAILABLE",
                "jira_ticket": "NOT YET AVAILABLE",
            }

    async def cleanup(self) -> None:
        """Clean up AI handler resources."""
        try:
            if hasattr(self.ai_handler, "cleanup"):
                await self.ai_handler.cleanup()
        except Exception as e:
            logger.error("Error cleaning up AI handler: %s", str(e))
