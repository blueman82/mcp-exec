import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.ai.core.operations.message_preparation import (
    MessagePreparationError,
    MessagePreparer,
)


class TestMessagePreparerParallel(unittest.TestCase):
    def setUp(self):
        self.token_tracker = MagicMock()
        self.channel_msg_ops = MagicMock()
        self.channel_info_ops = MagicMock()
        self.preparer = MessagePreparer(
            self.token_tracker, self.channel_msg_ops, self.channel_info_ops
        )

    @patch(
        "packages.ai.core.operations.message_preparation.get_prompt_for_command",
        return_value="dummy instructions",
    )
    def test_prepare_messages_parallel_success(self, mock_get_prompt):
        async def run_test():
            # Arrange
            self.channel_info_ops.get_channel_info_from_api = AsyncMock(
                return_value={"name": "test-channel", "is_member": True}
            )
            self.channel_msg_ops.fetch_channel_messages = AsyncMock(
                return_value=["message 1", "message 2"]
            )

            # Act
            messages, channel_info = await self.preparer.prepare_messages(
                "command", "U123", "C123"
            )

            # Assert
            self.assertIn("role", messages[0])
            self.assertIn("content", messages[0])
            self.assertIn("role", messages[1])
            self.assertIn("content", messages[1])
            self.assertIn("message 1", messages[1]["content"])
            self.assertEqual(channel_info["target_channel"], "C123")

        asyncio.run(run_test())

    def test_prepare_messages_parallel_channel_info_fails(self):
        async def run_test():
            # Arrange
            self.channel_info_ops.get_channel_info_from_api = AsyncMock(
                side_effect=Exception("API Error")
            )
            self.channel_msg_ops.fetch_channel_messages = AsyncMock(
                return_value=["message 1"]
            )

            # Act & Assert
            with self.assertRaises(MessagePreparationError):
                await self.preparer.prepare_messages("command", "U123", "C123")

        asyncio.run(run_test())

    def test_prepare_messages_parallel_fetch_messages_fails(self):
        async def run_test():
            # Arrange
            self.channel_info_ops.get_channel_info_from_api = AsyncMock(
                return_value={"name": "test-channel", "is_member": True}
            )
            self.channel_msg_ops.fetch_channel_messages = AsyncMock(
                side_effect=Exception("Fetch Error")
            )

            # Act & Assert
            with self.assertRaises(MessagePreparationError):
                await self.preparer.prepare_messages("command", "U123", "C123")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
