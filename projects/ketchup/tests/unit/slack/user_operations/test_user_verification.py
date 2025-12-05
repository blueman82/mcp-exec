"""
Unit tests for UserVerifier (user_verification.py).

Covers:
- UserVerifier.validate_user_id: all logic branches, error handling, and edge cases
- Logger is mocked

Edge Cases Covered:
- User is authorized in database
- User is in seed list but not in database
- User is not authorized
- Exception during validation

Expected Outcomes:
- validate_user_id returns True for authorized users
- validate_user_id returns False for unauthorized users
- validate_user_id returns False and logs error on exception
- Users in secrets but not in DB are added to DB
- All logger calls are asserted

"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.authorisation.user_verification import UserVerifier


class TestUserVerifier:
    def setup_method(self) -> None:
        self.authorised_user_ids: List[str] = ["U12345", "U67890"]
        self.mock_user_store = MagicMock()
        self.mock_user_ops = MagicMock()
        self.mock_secrets_manager = MagicMock()
        self.mock_secrets_manager.get_authorised_slack_user_ids = AsyncMock(
            return_value=self.authorised_user_ids
        )
        self.verifier = UserVerifier(
            user_store=self.mock_user_store,
            user_ops=self.mock_user_ops,
            secrets_manager=self.mock_secrets_manager,
        )

    @pytest.mark.asyncio
    async def test_validate_user_authorized(self) -> None:
        """Test user authorized in secrets and database."""
        with patch("packages.slack.authorisation.user_verification.logger") as mock_logger:
            # User exists in DB and is authorized
            self.mock_user_store.get_user = AsyncMock(
                return_value={"user_id": "U12345", "authorized": True}
            )

            result: bool = await self.verifier.validate_user_id("U12345")
            assert result is True
            mock_logger.info.assert_any_call("Validating authorization for user ID: U12345")
            mock_logger.info.assert_any_call("User U12345 found in authorized seed list")
            mock_logger.info.assert_any_call("User U12345 is authorized (from secrets)")

    @pytest.mark.asyncio
    async def test_validate_user_unauthorized(self) -> None:
        """Test user not authorized."""
        with patch("packages.slack.authorisation.user_verification.logger") as mock_logger:
            # User not in seed list
            self.mock_user_store.get_user = AsyncMock(return_value=None)

            result: bool = await self.verifier.validate_user_id("U99999")
            assert result is False
            mock_logger.info.assert_any_call("Validating authorization for user ID: U99999")
            mock_logger.info.assert_any_call(
                "User U99999 is not in authorized seed list from secrets"
            )

    @pytest.mark.asyncio
    async def test_validate_user_exception(self) -> None:
        """Test exception during validation."""
        with patch("packages.slack.authorisation.user_verification.logger") as mock_logger:
            # Secrets manager throws exception
            self.mock_secrets_manager.get_authorised_slack_user_ids = AsyncMock(
                side_effect=Exception("Secrets error")
            )

            result: bool = await self.verifier.validate_user_id("U12345")
            assert result is False
            mock_logger.info.assert_any_call("Validating authorization for user ID: U12345")
            mock_logger.error.assert_called_once()
            # Check that error was logged with the user ID
            error_call_args = str(mock_logger.error.call_args)
            assert "U12345" in error_call_args
            assert "Secrets error" in error_call_args

    @pytest.mark.asyncio
    async def test_validate_user_in_secrets_not_in_db(self) -> None:
        """Test user in secrets but not in database - should add to DB."""
        with patch("packages.slack.authorisation.user_verification.logger") as mock_logger:
            # User not in DB
            self.mock_user_store.get_user = AsyncMock(return_value=None)
            self.mock_user_store.store_user = AsyncMock()
            self.mock_user_ops._fetch_user_info_internal = AsyncMock(
                return_value={"profile": {"real_name": "Test User"}, "id": "U12345"}
            )

            result: bool = await self.verifier.validate_user_id("U12345")
            assert result is True

            # Verify user was stored in DB
            self.mock_user_store.store_user.assert_called_once_with(
                {"user_id": "U12345", "real_name": "Test User", "authorized": True}
            )
            mock_logger.info.assert_any_call("User U12345 not in DB, fetching from Slack")
            mock_logger.info.assert_any_call("User U12345 is authorized (from secrets)")
