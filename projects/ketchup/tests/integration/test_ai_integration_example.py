#!/usr/bin/env python3
"""
Example AI/OpenAI integration test using the base integration test framework.

Tests OpenAI handler functionality with real API calls.
"""

import asyncio
import sys

from base_integration_test import run_simple_integration_test


async def test_openai_summarization(services, logger):
    """Test OpenAI summarization capabilities."""
    openai_handler = services["openai"]

    logger.info("Testing OpenAI summarization...")

    # Test message for summarization
    test_messages = [
        "User1: We're experiencing authentication issues with the SSO system",
        "User2: Yes, I'm getting 401 errors when trying to log in",
        "User3: The SAML response seems to be malformed",
        "User1: I checked the logs and found expired certificates",
        "User2: That explains it. When can we get new certificates?",
    ]

    try:
        # Test short summary
        logger.info("Generating short summary...")
        short_summary = await openai_handler.generate_short_summary(
            messages=test_messages, channel_name="test-channel"
        )

        if short_summary:
            logger.info("✅ Short summary generated:")
            logger.info(f"  {short_summary}")
        else:
            logger.error("❌ Failed to generate short summary")
            return False

        # Test detailed summary
        logger.info("\nGenerating detailed summary...")
        detailed_summary = await openai_handler.generate_detailed_summary(
            messages=test_messages, channel_name="test-channel"
        )

        if detailed_summary:
            logger.info("✅ Detailed summary generated:")
            # Show first few lines
            lines = detailed_summary.split("\n")[:5]
            for line in lines:
                logger.info(f"  {line}")
            if len(detailed_summary.split("\n")) > 5:
                logger.info("  ...")
        else:
            logger.error("❌ Failed to generate detailed summary")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ OpenAI test failed: {e}")
        return False


async def test_openai_analysis(services, logger):
    """Test OpenAI analysis capabilities."""
    openai_handler = services["openai"]

    logger.info("Testing OpenAI analysis...")

    # Test incident analysis
    incident_description = """
    Multiple users reporting intermittent 503 errors from the API gateway.
    The errors started around 2PM and seem to correlate with increased traffic.
    CPU usage on gateway instances is at 85%. Some requests are timing out.
    """

    try:
        logger.info("Performing incident analysis...")

        # Use the AI to analyze the incident
        analysis = await openai_handler.process_ai_request(
            messages=[incident_description],
            system_prompt="Analyze this incident and provide: 1) Likely root cause, 2) Immediate actions, 3) Long-term fixes",
            max_tokens=500,
        )

        if analysis:
            logger.info("✅ Analysis completed:")
            # Show first few lines
            lines = analysis.split("\n")[:8]
            for line in lines:
                if line.strip():
                    logger.info(f"  {line}")
        else:
            logger.error("❌ Failed to analyze incident")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ OpenAI analysis failed: {e}")
        return False


async def main():
    """Run AI integration tests."""

    ai_services = [
        "openai",
        "slack_config",  # Needed for some AI operations
        "secrets_manager",
    ]

    # Test 1: Summarization
    success1 = await run_simple_integration_test(
        test_name="openai_summarization",
        test_func=test_openai_summarization,
        required_services=ai_services,
    )

    print("\n" + "=" * 60 + "\n")

    # Test 2: Analysis
    success2 = await run_simple_integration_test(
        test_name="openai_analysis",
        test_func=test_openai_analysis,
        required_services=ai_services,
    )

    return success1 and success2


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
