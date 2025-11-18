"""
Unit tests for packages/slack/channel_events/eligibility/creation_checker.py

Covers:
- is_new_channel_eligible
- All logic branches, including authorized/unauthorized creator, approved/unapproved channel name, and edge cases.

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, patch

import pytest

import packages.slack.channel_events.eligibility.creation_checker as creation_checker


@pytest.mark.asyncio
class TestIsNewChannelEligible:
    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_authorized_and_approved(self):
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Creator is authorized, channel name contains both 'cso' and approved keyword
        result = await creation_checker.is_new_channel_eligible(
            "cso-war-room", "U1", secrets_manager
        )
        assert result is True

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_authorized_but_unapproved_name(self):
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Creator is authorized, channel name does not contain approved keyword
        result = await creation_checker.is_new_channel_eligible(
            "random", "U1", secrets_manager
        )
        assert result is False

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_unauthorized_but_approved_name(self):
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Creator is not authorized, channel name contains both 'cso' and approved keyword
        result = await creation_checker.is_new_channel_eligible(
            "cso-war-room", "U2", secrets_manager
        )
        # Production logic only checks for approved channel name, not creator authorization
        assert result is True

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_unauthorized_and_unapproved(self):
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Creator is not authorized, channel name does not contain approved keyword
        result = await creation_checker.is_new_channel_eligible(
            "random", "U2", secrets_manager
        )
        assert result is False

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {},
    )
    async def test_empty_keywords(self):
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        result = await creation_checker.is_new_channel_eligible(
            "war-room", "U1", secrets_manager
        )
        assert result is False

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_exempt_channel_ketchup_access_requests(self):
        """Test that ketchup_access_requests channel is always eligible."""
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Channel is in exempt list, should be eligible regardless of naming convention
        result = await creation_checker.is_new_channel_eligible(
            "ketchup_access_requests", "U2", secrets_manager
        )
        assert result is True

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_exempt_channel_ketchup_alerts(self):
        """Test that ketchup-alerts channel is always eligible."""
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Channel is in exempt list, should be eligible regardless of naming convention
        result = await creation_checker.is_new_channel_eligible(
            "ketchup-alerts", "U2", secrets_manager
        )
        assert result is True

    @patch(
        "packages.slack.channel_events.eligibility.creation_checker.CHANNEL_KEYWORD_TO_PRODUCT",
        {"war": "product1", "room": "product2"},
    )
    async def test_exempt_channel_with_hash(self):
        """Test that exempt channels work with # prefix."""
        secrets_manager = AsyncMock()
        secrets_manager.get_exigence_user_id_async = AsyncMock(return_value="U1")
        # Channel is in exempt list with # prefix
        result = await creation_checker.is_new_channel_eligible(
            "#ketchup_access_requests", "U2", secrets_manager
        )
        assert result is True
