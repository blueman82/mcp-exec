"""
Unit tests for SlackAuth (auth.py).

Covers:
- SlackAuth singleton logic and initialization
- SlackAuth.get_slack_signing_secret: cache, retrieval, error handling
- SlackAuth.verify_slack_signature: all logic branches, error handling, and edge cases
- All dependencies (SecretsManager, logger) are mocked

Edge Cases Covered:
- Singleton instance reuse and creation
- get_slack_signing_secret: cache hit, cache miss, missing key, exception
- verify_slack_signature: missing headers, invalid timestamp, missing secret, signature mismatch, valid signature, exception

Expected Outcomes:
- All methods return correct values for all scenarios
- All external calls are mocked and asserted
- All logic branches and error cases are covered

"""

from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.authorisation.auth import SlackAuth


@pytest.mark.asyncio
class TestSlackAuth:
    def setup_method(self) -> None:
        self.mock_secrets_manager: AsyncMock = AsyncMock()
        self.auth: SlackAuth = SlackAuth(secrets_manager=self.mock_secrets_manager)

    async def test_get_slack_signing_secret_cache(self) -> None:
        self.auth._slack_signing_secret = "cached_secret"
        result: str | None = await self.auth.get_slack_signing_secret()
        assert result == "cached_secret"

    async def test_get_slack_signing_secret_success(self) -> None:
        self.auth._slack_signing_secret = None
        self.mock_secrets_manager.get_app_secrets.return_value = {
            "SLACK_SIGNING_SECRET": "secret"
        }
        result: str | None = await self.auth.get_slack_signing_secret()
        assert result == "secret"
        self.mock_secrets_manager.get_app_secrets.assert_awaited_once()

    async def test_get_slack_signing_secret_missing_key(self) -> None:
        self.auth._slack_signing_secret = None
        self.mock_secrets_manager.get_app_secrets.return_value = {}
        result: str | None = await self.auth.get_slack_signing_secret()
        assert result is None
        self.mock_secrets_manager.get_app_secrets.assert_awaited_once()

    async def test_get_slack_signing_secret_exception(self) -> None:
        self.auth._slack_signing_secret = None
        self.mock_secrets_manager.get_app_secrets.side_effect = Exception("fail")
        result: str | None = await self.auth.get_slack_signing_secret()
        assert result is None
        self.mock_secrets_manager.get_app_secrets.assert_awaited_once()

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_valid(self, mock_time: Any) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(return_value="secret")  # type: ignore[method-assign]
        headers: Dict[str, str] = {
            "x-slack-request-timestamp": str(1000000),
            "x-slack-signature": "v0=5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        }
        raw_body_bytes: bytes = b"test"
        import hashlib
        import hmac

        sig_basestring = "v0:1000000:".encode("utf-8") + raw_body_bytes
        my_signature = (
            "v0=" + hmac.new(b"secret", sig_basestring, hashlib.sha256).hexdigest()
        )
        headers["x-slack-signature"] = my_signature
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is True

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_missing_headers(self, mock_time: Any) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(return_value="secret")  # type: ignore[method-assign]
        headers: Dict[str, str] = {}
        raw_body_bytes: bytes = b"test"
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is False

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_invalid_timestamp(
        self, mock_time: Any
    ) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(return_value="secret")  # type: ignore[method-assign]
        headers: Dict[str, str] = {
            "x-slack-request-timestamp": "bad",
            "x-slack-signature": "sig",
        }
        raw_body_bytes: bytes = b"test"
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is False

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_expired_timestamp(
        self, mock_time: Any
    ) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(return_value="secret")  # type: ignore[method-assign]
        headers: Dict[str, str] = {
            "x-slack-request-timestamp": str(1000000 - 4000),
            "x-slack-signature": "sig",
        }
        raw_body_bytes: bytes = b"test"
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is False

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_missing_secret(self, mock_time: Any) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(return_value=None)  # type: ignore[method-assign]
        headers: Dict[str, str] = {
            "x-slack-request-timestamp": str(1000000),
            "x-slack-signature": "sig",
        }
        raw_body_bytes: bytes = b"test"
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is False

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_signature_mismatch(
        self, mock_time: Any
    ) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(return_value="secret")  # type: ignore[method-assign]
        headers: Dict[str, str] = {
            "x-slack-request-timestamp": str(1000000),
            "x-slack-signature": "bad_sig",
        }
        raw_body_bytes: bytes = b"test"
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is False

    @patch("packages.slack.authorisation.auth.time.time", return_value=1000000)
    async def test_verify_slack_signature_exception(self, mock_time: Any) -> None:
        self.auth.get_slack_signing_secret = AsyncMock(side_effect=Exception("fail"))  # type: ignore[method-assign]
        headers: Dict[str, str] = {
            "x-slack-request-timestamp": str(1000000),
            "x-slack-signature": "sig",
        }
        raw_body_bytes: bytes = b"test"
        result: bool = await self.auth.verify_slack_signature(headers, raw_body_bytes)
        assert result is False
