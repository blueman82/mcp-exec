"""
Unit tests for packages/slack/channel_events/incoming_events.py

Covers:
- process_request (module-level)
- EventProcessor.process_request
- All error and edge cases, including DI container, dependency setup, routing, and assertion errors.

All dependencies and routing handlers are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.incoming_events as incoming_events
from packages.slack.channel_events.models import ProcessingResult, SlackRequest


@pytest.mark.asyncio
class TestProcessRequestModuleLevel:
    async def test_uninitialized_container_returns_500(self):
        container = MagicMock()
        container.is_initialized.return_value = False
        request = SlackRequest(
            raw_body=b"",
            body_str="",
            headers={},
            path="/slack/events",
            parsed_body={},
            parsed_body_multivalue={},
        )
        result = await incoming_events.process_request(request, container)
        assert result.status_code == 500
        assert "not initialized" in result.body

    @patch(
        "packages.slack.channel_events.incoming_events.setup_dependencies",
        new_callable=AsyncMock,
    )
    async def test_dependency_setup_valueerror_returns_500(self, mock_setup):
        container = MagicMock()
        container.is_initialized.return_value = True
        mock_setup.side_effect = ValueError("bad config")
        request = SlackRequest(
            raw_body=b"",
            body_str="",
            headers={},
            path="/slack/events",
            parsed_body={},
            parsed_body_multivalue={},
        )
        result = await incoming_events.process_request(request, container)
        assert result.status_code == 500
        assert "bad config" in result.body

    @patch(
        "packages.slack.channel_events.incoming_events.setup_dependencies",
        new_callable=AsyncMock,
    )
    async def test_dependency_setup_exception_returns_500(self, mock_setup):
        container = MagicMock()
        container.is_initialized.return_value = True
        mock_setup.side_effect = Exception("fail")
        request = SlackRequest(
            raw_body=b"",
            body_str="",
            headers={},
            path="/slack/events",
            parsed_body={},
            parsed_body_multivalue={},
        )
        result = await incoming_events.process_request(request, container)
        assert result.status_code == 500
        assert "unexpected error" in result.body.lower()

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
        processor.process_request = AsyncMock(return_value=ProcessingResult(status_code=200, body="ok"))
        mock_ep.return_value = processor
        request = SlackRequest(
            raw_body=b"foo=bar",
            body_str="foo=bar",
            headers={},
            path="/slack/events",
            parsed_body={"foo": "bar"},
            parsed_body_multivalue={"foo": ["bar"]},
        )
        result = await incoming_events.process_request(request, container)
        assert result == ProcessingResult(status_code=200, body="ok")
        processor.process_request.assert_awaited_once_with(request)


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

    async def test_retry_header(self):
        request = SlackRequest(
            raw_body=b"body",
            body_str="body",
            headers={"x-slack-retry-num": "1"},
            path="/slack/events",
            parsed_body={"foo": "bar"},
            parsed_body_multivalue={"foo": ["bar"]},
        )
        result = await self.processor.process_request(request)
        assert result.status_code == 200
        assert "retry ignored" in result.body.lower()

    @patch(
        "packages.slack.channel_events.incoming_events.handle_slack_command",
        new_callable=AsyncMock,
    )
    async def test_handle_slack_command(self, mock_handle):
        request = SlackRequest(
            raw_body=b"body",
            body_str="body",
            headers={},
            path="/slack/commands",
            parsed_body={"foo": "bar"},
            parsed_body_multivalue={"command": ["/test"]},
        )
        mock_handle.return_value = ProcessingResult(status_code=201, body="command")
        result = await self.processor.process_request(request)
        mock_handle.assert_awaited_once()
        assert result.status_code == 201
        assert "command" in result.body

    @patch(
        "packages.slack.channel_events.incoming_events.handle_interactive_component",
        new_callable=AsyncMock,
    )
    async def test_handle_interactive_component(self, mock_handle):
        request = SlackRequest(
            raw_body=b"body",
            body_str="body",
            headers={},
            path="/slack/interactions",
            parsed_body={"foo": "bar"},
            parsed_body_multivalue={"payload": ["data"]},
        )
        mock_handle.reset_mock()
        mock_handle.return_value = ProcessingResult(status_code=202, body="interactive")
        result = await self.processor.process_request(request)
        mock_handle.assert_awaited_once()
        assert result.status_code == 202
        assert "interactive" in result.body

    @patch(
        "packages.slack.channel_events.incoming_events.handle_events_api",
        new_callable=AsyncMock,
    )
    async def test_handle_events_api(self, mock_handle):
        request = SlackRequest(
            raw_body=b"body",
            body_str="body",
            headers={},
            path="/slack/events",
            parsed_body={"event": {"type": "foo"}},
            parsed_body_multivalue={"foo": ["bar"]},
        )
        mock_handle.return_value = ProcessingResult(status_code=203, body="event")
        result = await self.processor.process_request(request)
        mock_handle.assert_awaited_once()
        assert result.status_code == 203
        assert "event" in result.body

    async def test_unknown_request_type(self):
        request = SlackRequest(
            raw_body=b"body",
            body_str="body",
            headers={},
            path="/slack/events",
            parsed_body={"foo": "bar"},
            parsed_body_multivalue={"foo": ["bar"]},
        )
        result = await self.processor.process_request(request)
        assert result.status_code == 400
        assert "unknown request type" in result.body.lower()

    async def test_assertion_errors_for_missing_handlers(self):
        # Remove handlers one by one and check assertion
        request = SlackRequest(
            raw_body=b"body",
            body_str="body",
            headers={},
            path="/slack/interactions",
            parsed_body={"foo": "bar"},
            parsed_body_multivalue={"payload": ["data"]},
        )
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
            await processor.process_request(request)
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
            await processor.process_request(request)
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
            await processor.process_request(request)
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
            await processor.process_request(request)
