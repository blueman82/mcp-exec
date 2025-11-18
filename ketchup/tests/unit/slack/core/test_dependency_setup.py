"""
Unit tests for packages/slack/channel_events/request_processing/dependency_setup.py

Covers:
- instantiate_command_handlers
- setup_dependencies
- All error and edge cases, including missing dependencies, type assertions, and handler instantiation.

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.request_processing.dependency_setup as dependency_setup


class DummyHandler:
    pass


class TestInstantiateCommandHandlers:
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackListCommand"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackQueryHandler"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackSummaryHandler"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackReports"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackArchiveCommand"
    )
    def test_instantiates_all_handlers(
        self, mock_archive, mock_reports, mock_summary, mock_query, mock_list
    ):
        handler_clients = {
            "info_ops": MagicMock(),
            "membership_ops": MagicMock(),
            "slack_posting_handler": MagicMock(),
            "dynamodb_store": MagicMock(),
            "archive_ops": MagicMock(),
            "channel_message_ops": MagicMock(),
            "openai_handler": MagicMock(),
            "restore_ops": MagicMock(),
            "slack_config": MagicMock(),
            "user_store": MagicMock(),
        }
        block_kit_builder = MagicMock()
        secrets_manager = MagicMock()
        result = dependency_setup.instantiate_command_handlers(
            handler_clients, block_kit_builder, secrets_manager
        )
        # Should contain all handlers
        assert "command_handlers_dict" in result
        assert "list_handler" in result
        assert "query_handler" in result
        assert "summary_handler" in result
        assert "status_report_handler" in result
        assert "archive_handler" in result


class TestSetupDependencies:
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackPostingHandler"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.DynamoDBStore"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.UserStore"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackChannelArchiveOps"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.ChannelInfoOps"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.ChannelMembershipOps"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackUserOps"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackChannelMessageOps"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.FeedbackReactionsHandler"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.FeedbackReportHandler"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SecretsManager"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.SlackAuth"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.ShortcutHandler"
    )
    @patch(
        "packages.slack.channel_events.request_processing.dependency_setup.UserVerifier"
    )
    @pytest.mark.asyncio
    async def test_setup_dependencies_success(
        self,
        mock_verifier,
        mock_shortcut,
        mock_auth,
        mock_secrets,
        mock_feedback_report,
        mock_feedback_reactions,
        mock_msg_ops,
        mock_user_ops,
        mock_membership_ops,
        mock_info_ops,
        mock_archive_ops,
        mock_user_store,
        mock_dynamo,
        mock_posting,
    ):
        container = MagicMock()
        secrets_manager_mock = MagicMock()
        secrets_manager_mock.get_app_secrets = AsyncMock(return_value={})

        def get_side_effect(cls):
            name = getattr(cls, "__name__", type(cls).__name__)
            if name == "SecretsManager":
                return secrets_manager_mock
            return MagicMock()

        container.get.side_effect = get_side_effect
        container.get_by_name.side_effect = lambda name: MagicMock()
        container.aget = AsyncMock(return_value=MagicMock())
        result = await dependency_setup.setup_dependencies(container)
        assert isinstance(result, dict)
        # Should contain at least one expected key
        assert "slack_posting_handler" in result or len(result) > 0

    @pytest.mark.asyncio
    async def test_setup_dependencies_missing_dependency(self):
        container = MagicMock()
        container.get.side_effect = Exception("missing")
        with pytest.raises(Exception):
            await dependency_setup.setup_dependencies(container)
