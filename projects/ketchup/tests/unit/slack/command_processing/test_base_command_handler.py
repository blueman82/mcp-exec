"""
test_base_command_handler.py

Unit tests for base_command_handler.py (BaseCommandHandler).

Covers:
- BaseCommandHandler: create_success_response, create_error_response, create_validation_error_response
- All logic branches and edge cases
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- create_success_response: returns correct dict
- create_error_response: default and custom status codes
- create_validation_error_response: returns correct dict

Expected Outcomes:
- All response methods return correct standardized dicts

"""

from packages.slack.channel_events.models import ProcessingResult
from packages.slack.command_processing.base_command_handler import BaseCommandHandler


class TestBaseCommandHandler:
    def setup_method(self) -> None:
        self.handler = BaseCommandHandler()

    def test_create_success_response(self) -> None:
        """Test create_success_response returns correct dict."""
        resp = self.handler.create_success_response("ok")
        assert resp == ProcessingResult(status_code=200, body="ok", feedback_sent=True)

    def test_create_error_response_default(self) -> None:
        """Test create_error_response returns correct dict with default status code."""
        resp = self.handler.create_error_response("fail")
        assert resp == ProcessingResult(status_code=500, body="fail", feedback_sent=True)

    def test_create_error_response_custom_status(self) -> None:
        """Test create_error_response returns correct dict with custom status code."""
        resp = self.handler.create_error_response("fail", status_code=404)
        assert resp == ProcessingResult(status_code=404, body="fail", feedback_sent=True)

    def test_create_validation_error_response(self) -> None:
        """Test create_validation_error_response returns correct dict."""
        resp = self.handler.create_validation_error_response("bad")
        assert resp == ProcessingResult(status_code=400, body="bad", feedback_sent=True)
