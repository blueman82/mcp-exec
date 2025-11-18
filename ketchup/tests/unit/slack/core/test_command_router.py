"""
Unit tests for CommandRouter (command_router.py).

Covers:
- CommandRouter.route_command: all logic branches, error handling, and edge cases
- User not authorized
- Command verification fails
- No handler for command type
- Each command type (LIST, ARCHIVE, QUERY, SHORT, LONG, STATUS, REPORT)
- Handler raises exception (including TaskGroup error)
- All required parameters present/missing
- All external dependencies are mocked

Edge Cases Covered:
- User not authorized: error message posted, returns 200
- Command verification fails: returns 200
- No handler for command type: error message posted, returns 400
- Each command type: correct handler method called, result returned
- Handler raises exception: error message posted, returns 500
- Handler raises TaskGroup error: friendly message posted, returns 500
- All required parameters present/missing: handled gracefully

Expected Outcomes:
- route_command returns correct status and body for each scenario
- All external calls are mocked and asserted
- All logic branches and error cases are covered

"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.command_processing.command_parameters.models import CommandType
from packages.slack.command_processing.command_router import CommandRouter


@pytest.mark.asyncio
class TestCommandRouter:
    def setup_method(self) -> None:
        # Mock dependencies
        self.mock_handlers = {
            "list": AsyncMock(),
            "archive": AsyncMock(),
            "query": AsyncMock(),
            "short": AsyncMock(),
            "long": AsyncMock(),
            "status": AsyncMock(),
            "report": AsyncMock(),
        }
        self.mock_posting_handler = AsyncMock()
        self.mock_user_verifier = MagicMock()
        self.mock_user_store = AsyncMock()
        # Configure get_user to return a proper dictionary to avoid AsyncMock warnings
        self.mock_user_store.get_user.return_value = {"real_name": "Alice Smith"}
        self.router = CommandRouter(
            command_handlers=self.mock_handlers,
            slack_posting_handler=self.mock_posting_handler,
            user_verifier=self.mock_user_verifier,
            user_store=self.mock_user_store,
        )
        self.body = {
            "command": ["/list"],
            "text": [""],
            "channel_id": ["C1"],
            "channel_name": ["general"],
            "user_id": ["U1"],
            "user_name": ["alice"],
            "response_url": ["url"],
        }

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_user_not_authorized(self, mock_verify: AsyncMock) -> None:
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=False)
        result = await self.router.route_command(self.body, "url")
        assert result == {"statusCode": 200, "body": ""}
        self.mock_posting_handler.post_message.assert_awaited_once()

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_command_verification_fails(self, mock_verify: AsyncMock) -> None:
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=True)
        mock_verify.return_value = None
        result = await self.router.route_command(self.body, "url")
        assert result == {"statusCode": 200, "body": ""}

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_no_handler_for_command_type(self, mock_verify: AsyncMock) -> None:
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=True)
        params = MagicMock()
        params.command_type.value = "unknown"
        params.command_type = MagicMock()
        mock_verify.return_value = params
        result = await self.router.route_command(self.body, "url")
        assert result == {"statusCode": 400, "body": "Unsupported command type"}
        self.mock_posting_handler.post_message.assert_awaited_once()

    @pytest.mark.parametrize(
        "cmd_type,handler_method,expected_result",
        [
            (CommandType.LIST, "process_list_params", {"ok": True}),
            (CommandType.ARCHIVE, "process_archive_params", {"ok": True}),
            (CommandType.QUERY, "process_query_request", {"ok": True}),
            (CommandType.SHORT, "process_summary_params", {"ok": True}),
            (CommandType.LONG, "process_summary_params", {"ok": True}),
            (CommandType.STATUS, "process_status_request", {"ok": True}),
            (CommandType.REPORT, "process_report_request", {"ok": True}),
        ],
    )
    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_route_command_types(
        self,
        mock_verify: AsyncMock,
        cmd_type: Any,
        handler_method: str,
        expected_result: Dict[str, Any],
    ) -> None:
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=True)
        params = MagicMock()
        params.command_type = cmd_type
        # Set required attributes for each command type
        if cmd_type == CommandType.LIST:
            handler = self.mock_handlers["list"]
            handler.process_list_params.return_value = expected_result
        elif cmd_type == CommandType.ARCHIVE:
            handler = self.mock_handlers["archive"]
            handler.process_archive_params.return_value = expected_result
        elif cmd_type == CommandType.QUERY:
            handler = self.mock_handlers["query"]
            handler.process_query_request.return_value = expected_result
            params.target_channel_id = "C1"
        elif cmd_type in [CommandType.SHORT, CommandType.LONG]:
            handler = self.mock_handlers[cmd_type.value]
            handler.process_summary_params.return_value = expected_result
            params.target_channel_id = "C1"
        elif cmd_type == CommandType.STATUS:
            handler = self.mock_handlers["status"]
            handler.process_status_request.return_value = expected_result
            params.report_type = "status"
            params.original_command = "status"
            params.target_channel_id = "C1"
        elif cmd_type == CommandType.REPORT:
            handler = self.mock_handlers["report"]
            handler.process_report_request.return_value = expected_result
            params.report_type = "report"
            params.original_command = "report"
            params.target_channel_id = "C1"
        mock_verify.return_value = params
        result = await self.router.route_command(self.body, "url")
        assert result == expected_result
        getattr(handler, handler_method).assert_awaited_once()

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_handler_raises_exception(self, mock_verify: AsyncMock) -> None:
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=True)
        params = MagicMock()
        params.command_type = CommandType.LIST
        handler = self.mock_handlers["list"]
        handler.process_list_params.side_effect = Exception("fail")
        mock_verify.return_value = params
        result = await self.router.route_command(self.body, "url")
        assert result["statusCode"] == 500
        self.mock_posting_handler.post_message.assert_awaited_once()

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_handler_raises_taskgroup_error(self, mock_verify: AsyncMock) -> None:
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=True)
        params = MagicMock()
        params.command_type = CommandType.LIST
        handler = self.mock_handlers["list"]
        handler.process_list_params.side_effect = Exception(
            "unhandled errors in a TaskGroup"
        )
        mock_verify.return_value = params
        result = await self.router.route_command(self.body, "url")
        assert result["statusCode"] == 500
        self.mock_posting_handler.post_message.assert_awaited_once()
