"""
test_openai_factory.py

Unit tests for packages.ai.core.openai_factory.create_openai_handler.

Covers:
- Successful creation and initialization of OpenAIHandler with all dependencies mocked
- Error/exception handling if a dependency fails
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.core.openai_factory import create_openai_handler


@pytest.mark.asyncio
@pytest.mark.unit
class TestCreateOpenAIHandler:
    """Unit tests for create_openai_handler factory function."""

    @patch("packages.ai.core.openai_factory.OpenAIHandler", autospec=True)
    @patch("packages.ai.core.openai_factory.get_token_tracker", autospec=True)
    @patch("packages.ai.core.openai_factory.SecretsManager", autospec=True)
    async def test_create_openai_handler_success(
        self,
        mock_secrets_manager: MagicMock,
        mock_get_token_tracker: MagicMock,
        mock_openai_handler: MagicMock,
    ) -> None:
        """Test successful creation and initialization of OpenAIHandler with all dependencies mocked."""
        # Arrange: Mock all dependencies and their async methods
        channel_info_ops = MagicMock()
        channel_membership_ops = MagicMock()
        channel_msg_ops = MagicMock()
        channel_ops = MagicMock()
        # OpenAIHandler instance with async initialize
        handler_instance = MagicMock()
        handler_instance.initialize = AsyncMock()
        mock_openai_handler.return_value = handler_instance
        # Act
        result = await create_openai_handler(
            channel_info_ops=channel_info_ops,
            channel_membership_ops=channel_membership_ops,
            channel_msg_ops=channel_msg_ops,
            channel_ops=channel_ops,
        )
        # Assert
        mock_get_token_tracker.assert_called_once_with()
        mock_secrets_manager.assert_called_once_with()
        mock_openai_handler.assert_called_once()
        handler_instance.initialize.assert_awaited_once_with()
        assert result is handler_instance

    @patch("packages.ai.core.openai_factory.OpenAIHandler", autospec=True)
    @patch("packages.ai.core.openai_factory.get_token_tracker", autospec=True)
    @patch("packages.ai.core.openai_factory.SecretsManager", autospec=True)
    async def test_create_openai_handler_init_error(
        self,
        mock_secrets_manager: MagicMock,
        mock_get_token_tracker: MagicMock,
        mock_openai_handler: MagicMock,
    ) -> None:
        """Test error handling if OpenAIHandler.initialize raises an exception."""
        # Arrange
        channel_info_ops = MagicMock()
        channel_membership_ops = MagicMock()
        channel_msg_ops = MagicMock()
        channel_ops = MagicMock()
        handler_instance = MagicMock()
        handler_instance.initialize = AsyncMock(side_effect=RuntimeError("init fail"))
        mock_openai_handler.return_value = handler_instance
        # Act & Assert
        with pytest.raises(RuntimeError, match="init fail"):
            await create_openai_handler(
                channel_info_ops=channel_info_ops,
                channel_membership_ops=channel_membership_ops,
                channel_msg_ops=channel_msg_ops,
                channel_ops=channel_ops,
            )
        handler_instance.initialize.assert_awaited_once_with()
