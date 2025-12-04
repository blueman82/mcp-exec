"""Miro board screenshot utilities for Slack bot integration.

Provides async functions to capture screenshots of public Miro boards
and return them as PNG bytes for uploading to Slack.
"""

import re
from typing import Optional

import structlog
from playwright.async_api import (  # type: ignore[import-not-found]
    TimeoutError as PlaywrightTimeoutError,
)
from playwright.async_api import async_playwright  # type: ignore[import-not-found]

__all__ = [
    "screenshot_miro_board",
]

logger = structlog.get_logger(__name__)

# Pattern for valid Miro board IDs (alphanumeric, underscores, hyphens, equals for base64)
BOARD_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_=-]+$")


async def screenshot_miro_board(
    board_id: str,
    width: int = 1700,
    height: int = 1000,
    timeout_ms: int = 30000,
) -> Optional[bytes]:
    """Take a screenshot of a Miro board and return as PNG bytes.

    Launches a headless Chromium browser, navigates to the specified Miro board,
    waits for the page to fully load, and captures a full-page screenshot. Handles
    timeouts and network errors gracefully.

    Args:
        board_id: The Miro board ID (e.g., "uXjVJ2FVjGM")
        width: Viewport width in pixels (default: 1700)
        height: Viewport height in pixels (default: 1000)
        timeout_ms: Navigation timeout in milliseconds (default: 30000)

    Returns:
        PNG image bytes, or None if screenshot fails

    Raises:
        ValueError: If board_id is empty or invalid format

    Example:
        >>> image_bytes = await screenshot_miro_board("uXjVJ2FVjGM")
        >>> if image_bytes:
        >>>     # Upload to Slack
        >>>     await upload_to_slack(image_bytes)
    """
    # Validate board_id
    if not board_id:
        raise ValueError("board_id cannot be empty")

    if not BOARD_ID_PATTERN.match(board_id):
        raise ValueError(
            f"Invalid board_id format: '{board_id}'. "
            "Board IDs must contain only alphanumeric characters, underscores, and hyphens."
        )

    logger.info(
        "miro_screenshot_started",
        board_id=board_id,
        width=width,
        height=height,
        timeout_ms=timeout_ms,
    )

    browser = None
    try:
        # Launch browser with Playwright
        async with async_playwright() as playwright:
            # Launch Chromium browser in headless mode
            browser = await playwright.chromium.launch(headless=True)

            # Create new page with specified viewport
            page = await browser.new_page(viewport={"width": width, "height": height})

            # Construct Miro board URL
            board_url = f"https://miro.com/app/board/{board_id}/"

            # Navigate to the board
            # wait_until="networkidle" ensures page is fully loaded
            await page.goto(
                board_url,
                wait_until="networkidle",
                timeout=timeout_ms,
            )

            # Capture full page screenshot as PNG
            screenshot_bytes: bytes = await page.screenshot(
                type="png",
                full_page=True,
            )

            # Close browser
            await browser.close()

            logger.info(
                "miro_screenshot_success",
                board_id=board_id,
                image_size=len(screenshot_bytes),
            )

            return screenshot_bytes

    except PlaywrightTimeoutError:
        logger.warning(
            "miro_screenshot_timeout",
            board_id=board_id,
            timeout_ms=timeout_ms,
        )
        return None

    except Exception as e:
        logger.error(
            "miro_screenshot_error",
            board_id=board_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return None

    finally:
        # Ensure browser is closed even if error occurs
        if browser:
            try:
                await browser.close()
            except Exception as cleanup_error:
                logger.warning(
                    "miro_browser_cleanup_failed",
                    board_id=board_id,
                    error=str(cleanup_error),
                )
