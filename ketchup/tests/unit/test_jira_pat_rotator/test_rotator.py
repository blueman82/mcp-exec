#!/usr/bin/env python3
"""
Tests for PAT rotation orchestrator.

Verifies:
- Complete successful rotation flow
- Validation failure keeps old PAT
- Secrets update failure keeps old PAT
- Revocation failure still alerts ops
- Distributed lock prevents concurrent rotations
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from ketchup_jira_pat_rotator.rotator import PATRotator


class TestCompleteSuccessfulRotationFlow:
    """Tests for complete successful PAT rotation."""

    @pytest.mark.asyncio
    async def test_successful_rotation_creates_validates_and_revokes(self):
        """Test that successful rotation creates new PAT, validates, updates secrets, and revokes old."""
        rotator = PATRotator()

        # Mock all dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._mcp_client = AsyncMock()
        rotator._secrets_manager = AsyncMock()
        rotator._slack_notifier = AsyncMock()
        rotator._lock_manager = AsyncMock()

        # Mock MCP responses
        rotator._mcp_client.create_pat.return_value = {
            "pat": "new-pat-token-xyz",
            "expiryDate": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "id": "pat-123"
        }
        rotator._mcp_client.validate_pat.return_value = {
            "valid": True,
            "jiraUser": "automation-user"
        }
        rotator._mcp_client.revoke_pat.return_value = {
            "success": True,
            "revokedPatId": "old-pat-456"
        }

        # Mock secrets manager
        rotator._secrets_manager.get_current_pat.return_value = {
            "JIRA_PAT": "old-pat-token-abc",
            "JIRA_PAT_ID": "old-pat-456",
            "JIRA_PAT_EXPIRY": (datetime.utcnow() + timedelta(days=60)).isoformat()
        }
        rotator._secrets_manager.update_pat.return_value = True

        # Mock lock manager
        rotator._lock_manager.acquire.return_value = True
        rotator._lock_manager.release.return_value = True

        # Execute rotation
        result = await rotator.rotate()

        # Verify the complete flow
        assert result["status"] == "success"
        assert result["action"] == "rotated"
        assert result["newPatId"] == "pat-123"

        # Verify MCP calls
        rotator._mcp_client.create_pat.assert_called_once()
        rotator._mcp_client.validate_pat.assert_called_once_with("new-pat-token-xyz")
        rotator._mcp_client.revoke_pat.assert_called_once_with("old-pat-456")

        # Verify secrets update
        rotator._secrets_manager.update_pat.assert_called_once()

        # Verify Slack notification
        rotator._slack_notifier.notify_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_rotation_skipped_when_not_needed(self):
        """Test that rotation is skipped when expiry check indicates no rotation needed."""
        rotator = PATRotator()

        # Mock monitor to say rotation not needed
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = False
        rotator._mcp_client = AsyncMock()
        rotator._slack_notifier = AsyncMock()

        # Execute rotation
        result = await rotator.rotate()

        # Verify early exit
        assert result["status"] == "skipped"
        assert result["action"] == "no_rotation_needed"

        # Verify no MCP calls were made
        rotator._mcp_client.create_pat.assert_not_called()
        rotator._slack_notifier.notify_success.assert_not_called()


class TestValidationFailureKeepsOldPAT:
    """Tests for validation failure handling."""

    @pytest.mark.asyncio
    async def test_validation_failure_keeps_old_pat(self):
        """Test that new PAT is not used if validation fails."""
        rotator = PATRotator()

        # Mock all dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._mcp_client = AsyncMock()
        rotator._secrets_manager = AsyncMock()
        rotator._slack_notifier = AsyncMock()
        rotator._lock_manager = AsyncMock()

        # Mock create_pat to succeed
        rotator._mcp_client.create_pat.return_value = {
            "pat": "new-invalid-pat",
            "expiryDate": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "id": "pat-invalid"
        }

        # Mock validate_pat to fail
        rotator._mcp_client.validate_pat.return_value = {
            "valid": False,
            "error": "Invalid token format"
        }

        # Mock get current PAT
        rotator._secrets_manager.get_current_pat.return_value = {
            "JIRA_PAT": "old-pat-token-abc",
            "JIRA_PAT_ID": "old-pat-456"
        }

        # Mock lock manager
        rotator._lock_manager.acquire.return_value = True
        rotator._lock_manager.release.return_value = True

        # Execute rotation - should fail gracefully
        result = await rotator.rotate()

        # Verify failure status
        assert result["status"] == "failed"
        assert result["reason"] == "validation_failed"

        # Verify old PAT was NOT updated
        rotator._secrets_manager.update_pat.assert_not_called()

        # Verify failure notification
        rotator._slack_notifier.notify_failure.assert_called_once()

        # Verify attempt to revoke new invalid PAT
        rotator._mcp_client.revoke_pat.assert_called_once_with("pat-invalid")


class TestSecretsUpdateFailureKeepsOldPAT:
    """Tests for secrets manager failure handling."""

    @pytest.mark.asyncio
    async def test_secrets_update_failure_keeps_old_pat(self):
        """Test that old PAT is preserved if secrets update fails."""
        rotator = PATRotator()

        # Mock all dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._mcp_client = AsyncMock()
        rotator._secrets_manager = AsyncMock()
        rotator._slack_notifier = AsyncMock()
        rotator._lock_manager = AsyncMock()

        # Mock create and validate to succeed
        rotator._mcp_client.create_pat.return_value = {
            "pat": "new-pat-token-xyz",
            "expiryDate": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "id": "pat-123"
        }
        rotator._mcp_client.validate_pat.return_value = {
            "valid": True,
            "jiraUser": "automation-user"
        }

        # Mock secrets update to fail
        rotator._secrets_manager.get_current_pat.return_value = {
            "JIRA_PAT": "old-pat-token-abc",
            "JIRA_PAT_ID": "old-pat-456"
        }
        rotator._secrets_manager.update_pat.side_effect = Exception("Secrets Manager error")

        # Mock lock manager
        rotator._lock_manager.acquire.return_value = True
        rotator._lock_manager.release.return_value = True

        # Execute rotation
        result = await rotator.rotate()

        # Verify failure
        assert result["status"] == "failed"
        assert result["reason"] == "secrets_update_failed"

        # Verify new PAT was revoked as cleanup
        rotator._mcp_client.revoke_pat.assert_called_once_with("pat-123")

        # Verify failure alert
        rotator._slack_notifier.notify_failure.assert_called_once()


class TestRevocationFailureStillAlerts:
    """Tests for revocation failure handling."""

    @pytest.mark.asyncio
    async def test_revocation_failure_still_alerts_ops(self):
        """Test that failure to revoke old PAT still sends alert to ops."""
        rotator = PATRotator()

        # Mock all dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._mcp_client = AsyncMock()
        rotator._secrets_manager = AsyncMock()
        rotator._slack_notifier = AsyncMock()
        rotator._lock_manager = AsyncMock()

        # Mock create, validate, and update to succeed
        rotator._mcp_client.create_pat.return_value = {
            "pat": "new-pat-token-xyz",
            "expiryDate": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "id": "pat-123"
        }
        rotator._mcp_client.validate_pat.return_value = {
            "valid": True,
            "jiraUser": "automation-user"
        }
        rotator._mcp_client.revoke_pat.side_effect = Exception("Failed to revoke PAT")

        rotator._secrets_manager.get_current_pat.return_value = {
            "JIRA_PAT": "old-pat-token-abc",
            "JIRA_PAT_ID": "old-pat-456"
        }
        rotator._secrets_manager.update_pat.return_value = True

        # Mock lock manager
        rotator._lock_manager.acquire.return_value = True
        rotator._lock_manager.release.return_value = True

        # Execute rotation
        result = await rotator.rotate()

        # Verify partial success with revocation warning
        assert result["status"] == "partial_success"
        assert result["newPatRotated"] is True
        assert result["oldPatRevoked"] is False

        # Verify alert was sent about revocation failure
        rotator._slack_notifier.notify_partial_success.assert_called_once()


class TestDistributedLockPreventsConurrentRotations:
    """Tests for distributed locking."""

    @pytest.mark.asyncio
    async def test_distributed_lock_prevents_concurrent_rotations(self):
        """Test that distributed lock prevents concurrent rotations."""
        rotator = PATRotator()

        # Mock dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._mcp_client = AsyncMock()
        rotator._slack_notifier = AsyncMock()
        rotator._lock_manager = AsyncMock()

        # Mock lock acquisition to fail (another process has it)
        rotator._lock_manager.acquire.return_value = False

        # Execute rotation
        result = await rotator.rotate()

        # Verify early exit due to lock failure
        assert result["status"] == "skipped"
        assert result["reason"] == "lock_unavailable"

        # Verify no rotation work was done
        rotator._mcp_client.create_pat.assert_not_called()

    @pytest.mark.asyncio
    async def test_lock_is_released_after_rotation(self):
        """Test that lock is properly released after rotation completes."""
        rotator = PATRotator()

        # Mock all dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._mcp_client = AsyncMock()
        rotator._secrets_manager = AsyncMock()
        rotator._slack_notifier = AsyncMock()
        rotator._lock_manager = AsyncMock()

        # Mock successful rotation
        rotator._mcp_client.create_pat.return_value = {
            "pat": "new-pat-token-xyz",
            "expiryDate": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "id": "pat-123"
        }
        rotator._mcp_client.validate_pat.return_value = {
            "valid": True,
            "jiraUser": "automation-user"
        }
        rotator._mcp_client.revoke_pat.return_value = {
            "success": True,
            "revokedPatId": "old-pat-456"
        }

        rotator._secrets_manager.get_current_pat.return_value = {
            "JIRA_PAT": "old-pat-token-abc",
            "JIRA_PAT_ID": "old-pat-456"
        }
        rotator._secrets_manager.update_pat.return_value = True

        # Mock lock operations
        rotator._lock_manager.acquire.return_value = True
        rotator._lock_manager.release.return_value = True

        # Execute rotation
        result = await rotator.rotate()

        # Verify lock was acquired and released
        rotator._lock_manager.acquire.assert_called_once()
        rotator._lock_manager.release.assert_called_once()

        # Verify release was called even after successful rotation
        assert result["status"] == "success"


class TestRotationOrchestrationSequence:
    """Tests for correct orchestration sequence of rotation steps."""

    @pytest.mark.asyncio
    async def test_rotation_steps_execute_in_correct_order(self):
        """Test that rotation steps execute in the correct sequence."""
        rotator = PATRotator()

        # Create a list to track call order
        call_order = []

        # Mock all dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True

        rotator._mcp_client = AsyncMock()
        rotator._mcp_client.create_pat.side_effect = lambda: (call_order.append("create"), {
            "pat": "new-pat-token-xyz",
            "expiryDate": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "id": "pat-123"
        })[1]
        rotator._mcp_client.validate_pat.side_effect = lambda pat: (call_order.append("validate"), {
            "valid": True,
            "jiraUser": "automation-user"
        })[1]
        rotator._mcp_client.revoke_pat.side_effect = lambda pat_id: (call_order.append("revoke"), {
            "success": True,
            "revokedPatId": pat_id
        })[1]

        rotator._secrets_manager = AsyncMock()
        rotator._secrets_manager.get_current_pat.side_effect = lambda: (call_order.append("get_current"), {
            "JIRA_PAT": "old-pat-token-abc",
            "JIRA_PAT_ID": "old-pat-456"
        })[1]
        rotator._secrets_manager.update_pat.side_effect = lambda *args: (call_order.append("update_secrets"), True)[1]

        rotator._slack_notifier = AsyncMock()
        rotator._slack_notifier.notify_success.side_effect = lambda *args: (call_order.append("notify"), None)[1]

        rotator._lock_manager = AsyncMock()
        rotator._lock_manager.acquire.return_value = True
        rotator._lock_manager.release.return_value = True

        # Execute rotation
        result = await rotator.rotate()

        # Verify success
        assert result["status"] == "success"

        # Verify call order: create -> validate -> update -> revoke -> notify
        assert "create" in call_order
        assert "validate" in call_order
        assert "update_secrets" in call_order
        assert "revoke" in call_order
        assert "notify" in call_order

        # Verify validate comes after create
        assert call_order.index("validate") > call_order.index("create")

        # Verify update comes after validate
        assert call_order.index("update_secrets") > call_order.index("validate")

        # Verify revoke comes after update
        assert call_order.index("revoke") > call_order.index("update_secrets")


class TestRotatorErrorHandling:
    """Tests for error handling in rotation orchestrator."""

    @pytest.mark.asyncio
    async def test_monitor_error_triggers_alert(self):
        """Test that monitor errors trigger failure alert."""
        rotator = PATRotator()

        # Mock monitor to raise exception
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.side_effect = Exception("Monitor check failed")
        rotator._slack_notifier = AsyncMock()

        # Execute rotation
        result = await rotator.rotate()

        # Verify failure - caught as unexpected_error
        assert result["status"] == "failed"
        assert result.get("error") == "Monitor check failed"

        # Verify alert was sent
        rotator._slack_notifier.notify_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_acquisition_timeout_handled_gracefully(self):
        """Test that lock acquisition timeout is handled gracefully."""
        rotator = PATRotator()

        # Mock dependencies
        rotator._monitor = MagicMock()
        rotator._monitor.should_rotate.return_value = True
        rotator._lock_manager = AsyncMock()

        # Mock lock acquisition timeout
        rotator._lock_manager.acquire.side_effect = Exception("Lock timeout")
        rotator._slack_notifier = AsyncMock()

        # Execute rotation
        result = await rotator.rotate()

        # Verify graceful handling - exception is caught as lock error
        assert result["status"] == "skipped"
        assert result.get("reason") == "lock_unavailable"
