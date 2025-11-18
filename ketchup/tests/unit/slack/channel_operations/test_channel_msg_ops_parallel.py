import asyncio
import unittest
from unittest.mock import MagicMock, patch

from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps


class TestSlackChannelMessageOpsParallel(unittest.TestCase):
    def setUp(self):
        self.user_ops = MagicMock()
        self.archive_ops = MagicMock()
        self.slack_config = MagicMock()
        self.ops = SlackChannelMessageOps(
            self.user_ops, self.archive_ops, self.slack_config
        )

    @patch(
        "packages.slack.channel_operations.channel_msg_ops.SlackChannelMessageOps.fetch_thread_messages"
    )
    def test_fetch_thread_messages_parallel(self, mock_fetch_thread_messages):
        async def run_test():
            # Arrange
            channel_id = "C12345"
            thread_timestamps = ["1", "2", "3", "4", "5"]
            mock_fetch_thread_messages.side_effect = [
                [{"text": "reply 1"}],
                [{"text": "reply 2"}],
                Exception("Fetch failed"),
                [{"text": "reply 4"}],
                [{"text": "reply 5"}],
            ]

            # Act
            results, user_mentions = await self.ops._fetch_thread_messages_parallel(
                channel_id, thread_timestamps
            )

            # Assert
            self.assertEqual(len(results), 5)
            self.assertEqual(results["1"], [{"text": "reply 1"}])
            self.assertEqual(results["2"], [{"text": "reply 2"}])
            self.assertEqual(results["3"], [])  # Fallback for the failed thread
            self.assertEqual(results["4"], [{"text": "reply 4"}])
            self.assertEqual(results["5"], [{"text": "reply 5"}])
            self.assertEqual(mock_fetch_thread_messages.call_count, 5)
            self.assertEqual(len(user_mentions), 0)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
