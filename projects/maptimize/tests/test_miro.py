"""Tests for Miro board screenshot functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,  # type: ignore[import-not-found]
)

from maptimize.miro import screenshot_miro_board


@pytest.fixture
def mock_screenshot_bytes():
    """Return sample PNG bytes."""
    # Minimal valid PNG header
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
    )


@pytest.fixture
def mock_playwright_browser(mock_screenshot_bytes):
    """Mock Playwright browser and page objects."""
    # Create mock page
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=mock_screenshot_bytes)

    # Create mock browser
    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()

    # Create mock playwright instance
    mock_playwright_instance = MagicMock()
    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)

    return {
        "playwright": mock_playwright_instance,
        "browser": mock_browser,
        "page": mock_page,
    }


@pytest.mark.asyncio
class TestScreenshotMiroBoard:
    """Tests for screenshot_miro_board function."""

    async def test_screenshot_miro_board_success(
        self, mock_playwright_browser, mock_screenshot_bytes
    ):
        """Test successful Miro board screenshot capture."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Call function
            result = await screenshot_miro_board("uXjVJ2FVjGM")

            # Assertions
            assert result is not None
            assert isinstance(result, bytes)
            assert result == mock_screenshot_bytes
            assert len(result) > 0

            # Verify browser operations
            mock_playwright_browser["playwright"].chromium.launch.assert_called_once_with(
                headless=True
            )
            mock_playwright_browser["browser"].new_page.assert_called_once_with(
                viewport={"width": 1700, "height": 1000}
            )
            mock_playwright_browser["page"].goto.assert_called_once_with(
                "https://miro.com/app/board/uXjVJ2FVjGM/",
                wait_until="networkidle",
                timeout=30000,
            )
            mock_playwright_browser["page"].screenshot.assert_called_once_with(
                type="png",
                full_page=True,
            )
            mock_playwright_browser["browser"].close.assert_called()

    async def test_screenshot_miro_board_invalid_board_id_empty_string(self):
        """Test with empty string board_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await screenshot_miro_board("")

        assert "board_id cannot be empty" in str(exc_info.value)

    async def test_screenshot_miro_board_invalid_board_id_none(self):
        """Test with None board_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await screenshot_miro_board(None)

        # Will raise because None is not a string and will fail validation
        assert "board_id cannot be empty" in str(exc_info.value) or "NoneType" in str(
            exc_info.value
        )

    async def test_screenshot_miro_board_invalid_board_id_special_chars(self):
        """Test with invalid characters in board_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await screenshot_miro_board("invalid@board#id!")

        assert "Invalid board_id format" in str(exc_info.value)
        assert "alphanumeric characters, underscores, and hyphens" in str(exc_info.value)

    async def test_screenshot_miro_board_timeout(self, mock_playwright_browser):
        """Test handling of page load timeout."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Make goto raise PlaywrightTimeoutError
            mock_playwright_browser["page"].goto.side_effect = PlaywrightTimeoutError(
                "Timeout exceeded"
            )

            # Call function
            result = await screenshot_miro_board("uXjVJ2FVjGM")

            # Should return None on timeout (not raise)
            assert result is None

            # Browser should still be closed
            mock_playwright_browser["browser"].close.assert_called()

    async def test_screenshot_miro_board_network_error(self, mock_playwright_browser):
        """Test handling of generic network errors."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Make goto raise generic exception
            mock_playwright_browser["page"].goto.side_effect = Exception("Network error")

            # Call function
            result = await screenshot_miro_board("uXjVJ2FVjGM")

            # Should return None on error (not raise)
            assert result is None

            # Browser should still be closed
            mock_playwright_browser["browser"].close.assert_called()

    async def test_screenshot_miro_board_browser_cleanup_on_error(self, mock_playwright_browser):
        """Test browser cleanup happens even when errors occur."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Make screenshot raise exception
            mock_playwright_browser["page"].screenshot.side_effect = Exception("Screenshot failed")

            # Call function
            result = await screenshot_miro_board("uXjVJ2FVjGM")

            # Should return None
            assert result is None

            # Verify browser.close() was called despite error
            mock_playwright_browser["browser"].close.assert_called()

    async def test_screenshot_miro_board_custom_dimensions(
        self, mock_playwright_browser, mock_screenshot_bytes
    ):
        """Test screenshot with custom width and height."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Call with custom dimensions
            custom_width = 1920
            custom_height = 1080
            result = await screenshot_miro_board(
                "uXjVJ2FVjGM",
                width=custom_width,
                height=custom_height,
            )

            # Verify result
            assert result == mock_screenshot_bytes

            # Verify new_page was called with custom viewport
            mock_playwright_browser["browser"].new_page.assert_called_once_with(
                viewport={"width": custom_width, "height": custom_height}
            )

    async def test_screenshot_miro_board_custom_timeout(
        self, mock_playwright_browser, mock_screenshot_bytes
    ):
        """Test screenshot with custom timeout."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Call with custom timeout
            custom_timeout = 60000  # 60 seconds
            result = await screenshot_miro_board(
                "uXjVJ2FVjGM",
                timeout_ms=custom_timeout,
            )

            # Verify result
            assert result == mock_screenshot_bytes

            # Verify goto was called with custom timeout
            mock_playwright_browser["page"].goto.assert_called_once_with(
                "https://miro.com/app/board/uXjVJ2FVjGM/",
                wait_until="networkidle",
                timeout=custom_timeout,
            )

    async def test_screenshot_miro_board_browser_close_failure_logged(
        self, mock_playwright_browser
    ):
        """Test that browser close failures are logged but don't raise."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Make screenshot succeed but browser.close fail
            mock_playwright_browser["browser"].close.side_effect = Exception("Close failed")

            # Call function - should not raise
            result = await screenshot_miro_board("uXjVJ2FVjGM")

            # Should return None when any error occurs (including during cleanup)
            # The important thing is that it doesn't raise an exception
            assert result is None

    async def test_screenshot_miro_board_valid_board_id_with_hyphens(
        self, mock_playwright_browser, mock_screenshot_bytes
    ):
        """Test that board IDs with hyphens are accepted."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Call with board ID containing hyphens
            result = await screenshot_miro_board("board-id-with-hyphens")

            # Should succeed
            assert result == mock_screenshot_bytes

    async def test_screenshot_miro_board_valid_board_id_with_underscores(
        self, mock_playwright_browser, mock_screenshot_bytes
    ):
        """Test that board IDs with underscores are accepted."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            # Call with board ID containing underscores
            result = await screenshot_miro_board("board_id_with_underscores")

            # Should succeed
            assert result == mock_screenshot_bytes

    async def test_screenshot_miro_board_constructs_correct_url(
        self, mock_playwright_browser, mock_screenshot_bytes
    ):
        """Test that the correct Miro board URL is constructed."""
        with patch("maptimize.miro.async_playwright") as mock_async_playwright:
            # Setup async context manager
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright_browser[
                "playwright"
            ]

            board_id = "testBoardId123"
            await screenshot_miro_board(board_id)

            # Verify correct URL was used
            expected_url = f"https://miro.com/app/board/{board_id}/"
            mock_playwright_browser["page"].goto.assert_called_once()
            call_args = mock_playwright_browser["page"].goto.call_args
            assert call_args[0][0] == expected_url
