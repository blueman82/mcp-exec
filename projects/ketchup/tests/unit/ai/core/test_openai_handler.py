"""
test_openai_handler.py

Unit tests for packages.ai.core.openai_handler.OpenAIHandler and OpenAIError.

Covers:
- OpenAIError: construction and raising
- OpenAIHandler: initialization (all dependencies mocked), error handling (missing API key, endpoint), _get_or_prepare_messages (provided/prepared/error/missing), call_openai_endpoint (mocked), get_usage_summary/calculate_token_usage/cleanup (mocked)
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.core.openai_handler import OpenAIError, OpenAIHandler


@pytest.mark.unit
class TestOpenAIError:
    """Unit tests for OpenAIError exception."""

    def test_error_construction_and_raise(self) -> None:
        """Test OpenAIError can be constructed and raised."""
        err = OpenAIError("fail")
        assert str(err) == "fail"
        with pytest.raises(OpenAIError):
            raise OpenAIError("fail2")


class TestOpenAIHandler:
    """Unit tests for OpenAIHandler core logic."""

    def setup_method(self) -> None:
        """Set up all dependencies as MagicMock/AsyncMock for each test."""
        self.token_tracker = MagicMock()
        self.secrets_manager = AsyncMock()
        self.channel_info_ops = MagicMock()
        self.channel_msg_ops = MagicMock()
        self.channel_ops = MagicMock()

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.ApiExecutor", autospec=True)
    @patch("packages.ai.core.openai_handler.AZURE_OPENAI_ENDPOINT", "https://foo")
    async def test_initialize_success(self, mock_api_executor: MagicMock) -> None:
        """Test successful async initialization of OpenAIHandler."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        self.secrets_manager.get_azure_openai_lb_api_key = AsyncMock(return_value="key")
        handler.setup = AsyncMock()
        # Should instantiate ApiExecutor and return self
        result = await handler.initialize()
        assert result is handler
        assert handler._lb_api_key == "key"
        handler.setup.assert_awaited_once()
        assert handler._api_executor is not None

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.AZURE_OPENAI_ENDPOINT", "https://foo")
    async def test_initialize_missing_key(self) -> None:
        """Test initialize raises if API key is missing."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        self.secrets_manager.get_azure_openai_lb_api_key = AsyncMock(return_value=None)
        handler.setup = AsyncMock()
        with pytest.raises(ValueError, match="Failed to retrieve Azure OpenAI LB API key"):
            await handler.initialize()

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.AZURE_OPENAI_ENDPOINT", "https://foo")
    async def test_initialize_missing_endpoint(self) -> None:
        """Test initialize raises if endpoint is None after setup."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        self.secrets_manager.get_azure_openai_lb_api_key = AsyncMock(return_value="key")
        handler.setup = AsyncMock()
        handler._endpoint = None
        with pytest.raises(ValueError, match="Azure OpenAI endpoint is None after setup"):
            await handler.initialize()

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.MessagePreparer", autospec=True)
    async def test_get_or_prepare_messages_provided(self, mock_msg_preparer: MagicMock) -> None:
        """Test _get_or_prepare_messages returns provided messages directly."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        provided = [{"role": "user", "content": "hi"}]
        result, channel_info = await handler._get_or_prepare_messages(
            messages=provided,
            combined_command=None,
            user_id=None,
            incoming_channel=None,
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            normalized_prefs_for_ai=None,
        )
        assert result == provided
        assert channel_info is None

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.MessagePreparer", autospec=True)
    async def test_get_or_prepare_messages_prepared_no_prefs(
        self, mock_msg_preparer_class: MagicMock
    ) -> None:
        """Test _get_or_prepare_messages prepares messages via MessagePreparer without prefs."""
        mock_preparer_instance = mock_msg_preparer_class.return_value
        mock_preparer_instance.prepare_messages = AsyncMock(
            return_value=(
                [{"role": "user", "content": "ok_no_prefs"}],
                {"chan": "no_prefs_c"},
            )
        )
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        handler._message_preparer = mock_preparer_instance

        result, channel_info = await handler._get_or_prepare_messages(
            messages=None,
            combined_command="/ketchup query",
            user_id="U1_no_prefs",
            incoming_channel="C1_no_prefs",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            normalized_prefs_for_ai=None,
        )
        assert result == [{"role": "user", "content": "ok_no_prefs"}]
        assert channel_info == {"chan": "no_prefs_c"}
        mock_preparer_instance.prepare_messages.assert_called_once_with(
            combined_command="/ketchup query",
            user_id="U1_no_prefs",
            incoming_channel="C1_no_prefs",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            oldest_ts="0",
            normalized_user_preferences=None,
        )

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.MessagePreparer", autospec=True)
    async def test_get_or_prepare_messages_prepared_with_prefs(
        self, mock_msg_preparer_class: MagicMock
    ) -> None:
        """Test _get_or_prepare_messages prepares messages and passes prefs."""
        mock_preparer_instance = mock_msg_preparer_class.return_value
        mock_preparer_instance.prepare_messages = AsyncMock(
            return_value=(
                [{"role": "user", "content": "ok_with_prefs"}],
                {"chan": "with_prefs_c"},
            )
        )
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        handler._message_preparer = mock_preparer_instance

        test_prefs = {"detail": "high"}
        result, channel_info = await handler._get_or_prepare_messages(
            messages=None,
            combined_command="/ketchup status",
            user_id="U2_with_prefs",
            incoming_channel="C2_with_prefs",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            normalized_prefs_for_ai=test_prefs,
        )
        assert result == [{"role": "user", "content": "ok_with_prefs"}]
        assert channel_info == {"chan": "with_prefs_c"}
        mock_preparer_instance.prepare_messages.assert_called_once_with(
            combined_command="/ketchup status",
            user_id="U2_with_prefs",
            incoming_channel="C2_with_prefs",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            oldest_ts="0",
            normalized_user_preferences=test_prefs,
        )

    @pytest.mark.asyncio
    @patch("packages.ai.core.openai_handler.MessagePreparer", autospec=True)
    async def test_get_or_prepare_messages_error(self, mock_msg_preparer: MagicMock) -> None:
        """Test _get_or_prepare_messages handles error messages from preparer."""
        mock_preparer = mock_msg_preparer.return_value
        mock_preparer.prepare_messages = AsyncMock(
            return_value=(
                [
                    {"role": "user", "content": "Error: bad input"},
                    {"role": "user", "content": "Error: more details"},
                ],
                {"chan": 2},
            )
        )
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        handler._message_preparer = mock_preparer
        result, channel_info = await handler._get_or_prepare_messages(
            messages=None,
            combined_command="/ketchup query",
            user_id="U1",
            incoming_channel="C1",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
        )
        assert result[0]["role"] == "user"
        assert "Error: bad input" in result[0]["content"]
        assert result[1]["role"] == "user"
        assert "Error: more details" in result[1]["content"]
        assert channel_info == {"chan": 2}

    @pytest.mark.asyncio
    async def test_get_or_prepare_messages_missing_params(self) -> None:
        """Test _get_or_prepare_messages raises on missing required params when preparing."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        with pytest.raises(ValueError, match="Missing required parameters"):
            await handler._get_or_prepare_messages(
                messages=None,
                combined_command=None,
                user_id=None,
                incoming_channel=None,
                passed_channel_id=None,
                channel_name=None,
                query_text=None,
            )

    @pytest.mark.asyncio
    @patch.object(OpenAIHandler, "_get_or_prepare_messages", new_callable=AsyncMock)
    async def test_call_openai_endpoint_no_prefs(self, mock_get_msgs: AsyncMock) -> None:
        """Test call_openai_endpoint orchestrates correctly when no prefs are provided."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        # Mock message prep and API executor
        mock_get_msgs.return_value = (
            [{"role": "user", "content": "hi_no_prefs"}],
            {"c_info": "channel_no_prefs"},
        )
        handler._api_executor = MagicMock()
        handler._api_executor.execute_request = AsyncMock(
            return_value={"choices": ["api_resp_no_prefs"]}
        )
        handler._token_manager = MagicMock()
        handler._token_manager.enforce_token_limit = AsyncMock(
            return_value=[{"role": "user", "content": "hi_no_prefs_limited"}]
        )
        handler._api_executor.build_openai_payload = MagicMock(
            return_value={"payload": "data_no_prefs"}
        )

        result = await handler.call_openai_endpoint(
            combined_command="/ketchup query",
            user_id="U_call_no_prefs",
            incoming_channel="C_call_no_prefs",
            normalized_prefs_for_ai=None,
        )
        assert result == {"choices": ["api_resp_no_prefs"]}
        mock_get_msgs.assert_called_once_with(
            messages=None,
            combined_command="/ketchup query",
            user_id="U_call_no_prefs",
            incoming_channel="C_call_no_prefs",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            oldest_ts="0",
            normalized_prefs_for_ai=None,
        )
        handler._token_manager.enforce_token_limit.assert_called_once_with(
            messages=[{"role": "user", "content": "hi_no_prefs"}],
            user_id="U_call_no_prefs",
            channel_context_id="C_call_no_prefs",
        )
        handler._api_executor.build_openai_payload.assert_called_once_with(
            messages=[{"role": "user", "content": "hi_no_prefs_limited"}],
            combined_command="/ketchup query",
            normalized_prefs=None,
        )
        handler._api_executor.execute_request.assert_awaited_once_with(
            payload={"payload": "data_no_prefs"},
            channel_info={"c_info": "channel_no_prefs"},
            user_id="U_call_no_prefs",
            incoming_channel="C_call_no_prefs",
        )

    @pytest.mark.asyncio
    @patch.object(OpenAIHandler, "_get_or_prepare_messages", new_callable=AsyncMock)
    async def test_call_openai_endpoint_with_prefs(self, mock_get_msgs: AsyncMock) -> None:
        """Test call_openai_endpoint passes normalized_prefs_for_ai to _get_or_prepare_messages."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        mock_get_msgs.return_value = (
            [{"role": "user", "content": "hi_with_prefs"}],
            {"c_info": "channel_with_prefs"},
        )
        handler._api_executor = MagicMock()
        handler._api_executor.execute_request = AsyncMock(
            return_value={"choices": ["api_resp_with_prefs"]}
        )
        handler._token_manager = MagicMock()
        handler._token_manager.enforce_token_limit = AsyncMock(
            return_value=[{"role": "user", "content": "hi_with_prefs_limited"}]
        )
        handler._api_executor.build_openai_payload = MagicMock(
            return_value={"payload": "data_with_prefs"}
        )

        test_prefs = {"detail": "high"}
        result = await handler.call_openai_endpoint(
            combined_command="/ketchup status",
            user_id="U_call_with_prefs",
            incoming_channel="C_call_with_prefs",
            normalized_prefs_for_ai=test_prefs,
        )
        assert result == {"choices": ["api_resp_with_prefs"]}
        mock_get_msgs.assert_called_once_with(
            messages=None,
            combined_command="/ketchup status",
            user_id="U_call_with_prefs",
            incoming_channel="C_call_with_prefs",
            passed_channel_id=None,
            channel_name=None,
            query_text=None,
            oldest_ts="0",
            normalized_prefs_for_ai=test_prefs,
        )
        handler._token_manager.enforce_token_limit.assert_called_once_with(
            messages=[{"role": "user", "content": "hi_with_prefs"}],
            user_id="U_call_with_prefs",
            channel_context_id="C_call_with_prefs",
        )
        handler._api_executor.build_openai_payload.assert_called_once_with(
            messages=[{"role": "user", "content": "hi_with_prefs_limited"}],
            combined_command="/ketchup status",
            normalized_prefs=test_prefs,
        )
        handler._api_executor.execute_request.assert_awaited_once_with(
            payload={"payload": "data_with_prefs"},
            channel_info={"c_info": "channel_with_prefs"},
            user_id="U_call_with_prefs",
            incoming_channel="C_call_with_prefs",
        )

    def test_get_usage_summary_and_calculate_token_usage(self) -> None:
        """Test get_usage_summary and calculate_token_usage delegate to token_tracker."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        handler._token_tracker.get_usage_summary.return_value = {"foo": 1}
        assert handler.get_usage_summary() == {"foo": 1}

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        """Test cleanup resets _api_executor and logs cleanup."""
        handler = OpenAIHandler(
            token_tracker=self.token_tracker,
            secrets_manager=self.secrets_manager,
            channel_info_ops=self.channel_info_ops,
            channel_msg_ops=self.channel_msg_ops,
            channel_ops=self.channel_ops,
        )
        handler._api_executor = MagicMock()
        # Patch logger to check log message
        with patch("packages.ai.core.openai_handler.logger") as mock_logger:
            await handler.cleanup()
            assert handler._api_executor is None
            mock_logger.info.assert_any_call(
                "Cleaning up OpenAIHandler resources (closing session)"
            )

    def test_call_openai_endpoint_success(self):
        """Test successful call to OpenAI endpoint."""
