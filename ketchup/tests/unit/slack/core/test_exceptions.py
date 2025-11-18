"""
test_exceptions.py

Unit tests for custom exceptions in packages.core.exceptions.

Covers:
- ClientError: Initialization, attributes, and string representation
- InvalidBlocksForResponseUrlError: Subclassing and string representation

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import pytest

from packages.core.exceptions import ClientError, InvalidBlocksForResponseUrlError

pytestmark = pytest.mark.unit


@pytest.mark.unit
def test_client_error_attributes() -> None:
    """Test ClientError initialization and attributes.

    Verifies that message, status_code, and response_data are set and __str__ returns the message.
    """
    err = ClientError("msg", status_code=400, response_data={"foo": "bar"})
    assert err.message == "msg"
    assert err.status_code == 400
    assert err.response_data == {"foo": "bar"}
    assert str(err) == "msg"


@pytest.mark.unit
def test_invalid_blocks_for_response_url_error() -> None:
    """Test InvalidBlocksForResponseUrlError is a subclass and string representation.

    Ensures that the error is a ClientError and __str__ returns the message.
    """
    err = InvalidBlocksForResponseUrlError("bad blocks", status_code=422)
    assert isinstance(err, ClientError)
    assert str(err) == "bad blocks"
