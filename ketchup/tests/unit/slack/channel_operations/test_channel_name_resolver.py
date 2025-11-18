"""
Test module for ChannelNameResolver class.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from packages.slack.channel_operations.channel_name_resolver import ChannelNameResolver
from packages.slack.config.slack_config import SlackConfig


class TestChannelNameResolver:
    """Test cases for ChannelNameResolver."""

    @pytest.fixture
    def mock_slack_config(self):
        """Create a mock SlackConfig for testing."""
        config = Mock(spec=SlackConfig)
        config.api_token = "xoxb-test-token"
        config.get_api_base_url.return_value = "https://slack.com/api"
        config.get_headers.return_value = {"Authorization": "Bearer xoxb-test-token"}
        return config

    @pytest.fixture
    def resolver(self, mock_slack_config):
        """Create a ChannelNameResolver instance for testing."""
        return ChannelNameResolver(slack_config=mock_slack_config)

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_valid_channel_id(self, resolver):
        """Test resolving a valid channel ID returns it unchanged."""
        channel_id = "C1234567890"

        result_id, format_type = await resolver.resolve_channel_parameter(channel_id)

        assert result_id == channel_id
        assert format_type == "channel_id"

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_valid_group_id(self, resolver):
        """Test resolving a valid group ID returns it unchanged."""
        group_id = "G1234567890"

        result_id, format_type = await resolver.resolve_channel_parameter(group_id)

        assert result_id == group_id
        assert format_type == "channel_id"

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_valid_mention(self, resolver):
        """Test resolving a valid channel mention extracts the channel ID."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        expected_id = "C08U5S51Z4N"

        result_id, format_type = await resolver.resolve_channel_parameter(mention)

        assert result_id == expected_id
        assert format_type == "channel_mention"

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_valid_mention_group(self, resolver):
        """Test resolving a valid group mention extracts the group ID."""
        mention = "<#G1234567890|private-channel>"
        expected_id = "G1234567890"

        result_id, format_type = await resolver.resolve_channel_parameter(mention)

        assert result_id == expected_id
        assert format_type == "channel_mention"

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_valid_name_found(self, resolver):
        """Test resolving a valid channel name that exists."""
        channel_name = "#general"
        expected_id = "C1234567890"

        # Mock the API call to return a matching channel
        with patch.object(
            resolver, "_resolve_channel_name_to_id", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = expected_id

            result_id, format_type = await resolver.resolve_channel_parameter(
                channel_name
            )

            assert result_id == expected_id
            assert format_type == "channel_name"
            mock_resolve.assert_called_once_with("general")

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_valid_name_not_found(self, resolver):
        """Test resolving a valid channel name that doesn't exist."""
        channel_name = "#nonexistent"

        # Mock the API call to return None (channel not found)
        with patch.object(
            resolver, "_resolve_channel_name_to_id", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = None

            result_id, format_type = await resolver.resolve_channel_parameter(
                channel_name
            )

            assert result_id is None
            assert (
                format_type == "Channel name '#nonexistent' not found or not accessible"
            )
            mock_resolve.assert_called_once_with("nonexistent")

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_invalid_format(self, resolver):
        """Test resolving an invalid channel parameter format."""
        invalid_param = "invalid-channel-format"

        result_id, format_type = await resolver.resolve_channel_parameter(invalid_param)

        assert result_id is None
        assert "Invalid channel format" in format_type
        assert invalid_param in format_type

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_empty_string(self, resolver):
        """Test resolving an empty string."""
        result_id, format_type = await resolver.resolve_channel_parameter("")

        assert result_id is None
        assert "Invalid channel format" in format_type

    @pytest.mark.asyncio
    async def test_resolve_channel_parameter_whitespace_trimmed(self, resolver):
        """Test that whitespace is trimmed from input."""
        channel_id = "  C1234567890  "

        result_id, format_type = await resolver.resolve_channel_parameter(channel_id)

        assert result_id == "C1234567890"
        assert format_type == "channel_id"

    @pytest.mark.asyncio
    async def test_resolve_channel_name_to_id_public_channel_found(self, resolver):
        """Test resolving channel name to ID for public channel."""
        channel_name = "general"
        expected_id = "C1234567890"

        # Mock the API response for public channels
        mock_response = {
            "ok": True,
            "channels": [
                {"id": expected_id, "name": channel_name},
                {"id": "C0987654321", "name": "random"},
            ],
            "response_metadata": {},
        }

        with patch.object(
            resolver, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await resolver._resolve_channel_name_to_id(channel_name)

            assert result == expected_id
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_channel_name_to_id_private_channel_found(self, resolver):
        """Test resolving channel name to ID for private channel."""
        channel_name = "private-channel"
        expected_id = "G1234567890"

        # Mock API responses - first call returns no public channels, second returns private
        public_response = {"ok": True, "channels": [], "response_metadata": {}}
        private_response = {
            "ok": True,
            "channels": [{"id": expected_id, "name": channel_name}],
            "response_metadata": {},
        }

        with patch.object(
            resolver, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [public_response, private_response]

            result = await resolver._resolve_channel_name_to_id(channel_name)

            assert result == expected_id
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_resolve_channel_name_to_id_channel_not_found(self, resolver):
        """Test resolving channel name that doesn't exist."""
        channel_name = "nonexistent"

        # Mock API responses - both public and private return empty
        empty_response = {"ok": True, "channels": [], "response_metadata": {}}

        with patch.object(
            resolver, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = empty_response

            result = await resolver._resolve_channel_name_to_id(channel_name)

            assert result is None
            assert mock_request.call_count == 2  # Called for both public and private

    @pytest.mark.asyncio
    async def test_resolve_channel_name_to_id_with_pagination(self, resolver):
        """Test resolving channel name with pagination."""
        channel_name = "target-channel"
        expected_id = "C1234567890"

        # Mock paginated responses
        first_response = {
            "ok": True,
            "channels": [{"id": "C0000000000", "name": "other-channel"}],
            "response_metadata": {"next_cursor": "next_page_cursor"},
        }
        second_response = {
            "ok": True,
            "channels": [{"id": expected_id, "name": channel_name}],
            "response_metadata": {},
        }

        with patch.object(
            resolver, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [first_response, second_response]

            result = await resolver._resolve_channel_name_to_id(channel_name)

            assert result == expected_id
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_resolve_channel_name_to_id_api_error(self, resolver):
        """Test resolving channel name when API returns error."""
        channel_name = "test-channel"

        # Mock API error response
        error_response = {"ok": False, "error": "invalid_auth"}

        with patch.object(
            resolver, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = error_response

            result = await resolver._resolve_channel_name_to_id(channel_name)

            assert result is None

    @pytest.mark.asyncio
    async def test_resolve_channel_name_to_id_exception_handling(self, resolver):
        """Test resolving channel name when exception is raised."""
        channel_name = "test-channel"

        with patch.object(
            resolver, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Network error")

            result = await resolver._resolve_channel_name_to_id(channel_name)

            assert result is None

    def test_initialization(self, mock_slack_config):
        """Test ChannelNameResolver initialization."""
        resolver = ChannelNameResolver(slack_config=mock_slack_config)

        assert resolver is not None
        # Verify it inherits from SlackAsyncClient
        assert hasattr(resolver, "_make_api_request")

    def test_initialization_with_custom_params(self, mock_slack_config):
        """Test ChannelNameResolver initialization with custom parameters."""
        from packages.core.resilience.backoff import ExponentialBackoffStrategy

        custom_strategy = ExponentialBackoffStrategy(max_retries=5)
        resolver = ChannelNameResolver(
            slack_config=mock_slack_config,
            max_concurrent_requests=20,
            backoff_strategy=custom_strategy,
        )

        assert resolver is not None

    @pytest.mark.asyncio
    async def test_real_world_mention_example(self, resolver):
        """Test with the real-world mention from the bug report."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        expected_id = "C08U5S51Z4N"

        result_id, format_type = await resolver.resolve_channel_parameter(mention)

        assert result_id == expected_id
        assert format_type == "channel_mention"

    @pytest.mark.asyncio
    async def test_case_sensitivity(self, resolver):
        """Test that channel name resolution is case sensitive as per Slack standards."""
        # Channel names in Slack are always lowercase
        channel_name = "#General"  # Invalid - uppercase

        result_id, format_type = await resolver.resolve_channel_parameter(channel_name)

        assert result_id is None
        assert "Invalid channel format" in format_type
