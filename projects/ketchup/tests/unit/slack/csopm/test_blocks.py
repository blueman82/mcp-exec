#!/usr/bin/env python3
"""
CSOPM Notification Blocks Tests.

Unit tests for the CSOPMNotificationBlocks Block Kit builders, verifying:
1. Assignment notification structure and content
2. RCA reminder structure and warning messages
3. Closure reminder structure and linked ticket warnings
4. Acknowledgment confirmation messages
5. Create follow-up modal structure and dynamic dropdowns
6. Fallback text generation

These tests were moved from tests/unit/csopm_notifier/test_slack_notifier.py
to align with the new package structure in packages/slack/csopm/blocks.py.
"""

import unittest
from datetime import datetime, timezone

from packages.core.typed_di.protocols import CSOPMTicket
from packages.slack.csopm.blocks import CSOPMNotificationBlocks


def _make_ticket(
    key: str = "CSOPM-1234",
    summary: str = "Test Issue Summary",
    assignee: str = "testuser",
    status: str = "New",
    exigence_id: str = None,
) -> CSOPMTicket:
    """Helper to create a CSOPMTicket."""
    return CSOPMTicket(
        key=key,
        summary=summary,
        assignee_username=assignee,
        created_at=datetime.now(timezone.utc),
        status=status,
        exigence_id=exigence_id,
    )


class TestCSOPMNotificationBlocksBuildAssignment(unittest.TestCase):
    """Test assignment notification block builder."""

    def test_build_assignment_notification_structure(self):
        """Test assignment notification has correct structure."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        # Verify block types
        block_types = [b["type"] for b in blocks]
        self.assertIn("header", block_types)
        self.assertIn("section", block_types)
        self.assertIn("actions", block_types)
        self.assertIn("divider", block_types)
        self.assertIn("context", block_types)

    def test_build_assignment_notification_has_five_buttons(self):
        """Test assignment notification has 5 action buttons."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        # Find actions block
        actions_block = next(b for b in blocks if b["type"] == "actions")
        elements = actions_block["elements"]

        self.assertEqual(len(elements), 5)

        # Verify button action IDs
        action_ids = [e["action_id"] for e in elements]
        self.assertIn("csopm_acknowledge", action_ids)
        self.assertIn("csopm_create_followup", action_ids)
        self.assertIn("csopm_mark_complete", action_ids)
        self.assertIn("csopm_stop_reminders", action_ids)
        self.assertIn("csopm_view_jira", action_ids)

    def test_build_assignment_notification_includes_ticket_key_as_value(self):
        """Test that ticket key is passed as button value."""
        ticket = _make_ticket(key="CSOPM-9999")
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        actions_block = next(b for b in blocks if b["type"] == "actions")
        for element in actions_block["elements"]:
            self.assertEqual(element["value"], "CSOPM-9999")

    def test_build_assignment_notification_jira_url(self):
        """Test that JIRA URL is included in View in JIRA button."""
        ticket = _make_ticket(key="CSOPM-1234")
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        actions_block = next(b for b in blocks if b["type"] == "actions")
        view_jira_button = next(
            e for e in actions_block["elements"] if e["action_id"] == "csopm_view_jira"
        )

        self.assertIn("url", view_jira_button)
        self.assertIn("CSOPM-1234", view_jira_button["url"])

    def test_build_assignment_notification_includes_exigence_id(self):
        """Test that Exigence ID is included in blocks when present."""
        ticket = _make_ticket(exigence_id="EX-12345")
        blocks = CSOPMNotificationBlocks.build_assignment_notification(ticket)

        # Find the section block with ticket details
        section_blocks = [b for b in blocks if b.get("type") == "section"]
        self.assertTrue(len(section_blocks) > 0)

        # Check that Exigence ID is in one of the section blocks
        found_exigence = False
        for block in section_blocks:
            text = block.get("text", {}).get("text", "")
            if "EX-12345" in text:
                found_exigence = True
                break

        self.assertTrue(found_exigence, "Exigence ID not found in blocks")


class TestCSOPMNotificationBlocksBuildRCAReminder(unittest.TestCase):
    """Test RCA reminder notification block builder."""

    def test_build_rca_reminder_structure(self):
        """Test RCA reminder has correct structure."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_rca_reminder(
            ticket=ticket,
            days_old=10,
            ping_count=1,
        )

        block_types = [b["type"] for b in blocks]
        self.assertIn("header", block_types)
        self.assertIn("section", block_types)
        self.assertIn("actions", block_types)

    def test_build_rca_reminder_shows_warning_at_high_ping_count(self):
        """Test RCA reminder shows warning at ping count >= 2."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_rca_reminder(
            ticket=ticket,
            days_old=10,
            ping_count=2,
        )

        # Find context block with warning
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        context_texts = [e.get("text", "") for b in context_blocks for e in b.get("elements", [])]

        has_warning = any("escalated" in text.lower() for text in context_texts)
        self.assertTrue(has_warning, "Warning about escalation not found")

    def test_build_rca_reminder_includes_days_old(self):
        """Test RCA reminder includes days old info."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_rca_reminder(
            ticket=ticket,
            days_old=15,
            ping_count=1,
        )

        # Find section block with ticket details
        section_blocks = [b for b in blocks if b.get("type") == "section"]
        section_texts = [b.get("text", {}).get("text", "") for b in section_blocks]

        has_days = any("15 days old" in text for text in section_texts)
        self.assertTrue(has_days, "Days old info not found in blocks")

    def test_build_rca_reminder_includes_ping_count_in_header(self):
        """Test RCA reminder includes ping count in header."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_rca_reminder(
            ticket=ticket,
            days_old=10,
            ping_count=2,
        )

        # Find header block
        header_block = next(b for b in blocks if b["type"] == "header")
        header_text = header_block["text"]["text"]

        self.assertIn("Ping 2/3", header_text)


class TestCSOPMNotificationBlocksBuildClosureReminder(unittest.TestCase):
    """Test closure reminder notification block builder."""

    def test_build_closure_reminder_structure(self):
        """Test closure reminder has correct structure."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_closure_reminder(
            ticket=ticket,
            days_old=50,
            ping_count=1,
            has_open_linked=False,
        )

        block_types = [b["type"] for b in blocks]
        self.assertIn("header", block_types)
        self.assertIn("actions", block_types)

        # Find actions block
        actions_block = next(b for b in blocks if b["type"] == "actions")
        action_ids = [e["action_id"] for e in actions_block["elements"]]

        self.assertIn("csopm_close_ticket", action_ids)
        self.assertIn("csopm_snooze", action_ids)

    def test_build_closure_reminder_shows_linked_tickets_warning(self):
        """Test closure reminder shows warning about linked tickets."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_closure_reminder(
            ticket=ticket,
            days_old=50,
            ping_count=1,
            has_open_linked=True,
        )

        context_blocks = [b for b in blocks if b.get("type") == "context"]
        context_texts = [e.get("text", "") for b in context_blocks for e in b.get("elements", [])]

        has_linked_warning = any("linked" in text.lower() for text in context_texts)
        self.assertTrue(has_linked_warning, "Linked tickets warning not found")

    def test_build_closure_reminder_shows_escalation_warning_at_high_ping(self):
        """Test closure reminder shows escalation warning at ping count >= 2."""
        ticket = _make_ticket()
        blocks = CSOPMNotificationBlocks.build_closure_reminder(
            ticket=ticket,
            days_old=50,
            ping_count=2,
            has_open_linked=False,
        )

        context_blocks = [b for b in blocks if b.get("type") == "context"]
        context_texts = [e.get("text", "") for b in context_blocks for e in b.get("elements", [])]

        has_escalation_warning = any("escalated" in text.lower() for text in context_texts)
        self.assertTrue(has_escalation_warning, "Escalation warning not found")


class TestCSOPMNotificationBlocksBuildAcknowledgment(unittest.TestCase):
    """Test acknowledgment confirmation message builder."""

    def test_build_acknowledgment_confirmation(self):
        """Test acknowledgment confirmation message."""
        blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
            ticket_key="CSOPM-1234",
            action_type="acknowledged",
        )

        self.assertTrue(len(blocks) > 0)

        # Find section with confirmation text
        section = next(b for b in blocks if b["type"] == "section")
        text = section["text"]["text"]

        self.assertIn("CSOPM-1234", text)
        self.assertIn("acknowledged", text)

    def test_build_acknowledgment_confirmation_done_type(self):
        """Test acknowledgment confirmation for done action type."""
        blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
            ticket_key="CSOPM-5678",
            action_type="done",
        )

        section = next(b for b in blocks if b["type"] == "section")
        text = section["text"]["text"]

        self.assertIn("CSOPM-5678", text)
        self.assertIn("marked as done", text)

    def test_build_acknowledgment_confirmation_snoozed_type(self):
        """Test acknowledgment confirmation for snoozed action type."""
        blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
            ticket_key="CSOPM-9999",
            action_type="snoozed",
        )

        section = next(b for b in blocks if b["type"] == "section")
        text = section["text"]["text"]

        self.assertIn("CSOPM-9999", text)
        self.assertIn("snoozed", text)

    def test_build_acknowledgment_confirmation_closed_type(self):
        """Test acknowledgment confirmation for closed action type."""
        blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
            ticket_key="CSOPM-1111",
            action_type="closed",
        )

        section = next(b for b in blocks if b["type"] == "section")
        text = section["text"]["text"]

        self.assertIn("CSOPM-1111", text)
        self.assertIn("closed", text)

    def test_build_acknowledgment_confirmation_has_context(self):
        """Test acknowledgment confirmation includes context with timestamp."""
        blocks = CSOPMNotificationBlocks.build_acknowledgment_confirmation(
            ticket_key="CSOPM-1234",
            action_type="acknowledged",
        )

        context_block = next(b for b in blocks if b["type"] == "context")
        context_text = context_block["elements"][0]["text"]

        self.assertIn("Updated at", context_text)
        self.assertIn("UTC", context_text)


class TestCSOPMNotificationBlocksBuildModal(unittest.TestCase):
    """Test create follow-up modal builder."""

    def test_build_create_followup_modal(self):
        """Test create followup modal structure."""
        ticket = _make_ticket()
        modal = CSOPMNotificationBlocks.build_create_followup_modal(ticket)

        self.assertEqual(modal["type"], "modal")
        self.assertEqual(modal["callback_id"], "csopm_create_followup_modal")
        # private_metadata is now JSON format with ticket_key
        import json
        metadata = json.loads(modal["private_metadata"])
        self.assertEqual(metadata["ticket_key"], ticket.key)
        self.assertIn("blocks", modal)

        # Verify input blocks are present
        block_types = [b["type"] for b in modal["blocks"]]
        self.assertIn("input", block_types)

        # Verify project and issue type blocks exist (fallback text inputs)
        block_ids = [b.get("block_id", "") for b in modal["blocks"]]
        self.assertIn("project_block", block_ids)
        self.assertIn("issue_type_block", block_ids)
        self.assertIn("summary_block", block_ids)
        self.assertIn("description_block", block_ids)

    def test_build_create_followup_modal_with_dynamic_projects(self):
        """Test create followup modal with dynamic project dropdown."""
        ticket = _make_ticket()
        projects = [
            {"key": "CSOPM", "name": "CSO Project Management"},
            {"key": "OTHER", "name": "Other Project"},
        ]
        modal = CSOPMNotificationBlocks.build_create_followup_modal(ticket, projects=projects)

        # Find project block
        project_block = next(b for b in modal["blocks"] if b.get("block_id") == "project_block")

        # Verify it's a static_select with options
        element = project_block["element"]
        self.assertEqual(element["type"], "static_select")
        self.assertEqual(len(element["options"]), 2)
        self.assertEqual(element["options"][0]["value"], "CSOPM")
        self.assertEqual(element["options"][1]["value"], "OTHER")

    def test_build_create_followup_modal_with_dynamic_issue_types(self):
        """Test create followup modal with dynamic issue type dropdown."""
        ticket = _make_ticket()
        issue_types = [
            {"id": "1", "name": "Task"},
            {"id": "2", "name": "Bug"},
            {"id": "3", "name": "Story"},
        ]
        modal = CSOPMNotificationBlocks.build_create_followup_modal(ticket, issue_types=issue_types)

        # Find issue type block
        issue_type_block = next(
            b for b in modal["blocks"] if b.get("block_id") == "issue_type_block"
        )

        # Verify it's a static_select with options
        element = issue_type_block["element"]
        self.assertEqual(element["type"], "static_select")
        self.assertEqual(len(element["options"]), 3)
        self.assertEqual(element["options"][0]["value"], "1")
        self.assertEqual(element["options"][0]["text"]["text"], "Task")

    def test_build_create_followup_modal_has_submit_and_close(self):
        """Test create followup modal has submit and close buttons."""
        ticket = _make_ticket()
        modal = CSOPMNotificationBlocks.build_create_followup_modal(ticket)

        self.assertIn("submit", modal)
        self.assertEqual(modal["submit"]["text"], "Create")

        self.assertIn("close", modal)
        self.assertEqual(modal["close"]["text"], "Cancel")

    def test_build_create_followup_modal_description_has_parent_reference(self):
        """Test create followup modal description pre-fills with parent reference."""
        ticket = _make_ticket(key="CSOPM-1234")
        modal = CSOPMNotificationBlocks.build_create_followup_modal(ticket)

        # Find description block
        description_block = next(
            b for b in modal["blocks"] if b.get("block_id") == "description_block"
        )

        initial_value = description_block["element"]["initial_value"]
        self.assertIn("CSOPM-1234", initial_value)
        self.assertIn("Follow-up ticket for", initial_value)


class TestCSOPMNotificationBlocksFallbackText(unittest.TestCase):
    """Test fallback text generation."""

    def test_get_fallback_text_assignment(self):
        """Test fallback text for assignment notification."""
        text = CSOPMNotificationBlocks.get_fallback_text(
            notification_type="assignment",
            ticket_key="CSOPM-1234",
        )

        self.assertIn("CSOPM-1234", text)
        self.assertIn("jira.corp.adobe.com", text)
        self.assertIn("assigned", text.lower())

    def test_get_fallback_text_rca(self):
        """Test fallback text for RCA reminder."""
        text = CSOPMNotificationBlocks.get_fallback_text(
            notification_type="rca",
            ticket_key="CSOPM-5678",
        )

        self.assertIn("CSOPM-5678", text)
        self.assertIn("jira.corp.adobe.com", text)
        self.assertIn("RCA", text)

    def test_get_fallback_text_closure(self):
        """Test fallback text for closure reminder."""
        text = CSOPMNotificationBlocks.get_fallback_text(
            notification_type="closure",
            ticket_key="CSOPM-9999",
        )

        self.assertIn("CSOPM-9999", text)
        self.assertIn("jira.corp.adobe.com", text)
        self.assertIn("Closure", text)

    def test_get_fallback_text_unknown_type(self):
        """Test fallback text for unknown notification type."""
        text = CSOPMNotificationBlocks.get_fallback_text(
            notification_type="unknown",
            ticket_key="CSOPM-1111",
        )

        self.assertIn("CSOPM-1111", text)
        self.assertIn("jira.corp.adobe.com", text)


if __name__ == "__main__":
    unittest.main()
