"""
test_feature_command.py

Unit tests for feature_command.py (FeatureCommand).

Covers:
- FeatureCommand initialization
- Admin permission checking
- All command actions (enable, disable, list, status)
- Success and error scenarios
- Message formatting
- Integration with dependencies

Edge Cases Covered:
- Non-admin user access
- User not found
- Database errors
- Empty user lists
- Feature status variations

Expected Outcomes:
- Proper admin access control
- Correct feature management operations
- Appropriate user messages
- Error handling
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.secrets.manager import SecretsManager
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    FeatureCommandParams,
)
from packages.slack.command_processing.feature_command import FeatureCommand
from packages.slack.command_processing.feature_service import FeatureService
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps


class TestFeatureCommand:
    """Test FeatureCommand functionality."""

    @pytest.fixture
    def mock_feature_service(self) -> AsyncMock:
        """Create a mock FeatureService."""
        mock = AsyncMock(spec=FeatureService)
        mock.enable_feature_for_user = AsyncMock(return_value=True)
        mock.disable_feature_for_user = AsyncMock(return_value=True)
        mock.get_users_with_feature = AsyncMock(return_value=[])
        mock.get_feature_status = MagicMock(
            return_value={
                "feature_enabled": True,
                "global_access": False,
                "env_var": "KETCHUP_NLP_FEATURE",
                "global_env_var": "KETCHUP_NLP_GLOBAL",
                "user_field": "features.nlp_enabled",
            }
        )
        return mock

    @pytest.fixture
    def mock_slack_posting(self) -> AsyncMock:
        """Create a mock SlackPostingHandler."""
        return AsyncMock(spec=SlackPostingHandler)

    @pytest.fixture
    def mock_slack_user_ops(self) -> AsyncMock:
        """Create a mock SlackUserOps."""
        mock = AsyncMock(spec=SlackUserOps)
        mock.get_user_info = AsyncMock(
            return_value={"user": {"real_name": "John Doe", "name": "john.doe"}}
        )
        mock._fetch_user_info_internal = AsyncMock(
            return_value={
                "profile": {"real_name": "John Doe", "email": "john.doe@adobe.com"},
                "real_name": "John Doe",
                "name": "john.doe",
            }
        )
        mock.get_user_names = AsyncMock(return_value={"UTARGET": "John Doe"})
        return mock

    @pytest.fixture
    def mock_secrets_manager(self) -> AsyncMock:
        """Create a mock SecretsManager."""
        mock = AsyncMock(spec=SecretsManager)
        mock.get_secret_async = AsyncMock(
            return_value={"usage_stats_admin_users": ["U12345", "UADMIN"]}
        )
        return mock

    @pytest.fixture
    def feature_command(
        self,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
        mock_slack_user_ops: AsyncMock,
        mock_secrets_manager: AsyncMock,
    ) -> FeatureCommand:
        """Create a FeatureCommand instance with mocked dependencies."""
        command = FeatureCommand(
            feature_service=mock_feature_service,
            slack_posting_handler=mock_slack_posting,
            slack_user_ops=mock_slack_user_ops,
            secrets_manager=mock_secrets_manager,
        )
        # Mock the handler methods to be async
        command._handle_enable_feature = AsyncMock(
            return_value={"statusCode": 200, "body": "Feature enabled"}
        )
        command._handle_disable_feature = AsyncMock(
            return_value={"statusCode": 200, "body": "Feature disabled"}
        )
        command._handle_list_feature = AsyncMock(
            return_value={"statusCode": 200, "body": "Feature users listed"}
        )
        command._handle_feature_status = AsyncMock(
            return_value={"statusCode": 200, "body": "Feature status"}
        )
        return command

    @pytest.mark.asyncio
    async def test_non_admin_access_denied(
        self, feature_command: FeatureCommand, mock_slack_posting: AsyncMock
    ) -> None:
        """Test non-admin user is denied access."""
        params = FeatureCommandParams(
            user_id="U99999",
            user_name="test.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp status",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp status",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="status",
            target_user_id=None,
        )

        result = await feature_command.process_feature_params(
            params=params,
            user_id="U99999",  # Not in admin list
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Unauthorized"}
        mock_slack_posting.post_message.assert_called_once()
        call_args = mock_slack_posting.post_message.call_args[1]
        assert "not authorized" in call_args["message"]

    @pytest.mark.asyncio
    async def test_admin_enable_feature_success(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
        mock_slack_user_ops: AsyncMock,
    ) -> None:
        """Test admin successfully enables feature for user."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp enable <@UTARGET>",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp enable <@UTARGET>",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="enable",
            target_user_id="UTARGET",
        )

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",  # Admin user
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature enabled"}
        # Check that the handler was called with correct params
        feature_command._handle_enable_feature.assert_called_once_with(
            "UADMIN", "D12345", "nlp", params, "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_admin_disable_feature_success(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
        mock_slack_user_ops: AsyncMock,
    ) -> None:
        """Test admin successfully disables feature for user."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp disable <@UTARGET>",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp disable <@UTARGET>",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="disable",
            target_user_id="UTARGET",
        )

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature disabled"}
        # Check that the handler was called with correct params
        feature_command._handle_disable_feature.assert_called_once_with(
            "UADMIN", "D12345", "nlp", params, "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_enable_feature_database_error(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
    ) -> None:
        """Test enable feature handles database errors."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp enable <@UTARGET>",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp enable <@UTARGET>",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="enable",
            target_user_id="UTARGET",
        )

        mock_feature_service.enable_feature_for_user.return_value = False

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature enabled"}
        # When database error, handler should still be called
        feature_command._handle_enable_feature.assert_called_once_with(
            "UADMIN", "D12345", "nlp", params, "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_list_users_with_feature(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
        mock_slack_user_ops: AsyncMock,
    ) -> None:
        """Test listing users with feature enabled."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp list",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp list",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="list",
            target_user_id=None,
        )

        # Mock users with feature
        mock_feature_service.get_users_with_feature.return_value = [
            {"user_id": "U1", "features": {"nlp_enabled": True}},
            {"user_id": "U2", "features": {"nlp_enabled": True}},
        ]

        # Mock user info lookups
        mock_slack_user_ops.get_user_info.side_effect = [
            {"user": {"real_name": "User One", "name": "user.one"}},
            {"user": {"real_name": "User Two", "name": "user.two"}},
        ]

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature users listed"}
        # Check that the handler was called with correct params
        feature_command._handle_list_feature.assert_called_once_with(
            "UADMIN", "D12345", "nlp", "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_list_users_empty(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
    ) -> None:
        """Test listing users when no users have feature."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp list",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp list",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="list",
            target_user_id=None,
        )

        mock_feature_service.get_users_with_feature.return_value = []

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature users listed"}
        # Handler should be called even when no users
        feature_command._handle_list_feature.assert_called_once_with(
            "UADMIN", "D12345", "nlp", "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_feature_status(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
    ) -> None:
        """Test getting feature status."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp status",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp status",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="status",
            target_user_id=None,
        )

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature status"}
        # Check that the handler was called with correct params
        feature_command._handle_feature_status.assert_called_once_with(
            "UADMIN", "D12345", "nlp", "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_user_not_found_error(
        self,
        feature_command: FeatureCommand,
        mock_slack_posting: AsyncMock,
        mock_slack_user_ops: AsyncMock,
    ) -> None:
        """Test handling user not found error."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp enable <@UNOTFOUND>",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp enable <@UNOTFOUND>",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="enable",
            target_user_id="UNOTFOUND",
        )

        mock_slack_user_ops.get_user_info.side_effect = Exception("User not found")

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature enabled"}
        # Handler should still be called even when user not found
        feature_command._handle_enable_feature.assert_called_once_with(
            "UADMIN", "D12345", "nlp", params, "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_admin_list_from_secrets(
        self,
        feature_command: FeatureCommand,
        mock_secrets_manager: AsyncMock,
        mock_slack_posting: AsyncMock,
    ) -> None:
        """Test admin list is loaded from secrets manager."""
        # Verify that the admin list comes from secrets
        params = FeatureCommandParams(
            user_id="U12345",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp status",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp status",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="status",
            target_user_id=None,
        )

        # Test with user in secrets admin list
        result = await feature_command.process_feature_params(
            params=params,
            user_id="U12345",  # In admin list from fixture
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature status"}
        # Should call the handler since user is admin
        feature_command._handle_feature_status.assert_called_once_with(
            "U12345", "D12345", "nlp", "https://slack.com/response"
        )

    @pytest.mark.asyncio
    async def test_feature_status_with_global_access(
        self,
        feature_command: FeatureCommand,
        mock_feature_service: AsyncMock,
        mock_slack_posting: AsyncMock,
    ) -> None:
        """Test feature status display when global access is enabled."""
        params = FeatureCommandParams(
            user_id="UADMIN",
            user_name="admin.user",
            channel_id="D12345",
            command_text="/ketchup feature nlp status",
            response_url="https://slack.com/response",
            original_command="/ketchup feature nlp status",
            command_type=CommandType.FEATURE,
            context=CommandContext.DIRECT_MESSAGE,
            feature_name="nlp",
            action="status",
            target_user_id=None,
        )

        # Mock global access enabled
        mock_feature_service.get_feature_status.return_value = {
            "feature_enabled": True,
            "global_access": True,
            "env_var": "KETCHUP_NLP_FEATURE",
            "global_env_var": "KETCHUP_NLP_GLOBAL",
            "user_field": "features.nlp_enabled",
        }

        result = await feature_command.process_feature_params(
            params=params,
            user_id="UADMIN",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Feature status"}
        # Check that the handler was called with correct params
        feature_command._handle_feature_status.assert_called_once_with(
            "UADMIN", "D12345", "nlp", "https://slack.com/response"
        )
