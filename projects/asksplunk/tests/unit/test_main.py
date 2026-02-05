"""Unit tests for application entry point.

Tests main() function, shutdown() function, signal handlers,
and graceful cleanup with mocked dependencies.
"""

import asyncio
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Mock external dependencies before importing main module to avoid import errors
sys.modules["slack_bolt"] = MagicMock()
sys.modules["slack_bolt.async_app"] = MagicMock()
sys.modules["slack_bolt.adapter"] = MagicMock()
sys.modules["slack_bolt.adapter.socket_mode"] = MagicMock()
sys.modules["slack_bolt.adapter.socket_mode.async_handler"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["openai"] = MagicMock()

from asksplunk.main import create_signal_handler, main, shutdown


class TestMain:
    """Test main application entry point and lifecycle."""

    @pytest.fixture
    def mock_slack_tokens(self):
        """Mock Slack tokens returned from SecretsManager.

        NOTE: These are FAKE TEST TOKENS, not real credentials.
        """
        return {"bot_token": "xoxb-fake-test-token", "app_token": "xapp-fake-test-token"}

    @pytest.fixture
    def mock_openai_config(self):
        """Mock Azure OpenAI config returned from SecretsManager."""
        return {
            "endpoint": "https://test.openai.azure.com/",
            "api_key": "test-api-key-123",
            "api_version": "2024-02-15-preview",
            "chat_deployment": "gpt-5",
        }

    @pytest.mark.asyncio
    async def test_main_fetches_secrets_from_secrets_manager(
        self, mock_slack_tokens, mock_openai_config
    ):
        """main() should fetch Slack tokens from AWS Secrets Manager."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
        ):

            # Mock SecretsManager as async context manager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock SlackClient
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main
            await main()

            # Verify SecretsManager was used as context manager
            MockSecretsManager.assert_called_once()
            mock_secrets_instance.__aenter__.assert_called_once()
            mock_manager.get_slack_tokens.assert_called_once()
            mock_manager.get_azure_openai_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_creates_slack_client_with_tokens(
        self, mock_slack_tokens, mock_openai_config
    ):
        """main() should create SlackClient with retrieved tokens."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
        ):

            # Mock SecretsManager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock Agent
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent

            # Mock SlackClient
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main
            await main()

            # Verify SlackClient was created with correct tokens and agent
            MockSlackClient.assert_called_once_with(
                bot_token=mock_slack_tokens["bot_token"],
                app_token=mock_slack_tokens["app_token"],
                agent=mock_agent,
            )

    @pytest.mark.asyncio
    async def test_main_registers_signal_handlers(self, mock_slack_tokens, mock_openai_config):
        """main() should register SIGTERM and SIGINT handlers."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
        ):

            # Mock SecretsManager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock SlackClient
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main
            await main()

            # Verify signal handlers were registered
            assert mock_signal.call_count == 2
            signal_calls = [call[0] for call in mock_signal.call_args_list]
            assert (signal.SIGTERM,) in [call[:1] for call in signal_calls]
            assert (signal.SIGINT,) in [call[:1] for call in signal_calls]

    @pytest.mark.asyncio
    async def test_main_starts_slack_client(self, mock_slack_tokens, mock_openai_config):
        """main() should call client.start() to begin Socket Mode connection."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
        ):

            # Mock SecretsManager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock SlackClient
            mock_client = AsyncMock()
            mock_client.start = AsyncMock()
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main
            await main()

            # Verify client.start() was called
            mock_client.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_handles_keyboard_interrupt(self, mock_slack_tokens, mock_openai_config):
        """main() should handle KeyboardInterrupt and shutdown gracefully."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
        ):

            # Mock SecretsManager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock SlackClient to raise KeyboardInterrupt
            mock_client = AsyncMock()
            mock_client.start = AsyncMock(side_effect=KeyboardInterrupt())
            mock_client.shutdown = AsyncMock()
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main - should not raise KeyboardInterrupt
            await main()

            # Verify shutdown was called
            mock_client.shutdown.assert_called_once()
            mock_loop.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_handles_startup_errors_and_exits(
        self, mock_slack_tokens, mock_openai_config
    ):
        """main() should handle startup errors, cleanup, and call sys.exit(1)."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
            patch("asksplunk.main.sys.exit") as mock_exit,
        ):

            # Mock SecretsManager to raise error
            MockSecretsManager.side_effect = Exception("AWS connection error")

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main
            await main()

            # Verify sys.exit(1) was called
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_main_cleans_up_client_on_startup_error(
        self, mock_slack_tokens, mock_openai_config
    ):
        """main() should call client.shutdown() even if startup fails after client creation."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
            patch("asksplunk.main.sys.exit") as mock_exit,
        ):

            # Mock SecretsManager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock SlackClient - client.start() raises error
            mock_client = AsyncMock()
            mock_client.start = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.shutdown = AsyncMock()
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main
            await main()

            # Verify client.shutdown() was called for cleanup
            mock_client.shutdown.assert_called_once()
            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_main_handles_cleanup_error_gracefully(
        self, mock_slack_tokens, mock_openai_config
    ):
        """main() should handle errors during cleanup without crashing."""
        with (
            patch("asksplunk.main.SecretsManager") as MockSecretsManager,
            patch("asksplunk.main.SlackClient") as MockSlackClient,
            patch("asksplunk.main.AsyncAzureOpenAI") as MockAzureOpenAI,
            patch("asksplunk.main.chromadb.HttpClient") as MockChromaClient,
            patch("asksplunk.main.DocumentRetriever") as MockRetriever,
            patch("asksplunk.main.SessionManager") as MockSessionManager,
            patch("asksplunk.main.Agent") as MockAgent,
            patch("asksplunk.main.signal.signal") as mock_signal,
            patch("asksplunk.main.asyncio.get_event_loop") as mock_get_loop,
            patch("asksplunk.main.sys.exit") as mock_exit,
            patch("asksplunk.main.logger") as mock_logger,
        ):

            # Mock SecretsManager
            mock_manager = AsyncMock()
            mock_manager.get_slack_tokens = AsyncMock(return_value=mock_slack_tokens)
            mock_manager.get_azure_openai_config = AsyncMock(return_value=mock_openai_config)
            mock_secrets_instance = AsyncMock()
            mock_secrets_instance.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_secrets_instance.__aexit__ = AsyncMock(return_value=None)
            MockSecretsManager.return_value = mock_secrets_instance

            # Mock SessionManager as async context manager
            mock_session_manager = AsyncMock()
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_manager)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            MockSessionManager.return_value = mock_session_instance

            # Mock SlackClient - both start() and shutdown() raise errors
            mock_client = AsyncMock()
            mock_client.start = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.shutdown = AsyncMock(side_effect=Exception("Shutdown failed"))
            MockSlackClient.return_value = mock_client

            # Mock event loop
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Run main - should not crash
            await main()

            # Verify both startup error and cleanup error were logged
            assert mock_logger.error.call_count >= 2
            error_messages = [call[0][0] for call in mock_logger.error.call_args_list]
            assert "application_startup_error" in error_messages
            assert "cleanup_error" in error_messages

            # Verify sys.exit(1) was still called
            mock_exit.assert_called_once_with(1)


class TestShutdown:
    """Test graceful shutdown function."""

    @pytest.mark.asyncio
    async def test_shutdown_calls_client_shutdown(self):
        """shutdown() should call client.shutdown()."""
        mock_client = AsyncMock()
        mock_client.shutdown = AsyncMock()
        mock_loop = Mock()

        await shutdown(mock_client, mock_loop)

        mock_client.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_event_loop(self):
        """shutdown() should call loop.stop()."""
        mock_client = AsyncMock()
        mock_client.shutdown = AsyncMock()
        mock_loop = Mock()

        await shutdown(mock_client, mock_loop)

        mock_loop.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_logs_progress(self):
        """shutdown() should log shutdown progress."""
        with patch("asksplunk.main.logger") as mock_logger:
            mock_client = AsyncMock()
            mock_client.shutdown = AsyncMock()
            mock_loop = Mock()

            await shutdown(mock_client, mock_loop)

            # Verify logging calls
            assert mock_logger.info.call_count >= 3
            log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
            assert "shutdown_initiated" in log_messages
            assert "slack_client_shutdown_complete" in log_messages
            assert "event_loop_stopped" in log_messages

    @pytest.mark.asyncio
    async def test_shutdown_handles_client_shutdown_error(self):
        """shutdown() should handle errors during client.shutdown() and still stop loop."""
        with patch("asksplunk.main.logger") as mock_logger:
            mock_client = AsyncMock()
            mock_client.shutdown = AsyncMock(side_effect=Exception("Shutdown error"))
            mock_loop = Mock()

            # Should not raise exception
            await shutdown(mock_client, mock_loop)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert error_call[0][0] == "shutdown_error"
            assert "error" in error_call[1]
            assert "Shutdown error" in error_call[1]["error"]
            assert error_call[1]["exc_info"] is True

            # Verify loop.stop() was still called
            mock_loop.stop.assert_called_once()


class TestCreateSignalHandler:
    """Test signal handler factory."""

    def test_create_signal_handler_returns_callable(self):
        """create_signal_handler() should return a callable function."""
        mock_client = AsyncMock()
        mock_loop = Mock()

        handler = create_signal_handler(mock_client, mock_loop)

        assert callable(handler)

    def test_signal_handler_logs_signal_received(self):
        """Signal handler should log the received signal."""
        with (
            patch("asksplunk.main.logger") as mock_logger,
            patch("asksplunk.main.asyncio.create_task") as mock_create_task,
        ):

            mock_client = AsyncMock()
            mock_loop = Mock()

            handler = create_signal_handler(mock_client, mock_loop)

            # Simulate SIGTERM signal
            handler(signal.SIGTERM, None)

            # Verify signal was logged
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args
            assert log_call[0][0] == "signal_received"
            assert log_call[1]["signal"] == "SIGTERM"

    def test_signal_handler_creates_shutdown_task(self):
        """Signal handler should create asyncio task for shutdown()."""
        with (
            patch("asksplunk.main.logger") as mock_logger,
            patch("asksplunk.main.asyncio.create_task") as mock_create_task,
        ):

            mock_client = AsyncMock()
            mock_loop = Mock()

            handler = create_signal_handler(mock_client, mock_loop)

            # Simulate SIGINT signal
            handler(signal.SIGINT, None)

            # Verify create_task was called
            mock_create_task.assert_called_once()
            # Verify the task is a coroutine (shutdown returns coroutine)
            task_arg = mock_create_task.call_args[0][0]
            assert asyncio.iscoroutine(task_arg)
            task_arg.close()  # Clean up unawaited coroutine to prevent RuntimeWarning

    def test_signal_handler_works_for_sigterm(self):
        """Signal handler should handle SIGTERM."""
        with (
            patch("asksplunk.main.logger") as mock_logger,
            patch("asksplunk.main.asyncio.create_task") as mock_create_task,
            patch("asksplunk.main.shutdown") as mock_shutdown,
        ):

            mock_client = AsyncMock()
            mock_loop = Mock()
            # Mock create_task to return a Task mock (not coroutine) to prevent "never awaited" warning
            mock_task = Mock(spec=["cancel"])
            mock_create_task.return_value = mock_task

            handler = create_signal_handler(mock_client, mock_loop)

            # Should not raise exception
            handler(signal.SIGTERM, None)

            mock_logger.info.assert_called_once()
            assert mock_logger.info.call_args[1]["signal"] == "SIGTERM"
            mock_create_task.assert_called_once()

    def test_signal_handler_works_for_sigint(self):
        """Signal handler should handle SIGINT."""
        with (
            patch("asksplunk.main.logger") as mock_logger,
            patch("asksplunk.main.asyncio.create_task") as mock_create_task,
            patch("asksplunk.main.shutdown") as mock_shutdown,
        ):

            mock_client = AsyncMock()
            mock_loop = Mock()
            # Mock create_task to return a Task mock (not coroutine) to prevent "never awaited" warning
            mock_task = Mock(spec=["cancel"])
            mock_create_task.return_value = mock_task

            handler = create_signal_handler(mock_client, mock_loop)

            # Should not raise exception
            handler(signal.SIGINT, None)

            mock_logger.info.assert_called_once()
            assert mock_logger.info.call_args[1]["signal"] == "SIGINT"
            mock_create_task.assert_called_once()
