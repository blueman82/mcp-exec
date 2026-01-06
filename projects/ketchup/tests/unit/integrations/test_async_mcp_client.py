"""Unit tests for the Async MCP client built on AsyncClient/httpx."""

from unittest.mock import AsyncMock

import orjson
import pytest

from packages.core.exceptions import ClientError
from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager
from packages.integrations.async_mcp_client import AsyncMCPClient, iPaaSRateLimiter

# Capture the real orjson functions at import time to avoid mock pollution
_real_orjson_loads = orjson.loads
_real_orjson_dumps = orjson.dumps

pytestmark = pytest.mark.unit


class TestiPaaSRateLimiter:
    """Test iPaaS rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_under_limit(self):
        """Requests within the limit should proceed without delay."""

        limiter = iPaaSRateLimiter(requests_per_minute=60)

        for _ in range(5):
            await limiter.acquire()

        assert len(limiter.request_times) == 5

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_when_limit_reached(self, mocker):
        """Exceeding the limit should trigger a sleep interval."""

        limiter = iPaaSRateLimiter(requests_per_minute=2)

        times = iter([100, 100, 100, 100, 161])
        mocker.patch("time.time", side_effect=lambda: next(times))
        sleep_mock = AsyncMock()
        mocker.patch("asyncio.sleep", sleep_mock)

        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        sleep_mock.assert_called_once()


class TestAsyncMCPClient:
    """Test coverage for AsyncMCPClient behaviour."""

    @pytest.fixture()
    def mock_token_manager(self):
        """Provide a mock IMS token manager."""

        manager = AsyncMock(spec=AsyncIMSTokenManager)
        manager.get_valid_token = AsyncMock(return_value="test_token")
        manager._token_cache = {}
        return manager

    @pytest.fixture()
    def client(self, mock_token_manager):
        """Create a client instance for tests."""

        return AsyncMCPClient(base_url="https://mcp", token_manager=mock_token_manager)

    @pytest.mark.asyncio
    async def test_health_check_success(self, client, mocker):
        """Health check should report healthy on 200 responses."""

        async def fake_request(url: str, method: str, **kwargs):
            assert url.endswith("/health")
            return {
                "status": 200,
                "headers": {},
                "body": b"",
                "content_type": "text/plain",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        assert await client.health_check() is True
        assert client._is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client, mocker):
        """Non-200 responses should flag the client unhealthy."""

        async def failing_request(url: str, method: str, **kwargs):
            return {
                "status": 500,
                "headers": {},
                "body": b"",
                "content_type": "text/plain",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=failing_request))

        assert await client.health_check() is False
        assert client._is_healthy is False

    @pytest.mark.asyncio
    async def test_reconnect_with_backoff(self, client, mocker):
        """Reconnect should clean up, sleep, and re-establish session."""

        # Mock health_check to return True immediately (exit the while loop)
        mocker.patch.object(client, "health_check", AsyncMock(return_value=True))
        # Mock cleanup, setup, and _establish_mcp_session to avoid real network calls
        mocker.patch.object(client, "cleanup", AsyncMock())
        mocker.patch.object(client, "setup", AsyncMock())
        mocker.patch.object(
            client, "_establish_mcp_session", AsyncMock(return_value="test-session-id")
        )

        sleep_mock = AsyncMock()
        mocker.patch("asyncio.sleep", sleep_mock)

        await client._reconnect()

        # health_check returns True immediately, so no sleep should be called
        assert sleep_mock.call_count == 0
        # Verify session was established
        assert client._session_id == "test-session-id"

    @pytest.mark.asyncio
    async def test_establish_mcp_session_rate_limited(self, client, mocker):
        """Session creation should honour rate limiting and headers."""

        acquire_mock = AsyncMock()
        mocker.patch.object(client.rate_limiter, "acquire", acquire_mock)

        async def fake_request(url: str, method: str, **kwargs):
            assert url.endswith("/sse")
            headers = kwargs["headers"]
            assert headers["Authorization"] == "Bearer test_token"
            return {
                "status": 200,
                "headers": {"X-Session-ID": "session-abc"},
                "body": b"",
                "content_type": "text/event-stream",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        session_id = await client._establish_mcp_session()

        assert session_id == "session-abc"
        assert client._session_id == "session-abc"
        acquire_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_mcp_tool_surfaces_jira_error(self, client, mocker):
        """Tool errors should raise with the detailed JIRA payload."""

        acquire_mock = AsyncMock()
        mocker.patch.object(client.rate_limiter, "acquire", acquire_mock)

        payload = {
            "error": {
                "message": "failed",
                "data": {"jiraError": "Detailed JIRA failure"},
            }
        }

        async def fake_request(url: str, method: str, **kwargs):
            assert url.endswith("/message")
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(payload),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        with pytest.raises(Exception) as exc:
            await client._call_mcp_tool("search", {})

        assert "Detailed JIRA failure" in str(exc.value)
        acquire_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_mcp_tool_returns_parsed_content(self, client, mocker):
        """Tool calls should return parsed JSON content."""

        async def fake_request(url: str, method: str, **kwargs):
            assert url.endswith("/message")
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {"result": {"content": [{"text": '{"issues": [{"key": "TEST-1"}]}'}]}}
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client._call_mcp_tool("search", {})

        assert result == {"issues": [{"key": "TEST-1"}]}
        assert len(client.rate_limiter.request_times) == 1

    @pytest.mark.asyncio
    async def test_search_issues_success(self, client, mocker):
        """search_issues should return the decoded issue list."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())

        async def fake_request(url: str, method: str, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {"result": {"content": [{"text": '{"issues": [{"key": "TEST-1"}]}'}]}}
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.search_issues("project = TEST")

        assert result == {"issues": [{"key": "TEST-1"}]}
        assert len(client.rate_limiter.request_times) == 2

    @pytest.mark.asyncio
    async def test_search_issues_auth_failure(self, client, mock_token_manager, mocker):
        """Auth errors should clear the token cache and bubble up."""

        mock_token_manager._token_cache = {"stale": "token"}
        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(side_effect=Exception("401 Unauthorized")),
        )

        with pytest.raises(Exception):
            await client.search_issues("project = TEST")

        assert mock_token_manager._token_cache == {}

    @pytest.mark.asyncio
    async def test_get_issue_success(self, client, mocker):
        """get_issue should return the first matching issue."""

        async def fake_search(jql: str, fields=None, max_results=50):
            assert jql == 'key = "TEST-1"'
            return {"issues": [{"key": "TEST-1", "fields": {"summary": "Test"}}]}

        mocker.patch.object(client, "search_issues", AsyncMock(side_effect=fake_search))

        result = await client.get_issue("TEST-1")

        assert result["key"] == "TEST-1"
        client.search_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_issue_not_found(self, client, mocker):
        """None should be returned when no issues matched."""

        mocker.patch.object(
            client,
            "search_issues",
            AsyncMock(return_value={"issues": []}),
        )

        assert await client.get_issue("MISSING-1") is None

    @pytest.mark.asyncio
    async def test_get_issues_batch_merges_results(self, client, mocker):
        """Batch results should map missing issues to None."""

        async def fake_search(jql: str, fields=None, max_results=50):
            assert "key IN" in jql
            return {"issues": [{"key": "A-1"}]}

        mocker.patch.object(client, "search_issues", AsyncMock(side_effect=fake_search))

        result = await client.get_issues_batch(["A-1", "B-2"])

        assert result["A-1"]["key"] == "A-1"
        assert result["B-2"] is None

    @pytest.mark.asyncio
    async def test_get_issue_comments_success(self, client, mocker):
        """Comment retrieval should return the decoded list."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())

        async def fake_request(url: str, method: str, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {
                        "result": {
                            "content": [
                                {"text": '{"success": true, "data": {"comments": [{"id": "1"}]}}'}
                            ]
                        }
                    }
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        comments = await client.get_issue_comments("A-1")

        assert comments == [{"id": "1"}]
        assert len(client.rate_limiter.request_times) == 2

    @pytest.mark.asyncio
    async def test_build_headers(self, client):
        """Headers should include bearer token and session ID."""

        client._session_id = "session123"

        headers = await client._build_headers()

        assert headers["Authorization"] == "Bearer test_token"
        assert headers["X-Session-ID"] == "session123"

    @pytest.mark.asyncio
    async def test_ensure_connection_triggers_health_check(self, client, mocker):
        """ensure_connection should poll health when interval elapsed."""

        client._last_health_check = 0
        mocker.patch("time.time", return_value=100)
        mocker.patch.object(client, "health_check", AsyncMock(return_value=True))

        await client.ensure_connection()

        client.health_check.assert_called_once()
        assert client._last_health_check == 100

    @pytest.mark.asyncio
    async def test_create_issue_comment_success(self, client, mocker):
        """create_issue_comment should return True on success."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(return_value={"success": True}),
        )

        assert await client.create_issue_comment("TEST-1", "Test comment") is True

    @pytest.mark.asyncio
    async def test_NETWORK_error_handling(self, client, mocker):
        """Network errors should propagate to the caller."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(
            client,
            "_make_api_request",
            AsyncMock(side_effect=ClientError("Network error")),
        )

        with pytest.raises(Exception) as exc:
            await client.search_issues("project = TEST")

        assert "Network error" in str(exc.value)

    @pytest.mark.asyncio
    async def test_list_projects_success(self, client, mocker):
        """list_projects should return the decoded project list."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())

        async def fake_request(url: str, method: str, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {
                        "result": {
                            "content": [
                                {
                                    "text": '{"success": true, "data": [{"key": "PROJ1", "name": "Project One"}, {"key": "PROJ2", "name": "Project Two"}]}'
                                }
                            ]
                        }
                    }
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.list_projects()

        assert result == [
            {"key": "PROJ1", "name": "Project One"},
            {"key": "PROJ2", "name": "Project Two"},
        ]

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, client, mocker):
        """list_projects should return empty list when no projects available."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())

        async def fake_request(url: str, method: str, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {"result": {"content": [{"text": '{"success": true, "data": []}'}]}}
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.list_projects()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_projects_error(self, client, mocker):
        """list_projects should return empty list on exception."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(side_effect=Exception("Network failure")),
        )

        result = await client.list_projects()

        assert result == []

    # ==========================================================================
    # PAT (Personal Access Token) Method Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_create_pat_success(self, client, mocker):
        """create_pat should return PAT data on successful creation."""

        ensure_conn_mock = AsyncMock()
        acquire_mock = AsyncMock()
        mocker.patch.object(client, "ensure_connection", ensure_conn_mock)
        mocker.patch.object(client.rate_limiter, "acquire", acquire_mock)
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(
                return_value={
                    "success": True,
                    "message": "PAT created",
                    "data": {
                        "pat": "test-pat-token-value",
                        "id": "pat-123",
                        "expiryDate": "2026-04-06T00:00:00Z",
                    },
                }
            ),
        )

        result = await client.create_pat(token_name="test-pat", expiry_days=90)

        assert result["pat"] == "test-pat-token-value"
        assert result["id"] == "pat-123"
        assert result["expiryDate"] == "2026-04-06T00:00:00Z"
        ensure_conn_mock.assert_called_once()
        acquire_mock.assert_called_once()
        client._call_mcp_tool.assert_called_once_with(
            "create_jira_pat", {"tokenName": "test-pat", "expiryDays": 90}
        )

    @pytest.mark.asyncio
    async def test_create_pat_failure(self, client, mocker):
        """create_pat should raise exception on failure response."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(
                return_value={
                    "success": False,
                    "message": "Rate limit exceeded",
                }
            ),
        )

        with pytest.raises(Exception) as exc:
            await client.create_pat()

        assert "Rate limit exceeded" in str(exc.value)

    @pytest.mark.asyncio
    async def test_create_pat_network_error(self, client, mocker):
        """create_pat should propagate network exceptions."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(side_effect=Exception("Connection refused")),
        )

        with pytest.raises(Exception) as exc:
            await client.create_pat()

        assert "Connection refused" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_pat_success(self, client, mocker):
        """validate_pat should return validation result on success."""

        ensure_conn_mock = AsyncMock()
        acquire_mock = AsyncMock()
        mocker.patch.object(client, "ensure_connection", ensure_conn_mock)
        mocker.patch.object(client.rate_limiter, "acquire", acquire_mock)
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(
                return_value={
                    "valid": True,
                    "message": "Token is valid",
                }
            ),
        )

        result = await client.validate_pat("test-token-value")

        assert result["valid"] is True
        assert result["message"] == "Token is valid"
        ensure_conn_mock.assert_called_once()
        acquire_mock.assert_called_once()
        client._call_mcp_tool.assert_called_once_with(
            "validate_jira_pat", {"token": "test-token-value"}
        )

    @pytest.mark.asyncio
    async def test_validate_pat_failure(self, client, mocker):
        """validate_pat should return failure result for invalid tokens."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(
                return_value={
                    "valid": False,
                    "message": "Token expired or invalid",
                }
            ),
        )

        result = await client.validate_pat("expired-token")

        assert result["valid"] is False
        assert "expired or invalid" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_pat_network_error(self, client, mocker):
        """validate_pat should propagate network exceptions."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(side_effect=Exception("Network timeout")),
        )

        with pytest.raises(Exception) as exc:
            await client.validate_pat("test-token")

        assert "Network timeout" in str(exc.value)

    @pytest.mark.asyncio
    async def test_revoke_pat_success(self, client, mocker):
        """revoke_pat should return success result on successful revocation."""

        ensure_conn_mock = AsyncMock()
        acquire_mock = AsyncMock()
        mocker.patch.object(client, "ensure_connection", ensure_conn_mock)
        mocker.patch.object(client.rate_limiter, "acquire", acquire_mock)
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(
                return_value={
                    "success": True,
                    "message": "PAT revoked successfully",
                }
            ),
        )

        result = await client.revoke_pat("pat-123")

        assert result["success"] is True
        assert result["message"] == "PAT revoked successfully"
        ensure_conn_mock.assert_called_once()
        acquire_mock.assert_called_once()
        client._call_mcp_tool.assert_called_once_with("revoke_jira_pat", {"tokenId": "pat-123"})

    @pytest.mark.asyncio
    async def test_revoke_pat_failure(self, client, mocker):
        """revoke_pat should return failure result when revocation fails."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(
                return_value={
                    "success": False,
                    "message": "Token not found",
                }
            ),
        )

        result = await client.revoke_pat("nonexistent-pat-id")

        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_revoke_pat_network_error(self, client, mocker):
        """revoke_pat should propagate network exceptions."""

        mocker.patch.object(client, "ensure_connection", AsyncMock())
        mocker.patch.object(client.rate_limiter, "acquire", AsyncMock())
        mocker.patch.object(
            client,
            "_call_mcp_tool",
            AsyncMock(side_effect=Exception("Service unavailable")),
        )

        with pytest.raises(Exception) as exc:
            await client.revoke_pat("pat-123")

        assert "Service unavailable" in str(exc.value)
