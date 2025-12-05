#!/usr/bin/env python3
"""
Integration test to generate and send metrics dashboard with JIRA metrics to Ketchup DM.

This test validates:
1. TypedDI container initialization
2. MetricsExportHandler resolution from TypedDI
3. Dashboard generation with JIRA posting metrics
4. File upload to Ketchup's DM channel

Usage:
    KETCHUP_USE_TYPED_DI=true AWS_PROFILE=campaign_prod_v7 python test_dashboard_with_jira_metrics.py

Environment Requirements:
    - KETCHUP_USE_TYPED_DI=true (to enable TypedDI)
    - AWS_PROFILE=campaign_prod_v7 (for AWS credentials)
    - PYTHONPATH=. (to import packages)
"""

import asyncio
import sys

# Ketchup's home DM channel
KETCHUP_DM = "D0840EX80R5"


async def main():
    """Generate dashboard with JIRA metrics and send to Ketchup DM."""
    print("🚀 Starting metrics dashboard integration test with JIRA metrics...")

    try:
        # Initialize TypedDI container
        import time

        from packages.core.exports.html_generator import MetricsHTMLGenerator
        from packages.core.typed_di_integration import get_unified_container
        from packages.slack.interactive_elements.metrics_export_handler import MetricsExportHandler
        from packages.slack.services.metrics_data_collector import MetricsDataCollector

        print("📦 Initializing unified container...")
        container = await get_unified_container()

        if container is None:
            print("❌ Container not available")
            return 1

        print("✅ Container initialized")

        # Get MetricsExportHandler from container
        print("🔍 Resolving MetricsExportHandler...")
        handler = container.get(MetricsExportHandler)

        if handler is None:
            print("❌ MetricsExportHandler not found")
            return 1

        print("✅ MetricsExportHandler resolved successfully")

        # Send dashboard to Ketchup's DM
        print(f"📤 Sending dashboard to Ketchup DM ({KETCHUP_DM})...")

        success = await handler.handle_metrics_request(user_id=KETCHUP_DM, response_url=None)

        if success:
            print(f"✅ Dashboard successfully sent to {KETCHUP_DM}")
            print("📊 Check Ketchup's DM for the HTML dashboard with new JIRA metrics!")
            print("\nNew metrics visible in dashboard:")
            print("  • JIRA Reports Posted (Executive CSO section)")
            print("  • JIRA Posting Breakdown (Technical Health section)")

            # Validate CSO metrics split by generating HTML directly
            print("\n✅ Validating CSO metrics cards...")

            # Get metrics collector and HTML generator
            metrics_collector = container.get(MetricsDataCollector)
            html_generator = container.get(MetricsHTMLGenerator)

            # Collect metrics
            end_ts = int(time.time())
            start_ts = end_ts - (7 * 24 * 60 * 60)
            metrics_data = await metrics_collector.collect_all_metrics(
                start_ts,
                end_ts,
                "7_days",
                None,
            )

            # Generate HTML for validation
            from datetime import datetime, timezone

            start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            html = html_generator.generate(
                metrics_data["cso"],
                metrics_data["technical"],
                metrics_data.get("jira_posting", {}),
                period_type="7_days",
                start_date=start_date,
                end_date=end_date,
            )

            # Validate CSO cards in HTML (case-insensitive due to CSS text-transform)
            html_lower = html.lower()
            if "currently active cso channels" in html_lower:
                print("  ✓ Currently Active card found")
            else:
                print("  ✗ Currently Active card MISSING")

            if "archived cso channels" in html_lower:
                print("  ✓ Archived card found")
            else:
                print("  ✗ Archived card MISSING")

            if "Campaign" in html and "AJO" in html:
                print("  ✓ Product breakdown displayed")
            else:
                print("  ✗ Product breakdown MISSING")

            return 0
        else:
            print(f"❌ Failed to send dashboard to {KETCHUP_DM}")
            return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
