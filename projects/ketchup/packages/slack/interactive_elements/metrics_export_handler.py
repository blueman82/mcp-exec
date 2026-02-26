"""
metrics_export_handler.py

Handles metrics dashboard export and delivery.
Follows pattern from UsageExportHandler.
"""

import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

from packages.core.exports.html_generator import MetricsHTMLGenerator
from packages.core.exports.time_period_formatter import (
    get_month_keys_for_range,
)
from packages.core.logging import setup_logger
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.services.metrics_data_collector import MetricsDataCollector

logger = setup_logger(__name__)


class MetricsExportHandler:
    """
    Handles metrics dashboard export and delivery.

    Follows exact pattern from UsageExportHandler with HTML generation.
    """

    def __init__(
        self,
        metrics_data_collector: MetricsDataCollector,
        slack_posting_handler: SlackPostingHandler,
        html_generator: MetricsHTMLGenerator,
    ):
        """
        Initialize MetricsExportHandler.

        Args:
            metrics_data_collector: Metrics data collection service
            slack_posting_handler: Slack posting handler
            html_generator: HTML dashboard generator
        """
        self._metrics_collector = metrics_data_collector
        self._slack_posting_handler = slack_posting_handler
        self._html_generator = html_generator
        logger.info("MetricsExportHandler initialized")

    async def handle_metrics_request(
        self,
        user_id: str,
        response_url: Optional[str] = None,
        time_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Handle metrics dashboard generation and delivery.

        Args:
            user_id: User ID to send dashboard to
            response_url: Optional response URL
            time_params: Optional time period parameters:
                - period_type: "7_days", "monthly", "quarterly"
                - start_ts: Start Unix timestamp
                - end_ts: End Unix timestamp
                - month: Month number
                - quarter: Quarter number
                - year: Year
                - is_partial: Is partial period
                - start_date: Start datetime
                - end_date: End datetime

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract time parameters (default to 7 days if not provided)
            if time_params:
                period_type = time_params.get("period_type", "7_days")
                start_ts = time_params.get("start_ts")
                end_ts = time_params.get("end_ts")
                month = time_params.get("month")
                quarter = time_params.get("quarter")
                year = time_params.get("year")
                is_partial = time_params.get("is_partial", False)
                start_date = time_params.get("start_date")
                end_date = time_params.get("end_date")
            else:
                # Default to 7 days
                period_type = "7_days"
                end_ts = int(time.time())
                start_ts = end_ts - (7 * 24 * 60 * 60)
                month = None
                quarter = None
                year = datetime.now(timezone.utc).year
                is_partial = False
                start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            # Calculate month keys if needed
            month_keys = None
            if period_type in ["monthly", "quarterly"]:
                month_keys = get_month_keys_for_range(start_date, end_date)

            # ALWAYS get DM channel ID for file upload
            dm_response = await self._slack_posting_handler.api_call(
                "conversations.open", {"users": [user_id]}
            )

            dm_channel_id = None
            if dm_response and dm_response.get("ok"):
                dm_channel_id = dm_response.get("channel", {}).get("id")
                logger.info(f"Opened DM channel {dm_channel_id} for user {user_id}")

            # Collect metrics with time parameters
            metrics_data = await self._metrics_collector.collect_all_metrics(
                start_ts,
                end_ts,
                period_type,
                month_keys,
            )

            # Generate HTML with time parameters
            # Note: jira_posting is nested inside cso metrics
            html_content = self._html_generator.generate(
                metrics_data["cso"],
                metrics_data["technical"],
                metrics_data["cso"].get("jira_posting", {}),
                csopm_metrics=metrics_data.get("csopm"),
                period_type=period_type,
                month=month,
                quarter=quarter,
                year=year,
                is_partial=is_partial,
                start_date=start_date,
                end_date=end_date,
            )

            # Generate filename with time period
            filename = self._generate_filename(period_type, month, quarter, year)
            success = await self._upload_html_to_slack(
                user_id=user_id,
                dm_channel_id=dm_channel_id,
                html_content=html_content,
                filename=filename,
            )

            if success:
                completion_msg = "✅ Metrics dashboard generated and sent via DM!"
                if response_url:
                    await self._slack_posting_handler.post_message(
                        response_url=response_url,
                        message=completion_msg,
                    )
                else:
                    await self._slack_posting_handler.post_message(
                        channel_id=user_id,
                        message=completion_msg,
                    )

            return success

        except Exception as e:
            logger.error(f"Error handling metrics request: {str(e)}")
            error_msg = "❌ Failed to generate metrics dashboard. " "Please try again later."
            if response_url:
                await self._slack_posting_handler.post_message(
                    response_url=response_url,
                    message=error_msg,
                )
            else:
                await self._slack_posting_handler.post_message(
                    channel_id=user_id,
                    message=error_msg,
                )
            return False

    async def _get_upload_url(
        self,
        filename: str,
        file_size: int,
    ) -> tuple[str, str] | tuple[None, None]:
        """
        Get upload URL from Slack for file upload.

        Step 1 of files.uploadV2 API: Call files.getUploadURLExternal
        to obtain an upload_url and file_id.

        Args:
            filename: Name of file to upload
            file_size: Size of file in bytes

        Returns:
            Tuple of (upload_url, file_id) on success, (None, None) on failure
        """
        upload_url_payload = {
            "filename": filename,
            "length": file_size,
            "title": filename,
        }

        url = (
            f"{self._slack_posting_handler.config.get_api_base_url()}" "/files.getUploadURLExternal"
        )
        headers = {
            "Authorization": (f"Bearer {self._slack_posting_handler._slack_token}"),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        form_data = urllib.parse.urlencode(upload_url_payload)

        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session,
            session.post(url, headers=headers, data=form_data) as response,
        ):
            upload_url_response = await response.json()

        if not upload_url_response.get("ok"):
            logger.error(
                f"Failed to get upload URL: " f"{upload_url_response.get('error', 'Unknown error')}"
            )
            return None, None

        return (upload_url_response["upload_url"], upload_url_response["file_id"])

    async def _upload_file_to_url(
        self,
        upload_url: str,
        html_bytes: bytes,
    ) -> bool:
        """
        Upload file bytes to the provided upload URL.

        Step 2 of files.uploadV2 API: POST file content to the
        upload_url obtained from getUploadURLExternal.

        Args:
            upload_url: URL to upload file to
            html_bytes: File content as bytes

        Returns:
            True if upload successful (HTTP 200), False otherwise
        """
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session,
            session.post(
                upload_url, data=html_bytes, headers={"Content-Type": "text/html"}
            ) as response,
        ):
            if response.status != 200:
                logger.error(f"Failed to upload file, status: {response.status}")
                return False
        return True

    async def _complete_upload(
        self,
        file_id: str,
        filename: str,
        target_channel: str,
    ) -> bool:
        """
        Complete upload and share file to channel.

        Step 3 of files.uploadV2 API: Call files.completeUploadExternal
        to finalize the upload and share the file to the target channel.

        Args:
            file_id: File ID from getUploadURLExternal
            filename: Display title for the file
            target_channel: Channel ID to share file to

        Returns:
            True if complete successful, False otherwise
        """
        complete_payload = {
            "files": [{"id": file_id, "title": filename}],
            "channel_id": target_channel,
            "initial_comment": ("Here's your Ketchup metrics dashboard! 📊"),
        }

        complete_response = await self._slack_posting_handler.api_call(
            "files.completeUploadExternal", complete_payload
        )

        if complete_response.get("ok"):
            logger.info(f"Successfully uploaded HTML file: {filename}")
            return True
        else:
            logger.error(
                f"Failed to complete upload: " f"{complete_response.get('error', 'Unknown error')}"
            )
            return False

    async def _upload_html_to_slack(
        self,
        user_id: str,
        dm_channel_id: str,
        html_content: str,
        filename: str,
    ) -> bool:
        """
        Upload HTML file to user via DM using files.uploadV2 API.

        3-Step Process:
        1. files.getUploadURLExternal → get upload_url + file_id
        2. POST HTML bytes to upload_url
        3. files.completeUploadExternal → finalize and share

        Args:
            user_id: User ID for DM
            dm_channel_id: Optional DM channel ID
            html_content: HTML content string
            filename: Output filename

        Returns:
            Success status
        """
        try:
            await self._slack_posting_handler._init_slack_token()

            target_channel = dm_channel_id if dm_channel_id else user_id
            logger.info(f"Using target channel: {target_channel}")

            html_bytes = html_content.encode("utf-8")
            file_size = len(html_bytes)

            # Step 1: Get upload URL
            upload_url, file_id = await self._get_upload_url(filename, file_size)
            if not upload_url or not file_id:
                return False

            # Step 2: Upload file to URL
            if not await self._upload_file_to_url(upload_url, html_bytes):
                return False

            # Step 3: Complete upload
            return await self._complete_upload(file_id, filename, target_channel)

        except Exception as e:
            logger.error(f"Error uploading HTML: {str(e)}")
            return False

    def _generate_filename(
        self,
        period_type: str,
        month: int = None,
        quarter: int = None,
        year: int = None,
    ) -> str:
        """
        Generate descriptive filename for dashboard HTML.

        Examples:
            "ketchup-dashboard-7-days-20251010.html"
            "ketchup-dashboard-september-2025.html"
            "ketchup-dashboard-q1-2025.html"
        """
        timestamp = datetime.now().strftime("%Y%m%d")

        if period_type == "7_days":
            return f"ketchup-dashboard-7-days-{timestamp}.html"
        elif period_type == "monthly":
            month_name = datetime(year, month, 1).strftime("%B").lower()
            return f"ketchup-dashboard-{month_name}-{year}.html"
        elif period_type == "quarterly":
            return f"ketchup-dashboard-q{quarter}-{year}.html"

        return f"ketchup-dashboard-{timestamp}.html"
