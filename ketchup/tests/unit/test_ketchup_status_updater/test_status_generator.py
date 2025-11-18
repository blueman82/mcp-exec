"""
Unit tests for AutoStatusGenerator
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_status_updater.status_generator import AutoStatusGenerator


class TestAutoStatusGenerator:
    """Test cases for AutoStatusGenerator"""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for AutoStatusGenerator"""
        return {
            "db_store": MagicMock(),
            "mcp_client": AsyncMock(),
            "secrets_manager": AsyncMock(),
            "slack_config": MagicMock(openai_model="gpt-4"),
            "openai_handler": MagicMock(),
            "channel_info_ops": AsyncMock(),
            "channel_msg_ops": AsyncMock(),
            "posting_handler": AsyncMock(),
            "channel_operations": AsyncMock(),
        }

    @pytest.fixture
    def generator(self, mock_dependencies):
        """Create AutoStatusGenerator instance with mocked dependencies"""
        return AutoStatusGenerator(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_get_ketchup_bot_user_id_success(self, generator, mock_dependencies):
        """Test successful retrieval of bot user ID"""
        mock_dependencies["secrets_manager"].get_bot_slack_user_id_async = AsyncMock(
            return_value="U123456"
        )

        result = await generator.secrets_manager.get_bot_slack_user_id_async()
        assert result == "U123456"

    @pytest.mark.asyncio
    async def test_get_ketchup_bot_user_id_not_found(
        self, generator, mock_dependencies
    ):
        """Test when bot user ID is not found"""
        mock_dependencies["secrets_manager"].get_bot_slack_user_id_async = AsyncMock(
            return_value=None
        )

        result = await generator.secrets_manager.get_bot_slack_user_id_async()
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_jira_comments_raw_success(self, generator, mock_dependencies):
        """Test successful fetching of JIRA comments"""
        mock_comments = [
            {
                "author": {"displayName": "John Doe"},
                "created": "2024-01-01T10:00:00",
                "body": "Test comment 1",
            },
            {
                "author": {"displayName": "Jane Smith"},
                "created": "2024-01-02T10:00:00",
                "body": "Test comment 2",
            },
        ]
        mock_dependencies["mcp_client"].get_issue_comments = AsyncMock(
            return_value=mock_comments
        )

        result = await generator._fetch_jira_comments_raw("TEST-123")

        assert result is not None
        assert "[2024-01-02] Jane Smith: Test comment 2" in result
        assert "[2024-01-01] John Doe: Test comment 1" in result

    @pytest.mark.asyncio
    async def test_fetch_jira_comments_raw_no_comments(
        self, generator, mock_dependencies
    ):
        """Test when no JIRA comments are found"""
        mock_dependencies["mcp_client"].get_issue_comments = AsyncMock(return_value=[])

        result = await generator._fetch_jira_comments_raw("TEST-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_jira_comments_raw_error(self, generator, mock_dependencies):
        """Test error handling in JIRA comment fetching"""
        mock_dependencies["mcp_client"].get_issue_comments = AsyncMock(
            side_effect=Exception("MCP error")
        )

        result = await generator._fetch_jira_comments_raw("TEST-123")
        assert result is None

    def test_apply_corrections(self, generator):
        """Test corrections applied to AI output"""
        content = "Check NOT YET AVAILABLE for updates on TEST-123"
        channel_details = {"jira_ticket": "TEST-123"}

        result = generator._apply_corrections(
            content=content,
            channel_name="test-channel",
            channel_details=channel_details,
        )

        assert "#test-channel" in result
        assert "<https://jira.corp.adobe.com/browse/TEST-123|TEST-123>" in result

    def test_format_final_message(self, generator):
        """Test final message formatting"""
        content = "Test status content"
        channel_name = "test-channel"
        channel_id = "C123456"

        result = generator._format_final_message(content, channel_name, channel_id)

        assert "*Ketchup Automated Status Update*" in result
        assert f"<#{channel_id}|{channel_name}>" in result
        assert "Status checked hourly" in result
        assert content in result

    @pytest.mark.asyncio
    async def test_post_to_slack_public_success(self, generator, mock_dependencies):
        """Test successful posting to Slack"""
        mock_dependencies["posting_handler"]._slack_token = "test-token"
        mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123456"}
        )
        # Mock channel operations for delete previous post
        mock_dependencies["channel_operations"].get_channel_details = AsyncMock(
            return_value={"auto_status_last_post_ts": "0"}
        )
        mock_dependencies["channel_operations"].update_channel_fields = AsyncMock()

        result = await generator._post_to_slack_public("C123456", "Test message", "status_123")

        assert result.get("success") is True
        assert mock_dependencies["posting_handler"]._post_channel_message.called

    @pytest.mark.asyncio
    async def test_post_to_slack_public_init_token(self, generator, mock_dependencies):
        """Test token initialization before posting"""
        mock_dependencies["posting_handler"]._slack_token = None
        mock_dependencies["posting_handler"]._init_slack_token = AsyncMock()
        mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123456"}
        )
        # Mock channel operations for delete previous post
        mock_dependencies["channel_operations"].get_channel_details = AsyncMock(
            return_value={"auto_status_last_post_ts": "0"}
        )
        mock_dependencies["channel_operations"].update_channel_fields = AsyncMock()

        result = await generator._post_to_slack_public("C123456", "Test message", "status_123")

        assert result.get("success") is True
        assert mock_dependencies["posting_handler"]._init_slack_token.called

    @pytest.mark.asyncio
    async def test_generate_ai_response(self, generator, mock_dependencies):
        """Test AI response generation"""
        # Mock the openai_handler execute_prompt method directly
        mock_dependencies["openai_handler"].execute_prompt = AsyncMock(
            return_value="Generated status update"
        )

        result = await generator._generate_ai_response(
            system_prompt="System prompt", user_prompt="User prompt"
        )

        assert result == "Generated status update"
        # Verify the execute_prompt was called with correct parameters
        mock_dependencies["openai_handler"].execute_prompt.assert_called_once()
        call_args = mock_dependencies["openai_handler"].execute_prompt.call_args
        assert call_args[1]["messages"][0]["role"] == "system"
        assert call_args[1]["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_and_post_status_no_messages(
        self, generator, mock_dependencies
    ):
        """Test status generation when no messages are found"""
        channel_config = {"auto_status_last_message_ts": "0"}

        # Mock message preparer
        with patch(
            "ketchup_status_updater.status_generator.MessagePreparer"
        ) as mock_preparer_class:
            mock_preparer = mock_preparer_class.return_value
            mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                return_value=("No messages found", {"latest_ts": "0"})
            )

            # Mock bot user ID
            mock_dependencies["secrets_manager"].get_bot_slack_user_id_async = (
                AsyncMock(return_value="U123456")
            )

            # Mock channel details for both paths
            mock_dependencies["channel_operations"].get_channel_details = AsyncMock(
                return_value={"jira_ticket": "NOT YET AVAILABLE"}
            )
            # Mock query_ops path for verification
            mock_query_ops = MagicMock()
            mock_query_ops.get_channel_details = AsyncMock(
                return_value={"jira_ticket": "NOT YET AVAILABLE", "auto_status_last_run": 0}
            )
            mock_dependencies["channel_operations"].query_ops = mock_query_ops

            # Mock verification flow dependencies
            mock_dependencies["channel_msg_ops"].get_api_base_url = AsyncMock(
                return_value="https://slack.com/api"
            )
            mock_dependencies["channel_msg_ops"]._make_api_request = AsyncMock(
                return_value={"body": '{"ok": true, "messages": []}'}
            )
            mock_dependencies["channel_msg_ops"].check_recent_thread_activity = AsyncMock(
                return_value=(False, "0", 0)
            )

            # Mock posting
            mock_dependencies["posting_handler"]._init_slack_token = AsyncMock()
            mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
                return_value={"ok": True, "ts": "1234567890.123456"}
            )
            mock_dependencies["posting_handler"].update_message = AsyncMock()

            # Mock AI response generation
            mock_dependencies["openai_handler"].execute_prompt = AsyncMock(
                return_value="No new activity detected since last update."
            )

            # Mock the verification to allow first-run posting
            with patch.object(generator, "_verify_real_activity", return_value=True):
                result = await generator.generate_and_post_status(
                    channel_id="C123456",
                    channel_name="test-channel",
                    channel_config=channel_config,
                )

            assert result is True
            post_call = mock_dependencies[
                "posting_handler"
            ]._post_channel_message.call_args
            assert "No new activity detected" in post_call[1]["message"]

    @pytest.mark.asyncio
    async def test_generate_and_post_status_with_jira(
        self, generator, mock_dependencies
    ):
        """Test status generation with JIRA comments"""
        channel_config = {
            "auto_status_last_message_ts": "0",
            "auto_status_last_content": "",
        }

        # Mock channel details
        channel_details = {
            "jira_ticket": "TEST-123",
            "customer_name": "Test Customer",
            "product": "test-product",
            "auto_status_last_run": 0,
        }
        mock_dependencies["channel_operations"].get_channel_details = AsyncMock(
            return_value=channel_details
        )
        # Mock query_ops path for verification
        mock_query_ops = MagicMock()
        mock_query_ops.get_channel_details = AsyncMock(return_value=channel_details)
        mock_dependencies["channel_operations"].query_ops = mock_query_ops

        # Mock message preparer
        with patch(
            "ketchup_status_updater.status_generator.MessagePreparer"
        ) as mock_preparer_class:
            mock_preparer = mock_preparer_class.return_value
            mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                return_value=("Test messages", {"latest_ts": "123456"})
            )

            # Mock JIRA comments
            mock_dependencies["mcp_client"].get_issue_comments = AsyncMock(
                return_value=[
                    {
                        "author": {"displayName": "Test User"},
                        "created": "2024-01-01T10:00:00",
                        "body": "JIRA comment",
                    }
                ]
            )

            # Mock verification flow dependencies
            mock_dependencies["channel_msg_ops"].get_api_base_url = AsyncMock(
                return_value="https://slack.com/api"
            )
            mock_dependencies["channel_msg_ops"]._make_api_request = AsyncMock(
                return_value={"body": '{"ok": true, "messages": [{"user": "U999999", "text": "Test message", "ts": "123456"}]}'}
            )
            mock_dependencies["channel_msg_ops"].check_recent_thread_activity = AsyncMock(
                return_value=(False, "0", 0)
            )

            # Mock AI response
            with patch.object(
                generator,
                "_generate_ai_response",
                return_value="**Overview:** Test status\n\n**What's been done / What's next:**\n• Action 1\n• Action 2\n• Action 3\n• Action 4",
            ):

                # Mock posting
                mock_dependencies["posting_handler"]._init_slack_token = AsyncMock()
                mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
                    return_value={"ok": True}
                )

                # Mock field update
                mock_dependencies[
                    "db_store"
                ].channel_operations.update_channel_fields = AsyncMock()

                # Mock bot user ID
                mock_dependencies["secrets_manager"].get_bot_slack_user_id_async = (
                    AsyncMock(return_value="U123456")
                )

                # Mock the verification to allow first-run posting
                with patch.object(generator, "_verify_real_activity", return_value=True):
                    result = await generator.generate_and_post_status(
                        channel_id="C123456",
                        channel_name="test-channel",
                        channel_config=channel_config,
                    )

                assert result is True

                # Verify AI was called with JIRA comments
                ai_call = generator._generate_ai_response.call_args
                assert "JIRA Comments to Analyze:" in ai_call[1]["user_prompt"]
                assert "JIRA comment" in ai_call[1]["user_prompt"]
