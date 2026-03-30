"""Tests for time_window_to_oldest_ts conversion utility."""

from unittest.mock import patch

from packages.ai.core.operations.message_preparation import time_window_to_oldest_ts


class TestTimeWindowToOldestTs:
    """Tests for the time_window_to_oldest_ts function."""

    @patch("packages.ai.core.operations.message_preparation.time.time")
    def test_past_2_hours(self, mock_time):
        mock_time.return_value = 1000000.0
        result = time_window_to_oldest_ts("past_2_hours")
        assert result == str(1000000.0 - 7200)

    @patch("packages.ai.core.operations.message_preparation.time.time")
    def test_past_24_hours(self, mock_time):
        mock_time.return_value = 1000000.0
        result = time_window_to_oldest_ts("past_24_hours")
        assert result == str(1000000.0 - 86400)

    def test_all_time(self):
        result = time_window_to_oldest_ts("all_time")
        assert result == "0"

    def test_unknown_value(self):
        result = time_window_to_oldest_ts("some_unknown_value")
        assert result == "0"
