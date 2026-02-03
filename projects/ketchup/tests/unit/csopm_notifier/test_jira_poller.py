#!/usr/bin/env python3
"""
CSOPM JIRA Poller Tests.

Unit tests for the CSOPMJIRAPoller service, verifying:
1. Protocol compliance with CSOPMJIRAPollerProtocol
2. JQL query construction
3. JIRA response parsing into CSOPMTicket instances
4. Exigence ID extraction from descriptions
5. Error handling for various edge cases
"""

import unittest
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock

from packages.core.typed_di.protocols import CSOPMJIRAPollerProtocol, CSOPMTicket


class MockAsyncMCPClient:
    """Mock AsyncMCPClient for testing."""

    def __init__(self) -> None:
        self.search_issues = AsyncMock()
        self.get_issue = AsyncMock()


class TestCSOPMJIRAPollerProtocolCompliance(unittest.TestCase):
    """Test that CSOPMJIRAPoller implements the protocol correctly."""

    def test_implements_protocol(self):
        """Test CSOPMJIRAPoller implements CSOPMJIRAPollerProtocol."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        # Verify it's recognized as implementing the protocol
        mock_client = MockAsyncMCPClient()
        poller = CSOPMJIRAPoller(mcp_client=mock_client)

        self.assertIsInstance(poller, CSOPMJIRAPollerProtocol)

    def test_has_poll_for_new_assignments_method(self):
        """Test CSOPMJIRAPoller has poll_for_new_assignments method."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.assertTrue(hasattr(CSOPMJIRAPoller, "poll_for_new_assignments"))

    def test_has_get_ticket_details_method(self):
        """Test CSOPMJIRAPoller has get_ticket_details method."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.assertTrue(hasattr(CSOPMJIRAPoller, "get_ticket_details"))

    def test_has_get_tickets_by_assignee_method(self):
        """Test CSOPMJIRAPoller has get_tickets_by_assignee method."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.assertTrue(hasattr(CSOPMJIRAPoller, "get_tickets_by_assignee"))


class TestCSOPMJIRAPollerExigenceExtraction(unittest.TestCase):
    """Test Exigence ID extraction from descriptions."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.mock_client = MockAsyncMCPClient()
        self.poller = CSOPMJIRAPoller(mcp_client=self.mock_client)

    def test_extract_5_digit_exigence_id(self):
        """Test extraction of 5-digit Exigence ID from description."""
        description = "Issue link: https://adobe.app.exigence.io/secure/index.html#/events/12345/situationroom"

        result = self.poller._extract_exigence_id(description)

        self.assertEqual(result, "12345")

    def test_extract_6_digit_exigence_id(self):
        """Test extraction of 6-digit Exigence ID from description."""
        description = "Issue link: https://adobe.app.exigence.io/secure/index.html#/events/123456/situationroom"

        result = self.poller._extract_exigence_id(description)

        self.assertEqual(result, "123456")

    def test_extract_exigence_id_no_match(self):
        """Test extraction returns None when no Exigence ID present."""
        description = "This is a regular description without any Exigence links."

        result = self.poller._extract_exigence_id(description)

        self.assertIsNone(result)

    def test_extract_exigence_id_empty_description(self):
        """Test extraction returns None for empty description."""
        result = self.poller._extract_exigence_id("")
        self.assertIsNone(result)

        result = self.poller._extract_exigence_id(None)
        self.assertIsNone(result)

    def test_extract_exigence_id_multiple_urls(self):
        """Test extraction finds first Exigence ID when multiple present."""
        description = "First: /events/11111/situationroom " "Second: /events/22222/situationroom"

        result = self.poller._extract_exigence_id(description)

        # Should return the first match
        self.assertEqual(result, "11111")


class TestCSOPMJIRAPollerParsing(unittest.TestCase):
    """Test JIRA issue parsing into CSOPMTicket."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.mock_client = MockAsyncMCPClient()
        self.poller = CSOPMJIRAPoller(mcp_client=self.mock_client)

    def _make_jira_issue(
        self,
        key: str = "CSOPM-1234",
        summary: str = "Test Issue",
        status: str = "New",
        assignee_name: str = "testuser",
        created: str = "2024-01-15T10:30:00.000+0000",
        description: str = "",
    ) -> Dict[str, Any]:
        """Helper to create a mock JIRA issue."""
        return {
            "key": key,
            "fields": {
                "summary": summary,
                "status": {"name": status},
                "assignee": {"name": assignee_name, "displayName": "Test User"},
                "created": created,
                "description": description,
            },
        }

    def test_parse_valid_issue(self):
        """Test parsing a valid JIRA issue into CSOPMTicket."""
        issue = self._make_jira_issue(
            key="CSOPM-5678",
            summary="Customer Issue",
            status="New",
            assignee_name="jdoe",
            description="Link: /events/12345/situationroom",
        )

        result = self.poller._parse_jira_issue(issue)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CSOPMTicket)
        self.assertEqual(result.key, "CSOPM-5678")
        self.assertEqual(result.summary, "Customer Issue")
        self.assertEqual(result.status, "New")
        self.assertEqual(result.assignee_username, "jdoe")
        self.assertEqual(result.exigence_id, "12345")

    def test_parse_issue_without_exigence_id(self):
        """Test parsing issue without Exigence ID in description."""
        issue = self._make_jira_issue(description="Regular description without Exigence link")

        result = self.poller._parse_jira_issue(issue)

        self.assertIsNotNone(result)
        self.assertIsNone(result.exigence_id)

    def test_parse_issue_missing_key(self):
        """Test parsing returns None when issue missing key."""
        issue = {"fields": {"summary": "No key issue"}}

        result = self.poller._parse_jira_issue(issue)

        self.assertIsNone(result)

    def test_parse_issue_missing_assignee(self):
        """Test parsing returns None when issue has no assignee."""
        issue = {
            "key": "CSOPM-1234",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": None,
                "created": "2024-01-15T10:30:00.000+0000",
            },
        }

        result = self.poller._parse_jira_issue(issue)

        self.assertIsNone(result)

    def test_parse_issue_empty_assignee(self):
        """Test parsing returns None when assignee username is empty."""
        issue = {
            "key": "CSOPM-1234",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": {"name": "", "displayName": ""},
                "created": "2024-01-15T10:30:00.000+0000",
            },
        }

        result = self.poller._parse_jira_issue(issue)

        self.assertIsNone(result)

    def test_parse_issue_uses_display_name_fallback(self):
        """Test parsing uses displayName when name is not available."""
        issue = {
            "key": "CSOPM-1234",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "assignee": {"displayName": "John Doe"},
                "created": "2024-01-15T10:30:00.000+0000",
            },
        }

        result = self.poller._parse_jira_issue(issue)

        self.assertIsNotNone(result)
        self.assertEqual(result.assignee_username, "John Doe")

    def test_parse_issue_invalid_date(self):
        """Test parsing handles invalid created date gracefully."""
        issue = self._make_jira_issue(created="invalid-date")

        result = self.poller._parse_jira_issue(issue)

        # Should still parse, using current datetime as fallback
        self.assertIsNotNone(result)
        self.assertIsInstance(result.created_at, datetime)


class TestCSOPMJIRAPollerPollForNewAssignments(unittest.IsolatedAsyncioTestCase):
    """Test poll_for_new_assignments method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.mock_client = MockAsyncMCPClient()
        self.poller = CSOPMJIRAPoller(mcp_client=self.mock_client)

    async def test_poll_returns_tickets(self):
        """Test poll_for_new_assignments returns list of CSOPMTicket."""
        self.mock_client.search_issues.return_value = {
            "issues": [
                {
                    "key": "CSOPM-1001",
                    "fields": {
                        "summary": "Issue 1",
                        "status": {"name": "New"},
                        "assignee": {"name": "user1"},
                        "created": "2024-01-15T10:00:00.000+0000",
                        "description": "/events/11111/",
                    },
                },
                {
                    "key": "CSOPM-1002",
                    "fields": {
                        "summary": "Issue 2",
                        "status": {"name": "New"},
                        "assignee": {"name": "user2"},
                        "created": "2024-01-15T11:00:00.000+0000",
                        "description": "/events/22222/",
                    },
                },
            ]
        }

        result = await self.poller.poll_for_new_assignments()

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], CSOPMTicket)
        self.assertEqual(result[0].key, "CSOPM-1001")
        self.assertEqual(result[1].key, "CSOPM-1002")

    async def test_poll_uses_correct_jql(self):
        """Test poll_for_new_assignments uses correct JQL query."""
        self.mock_client.search_issues.return_value = {"issues": []}

        await self.poller.poll_for_new_assignments()

        self.mock_client.search_issues.assert_called_once()
        call_args = self.mock_client.search_issues.call_args

        # Verify JQL contains expected clauses
        # Note: We don't filter by 'assignee IS NOT EMPTY' in JQL because CSOPM project
        # restricts that field. Instead, we filter out unassigned tickets in Python code.
        # Filter by TechOps Product (customfield_20800) for Adobe Campaign/AJO only.
        jql = call_args.kwargs.get("jql", "")
        self.assertIn("project = CSOPM", jql)
        self.assertIn("status = 'New'", jql)
        self.assertIn("cf[20800]", jql)
        self.assertIn("Adobe Campaign", jql)

    async def test_poll_returns_empty_on_no_results(self):
        """Test poll_for_new_assignments returns empty list when no issues."""
        self.mock_client.search_issues.return_value = {"issues": []}

        result = await self.poller.poll_for_new_assignments()

        self.assertEqual(result, [])

    async def test_poll_returns_empty_on_error(self):
        """Test poll_for_new_assignments returns empty list on MCP error."""
        self.mock_client.search_issues.side_effect = Exception("MCP error")

        result = await self.poller.poll_for_new_assignments()

        self.assertEqual(result, [])

    async def test_poll_filters_invalid_issues(self):
        """Test poll_for_new_assignments filters out invalid issues."""
        self.mock_client.search_issues.return_value = {
            "issues": [
                {
                    "key": "CSOPM-1001",
                    "fields": {
                        "summary": "Valid Issue",
                        "status": {"name": "New"},
                        "assignee": {"name": "user1"},
                        "created": "2024-01-15T10:00:00.000+0000",
                    },
                },
                {
                    # Missing assignee - should be filtered
                    "key": "CSOPM-1002",
                    "fields": {
                        "summary": "No Assignee",
                        "status": {"name": "New"},
                        "assignee": None,
                        "created": "2024-01-15T11:00:00.000+0000",
                    },
                },
            ]
        }

        result = await self.poller.poll_for_new_assignments()

        # Only valid issue should be returned
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].key, "CSOPM-1001")


class TestCSOPMJIRAPollerGetTicketDetails(unittest.IsolatedAsyncioTestCase):
    """Test get_ticket_details method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.mock_client = MockAsyncMCPClient()
        self.poller = CSOPMJIRAPoller(mcp_client=self.mock_client)

    async def test_get_ticket_details_success(self):
        """Test get_ticket_details returns CSOPMTicket for valid issue."""
        self.mock_client.get_issue.return_value = {
            "key": "CSOPM-5678",
            "fields": {
                "summary": "Test Ticket",
                "status": {"name": "In Progress"},
                "assignee": {"name": "testuser"},
                "created": "2024-01-15T10:30:00.000+0000",
                "description": "Link: /events/54321/room",
            },
        }

        result = await self.poller.get_ticket_details("CSOPM-5678")

        self.assertIsNotNone(result)
        self.assertEqual(result.key, "CSOPM-5678")
        self.assertEqual(result.status, "In Progress")
        self.assertEqual(result.exigence_id, "54321")

    async def test_get_ticket_details_not_found(self):
        """Test get_ticket_details returns None for non-existent ticket."""
        self.mock_client.get_issue.return_value = None

        result = await self.poller.get_ticket_details("CSOPM-9999")

        self.assertIsNone(result)

    async def test_get_ticket_details_on_error(self):
        """Test get_ticket_details returns None on MCP error."""
        self.mock_client.get_issue.side_effect = Exception("MCP error")

        result = await self.poller.get_ticket_details("CSOPM-1234")

        self.assertIsNone(result)


class TestCSOPMJIRAPollerGetTicketsByAssignee(unittest.IsolatedAsyncioTestCase):
    """Test get_tickets_by_assignee method."""

    def setUp(self):
        """Set up test fixtures."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        self.mock_client = MockAsyncMCPClient()
        self.poller = CSOPMJIRAPoller(mcp_client=self.mock_client)

    async def test_get_tickets_by_assignee_success(self):
        """Test get_tickets_by_assignee returns list of tickets."""
        self.mock_client.search_issues.return_value = {
            "issues": [
                {
                    "key": "CSOPM-1001",
                    "fields": {
                        "summary": "User's Issue 1",
                        "status": {"name": "In Progress"},
                        "assignee": {"name": "jsmith"},
                        "created": "2024-01-10T10:00:00.000+0000",
                    },
                },
                {
                    "key": "CSOPM-1002",
                    "fields": {
                        "summary": "User's Issue 2",
                        "status": {"name": "New"},
                        "assignee": {"name": "jsmith"},
                        "created": "2024-01-12T10:00:00.000+0000",
                    },
                },
            ]
        }

        result = await self.poller.get_tickets_by_assignee("jsmith")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].key, "CSOPM-1001")
        self.assertEqual(result[1].key, "CSOPM-1002")

    async def test_get_tickets_by_assignee_uses_correct_jql(self):
        """Test get_tickets_by_assignee uses correct JQL with assignee filter."""
        self.mock_client.search_issues.return_value = {"issues": []}

        await self.poller.get_tickets_by_assignee("testuser")

        self.mock_client.search_issues.assert_called_once()
        call_args = self.mock_client.search_issues.call_args

        jql = call_args.kwargs.get("jql", "")
        self.assertIn("project = CSOPM", jql)
        self.assertIn('assignee = "testuser"', jql)
        self.assertIn("status NOT IN", jql)

    async def test_get_tickets_by_assignee_no_results(self):
        """Test get_tickets_by_assignee returns empty list when no tickets."""
        self.mock_client.search_issues.return_value = {"issues": []}

        result = await self.poller.get_tickets_by_assignee("newuser")

        self.assertEqual(result, [])

    async def test_get_tickets_by_assignee_on_error(self):
        """Test get_tickets_by_assignee returns empty list on error."""
        self.mock_client.search_issues.side_effect = Exception("MCP error")

        result = await self.poller.get_tickets_by_assignee("testuser")

        self.assertEqual(result, [])


class TestCSOPMJIRAPollerJQLConstruction(unittest.TestCase):
    """Test JQL query constants."""

    def test_new_assignments_jql_has_required_clauses(self):
        """Test NEW_ASSIGNMENTS_JQL contains all required clauses."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        jql = CSOPMJIRAPoller.NEW_ASSIGNMENTS_JQL

        # Note: We don't filter by 'assignee IS NOT EMPTY' in JQL because CSOPM project
        # restricts that field. Instead, we filter out unassigned tickets in Python code.
        # Filter by TechOps Product (customfield_20800) for Adobe Campaign/AJO only.
        self.assertIn("project = CSOPM", jql)
        self.assertIn("status = 'New'", jql)
        self.assertIn("ORDER BY created DESC", jql)
        self.assertIn("cf[20800]", jql)
        self.assertIn("Adobe Campaign", jql)
        self.assertIn("Adobe Journey Optimizer", jql)


if __name__ == "__main__":
    unittest.main()
