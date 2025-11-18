"""
test_metrics_integration.py

Integration tests for metrics dashboard with real Ketchup bot.

Tests the complete end-to-end flow:
1. Collect metrics data from DynamoDB
2. Generate HTML dashboard
3. Upload to Slack via files.uploadV2 API
4. Deliver to Ketchup's home channel (D0840EX80R5)

Requires:
- AWS credentials (AWS_PROFILE=campaign_prod_v7)
- DynamoDB table: ketchup_channel_information
- AWS Secrets Manager: Ketchup_Token_Secrets
- Slack permissions: files:write, users:read, conversations:open

Test Target: D0840EX80R5 (Ketchup's home/DM channel)
"""

import os
import pytest

# Skip if not in integration test mode
pytestmark = pytest.mark.integration

# Test target channel
KETCHUP_HOME_CHANNEL = "D0840EX80R5"


class TestMetricsIntegration:
    """Integration tests for metrics dashboard with real Ketchup bot."""

    @pytest.mark.asyncio
    async def test_full_metrics_upload_to_ketchup_home(self) -> None:
        """
        Test complete metrics dashboard generation and upload to Ketchup's home.

        This test validates:
        1. TypedDI resolution of all metrics services
        2. Data collection from real DynamoDB
        3. HTML generation with real data
        4. 3-step Slack upload API (getUploadURLExternal → POST → completeUploadExternal)
        5. File delivery to D0840EX80R5

        Expected outcome: Dashboard HTML file appears in Ketchup's DM channel
        """
        # Import here to avoid issues if dependencies not available
        from packages.core.typed_di_integration import get_unified_container

        # Get TypedDI container
        container = await get_unified_container()

        # Resolve MetricsExportHandler from container
        from packages.slack.interactive_elements.metrics_export_handler import (
            MetricsExportHandler
        )

        metrics_export_handler = container.get(MetricsExportHandler)

        assert metrics_export_handler is not None, "Failed to resolve MetricsExportHandler from DI container"

        # Execute full metrics request to Ketchup's home
        success = await metrics_export_handler.handle_metrics_request(
            user_id=KETCHUP_HOME_CHANNEL,  # Send to Ketchup's DM
            response_url=None,
        )

        assert success is True, "Metrics dashboard upload failed"

    @pytest.mark.asyncio
    async def test_metrics_with_monthly_period(self) -> None:
        """
        Test metrics dashboard with monthly time period.

        Validates:
        1. Parameter extraction for monthly periods
        2. Month key calculation
        3. Metrics collection with monthly aggregates
        4. HTML generation with time period context
        5. Dashboard upload to Slack
        """
        from datetime import datetime, timezone
        from packages.core.typed_di_integration import get_unified_container
        from packages.slack.command_processing.command_parameters.extractors.metrics import (
            extract_metrics_params,
        )
        from packages.slack.command_processing.command_parameters.models import CommandContext
        from packages.slack.interactive_elements.metrics_export_handler import (
            MetricsExportHandler
        )

        # Get previous month (guaranteed to be complete)
        now = datetime.now(timezone.utc)
        if now.month == 1:
            prev_month = 12
            prev_year = now.year - 1
        else:
            prev_month = now.month - 1
            prev_year = now.year
        
        month_name = datetime(prev_year, prev_month, 1).strftime("%B").lower()
        year_str = str(prev_year)
        
        # Extract params
        params = extract_metrics_params(
            f"/ketchup metrics {month_name} {year_str}",
            CommandContext.DIRECT_MESSAGE
        )
        
        assert params.time_period_type == "monthly"
        assert params.month == prev_month
        assert params.year == prev_year

        # Get container and handler
        container = await get_unified_container()
        handler = container.get(MetricsExportHandler)

        # Execute metrics request with monthly parameters
        success = await handler.handle_metrics_request(
            user_id=KETCHUP_HOME_CHANNEL,
            response_url=None,
            time_params={
                "period_type": params.time_period_type,
                "start_ts": int(params.start_date.timestamp()),
                "end_ts": int(params.end_date.timestamp()),
                "month": params.month,
                "quarter": params.quarter,
                "year": params.year,
                "is_partial": params.is_partial,
                "start_date": params.start_date,
                "end_date": params.end_date,
            },
        )

        assert success is True, "Monthly metrics dashboard upload failed"

    @pytest.mark.asyncio
    async def test_metrics_with_quarterly_period(self) -> None:
        """
        Test metrics dashboard with quarterly time period.

        Validates:
        1. Parameter extraction for quarterly periods
        2. Month key calculation for 3-month span
        3. Metrics collection across multiple months
        4. HTML generation with quarterly context
        5. Dashboard upload to Slack
        """
        from datetime import datetime, timezone
        from packages.core.typed_di_integration import get_unified_container
        from packages.slack.command_processing.command_parameters.extractors.metrics import (
            extract_metrics_params,
        )
        from packages.slack.command_processing.command_parameters.models import CommandContext
        from packages.slack.interactive_elements.metrics_export_handler import (
            MetricsExportHandler
        )

        # Use Q3 of current year (June-Aug) as example
        current_year = datetime.now(timezone.utc).year
        
        # Extract params
        params = extract_metrics_params(
            f"/ketchup metrics q3 {current_year}",
            CommandContext.DIRECT_MESSAGE
        )
        
        assert params.time_period_type == "quarterly"
        assert params.quarter == 3
        assert params.year == current_year

        # Get container and handler
        container = await get_unified_container()
        handler = container.get(MetricsExportHandler)

        # Execute metrics request with quarterly parameters
        success = await handler.handle_metrics_request(
            user_id=KETCHUP_HOME_CHANNEL,
            response_url=None,
            time_params={
                "period_type": params.time_period_type,
                "start_ts": int(params.start_date.timestamp()),
                "end_ts": int(params.end_date.timestamp()),
                "month": params.month,
                "quarter": params.quarter,
                "year": params.year,
                "is_partial": params.is_partial,
                "start_date": params.start_date,
                "end_date": params.end_date,
            },
        )

        assert success is True, "Quarterly metrics dashboard upload failed"

    @pytest.mark.asyncio
    async def test_metrics_data_collection(self) -> None:
        """
        Test metrics data collection from DynamoDB.

        Validates that MetricsDataCollector can retrieve:
        - Executive CSO metrics (product coverage, war room readiness)
        - Technical system metrics (status updates, auto-messages)
        """
        import time
        from packages.core.typed_di_integration import get_unified_container
        from packages.slack.services.metrics_data_collector import MetricsDataCollector

        container = await get_unified_container()
        data_collector = container.get(MetricsDataCollector)

        assert data_collector is not None, "Failed to resolve MetricsDataCollector"

        # Calculate 7-day time window
        end_ts = int(time.time())
        start_ts = end_ts - (7 * 24 * 60 * 60)

        # Test complete metrics collection with time parameters
        metrics = await data_collector.collect_all_metrics(
            start_ts,
            end_ts,
            "7_days",
            None,
        )

        assert "cso" in metrics, "Should have CSO metrics"
        assert "technical" in metrics, "Should have technical metrics"
        assert isinstance(metrics["cso"], dict), "CSO metrics should be a dictionary"
        assert isinstance(metrics["technical"], dict), "Technical metrics should be a dictionary"

    @pytest.mark.asyncio
    async def test_html_generation(self) -> None:
        """
        Test HTML dashboard generation with time periods.

        Validates that MetricsHTMLGenerator can create valid HTML
        from metrics data with time period context.
        """
        from datetime import datetime, timezone
        from packages.core.typed_di_integration import get_unified_container
        from packages.core.exports.html_generator import MetricsHTMLGenerator
        from packages.slack.services.metrics_data_collector import MetricsDataCollector

        container = await get_unified_container()

        data_collector = container.get(MetricsDataCollector)
        html_generator = container.get(MetricsHTMLGenerator)

        # Calculate 7-day time window
        import time
        end_ts = int(time.time())
        start_ts = end_ts - (7 * 24 * 60 * 60)
        start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)
        end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc)

        # Collect real metrics data
        metrics = await data_collector.collect_all_metrics(
            start_ts,
            end_ts,
            "7_days",
            None,
        )

        # Generate HTML with time period
        html_content = html_generator.generate(
            metrics["cso"],
            metrics["technical"],
            metrics.get("jira_posting", {}),
            period_type="7_days",
            start_date=start_date,
            end_date=end_date,
        )

        assert html_content is not None, "HTML content should not be None"
        assert isinstance(html_content, str), "HTML should be a string"
        assert len(html_content) > 0, "HTML should not be empty"
        assert "<html" in html_content.lower(), "Should contain HTML tags"
        assert "ketchup" in html_content.lower(), "Should contain Ketchup branding"
        assert "Past 7 Days" in html_content, "Should show 7-day period in title"


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration tests only run when RUN_INTEGRATION_TESTS=true"
)
class TestMetricsIntegrationConditional:
    """
    Integration tests that only run when explicitly enabled.

    Run with: RUN_INTEGRATION_TESTS=true pytest tests/integration/test_metrics_integration.py
    """

    @pytest.mark.asyncio
    async def test_manual_metrics_upload(self) -> None:
        """
        Manual test for uploading metrics dashboard.

        This test should be run manually to validate the upload
        without running automatically in CI/CD.
        """
        from packages.core.typed_di_integration import get_unified_container
        from packages.slack.interactive_elements.metrics_export_handler import (
            MetricsExportHandler
        )

        container = await get_unified_container()
        handler = container.get(MetricsExportHandler)

        # Manual upload to Ketchup's home
        success = await handler.handle_metrics_request(
            user_id=KETCHUP_HOME_CHANNEL,
            response_url=None,
        )

        # Log result for manual verification
        if success:
            print(f"\n✅ Dashboard successfully uploaded to {KETCHUP_HOME_CHANNEL}")
            print("   Check Ketchup's DM for the HTML file")
        else:
            print(f"\n❌ Dashboard upload failed to {KETCHUP_HOME_CHANNEL}")

        assert success is True
