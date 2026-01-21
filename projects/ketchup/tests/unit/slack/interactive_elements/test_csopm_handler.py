"""
Test CSOPM interactive element handler.

Unit tests for the CSOPMHandler class, verifying:
1. Block action routing for all CSOPM button types
2. Modal view submission handling for follow-up creation
3. Integration with CSOPMButtonActionHandler service
4. MCP tool coordination for JIRA operations
5. Error handling across all operations

Action IDs Covered:
- csopm_acknowledge: Acknowledge ticket
- csopm_create_followup: Open follow-up creation modal
- csopm_stop_reminders: Stop ketchup reminders
- csopm_enable_reminders: Re-enable ketchup reminders
- csopm_snooze: Snooze closure reminder
- csopm_close_ticket: Close ticket in JIRA
- csopm_view_jira: View ticket in JIRA (no-op)

Modal Callback IDs Covered:
- csopm_create_followup_modal: Create follow-up ticket submission
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.interactive_elements.csopm_handler import (
    CSOPM_ACTION_PREFIX,
    CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID,
    CSOPMHandler,
    is_csopm_action,
    is_csopm_modal,
)


class MockCSOPMButtonActionHandler:
    """Mock CSOPMButtonActionHandler for testing."""

    def __init__(self) -> None:
        self.handle_button_action = AsyncMock(return_value=True)
        self._state_tracker = None


class MockAsyncMCPClient:
    """Mock AsyncMCPClient for testing."""

    def __init__(self) -> None:
        self.get_issue = AsyncMock()
        self.list_projects = AsyncMock()
        self._call_mcp_tool = AsyncMock()


class MockSecretsManager:
    """Mock SecretsManager for testing."""

    def __init__(self) -> None:
        self.get_slack_api_token_async = AsyncMock(return_value="xoxb-test-token")


class MockSlackPostingHandler:
    """Mock SlackPostingHandler for testing."""

    def __init__(self) -> None:
        self.post_message = AsyncMock()
        self.open_modal = AsyncMock()
        self._secrets_manager = MockSecretsManager()


class MockUserPATOperations:
    """Mock UserPATOperations for testing."""

    def __init__(self) -> None:
        self.store_pat = AsyncMock()
        self.get_pat = AsyncMock(return_value="test-pat-token")
        self.delete_pat = AsyncMock()
        self.has_valid_pat = AsyncMock(return_value=True)
        self.get_pat_expiry_minutes = AsyncMock(return_value=45)


@pytest.fixture
def mock_user_pat_ops():
    """Create mock UserPATOperations."""
    return MockUserPATOperations()


@pytest.fixture
def mock_button_handler():
    """Create mock CSOPMButtonActionHandler."""
    return MockCSOPMButtonActionHandler()


@pytest.fixture
def mock_mcp_client():
    """Create mock AsyncMCPClient."""
    return MockAsyncMCPClient()


@pytest.fixture
def mock_posting_handler():
    """Create mock SlackPostingHandler."""
    return MockSlackPostingHandler()


@pytest.fixture
def handler(mock_button_handler, mock_mcp_client, mock_posting_handler, mock_user_pat_ops):
    """Create CSOPMHandler instance with mocks."""
    return CSOPMHandler(
        button_handler=mock_button_handler,
        mcp_client=mock_mcp_client,
        posting_handler=mock_posting_handler,
        user_pat_ops=mock_user_pat_ops,
    )


@pytest.fixture
def sample_block_action_payload():
    """Create a sample block_actions payload."""
    return {
        "type": "block_actions",
        "user": {"id": "U12345678", "name": "testuser"},
        "channel": {"id": "C87654321"},
        "trigger_id": "12345.67890.abcdef",
        "message": {
            "ts": "1234567890.123456",
            "blocks": [{"type": "section", "text": {"text": "Original message"}}],
        },
        "actions": [
            {
                "action_id": "csopm_acknowledge",
                "value": "CSOPM-1234",
                "type": "button",
            }
        ],
    }


@pytest.fixture
def sample_view_submission_payload():
    """Create a sample view_submission payload."""
    return {
        "type": "view_submission",
        "user": {"id": "U12345678", "name": "testuser"},
        "trigger_id": "12345.67890.abcdef",
        "view": {
            "callback_id": "csopm_create_followup_modal",
            "private_metadata": "CSOPM-1234",
            "state": {
                "values": {
                    "project_block": {
                        "project_input": {
                            "type": "static_select",
                            "selected_option": {"value": "CSOPM"},
                        }
                    },
                    "issue_type_block": {
                        "issue_type_input": {
                            "type": "static_select",
                            "selected_option": {"value": "Task"},
                        }
                    },
                    "summary_block": {"summary_input": {"value": "Follow-up task for CSOPM-1234"}},
                    "description_block": {
                        "description_input": {"value": "Follow-up description here"}
                    },
                }
            },
        },
    }


class TestCSOPMHandlerHelperFunctions:
    """Tests for helper functions."""

    def test_is_csopm_action_with_csopm_prefix(self):
        """Test is_csopm_action with CSOPM action IDs."""
        assert is_csopm_action("csopm_acknowledge") is True
        assert is_csopm_action("csopm_create_followup") is True
        assert is_csopm_action("csopm_stop_reminders") is True
        assert is_csopm_action("csopm_enable_reminders") is True
        assert is_csopm_action("csopm_snooze") is True
        assert is_csopm_action("csopm_close_ticket") is True
        assert is_csopm_action("csopm_view_jira") is True

    def test_is_csopm_action_with_non_csopm_prefix(self):
        """Test is_csopm_action with non-CSOPM action IDs."""
        assert is_csopm_action("feedback_positive") is False
        assert is_csopm_action("trust_status_update") is False
        assert is_csopm_action("request_access") is False
        assert is_csopm_action("") is False

    def test_is_csopm_modal_with_csopm_modal(self):
        """Test is_csopm_modal with CSOPM modal callback IDs."""
        assert is_csopm_modal("csopm_create_followup_modal") is True

    def test_is_csopm_modal_with_non_csopm_modal(self):
        """Test is_csopm_modal with non-CSOPM modal callback IDs."""
        assert is_csopm_modal("reject_reason_modal") is False
        assert is_csopm_modal("flag_review_modal") is False
        assert is_csopm_modal("edit_channel_metadata") is False
        assert is_csopm_modal("") is False


class TestCSOPMHandlerBlockActions:
    """Tests for block action handling."""

    @pytest.mark.asyncio
    async def test_handle_block_action_acknowledge(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling csopm_acknowledge action."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_acknowledge"

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        mock_button_handler.handle_button_action.assert_awaited_once_with(
            action_id="csopm_acknowledge",
            user_id="U12345678",
            ticket_key="CSOPM-1234",
            payload=sample_block_action_payload,
        )

    @pytest.mark.asyncio
    async def test_handle_block_action_stop_reminders(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling csopm_stop_reminders action."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_stop_reminders"

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        mock_button_handler.handle_button_action.assert_awaited_once()
        call_args = mock_button_handler.handle_button_action.call_args
        assert call_args.kwargs["action_id"] == "csopm_stop_reminders"

    @pytest.mark.asyncio
    async def test_handle_block_action_enable_reminders(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling csopm_enable_reminders action."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_enable_reminders"

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        mock_button_handler.handle_button_action.assert_awaited_once()
        call_args = mock_button_handler.handle_button_action.call_args
        assert call_args.kwargs["action_id"] == "csopm_enable_reminders"

    @pytest.mark.asyncio
    async def test_handle_block_action_snooze(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling csopm_snooze action."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_snooze"

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        mock_button_handler.handle_button_action.assert_awaited_once()
        call_args = mock_button_handler.handle_button_action.call_args
        assert call_args.kwargs["action_id"] == "csopm_snooze"

    @pytest.mark.asyncio
    async def test_handle_block_action_close_ticket(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling csopm_close_ticket action."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_close_ticket"

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        mock_button_handler.handle_button_action.assert_awaited_once()
        call_args = mock_button_handler.handle_button_action.call_args
        assert call_args.kwargs["action_id"] == "csopm_close_ticket"

    @pytest.mark.asyncio
    async def test_handle_block_action_view_jira(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling csopm_view_jira action (no-op, just logs)."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_view_jira"

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        # View JIRA is still routed to notifier which returns True immediately
        mock_button_handler.handle_button_action.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_block_action_no_actions(self, handler):
        """Test handling payload with no actions."""
        payload = {
            "type": "block_actions",
            "user": {"id": "U12345678"},
            "actions": [],
        }

        result = await handler.handle_block_action(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_block_action_non_csopm_action(self, handler, mock_button_handler):
        """Test handling non-CSOPM action returns False."""
        payload = {
            "type": "block_actions",
            "user": {"id": "U12345678"},
            "actions": [
                {
                    "action_id": "feedback_positive",
                    "value": "some_value",
                }
            ],
        }

        result = await handler.handle_block_action(payload)

        assert result is False
        mock_button_handler.handle_button_action.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_block_action_notifier_failure(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling when notifier returns failure."""
        mock_button_handler.handle_button_action.return_value = False

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_block_action_exception(
        self, handler, mock_button_handler, sample_block_action_payload
    ):
        """Test handling exception during processing."""
        mock_button_handler.handle_button_action.side_effect = Exception("API Error")

        result = await handler.handle_block_action(sample_block_action_payload)

        assert result is False


class TestCSOPMHandlerCreateFollowupAction:
    """Tests for create followup button action (opens modal)."""

    @pytest.mark.asyncio
    async def test_handle_create_followup_opens_modal(
        self,
        handler,
        mock_button_handler,
        mock_mcp_client,
        mock_posting_handler,
        sample_block_action_payload,
    ):
        """Test that create_followup action opens modal after notifier succeeds."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_create_followup"

        # Mock MCP responses for modal data
        mock_mcp_client.get_issue.return_value = {
            "key": "CSOPM-1234",
            "fields": {
                "summary": "Test Issue",
                "status": {"name": "Open"},
                "assignee": {"name": "testuser"},
            },
        }
        mock_mcp_client.list_projects.return_value = [
            {"key": "CSOPM", "name": "CSO PM", "issueTypes": [{"id": "1", "name": "Task"}]},
        ]

        # Mock aiohttp response for views.open
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
            )
        )
        mock_session = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_session_instance), __aexit__=AsyncMock()
            )
        )

        with patch("aiohttp.ClientSession", mock_session):
            result = await handler.handle_block_action(sample_block_action_payload)

        assert result is True
        mock_button_handler.handle_button_action.assert_awaited_once()
        # Modal should be opened after notifier succeeds
        mock_mcp_client.get_issue.assert_awaited_once()
        mock_mcp_client.list_projects.assert_awaited_once()
        # Verify views.open was called via aiohttp (no longer using posting_handler.open_modal)
        mock_session_instance.post.assert_called_once()
        call_args = mock_session_instance.post.call_args
        assert "views.open" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_create_followup_no_trigger_id(
        self, handler, mock_button_handler, mock_posting_handler, sample_block_action_payload
    ):
        """Test create_followup without trigger_id doesn't open modal."""
        sample_block_action_payload["actions"][0]["action_id"] = "csopm_create_followup"
        sample_block_action_payload["trigger_id"] = None

        result = await handler.handle_block_action(sample_block_action_payload)

        # Notifier still succeeds, modal just doesn't open
        assert result is True
        mock_posting_handler.open_modal.assert_not_awaited()


class TestCSOPMHandlerViewSubmission:
    """Tests for modal view submission handling."""

    @pytest.mark.asyncio
    async def test_handle_view_submission_create_followup(
        self,
        handler,
        mock_mcp_client,
        mock_posting_handler,
        sample_view_submission_payload,
    ):
        """Test handling create followup modal submission."""
        # Mock successful JIRA issue creation and linking
        mock_mcp_client._call_mcp_tool.side_effect = [
            {"success": True, "key": "CSOPM-5001"},  # create_jira_issue
            {"success": True},  # link_issues
        ]

        result = await handler.handle_view_submission(sample_view_submission_payload)

        # Modal closes immediately while JIRA work happens in background
        assert result == {"response_action": "clear"}

        # Allow background task to complete
        import asyncio
        await asyncio.sleep(0.01)

        # Verify create_jira_issue was called
        create_call = mock_mcp_client._call_mcp_tool.call_args_list[0]
        assert create_call[0][0] == "create_jira_issue"
        # The create call uses fields.project.key and fields.issuetype.name
        assert create_call[0][1]["fields"]["project"]["key"] == "CSOPM"
        assert create_call[0][1]["fields"]["issuetype"]["name"] == "Task"
        assert create_call[0][1]["fields"]["summary"] == "Follow-up task for CSOPM-1234"

        # Verify link_issues was called
        link_call = mock_mcp_client._call_mcp_tool.call_args_list[1]
        assert link_call[0][0] == "link_issues"
        assert link_call[0][1]["inwardIssue"] == "CSOPM-1234"
        assert link_call[0][1]["outwardIssue"] == "CSOPM-5001"
        assert link_call[0][1]["linkType"] == "Relates"

        # Verify confirmation blocks were sent (not plain message)
        mock_posting_handler.post_message.assert_awaited()
        call_kwargs = mock_posting_handler.post_message.call_args.kwargs
        # Now uses blocks instead of message
        assert "blocks" in call_kwargs
        blocks_str = str(call_kwargs["blocks"])
        assert "CSOPM-5001" in blocks_str
        assert "CSOPM-1234" in blocks_str

    @pytest.mark.asyncio
    async def test_handle_view_submission_create_followup_with_text_input(
        self, handler, mock_mcp_client, mock_posting_handler
    ):
        """Test handling modal with plain text input fields (fallback mode)."""
        payload = {
            "type": "view_submission",
            "user": {"id": "U12345678"},
            "view": {
                "callback_id": "csopm_create_followup_modal",
                "private_metadata": "CSOPM-1234",
                "state": {
                    "values": {
                        "project_block": {
                            "project_input": {
                                "type": "plain_text_input",
                                "value": "CSOPM",
                            }
                        },
                        "issue_type_block": {
                            "issue_type_input": {
                                "type": "plain_text_input",
                                "value": "Bug",
                            }
                        },
                        "summary_block": {"summary_input": {"value": "Test summary"}},
                        "description_block": {"description_input": {"value": "Test description"}},
                    }
                },
            },
        }

        mock_mcp_client._call_mcp_tool.side_effect = [
            {"success": True, "key": "CSOPM-5002"},
            {"success": True},
        ]

        result = await handler.handle_view_submission(payload)

        # Modal closes immediately while JIRA work happens in background
        assert result == {"response_action": "clear"}

        # Allow background task to complete
        import asyncio
        await asyncio.sleep(0.01)

        create_call = mock_mcp_client._call_mcp_tool.call_args_list[0]
        # The create call uses fields.project.key and fields.issuetype.name
        assert create_call[0][1]["fields"]["project"]["key"] == "CSOPM"
        assert create_call[0][1]["fields"]["issuetype"]["name"] == "Bug"

    @pytest.mark.asyncio
    async def test_handle_view_submission_create_failure(
        self, handler, mock_mcp_client, mock_posting_handler
    ):
        """Test handling when JIRA issue creation fails."""
        payload = {
            "type": "view_submission",
            "user": {"id": "U12345678"},
            "view": {
                "callback_id": "csopm_create_followup_modal",
                "private_metadata": "CSOPM-1234",
                "state": {
                    "values": {
                        "project_block": {"project_input": {"value": "CSOPM"}},
                        "issue_type_block": {"issue_type_input": {"value": "Task"}},
                        "summary_block": {"summary_input": {"value": "Test"}},
                        "description_block": {"description_input": {"value": ""}},
                    }
                },
            },
        }

        mock_mcp_client._call_mcp_tool.return_value = {
            "success": False,
            "message": "Permission denied",
        }

        result = await handler.handle_view_submission(payload)

        assert result is False
        # Error message should be sent to user
        mock_posting_handler.post_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_view_submission_no_summary(self, handler, mock_mcp_client):
        """Test handling when summary is empty."""
        payload = {
            "type": "view_submission",
            "user": {"id": "U12345678"},
            "view": {
                "callback_id": "csopm_create_followup_modal",
                "private_metadata": "CSOPM-1234",
                "state": {
                    "values": {
                        "project_block": {"project_input": {"value": "CSOPM"}},
                        "issue_type_block": {"issue_type_input": {"value": "Task"}},
                        "summary_block": {"summary_input": {"value": ""}},
                        "description_block": {"description_input": {"value": ""}},
                    }
                },
            },
        }

        result = await handler.handle_view_submission(payload)

        assert result is False
        mock_mcp_client._call_mcp_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_view_submission_no_parent_ticket(self, handler, mock_mcp_client):
        """Test handling when private_metadata (parent ticket) is missing."""
        payload = {
            "type": "view_submission",
            "user": {"id": "U12345678"},
            "view": {
                "callback_id": "csopm_create_followup_modal",
                "private_metadata": "",
                "state": {
                    "values": {
                        "project_block": {"project_input": {"value": "CSOPM"}},
                        "issue_type_block": {"issue_type_input": {"value": "Task"}},
                        "summary_block": {"summary_input": {"value": "Test"}},
                        "description_block": {"description_input": {"value": ""}},
                    }
                },
            },
        }

        result = await handler.handle_view_submission(payload)

        assert result is False
        mock_mcp_client._call_mcp_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_view_submission_link_failure_still_succeeds(
        self, handler, mock_mcp_client, mock_posting_handler
    ):
        """Test that follow-up creation succeeds even if linking fails."""
        payload = {
            "type": "view_submission",
            "user": {"id": "U12345678"},
            "view": {
                "callback_id": "csopm_create_followup_modal",
                "private_metadata": "CSOPM-1234",
                "state": {
                    "values": {
                        "project_block": {"project_input": {"value": "CSOPM"}},
                        "issue_type_block": {"issue_type_input": {"value": "Task"}},
                        "summary_block": {"summary_input": {"value": "Test"}},
                        "description_block": {"description_input": {"value": ""}},
                    }
                },
            },
        }

        mock_mcp_client._call_mcp_tool.side_effect = [
            {"success": True, "key": "CSOPM-5003"},  # create succeeds
            {"success": False, "message": "Link error"},  # link fails
        ]

        result = await handler.handle_view_submission(payload)

        # Should still succeed because the ticket was created
        assert result is True
        mock_posting_handler.post_message.assert_awaited()
        call_kwargs = mock_posting_handler.post_message.call_args.kwargs
        # Now uses blocks instead of message
        assert "blocks" in call_kwargs
        blocks_str = str(call_kwargs["blocks"])
        assert "CSOPM-5003" in blocks_str

    @pytest.mark.asyncio
    async def test_handle_view_submission_unknown_modal(self, handler):
        """Test handling unknown modal callback_id."""
        payload = {
            "type": "view_submission",
            "user": {"id": "U12345678"},
            "view": {
                "callback_id": "unknown_modal",
                "state": {"values": {}},
            },
        }

        result = await handler.handle_view_submission(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_view_submission_exception(
        self, handler, mock_mcp_client, sample_view_submission_payload
    ):
        """Test handling exception during modal submission."""
        mock_mcp_client._call_mcp_tool.side_effect = Exception("Network error")

        result = await handler.handle_view_submission(sample_view_submission_payload)

        assert result is False


class TestCSOPMHandlerIntegration:
    """Integration tests for CSOPM handler with payload processor patterns."""

    @pytest.mark.asyncio
    async def test_handler_can_be_instantiated(self):
        """Test that CSOPMHandler can be instantiated with mock dependencies."""
        handler = CSOPMHandler(
            button_handler=MockCSOPMButtonActionHandler(),
            mcp_client=MockAsyncMCPClient(),
            posting_handler=MockSlackPostingHandler(),
        )

        assert handler is not None
        assert handler._button_handler is not None
        assert handler._mcp_client is not None
        assert handler._posting_handler is not None

    def test_action_prefix_constant(self):
        """Test that action prefix constant is correct."""
        assert CSOPM_ACTION_PREFIX == "csopm_"

    def test_modal_callback_constant(self):
        """Test that modal callback ID constant is correct."""
        assert CSOPM_CREATE_FOLLOWUP_MODAL_CALLBACK_ID == "csopm_create_followup_modal"
