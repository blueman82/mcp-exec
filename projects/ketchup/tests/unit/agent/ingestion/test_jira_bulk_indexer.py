"""Tests for JiraBulkIndexer."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from packages.agent.ingestion.jira_bulk_indexer import TICKETS_PER_PAGE, JiraBulkIndexer

# Import the protocol directly from its source file to avoid triggering the
# service_registrations package __init__, which imports agent_services.py and
# requires chromadb (not installed in the unit-test venv).
_PROTO_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages/core/typed_di/service_registrations/protocols/agent_protocols.py"
)
_proto_spec = importlib.util.spec_from_file_location("agent_protocols", _PROTO_PATH)
_proto_module = importlib.util.module_from_spec(_proto_spec)  # type: ignore[arg-type]
_proto_spec.loader.exec_module(_proto_module)  # type: ignore[union-attr]
JiraBulkIndexerProtocol = _proto_module.JiraBulkIndexerProtocol

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    key: str,
    summary: str = "Test summary",
    description: str = "Test description",
    status: str = "Resolved",
    priority: str = "Medium",
    resolution: str = "Fixed",
    assignee: str = "Test User",
    extra_fields: dict | None = None,
) -> dict:
    """Build a minimal JIRA issue dict matching the API response shape."""
    fields = {
        "summary": summary,
        "description": description,
        "status": {"name": status},
        "priority": {"name": priority},
        "resolution": {"name": resolution},
        "assignee": {"displayName": assignee},
        "issuetype": {"name": "Bug"},
        "components": [],
        "issuelinks": [],
        "comment": {"comments": []},
    }
    if extra_fields:
        fields.update(extra_fields)
    return {"key": key, "fields": fields}


def _make_comment(
    comment_id: str, author_display: str, body: str, created: str = "2026-01-01"
) -> dict:
    """Build a minimal JIRA comment dict."""
    return {
        "id": comment_id,
        "author": {"displayName": author_display},
        "body": body,
        "created": created,
    }


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Return a dummy 1536-dim embedding per text."""
    return [[0.1] * 1536] * len(texts)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_deps():
    embeddings_client = AsyncMock()
    embeddings_client.embed_texts.side_effect = _fake_embed
    vector_store = AsyncMock()
    mcp_client = AsyncMock()
    mcp_client.get_issue_comments.return_value = []
    return {
        "embeddings_client": embeddings_client,
        "vector_store": vector_store,
        "mcp_client": mcp_client,
    }


@pytest.fixture
def indexer(mock_deps):
    return JiraBulkIndexer(**mock_deps)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIndexSingleProject:
    async def test_index_single_project(self, mock_deps):
        """Two tickets on one project page → 2 summary docs with correct IDs and text."""
        issue1 = _make_issue("CAMP-1", summary="First ticket", status="Resolved")
        issue2 = _make_issue("CAMP-2", summary="Second ticket", status="Closed")

        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue1, issue2],
            "total": 2,
        }

        indexer = JiraBulkIndexer(**mock_deps)
        # Exercise through the project directly by calling _index_project
        tickets, docs = await indexer._index_project("CAMP", "project = CAMP", {})

        assert tickets == 2, "should count 2 tickets indexed"
        assert docs == 2, "should produce 1 summary doc per ticket"

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        ids = [d["id"] for d in stored]
        assert "jira_bulk:CAMP-1:summary" in ids
        assert "jira_bulk:CAMP-2:summary" in ids

        # Verify text formatting for the first ticket
        ticket1_doc = next(d for d in stored if d["id"] == "jira_bulk:CAMP-1:summary")
        assert "[JIRA:CAMP-1]" in ticket1_doc["text"]
        assert "First ticket" in ticket1_doc["text"]
        assert "Resolved" in ticket1_doc["text"]


class TestCsopmJqlWindow:
    async def test_csopm_uses_12_month_window(self, mock_deps):
        """CSOPM project uses KETCHUP_JIRA_INDEX_MONTHS_CSOPM; other projects use default."""
        jql_calls: list[str] = []

        async def capture_search(jql: str, **_) -> dict:
            jql_calls.append(jql)
            return {"issues": [], "total": 0}

        mock_deps["mcp_client"].search_issues.side_effect = capture_search

        indexer = JiraBulkIndexer(**mock_deps)
        with patch.dict(os.environ, {"KETCHUP_JIRA_INDEX_MONTHS_CSOPM": "12"}):
            await indexer.index_all_projects()

        csopm_jql = next((j for j in jql_calls if "CSOPM" in j), None)
        other_jql = next((j for j in jql_calls if "CAMP" in j), None)

        assert csopm_jql is not None, "no JQL call found for CSOPM project"
        assert "-12m" in csopm_jql, f"expected -12m in CSOPM JQL, got: {csopm_jql}"

        assert other_jql is not None, "no JQL call found for CAMP project"
        assert "-6m" in other_jql, f"expected -6m for non-CSOPM project, got: {other_jql}"


class TestBotCommentFiltering:
    async def test_bot_comments_filtered(self, indexer, mock_deps):
        """Comments from known bot authors are excluded; human comments are kept."""
        issue = _make_issue("CAMP-100")
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }
        mock_deps["mcp_client"].get_issue_comments.return_value = [
            _make_comment("c1", "ketchup Generic", "automated bot message"),
            _make_comment("c2", "jiradydx", "another bot message"),
            _make_comment("c3", "jarvis", "jarvis auto-comment"),
            _make_comment("c4", "Alice Human", "this is a real comment"),
        ]

        await indexer._index_project("CAMP", "project = CAMP", {})

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        ids = [d["id"] for d in stored]

        # One summary doc + one human comment
        assert "jira_bulk:CAMP-100:summary" in ids
        assert "jira_bulk:CAMP-100:c:c4" in ids
        assert "jira_bulk:CAMP-100:c:c1" not in ids
        assert "jira_bulk:CAMP-100:c:c2" not in ids
        assert "jira_bulk:CAMP-100:c:c3" not in ids
        assert len(ids) == 2, f"expected exactly 2 docs, got {len(ids)}: {ids}"


class TestRcaDocument:
    async def test_rca_document_created_for_csopm(self, indexer, mock_deps):
        """CSOPM ticket with RCA Description produces a separate doc with doc_type='rca'."""
        issue = _make_issue(
            "CSOPM-500",
            extra_fields={
                "customfield_34000": "Root cause was a misconfiguration in the pipeline."
            },
        )
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        await indexer._index_project("CSOPM", "project = CSOPM", {})

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        ids = [d["id"] for d in stored]

        assert "jira_bulk:CSOPM-500:summary" in ids
        assert "jira_bulk:CSOPM-500:rca" in ids, "expected RCA document for CSOPM ticket"

        rca_doc = next(d for d in stored if d["id"] == "jira_bulk:CSOPM-500:rca")
        assert rca_doc["metadata"]["jira_doc_type"] == "rca"
        assert "misconfiguration" in rca_doc["text"]

    async def test_rca_document_not_created_without_field(self, indexer, mock_deps):
        """CSOPM ticket without customfield_34000 should not produce an RCA doc."""
        issue = _make_issue("CSOPM-501")
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        await indexer._index_project("CSOPM", "project = CSOPM", {})

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        ids = [d["id"] for d in stored]

        assert "jira_bulk:CSOPM-501:rca" not in ids

    async def test_rca_document_not_created_for_non_csopm(self, indexer, mock_deps):
        """Non-CSOPM ticket with RCA field populated should NOT produce an RCA doc."""
        issue = _make_issue(
            "CAMP-502",
            extra_fields={"customfield_34000": "Some RCA text"},
        )
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        await indexer._index_project("CAMP", "project = CAMP", {})

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        ids = [d["id"] for d in stored]

        assert "jira_bulk:CAMP-502:rca" not in ids


class TestRecursiveLinkIndexing:
    async def test_recursive_link_indexing(self, mock_deps):
        """Linked tickets not yet indexed are fetched and stored in the link-following pass."""
        primary_issue = _make_issue(
            "CAMP-200",
            extra_fields={
                "issuelinks": [
                    {
                        "outwardIssue": {"key": "NEO-999"},
                    }
                ]
            },
        )
        linked_issue = _make_issue("NEO-999", summary="Linked ticket summary")

        async def search_issues(jql: str, **_) -> dict:
            if "CAMP" in jql and "startAt" in jql:
                return {"issues": [primary_issue], "total": 1}
            elif 'key = "NEO-999"' in jql:
                return {"issues": [linked_issue], "total": 1}
            return {"issues": [], "total": 0}

        mock_deps["mcp_client"].search_issues.side_effect = search_issues

        indexer = JiraBulkIndexer(**mock_deps)
        indexed_fields: dict = {}
        await indexer._index_project("CAMP", "project = CAMP", indexed_fields)

        assert "CAMP-200" in indexed_fields, "primary ticket should be in indexed_fields"

        linked_count = await indexer._index_linked_tickets(
            set(indexed_fields.keys()), indexed_fields
        )

        assert linked_count == 1, "one linked ticket should be additionally indexed"

        # Confirm NEO-999 summary doc was stored in the second add_documents call
        all_stored_calls = mock_deps["vector_store"].add_documents.call_args_list
        assert len(all_stored_calls) == 2, "expected add_documents called for primary + linked pass"
        linked_docs = all_stored_calls[1].args[0]
        linked_ids = [d["id"] for d in linked_docs]
        assert "jira_bulk:NEO-999:summary" in linked_ids


class TestCustomFieldsInMetadata:
    async def test_custom_fields_in_metadata(self, indexer, mock_deps):
        """Issue Category (customfield_15709) and Severity from CC (customfield_15901)
        appear in document metadata when provided."""
        issue = _make_issue(
            "CSOPM-300",
            extra_fields={
                "customfield_15709": {"value": "Data Loss"},
                "customfield_15901": {"value": "P1"},
            },
        )
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        await indexer._index_project("CSOPM", "project = CSOPM", {})

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        summary_doc = next(d for d in stored if d["id"] == "jira_bulk:CSOPM-300:summary")

        assert summary_doc["metadata"]["issue_category"] == "Data Loss"
        assert summary_doc["metadata"]["severity_from_cc"] == "P1"


class TestDescriptionTruncation:
    async def test_description_truncation(self, indexer, mock_deps):
        """Descriptions longer than 4,000 chars are truncated in the document text."""
        long_description = "x" * 10_000
        issue = _make_issue("CAMP-400", description=long_description)
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        await indexer._index_project("CAMP", "project = CAMP", {})

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        summary_doc = next(d for d in stored if d["id"] == "jira_bulk:CAMP-400:summary")

        # The full 10k description must not appear in the text
        assert long_description not in summary_doc["text"]
        # Exactly 4,000 x's must appear (the truncated value)
        assert "x" * 4_000 in summary_doc["text"]
        assert "x" * 4_001 not in summary_doc["text"]


class TestIdempotentRerun:
    async def test_idempotent_rerun(self, mock_deps):
        """Running index twice with identical ticket data produces the same doc IDs both times."""
        issue = _make_issue("CAMP-500", summary="Stable ticket")
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        indexer = JiraBulkIndexer(**mock_deps)

        await indexer._index_project("CAMP", "project = CAMP", {})
        first_call_docs = mock_deps["vector_store"].add_documents.call_args.args[0]
        first_ids = [d["id"] for d in first_call_docs]

        # Reset call tracking but keep same issue data
        mock_deps["vector_store"].reset_mock()
        mock_deps["mcp_client"].search_issues.return_value = {
            "issues": [issue],
            "total": 1,
        }

        await indexer._index_project("CAMP", "project = CAMP", {})
        second_call_docs = mock_deps["vector_store"].add_documents.call_args.args[0]
        second_ids = [d["id"] for d in second_call_docs]

        assert (
            first_ids == second_ids
        ), "doc IDs must be identical across runs (upsert/idempotency guarantee)"


class TestPagination:
    async def test_pagination(self, mock_deps):
        """Two pages of results (50 then 10) → all 60 tickets processed."""
        page1_issues = [_make_issue(f"CAMP-{i}") for i in range(1, 51)]  # 50 issues
        page2_issues = [_make_issue(f"CAMP-{i}") for i in range(51, 61)]  # 10 issues

        call_count = 0

        async def search_issues(jql: str, **_) -> dict:
            nonlocal call_count
            call_count += 1
            if "startAt=0" in jql:
                return {"issues": page1_issues, "total": 60}
            elif f"startAt={TICKETS_PER_PAGE}" in jql:
                return {"issues": page2_issues, "total": 60}
            return {"issues": [], "total": 60}

        mock_deps["mcp_client"].search_issues.side_effect = search_issues

        indexer = JiraBulkIndexer(**mock_deps)
        tickets, _ = await indexer._index_project("CAMP", "project = CAMP", {})

        assert tickets == 60, f"expected 60 tickets total, got {tickets}"
        assert call_count == 2, f"expected exactly 2 search_issues calls, got {call_count}"


class TestProtocolCompliance:
    def test_protocol_compliance(self, mock_deps):
        """JiraBulkIndexer must implement every method declared in JiraBulkIndexerProtocol."""
        import inspect

        indexer = JiraBulkIndexer(**mock_deps)

        protocol_methods = {
            name
            for name, _ in inspect.getmembers(JiraBulkIndexerProtocol, predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        # Collect both bound methods and unbound functions on the instance/class
        instance_methods = {
            name
            for name, member in inspect.getmembers(indexer)
            if not name.startswith("_") and callable(member)
        }

        missing = protocol_methods - instance_methods
        assert not missing, f"JiraBulkIndexer is missing protocol methods: {missing}"
