"""
Unit tests for packages/slack/channel_events/incoming_events.py

Covers:
- process_request (module-level)
- EventProcessor.process_request
- All error and edge cases, including DI container, dependency setup, warm-up, signature verification, retry, routing, and assertion errors.

All dependencies and routing handlers are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.incoming_events as incoming_events


@pytest.mark.asyncio
class TestProcessRequestModuleLevel:
    async def test_uninitialized_container_returns_500(self):
        container = MagicMock()
        container.is_initialized.return_value = False
        event = {}
        result = await incoming_events.process_request(event, container)
        assert result["statusCode"] == 500
        assert "not initialized" in result["body"]

    @patch(
        "packages.slack.channel_events.incoming_events.setup_dependencies",
        new_callable=AsyncMock,
    )
    async def test_dependency_setup_valueerror_returns_500(self, mock_setup):
        container = MagicMock()
        container.is_initialized.return_value = True
        mock_setup.side_effect = ValueError("bad config")
        event = {}
        result = await incoming_events.process_request(event, container)
        assert result["statusCode"] == 500
        assert "bad config" in result["body"]

    @patch(
        "packages.slack.channel_events.incoming_events.setup_dependencies",
        new_callable=AsyncMock,
    )
    async def test_dependency_setup_exception_returns_500(self, mock_setup):
        container = MagicMock()
        container.is_initialized.return_value = True
        mock_setup.side_effect = Exception("fail")
        event = {}
        result = await incoming_events.process_request(event, container)
        assert result["statusCode"] == 500
        assert "unexpected error" in result["body"].lower()

    @patch(
        "packages.slack.channel_events.incoming_events.setup_dependencies",
        new_callable=AsyncMock,
    )
    @patch.object(incoming_events, "EventProcessor")
    async def test_success_calls_eventprocessor(self, mock_ep, mock_setup):
        container = MagicMock()
        container.is_initialized.return_value = True
        deps = {
            "slack_auth": MagicMock(),
            "command_router": MagicMock(),
            "event_handler": MagicMock(),
        }
        mock_setup.return_value = deps
        processor = MagicMock()
        processor.process_request = AsyncMock(
            return_value={"statusCode": 200, "body": "ok"}
        )
        mock_ep.return_value = processor
        event = {"foo": "bar"}
        result = await incoming_events.process_request(event, container)
        assert result == {"statusCode": 200, "body": "ok"}
        processor.process_request.assert_awaited_once_with(event)


@pytest.mark.asyncio
class TestEventProcessor:
    def setup_method(self):
        # Minimal required dependencies
        self.clients = {
            "slack_posting": MagicMock(),
            "feedback_reactions_handler": MagicMock(),
            "shortcut_handler": MagicMock(),
            "feedback_report_handler": MagicMock(),
            "trust_endorsement_handler": MagicMock(),
            "flag_review_handler": MagicMock(),
        }
        self.slack_auth = MagicMock()
        self.command_router = MagicMock()
        self.event_handler = MagicMock()
        self.processor = incoming_events.EventProcessor(
            clients=self.clients,
            slack_auth=self.slack_auth,
            command_router=self.command_router,
            event_handler=self.event_handler,
        )

    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_warmup_ping(self, mock_verify):
        event = {"source": "aws.events"}
        result = await self.processor.process_request(event)
        assert result["statusCode"] == 200
        assert "warm-up" in result["body"].lower()
        mock_verify.assert_not_called()

    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_signature_verification_failure(self, mock_verify):
        event = {}
        mock_verify.return_value = (None, None, None)
        result = await self.processor.process_request(event)
        assert result["statusCode"] == 401
        assert "unauthorized" in result["body"].lower()

    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_parsed_bodies_none(self, mock_verify):
        event = {}
        mock_verify.return_value = (b"body", None, None)
        result = await self.processor.process_request(event)
        assert result["statusCode"] == 500
        assert "internal processing error" in result["body"].lower()

    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_retry_header(self, mock_verify):
        event = {"headers": {"X-Slack-Retry-Num": "1"}}
        mock_verify.return_value = (b"body", {"foo": "bar"}, {"foo": "bar"})
        result = await self.processor.process_request(event)
        assert result["statusCode"] == 200
        assert "retry ignored" in result["body"].lower()

    @patch(
        "packages.slack.channel_events.incoming_events.handle_slack_command",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_handle_slack_command(self, mock_verify, mock_handle):
        event = {}
        mock_verify.return_value = (b"body", {"foo": "bar"}, {"command": ["/test"]})
        mock_handle.return_value = {"statusCode": 201, "body": "command"}
        result = await self.processor.process_request(event)
        mock_handle.assert_awaited_once()
        assert result["statusCode"] == 201
        assert "command" in result["body"]

    @patch(
        "packages.slack.channel_events.incoming_events.handle_interactive_component",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_handle_interactive_component(self, mock_verify, mock_handle):
        event = {}
        # Reset mocks to ensure clean state
        mock_verify.reset_mock()
        mock_handle.reset_mock()
        mock_verify.return_value = (b"body", {"foo": "bar"}, {"payload": ["data"]})
        mock_handle.return_value = {"statusCode": 202, "body": "interactive"}
        # All handlers present
        result = await self.processor.process_request(event)
        mock_handle.assert_awaited_once()
        assert result["statusCode"] == 202
        assert "interactive" in result["body"]

    @patch(
        "packages.slack.channel_events.incoming_events.handle_events_api",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_handle_events_api(self, mock_verify, mock_handle):
        event = {}
        mock_verify.return_value = (b"body", {"event": {"type": "foo"}}, {"foo": "bar"})
        mock_handle.return_value = {"statusCode": 203, "body": "event"}
        result = await self.processor.process_request(event)
        mock_handle.assert_awaited_once()
        assert result["statusCode"] == 203
        assert "event" in result["body"]

    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_unknown_request_type(self, mock_verify):
        event = {}
        mock_verify.return_value = (b"body", {"foo": "bar"}, {"foo": "bar"})
        result = await self.processor.process_request(event)
        assert result["statusCode"] == 400
        assert "unknown request type" in result["body"].lower()

    @patch(
        "packages.slack.channel_events.incoming_events.verify_and_parse_body",
        new_callable=AsyncMock,
    )
    async def test_assertion_errors_for_missing_handlers(self, mock_verify):
        # Remove handlers one by one and check assertion
        event = {}
        mock_verify.return_value = (b"body", {"foo": "bar"}, {"payload": ["data"]})
        # Remove slack_posting_handler
        processor = incoming_events.EventProcessor(
            clients={
                "feedback_reactions_handler": MagicMock(),
                "shortcut_handler": MagicMock(),
                "feedback_report_handler": MagicMock(),
            },
            slack_auth=self.slack_auth,
            command_router=self.command_router,
            event_handler=self.event_handler,
        )
        with pytest.raises(RuntimeError, match="Slack posting handler is None"):
            await processor.process_request(event)
        # Remove feedback_reactions_handler
        processor = incoming_events.EventProcessor(
            clients={
                "slack_posting": MagicMock(),
                "shortcut_handler": MagicMock(),
                "feedback_report_handler": MagicMock(),
            },
            slack_auth=self.slack_auth,
            command_router=self.command_router,
            event_handler=self.event_handler,
        )
        with pytest.raises(RuntimeError, match="Feedback reactions handler is None"):
            await processor.process_request(event)
        # Remove shortcut_handler
        processor = incoming_events.EventProcessor(
            clients={
                "slack_posting": MagicMock(),
                "feedback_reactions_handler": MagicMock(),
                "feedback_report_handler": MagicMock(),
            },
            slack_auth=self.slack_auth,
            command_router=self.command_router,
            event_handler=self.event_handler,
        )
        with pytest.raises(RuntimeError, match="Shortcut handler is None"):
            await processor.process_request(event)
        # Remove feedback_report_handler
        processor = incoming_events.EventProcessor(
            clients={
                "slack_posting": MagicMock(),
                "feedback_reactions_handler": MagicMock(),
                "shortcut_handler": MagicMock(),
            },
            slack_auth=self.slack_auth,
            command_router=self.command_router,
            event_handler=self.event_handler,
        )
        with pytest.raises(RuntimeError, match="Feedback report handler is None"):
            await processor.process_request(event)
