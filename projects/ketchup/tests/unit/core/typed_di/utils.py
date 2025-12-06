"""TypedDI test utilities: reusable mocks and patch helpers for DI tests."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

_SECRETS_PAYLOAD = {
    "SLACK_SIGNING_SECRET": "test-signing-secret",
    "SLACK_API_TOKEN": "x-token",
    "SLACK_USER_API_TOKEN": "x-user-token",
    "APP_BOT_USER_ID": "BTEST123",
    "EXIGENCE_USER_ID": "UTEST123",
    "AZURE_OPENAI_LB_API_KEY": "test-azure-key",
    "BOT_SLACK_USER_ID": "UTESTBOT",
    "IMS_CLIENT_ID": "ketchup_prod",
    "IMS_CLIENT_SECRET": "",
    "IMS_CODE": "",
    "IPAAS_USERNAME": "ketchup",
    "IPAAS_PASSWORD": "",
    "IPAAS_API_KEY": "",
    "IMS_ACCESS_TOKEN": "",
    "IMS_REFRESH_TOKEN": "",
    "IMS_TOKEN_EXPIRES_AT": 0,
    "USAGE_STATS_ADMIN_USERS": [],
    "AUTHORISED_SLACK_USER_IDS": [],
    "AUTHORISED_USERS_LDAP_BACKUP": [],
}


class _SlackConfigStub:
    def __init__(self):
        self.headers = {
            "Authorization": "Bearer x-token",
            "Content-Type": "application/json",
        }
        self.api_base_url = "https://slack.test/api"

    def get_headers(self):
        return self.headers

    def get_api_base_url(self) -> str:
        return self.api_base_url


@contextmanager
def patch_core_dependencies():
    """Patch critical external integrations to return deterministic test doubles."""

    from packages.ai.core.openai_handler import OpenAIHandler
    from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
    from packages.integrations.mcp_async_client import MCPAsyncClient
    from packages.secrets.manager import SecretsManager

    slack_config_stub = _SlackConfigStub()

    dynamodb_mock_client = MagicMock()
    dynamodb_mock_client.put_item.return_value = {}
    dynamodb_mock_client.update_item.return_value = {}
    dynamodb_mock_client.get_item.return_value = {}
    dynamodb_mock_client.delete_item.return_value = {}
    dynamodb_mock_client.scan.return_value = {}
    dynamodb_mock_client.query.return_value = {}

    # Mock OpenAIHandler's initialize method instead of __init__ to prevent real API calls
    mock_openai_initialize = AsyncMock(return_value=None)

    patches = [
        patch.object(
            SecretsManager,
            "get_app_secrets",
            AsyncMock(return_value=_SECRETS_PAYLOAD),
        ),
        patch.object(
            SecretsManager,
            "get_secret_async",
            AsyncMock(
                return_value={
                    "slack_signing_secret": "test-signing-secret",
                    "slack_api_token": "x-token",
                    "slack_user_api_token": "x-user-token",
                    "slack_bot_app_id": "BTEST123",
                    "exigence_user_id": "UTEST123",
                    "azure_openai_lb_api_key": "test-azure-key",
                    "bot_slack_user_id": "UTESTBOT",
                }
            ),
        ),
        patch.object(
            SecretsManager,
            "get_slack_api_token_async",
            AsyncMock(return_value="x-token"),
        ),
        patch.object(
            SecretsManager,
            "get_azure_openai_lb_api_key",
            AsyncMock(return_value="test-azure-key"),
        ),
        patch(
            "packages.slack.config.slack_config.SlackConfig.create",
            new=AsyncMock(return_value=slack_config_stub),
        ),
        patch.object(
            DynamoDBAsyncClient,
            "_get_client",
            AsyncMock(return_value=dynamodb_mock_client),
        ),
        patch.object(
            DynamoDBAsyncClient,
            "cleanup",
            AsyncMock(return_value=None),
        ),
        patch.object(OpenAIHandler, "initialize", mock_openai_initialize),
        patch.object(OpenAIHandler, "setup", AsyncMock(return_value=None)),
        patch.object(OpenAIHandler, "__call__", AsyncMock(return_value={"choices": []})),
        patch.object(MCPAsyncClient, "search_issues", AsyncMock(return_value={"issues": []})),
        patch.object(MCPAsyncClient, "get_issue", AsyncMock(return_value={})),
    ]

    started = []
    try:
        for p in patches:
            started.append(p.start())
        yield
    finally:
        for p in reversed(patches):
            p.stop()
