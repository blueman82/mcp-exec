"""Tests for the Jira MCP client service."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bravo.config import JiraSettings
from bravo.services.jira import JiraMCPClient, JiraMCPError, JiraTicket


def _make_settings(**overrides) -> JiraSettings:
    """Create JiraSettings with test defaults."""
    defaults = {"mcp_url": "http://localhost:8081"}
    return JiraSettings(**(defaults | overrides))


def _mock_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a MagicMock httpx response (sync .json() and .raise_for_status())."""
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    resp.status_code = status_code
    return resp


def _jsonrpc_ok(data: dict) -> dict:
    """Wrap data as a successful JSON-RPC 2.0 response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(data)}]},
    }


def _jsonrpc_error(message: str, code: int = -32000) -> dict:
    """Wrap an error as a JSON-RPC 2.0 response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": code, "message": message},
    }


def _make_client_with_mock(
    response_data: dict, *, pat_service: AsyncMock | None = None,
) -> tuple[JiraMCPClient, AsyncMock]:
    """Create a JiraMCPClient with a mocked httpx client returning response_data."""
    client = JiraMCPClient(_make_settings(), pat_service=pat_service)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.post.return_value = _mock_response(response_data)
    client._client = mock_http
    return client, mock_http


class TestSearchTickets:
    """Tests for JiraMCPClient.search_tickets()."""

    async def test_search_returns_tickets(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "CPGNCX-100",
                                "id": "12345",
                                "fields": {
                                    "summary": "Test ticket",
                                    "assignee": {
                                        "name": "jdoe",
                                        "displayName": "Jane Doe",
                                    },
                                    "status": {"name": "Open"},
                                    "updated": "2026-01-15T10:00:00+00:00",
                                    "comment": {
                                        "comments": [
                                            {"updated": "2026-01-15T12:00:00+00:00"}
                                        ]
                                    },
                                },
                            }
                        ]
                    }
                }
            )
        )

        tickets = await client.search_tickets("project = CPGNCX")

        assert len(tickets) == 1
        assert tickets[0].key == "CPGNCX-100"
        assert tickets[0].project == "CPGNCX"
        assert tickets[0].assignee_id == "jdoe"
        assert tickets[0].assignee_name == "Jane Doe"
        assert tickets[0].status == "Open"
        assert tickets[0].last_comment_at is not None

    async def test_search_empty_results(self):
        client, _ = _make_client_with_mock(_jsonrpc_ok({"data": {"issues": []}}))
        tickets = await client.search_tickets("project = NONE")
        assert tickets == []

    async def test_search_string_assignee(self):
        """When minimizeOutput is true, assignee may be a plain string."""
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "id": "1",
                                "fields": {
                                    "summary": "Ticket",
                                    "assignee": "Jane Doe",
                                    "status": {"name": "Open"},
                                    "updated": "2026-01-15T10:00:00Z",
                                },
                            }
                        ]
                    }
                }
            )
        )

        tickets = await client.search_tickets("key = TEST-1")
        assert tickets[0].assignee_id is None
        assert tickets[0].assignee_name == "Jane Doe"

    async def test_search_null_assignee(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-2",
                                "id": "2",
                                "fields": {
                                    "summary": "Unassigned",
                                    "assignee": None,
                                    "status": "Open",
                                    "updated": "2026-01-15T10:00:00Z",
                                },
                            }
                        ]
                    }
                }
            )
        )

        tickets = await client.search_tickets("key = TEST-2")
        assert tickets[0].assignee_id is None
        assert tickets[0].assignee_name is None
        assert tickets[0].status == "Open"


class TestGetTicketComments:
    """Tests for JiraMCPClient.get_ticket_comments()."""

    async def test_get_ticket_comments_returns_bodies(self):
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "fields": {
                                    "comment": {
                                        "comments": [
                                            {"body": "First comment"},
                                            {"body": "Second comment"},
                                            {"body": "Third comment"},
                                        ]
                                    }
                                },
                            }
                        ]
                    }
                }
            )
        )

        result = await client.get_ticket_comments("TEST-1")

        assert result == ["First comment", "Second comment", "Third comment"]
        payload = mock_http.post.call_args.kwargs["json"]
        args = payload["params"]["arguments"]
        assert args["jql"] == "key = TEST-1"
        assert args["minimizeOutput"] is False

    async def test_get_ticket_comments_empty(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "fields": {"comment": {"comments": []}},
                            }
                        ]
                    }
                }
            )
        )

        result = await client.get_ticket_comments("TEST-1")

        assert result == []

    async def test_get_ticket_comments_no_issue_found(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok({"data": {"issues": []}})
        )

        result = await client.get_ticket_comments("MISSING-1")

        assert result == []

    async def test_get_ticket_comments_caps_at_limit(self):
        bodies = [{"body": f"Comment {i}"} for i in range(15)]
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "fields": {"comment": {"comments": bodies}},
                            }
                        ]
                    }
                }
            )
        )

        result = await client.get_ticket_comments("TEST-1")

        assert len(result) == 10
        assert result[0] == "Comment 5"
        assert result[-1] == "Comment 14"


class TestJsonRpcFormatting:
    """Tests for JSON-RPC 2.0 request formatting."""

    async def test_call_tool_sends_correct_payload(self):
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client._call_tool("test_tool", {"arg1": "value1"})

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "test_tool"
        assert payload["params"]["arguments"] == {"arg1": "value1"}
        assert isinstance(payload["id"], int)

    async def test_request_id_increments(self):
        client = JiraMCPClient(_make_settings())
        assert client._next_id() == 1
        assert client._next_id() == 2
        assert client._next_id() == 3


class TestErrorHandling:
    """Tests for MCP error responses."""

    async def test_mcp_error_raises_jira_mcp_error(self):
        client, _ = _make_client_with_mock(_jsonrpc_error("Permission denied"))

        with pytest.raises(JiraMCPError, match="Permission denied"):
            await client._call_tool("forbidden_tool", {})

    async def test_invalid_json_in_content_raises_jira_mcp_error(self):
        client, _ = _make_client_with_mock(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "not valid json!"}]},
            }
        )

        with pytest.raises(JiraMCPError, match="Invalid MCP response"):
            await client._call_tool("bad_tool", {})


class TestGetTicketFields:
    """Tests for JiraMCPClient.get_ticket_fields()."""

    async def test_get_ticket_fields_returns_all(self):
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "fields": {
                                    "summary": "A ticket",
                                    "description": "Some description",
                                    "priority": {"name": "Major"},
                                    "components": [
                                        {"name": "Backend"},
                                        {"name": "API"},
                                    ],
                                },
                            }
                        ]
                    }
                }
            )
        )

        result = await client.get_ticket_fields("TEST-1")

        assert result["summary"] == "A ticket"
        assert result["description"] == "Some description"
        assert result["priority"] == "Major"
        assert result["components"] == ["Backend", "API"]
        payload = mock_http.post.call_args.kwargs["json"]
        args = payload["params"]["arguments"]
        assert args["minimizeOutput"] is False

    async def test_get_ticket_fields_missing_description(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "fields": {
                                    "summary": "A ticket",
                                    "description": None,
                                    "priority": {"name": "Normal"},
                                    "components": [],
                                },
                            }
                        ]
                    }
                }
            )
        )

        result = await client.get_ticket_fields("TEST-1")

        assert result["description"] == ""
        assert result["priority"] == "Normal"
        assert result["components"] == []

    async def test_get_ticket_fields_no_issue_found(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok({"data": {"issues": []}})
        )

        result = await client.get_ticket_fields("MISSING-1")

        assert result == {}

    async def test_get_ticket_fields_components_parsed(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_ok(
                {
                    "data": {
                        "issues": [
                            {
                                "key": "TEST-1",
                                "fields": {
                                    "summary": "Ticket",
                                    "description": "desc",
                                    "priority": None,
                                    "components": [
                                        {"name": "Frontend"},
                                        {"id": "123"},
                                        {"name": "Backend"},
                                    ],
                                },
                            }
                        ]
                    }
                }
            )
        )

        result = await client.get_ticket_fields("TEST-1")

        # Component without "name" key should be skipped
        assert result["components"] == ["Frontend", "Backend"]
        assert result["priority"] == ""


class TestAddComment:
    """Tests for JiraMCPClient.add_comment()."""

    async def test_add_comment_sends_nested_body(self):
        """Comment body must be nested: {"comment": {"body": "..."}}."""
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client.add_comment("TEST-1", "Hello world")

        payload = mock_http.post.call_args.kwargs["json"]
        args = payload["params"]["arguments"]
        assert args["issueIdOrKey"] == "TEST-1"
        assert args["comment"] == {"body": "Hello world"}


class TestTransitions:
    """Tests for transition and get_transitions methods."""

    async def test_transition_status_with_resolution(self):
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client.transition_status("TEST-1", "991", resolution={"name": "Fixed"})

        payload = mock_http.post.call_args.kwargs["json"]
        args = payload["params"]["arguments"]
        assert args["issueIdOrKey"] == "TEST-1"
        assert args["transitionId"] == "991"
        assert args["resolution"] == {"name": "Fixed"}

    async def test_transition_status_without_resolution(self):
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client.transition_status("TEST-1", "2")

        payload = mock_http.post.call_args.kwargs["json"]
        args = payload["params"]["arguments"]
        assert "resolution" not in args

    async def test_get_transitions_returns_list(self):
        transitions = [
            {"id": "2", "name": "Close Issue", "to": {"name": "Closed"}},
            {"id": "991", "name": "Resolved", "to": {"name": "Resolved"}},
        ]
        client, _ = _make_client_with_mock(
            _jsonrpc_ok({"data": {"transitions": transitions}})
        )

        result = await client.get_transitions("TEST-1")
        assert len(result) == 2
        assert result[0]["id"] == "2"
        assert result[1]["name"] == "Resolved"


class TestCreateUpdateIssue:
    """Tests for create_issue and update_issue."""

    async def test_create_issue_passes_fields(self):
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok({"key": "TEST-99", "id": "99999"})
        )

        fields = {
            "project": {"key": "TEST"},
            "issuetype": {"name": "Task"},
            "summary": "New ticket",
        }
        result = await client.create_issue(fields)

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["params"]["arguments"]["fields"] == fields
        assert result["key"] == "TEST-99"

    async def test_update_issue_passes_fields(self):
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client.update_issue("TEST-1", {"summary": "Updated"})

        payload = mock_http.post.call_args.kwargs["json"]
        args = payload["params"]["arguments"]
        assert args["issueIdOrKey"] == "TEST-1"
        assert args["fields"] == {"summary": "Updated"}


class TestUserPatPlumbing:
    """Tests for per-user PAT pass-through on write operations."""

    async def test_call_tool_injects_user_pat(self):
        """When user_pat provided, MCP payload includes userPat in arguments."""
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client._call_tool("test_tool", {"arg1": "v1"}, user_pat="pat-abc")

        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["params"]["arguments"]["userPat"] == "pat-abc"
        assert payload["params"]["arguments"]["arg1"] == "v1"

    async def test_call_tool_omits_user_pat_when_none(self):
        """When user_pat=None, MCP payload has no userPat key."""
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client._call_tool("test_tool", {"arg1": "v1"}, user_pat=None)

        payload = mock_http.post.call_args.kwargs["json"]
        assert "userPat" not in payload["params"]["arguments"]

    async def test_add_comment_resolves_pat(self):
        """With pat_service + slack_user_id, get_pat called and userPat in args."""
        mock_pat = AsyncMock()
        mock_pat.get_pat.return_value = "pat-from-db"
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok({"ok": True}), pat_service=mock_pat,
        )

        await client.add_comment("TEST-1", "Hello", slack_user_id="U456")

        mock_pat.get_pat.assert_awaited_once_with("U456")
        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["params"]["arguments"]["userPat"] == "pat-from-db"

    async def test_update_issue_resolves_pat(self):
        """With pat_service + slack_user_id, userPat injected for update_issue."""
        mock_pat = AsyncMock()
        mock_pat.get_pat.return_value = "pat-upd"
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok({"ok": True}), pat_service=mock_pat,
        )

        await client.update_issue("TEST-1", {"summary": "X"}, slack_user_id="U789")

        mock_pat.get_pat.assert_awaited_once_with("U789")
        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["params"]["arguments"]["userPat"] == "pat-upd"

    async def test_write_no_pat_service_skips_lookup(self):
        """pat_service=None means no userPat in MCP args."""
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))

        await client.add_comment("TEST-1", "Hello", slack_user_id="U456")

        payload = mock_http.post.call_args.kwargs["json"]
        assert "userPat" not in payload["params"]["arguments"]


class TestClientLifecycle:
    """Tests for httpx client lazy init and close."""

    async def test_get_client_creates_on_first_call(self):
        client = JiraMCPClient(_make_settings())
        assert client._client is None

        http = await client._get_client()
        assert http is not None
        assert isinstance(http, httpx.AsyncClient)
        await client.close()

    async def test_get_client_reuses_existing(self):
        client = JiraMCPClient(_make_settings())
        http1 = await client._get_client()
        http2 = await client._get_client()
        assert http1 is http2
        await client.close()

    async def test_close_sets_client_none(self):
        client = JiraMCPClient(_make_settings())
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        client._client = mock_http

        await client.close()

        mock_http.aclose.assert_awaited_once()
        assert client._client is None

    async def test_close_noop_when_no_client(self):
        client = JiraMCPClient(_make_settings())
        await client.close()  # Should not raise
        assert client._client is None


class TestTestAuth:
    """Tests for JiraMCPClient.test_auth()."""

    async def test_test_auth_returns_true_on_success(self):
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok({"name": "testuser", "displayName": "Test User"})
        )

        result = await client.test_auth()

        assert result is True
        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["params"]["name"] == "test_jira_auth"

    async def test_test_auth_returns_false_on_mcp_error(self):
        client, _ = _make_client_with_mock(
            _jsonrpc_error("Unauthorized")
        )

        result = await client.test_auth()

        assert result is False

    async def test_test_auth_passes_user_pat(self):
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok({"name": "patuser"})
        )

        result = await client.test_auth(user_pat="my-pat-token")

        assert result is True
        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["params"]["arguments"]["userPat"] == "my-pat-token"

    async def test_test_auth_no_user_pat_omits_key(self):
        client, mock_http = _make_client_with_mock(
            _jsonrpc_ok({"name": "testuser"})
        )

        await client.test_auth(user_pat=None)

        payload = mock_http.post.call_args.kwargs["json"]
        assert "userPat" not in payload["params"]["arguments"]


class TestResilience:
    """Tests for retry, semaphore, and error resilience in JiraMCPClient."""

    async def test_retries_on_transport_error(self):
        client, mock_http = _make_client_with_mock(_jsonrpc_ok({"ok": True}))
        mock_http.post.side_effect = [
            httpx.ConnectError("conn refused"),
            _mock_response(_jsonrpc_ok({"ok": True})),
        ]

        with patch("bravo.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await client._call_tool("test_tool", {})

        assert result == {"ok": True}
        assert mock_http.post.await_count == 2

    async def test_mcp_error_not_retried(self):
        client, mock_http = _make_client_with_mock(_jsonrpc_error("Bad request"))

        with pytest.raises(JiraMCPError, match="Bad request"):
            await client._call_tool("bad_tool", {})

        mock_http.post.assert_awaited_once()

    async def test_semaphore_limits_concurrency(self):
        settings = _make_settings(max_concurrent_requests=2)
        client = JiraMCPClient(settings)

        max_concurrent = 0
        current = 0
        lock = asyncio.Lock()
        gate = asyncio.Event()

        async def _slow_post(*args, **kwargs):
            nonlocal max_concurrent, current
            async with lock:
                current += 1
                max_concurrent = max(max_concurrent, current)
            await gate.wait()
            async with lock:
                current -= 1
            return _mock_response(_jsonrpc_ok({"ok": True}))

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post = _slow_post
        client._client = mock_http

        tasks = [asyncio.create_task(client._call_tool(f"t{i}", {})) for i in range(5)]
        await asyncio.sleep(0.05)

        assert max_concurrent == 2

        gate.set()
        await asyncio.gather(*tasks)

    async def test_jira_mcp_error_attributes(self):
        client, _ = _make_client_with_mock(_jsonrpc_error("Not found"))

        with pytest.raises(JiraMCPError) as exc_info:
            await client._call_tool("missing_tool", {})

        assert exc_info.value.tool_name == "missing_tool"
        assert exc_info.value.status_code is None

    async def test_settings_timeout_used(self):
        client = JiraMCPClient(_make_settings(request_timeout=42.0))
        http = await client._get_client()

        assert http.timeout == httpx.Timeout(42.0)
        await client.close()

    async def test_exhausted_retries_propagates(self):
        settings = _make_settings(max_retries=2)
        client = JiraMCPClient(settings)
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        mock_http.post.side_effect = httpx.ConnectError("down")
        client._client = mock_http

        with patch("bravo.services.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError, match="down"):
                await client._call_tool("test_tool", {})

        assert mock_http.post.await_count == 2
