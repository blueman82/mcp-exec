"""
usage_export_handler.py

This module handles export requests for command usage data.
Following pattern from FeedbackReportHandler.
"""

import aiohttp

from packages.core.exports.csv_generator import CommandUsageCSVGenerator
from packages.core.logging import setup_logger
from packages.db.operations.command_tracking_operations import CommandTrackingOperations
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class UsageExportHandler:
    """
    Handles export requests for command usage data.
    Following pattern from FeedbackReportHandler.
    """

    def __init__(
        self,
        command_tracking_ops: CommandTrackingOperations,
        slack_posting_handler: SlackPostingHandler,
        csv_generator: CommandUsageCSVGenerator,
    ):
        self._command_tracking_ops = command_tracking_ops
        self._slack_posting_handler = slack_posting_handler
        self._csv_generator = csv_generator
        logger.info("UsageExportHandler initialized")

    async def handle_export_request(
        self,
        trigger_id: str,
        user_id: str,
        response_url: str = None,
    ) -> bool:
        """
        Handle CSV export request from Slack button.

        Args:
            trigger_id: Slack trigger ID for modal
            user_id: User requesting export
            response_url: URL to post results (optional, None for Home tab)

        Returns:
            bool: Success status
        """
        try:
            # Send immediate acknowledgment
            # For Home tab actions (no response_url), send as DM
            dm_channel_id = None
            if response_url:
                await self._slack_posting_handler.post_message(
                    response_url=response_url,
                    message="Generating usage report... This may take a moment.",
                )
            else:
                ack_response = await self._slack_posting_handler.post_message(
                    channel_id=user_id,  # DM to user
                    message="Generating usage report... This may take a moment.",
                )
                # Extract the actual DM channel ID from the response
                if ack_response and ack_response.get("ok"):
                    dm_channel_id = ack_response.get("channel")
                    logger.info(f"Got DM channel ID {dm_channel_id} from acknowledgment message")

            # Fetch export data
            export_data = await self._command_tracking_ops.get_full_export_data(days=7)

            if not export_data:
                if response_url:
                    await self._slack_posting_handler.post_message(
                        response_url=response_url,
                        message="No usage data available for export.",
                    )
                else:
                    await self._slack_posting_handler.post_message(
                        channel_id=user_id,  # DM to user
                        message="No usage data available for export.",
                    )
                return False

            # Generate CSV
            csv_content = await self._csv_generator.generate_csv(export_data)

            # Send CSV as file upload
            await self._upload_csv_to_slack(
                user_id=user_id,
                dm_channel_id=dm_channel_id,
                csv_content=csv_content,
                filename=f"ketchup_usage_report_{export_data['export_timestamp']}.csv",
            )

            # Send completion message
            if response_url:
                await self._slack_posting_handler.post_message(
                    response_url=response_url,
                    message="✅ Usage report generated and sent via DM!",
                )
            else:
                await self._slack_posting_handler.post_message(
                    channel_id=user_id,  # DM to user
                    message="✅ Usage report generated and sent via DM!",
                )

            return True

        except Exception as e:
            logger.error(f"Error handling export request: {str(e)}")
            if response_url:
                await self._slack_posting_handler.post_message(
                    response_url=response_url,
                    message="❌ Failed to generate usage report. Please try again later.",
                )
            else:
                await self._slack_posting_handler.post_message(
                    channel_id=user_id,  # DM to user
                    message="❌ Failed to generate usage report. Please try again later.",
                )
            return False

    async def _upload_csv_to_slack(
        self, user_id: str, dm_channel_id: str, csv_content: str, filename: str
    ) -> bool:
        """Upload CSV file to user via DM using new files.uploadV2 API."""
        try:
            # Get the Slack token
            await self._slack_posting_handler._init_slack_token()

            # Determine the target channel - prefer dm_channel_id if available
            target_channel = dm_channel_id if dm_channel_id else user_id
            logger.info(
                f"Using target channel: {target_channel} (from dm_channel_id: {dm_channel_id}, user_id: {user_id})"
            )

            csv_bytes = csv_content.encode("utf-8")
            file_size = len(csv_bytes)

            # Step 1: Get upload URL
            upload_url_payload = {
                "filename": filename,
                "length": file_size,
                "title": filename,  # Add title parameter
            }

            logger.info(f"Getting upload URL with payload: {upload_url_payload}")

            # The files.getUploadURLExternal API expects form data, not JSON
            url = f"{self._slack_posting_handler.config.get_api_base_url()}/files.getUploadURLExternal"
            headers = {
                "Authorization": f"Bearer {self._slack_posting_handler._slack_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            # Convert to form data
            import urllib.parse

            form_data = urllib.parse.urlencode(upload_url_payload)

            async with (
                aiohttp.ClientSession() as session,
                session.post(url, headers=headers, data=form_data) as response,
            ):
                upload_url_response = await response.json()

            if not upload_url_response.get("ok"):
                logger.error(
                    f"Failed to get upload URL: {upload_url_response.get('error', 'Unknown error')}"
                )
                logger.error(f"Full response: {upload_url_response}")
                return False

            upload_url = upload_url_response["upload_url"]
            file_id = upload_url_response["file_id"]

            # Step 2: Upload file to the URL
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    upload_url, data=csv_bytes, headers={"Content-Type": "text/csv"}
                ) as response,
            ):
                if response.status != 200:
                    logger.error(f"Failed to upload file to URL, status: {response.status}")
                    return False

            # Step 3: Complete the upload and share to channel
            complete_payload = {
                "files": [{"id": file_id, "title": filename}],
                "channel_id": target_channel,
                "initial_comment": "Here's your Ketchup usage report! 📊",
            }

            complete_response = await self._slack_posting_handler.api_call(
                "files.completeUploadExternal", complete_payload
            )

            if complete_response.get("ok"):
                logger.info(f"Successfully uploaded CSV file: {filename}")
                return True
            else:
                logger.error(
                    f"Failed to complete upload: {complete_response.get('error', 'Unknown error')}"
                )
                return False

        except Exception as e:
            logger.error(f"Error uploading CSV: {str(e)}")
            return False
