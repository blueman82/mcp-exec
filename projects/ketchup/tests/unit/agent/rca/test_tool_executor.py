"""Tests for RCAToolExecutor — routing, error handling, and truncation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

import json
from unittest.mock import AsyncMock

import pytest

from packages.agent.rca.tool_executor import RCA_TOOL_RESULT_MAX_CHARS, RCAToolExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.retrieve.return_value = [{"id": "1", "text": "incident data", "score": 0.9}]
    return r


@pytest.fixture
def mock_mcp_client():
    c = AsyncMock()
    c.search_issues.return_value = {"issues": [{"key": "CPGNCX-123"}]}
    return c


@pytest.fixture
def mock_newrelic_client():
    c = AsyncMock()
    c.execute_nrql.return_value = [{"count": 42}]
    c.get_active_alerts.return_value = [{"id": 1, "entity": {"name": "test"}}]
    return c


@pytest.fixture
def executor(mock_retriever, mock_mcp_client, mock_newrelic_client):
    return RCAToolExecutor(
        retriever=mock_retriever,
        mcp_client=mock_mcp_client,
        newrelic_client=mock_newrelic_client,
    )


@pytest.mark.asyncio
async def test_search_similar_incidents(executor, mock_retriever):
    result = await executor.execute("search_similar_incidents", {"query": "ORA-01555"})
    mock_retriever.retrieve.assert_called_once_with(query="ORA-01555", channel_id=None)
    parsed = json.loads(result)
    assert isinstance(parsed, list)


@pytest.mark.asyncio
async def test_search_jira_history(executor, mock_mcp_client):
    result = await executor.execute("search_jira_history", {"jql": "text ~ 'ORA-01555'"})
    mock_mcp_client.search_issues.assert_called_once_with(jql="text ~ 'ORA-01555'")
    parsed = json.loads(result)
    assert "issues" in parsed


@pytest.mark.asyncio
async def test_query_instance_health(executor, mock_newrelic_client):
    result = await executor.execute(
        "query_instance_health", {"nrql": "SELECT count(*) FROM Transaction"}
    )
    mock_newrelic_client.execute_nrql.assert_called_once_with(
        nrql="SELECT count(*) FROM Transaction"
    )
    parsed = json.loads(result)
    assert parsed[0]["count"] == 42


@pytest.mark.asyncio
async def test_get_active_alerts(executor, mock_newrelic_client):
    result = await executor.execute("get_active_alerts", {})
    mock_newrelic_client.get_active_alerts.assert_called_once()
    parsed = json.loads(result)
    assert len(parsed) == 1


@pytest.mark.asyncio
async def test_unknown_tool(executor):
    result = await executor.execute("unknown_tool", {})
    parsed = json.loads(result)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_truncation(executor, mock_retriever):
    # Return a very large result
    mock_retriever.retrieve.return_value = [{"text": "x" * 5000}]
    result = await executor.execute("search_similar_incidents", {"query": "test"})
    assert len(result) <= RCA_TOOL_RESULT_MAX_CHARS + len("...[truncated]")
