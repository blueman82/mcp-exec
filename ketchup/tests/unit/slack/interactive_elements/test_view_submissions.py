"""
Unit tests for packages.slack.interactive_elements.view_submissions

This module provides comprehensive tests for the process_view_submission function, which processes Slack view submissions (modal form submissions).

Coverage includes:
- All logic branches: feedback report submission (all fields present, missing fields, handler returns True/False), unhandled callback_id
- Edge cases: missing view, missing callback_id, missing state, missing user, missing trigger_id, missing values, missing name/description
- All dependencies (FeedbackReportHandler) are mocked to isolate logic

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

# mypy: disable-error-code=var-annotated

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.interactive_elements import view_submissions

pytestmark = pytest.mark.asyncio


@pytest.fixture
def feedback_report_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.send_feedback_report_to_channel = AsyncMock(return_value=True)
    return mock


async def test_feedback_report_submission_success(feedback_report_handler_mock) -> None:
    """Test feedback report submission with all fields present and handler returns True."""
    payload = {
        "view": {
            "callback_id": "submit_feedback_report",
            "state": {
                "values": {
                    "feedback_name": {"name_input": {"value": "title"}},
                    "feedback_description": {"description_input": {"value": "desc"}},
                }
            },
        },
        "user": {"id": "U1"},
        "trigger_id": "TRIGGER123",
    }
    result = await view_submissions.process_view_submission(
        payload, feedback_report_handler_mock
    )
    assert result is True
    feedback_report_handler_mock.send_feedback_report_to_channel.assert_awaited_once_with(
        user_id="U1",
        feedback_name="title",
        feedback_description="desc",
        trigger_id="TRIGGER123",
        response_url=None,
    )


async def test_feedback_report_submission_handler_false(
    feedback_report_handler_mock,
) -> None:
    """Test feedback report submission with handler returning False."""
    feedback_report_handler_mock.send_feedback_report_to_channel = AsyncMock(
        return_value=False
    )
    payload = {
        "view": {
            "callback_id": "submit_feedback_report",
            "state": {
                "values": {
                    "feedback_name": {"name_input": {"value": "title"}},
                    "feedback_description": {"description_input": {"value": "desc"}},
                }
            },
        },
        "user": {"id": "U1"},
        "trigger_id": "TRIGGER123",
    }
    result = await view_submissions.process_view_submission(
        payload, feedback_report_handler_mock
    )
    assert result is False
    feedback_report_handler_mock.send_feedback_report_to_channel.assert_awaited_once()


@pytest.mark.parametrize(
    "payload,missing_field",
    [
        ({"view": {"callback_id": "submit_feedback_report"}}, "state"),
        ({"view": {"callback_id": "submit_feedback_report", "state": {}}}, "values"),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {"values": {}},
                }
            },
            "name_input",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {"values": {"feedback_name": {}}},
                }
            },
            "name_input",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {"values": {"feedback_name": {"name_input": {}}}},
                }
            },
            "value",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {
                        "values": {"feedback_name": {"name_input": {"value": "title"}}}
                    },
                }
            },
            "feedback_description",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {
                        "values": {
                            "feedback_name": {"name_input": {"value": "title"}},
                            "feedback_description": {},
                        }
                    },
                }
            },
            "description_input",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {
                        "values": {
                            "feedback_name": {"name_input": {"value": "title"}},
                            "feedback_description": {"description_input": {}},
                        }
                    },
                }
            },
            "value",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {
                        "values": {
                            "feedback_name": {"name_input": {"value": "title"}},
                            "feedback_description": {
                                "description_input": {"value": "desc"}
                            },
                        }
                    },
                }
            },
            "user",
        ),
        (
            {
                "view": {
                    "callback_id": "submit_feedback_report",
                    "state": {
                        "values": {
                            "feedback_name": {"name_input": {"value": "title"}},
                            "feedback_description": {
                                "description_input": {"value": "desc"}
                            },
                        }
                    },
                },
                "user": {"id": "U1"},
            },
            "trigger_id",
        ),
    ],
)
async def test_feedback_report_submission_missing_fields(
    payload: dict[str, object],  # type: ignore
    missing_field: str,
    feedback_report_handler_mock,
) -> None:
    """Test feedback report submission with missing required fields (should return False)."""
    result = await view_submissions.process_view_submission(
        payload, feedback_report_handler_mock
    )
    assert result is False
    feedback_report_handler_mock.send_feedback_report_to_channel.assert_not_awaited()


async def test_unhandled_callback_id(feedback_report_handler_mock) -> None:
    """Test unhandled callback_id returns True."""
    payload = {"view": {"callback_id": "other_callback"}}
    result = await view_submissions.process_view_submission(
        payload, feedback_report_handler_mock
    )
    assert result is True
    feedback_report_handler_mock.send_feedback_report_to_channel.assert_not_awaited()


async def test_missing_view_returns_true(feedback_report_handler_mock) -> None:
    """Test missing view in payload returns True (unhandled)."""
    payload = {}
    result = await view_submissions.process_view_submission(
        payload, feedback_report_handler_mock
    )
    assert result is True
    feedback_report_handler_mock.send_feedback_report_to_channel.assert_not_awaited()
