"""security_validation.py

Core security and validation services for flag review functionality.
Provides centralized user verification, permission checking, security compliance,
and input sanitization services for secure operations.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class UserVerificationService:
    """Handles user authentication and verification operations."""

    def __init__(self):
        """Initialize the user verification service."""
        self.verified_users = set()
        self.blocked_users = set()

    def verify_user_identity(self, user_id: str, workspace_id: str = "T018BPFUD75") -> Tuple[bool, str]:
        """Verify user identity and workspace membership."""
        if not user_id or not isinstance(user_id, str):
            return False, "Invalid user ID"

        if not user_id.startswith("U"):
            return False, "Invalid user ID format"

        if workspace_id != "T018BPFUD75":
            return False, "Invalid workspace"

        if user_id in self.blocked_users:
            return False, "User is blocked"

        return True, "User verified"

    def validate_user_format(self, user_id: str) -> bool:
        """Validate user ID format compliance."""
        if not user_id:
            return False
        return user_id.startswith("U") and len(user_id) >= 9

    def extract_user_info(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Extract and validate user information from payload."""
        user_data = payload.get("user", {})
        return {
            "user_id": user_data.get("id", ""),
            "username": user_data.get("username", "Unknown"),
            "real_name": user_data.get("real_name", ""),
            "team_id": user_data.get("team_id", "")
        }

    def check_user_status(self, user_id: str) -> Dict[str, Any]:
        """Check comprehensive user status and permissions."""
        is_verified = user_id in self.verified_users
        is_blocked = user_id in self.blocked_users

        return {
            "user_id": user_id,
            "is_verified": is_verified,
            "is_blocked": is_blocked,
            "can_interact": is_verified and not is_blocked,
            "verification_level": "high" if is_verified else "basic"
        }

    def mark_user_verified(self, user_id: str) -> bool:
        """Mark user as verified for enhanced permissions."""
        if self.validate_user_format(user_id):
            self.verified_users.add(user_id)
            return True
        return False

    def block_user(self, user_id: str, reason: str = "Security violation") -> bool:
        """Block user from system interactions."""
        if self.validate_user_format(user_id):
            self.blocked_users.add(user_id)
            logger.warning(f"User {user_id} blocked: {reason}")
            return True
        return False


class PermissionValidationService:
    """Handles permission checking and authorization validation."""

    def __init__(self):
        """Initialize the permission validation service."""
        self.admin_users = set()
        self.moderator_users = set()

    def validate_admin_permissions(self, user_id: str) -> bool:
        """Check if user has admin permissions."""
        return user_id in self.admin_users

    def validate_moderator_permissions(self, user_id: str) -> bool:
        """Check if user has moderator permissions."""
        return user_id in self.moderator_users or user_id in self.admin_users

    def check_channel_permissions(self, user_id: str, channel_id: str) -> Dict[str, bool]:
        """Check user permissions for specific channel operations."""
        is_admin = self.validate_admin_permissions(user_id)
        is_moderator = self.validate_moderator_permissions(user_id)

        return {
            "can_flag": True,  # All users can flag
            "can_acknowledge": is_moderator,
            "can_reply": is_moderator,
            "can_moderate": is_admin,
            "can_delete": is_admin
        }

    def validate_action_permission(self, user_id: str, action: str) -> Tuple[bool, str]:
        """Validate user permission for specific action."""
        permissions = {
            "flag_content": True,
            "acknowledge_flag": self.validate_moderator_permissions(user_id),
            "reply_to_flag": self.validate_moderator_permissions(user_id),
            "delete_flag": self.validate_admin_permissions(user_id),
            "bulk_operations": self.validate_admin_permissions(user_id)
        }

        has_permission = permissions.get(action, False)
        message = "Permission granted" if has_permission else f"Insufficient permissions for {action}"

        return has_permission, message

    def check_rate_limit_exemption(self, user_id: str) -> bool:
        """Check if user is exempt from rate limiting."""
        return self.validate_admin_permissions(user_id)

    def add_admin_user(self, user_id: str) -> bool:
        """Add user to admin list."""
        if self._validate_user_id_format(user_id):
            self.admin_users.add(user_id)
            return True
        return False

    def add_moderator_user(self, user_id: str) -> bool:
        """Add user to moderator list."""
        if self._validate_user_id_format(user_id):
            self.moderator_users.add(user_id)
            return True
        return False

    def _validate_user_id_format(self, user_id: str) -> bool:
        """Validate user ID format for permission assignment."""
        return bool(user_id and user_id.startswith("U") and len(user_id) >= 9)


class SecurityComplianceService:
    """Handles security monitoring and compliance checks."""

    def __init__(self):
        """Initialize the security compliance service."""
        self.security_events = []
        self.compliance_violations = []

    def scan_for_security_threats(self, content: str) -> Dict[str, Any]:
        """Scan content for potential security threats."""
        threats = []
        severity = "low"

        # Check for script injection
        script_patterns = [r'<script.*?>', r'javascript:', r'onclick=', r'onerror=']
        for pattern in script_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                threats.append("Script injection detected")
                severity = "high"
                break

        # Check for excessive URLs
        url_count = len(re.findall(r'https?://', content))
        if url_count > 5:
            threats.append("Excessive URL content")
            severity = max(severity, "medium")

        # Check for suspicious patterns
        suspicious_patterns = [r'eval\(', r'exec\(', r'system\(', r'shell_exec']
        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                threats.append("Suspicious code pattern")
                severity = "high"
                break

        return {
            "threats_found": len(threats) > 0,
            "threat_list": threats,
            "severity": severity,
            "scan_timestamp": datetime.now(timezone.utc).isoformat()
        }

    def validate_compliance_requirements(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against compliance requirements."""
        violations = []

        # Check for required fields
        required_fields = ["user_id", "timestamp", "content"]
        for field in required_fields:
            if field not in data:
                violations.append(f"Missing required field: {field}")

        # Check data retention compliance
        if "timestamp" in data:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
                age_days = (datetime.now(timezone.utc) - timestamp).days
                if age_days > 90:  # 90-day retention policy
                    violations.append("Data exceeds retention period")
            except ValueError:
                violations.append("Invalid timestamp format")

        return {
            "is_compliant": len(violations) == 0,
            "violations": violations,
            "compliance_level": "full" if len(violations) == 0 else "partial"
        }

    def log_security_event(self, event_type: str, user_id: str, details: Dict[str, Any]) -> None:
        """Log security event for monitoring."""
        event = {
            "event_type": event_type,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details
        }
        self.security_events.append(event)

        if len(self.security_events) > 1000:  # Rotate logs
            self.security_events = self.security_events[-500:]

    def check_anomaly_patterns(self, user_id: str, action: str) -> bool:
        """Check for anomalous user behavior patterns."""
        # Count recent events for this user
        recent_events = [
            e for e in self.security_events
            if e["user_id"] == user_id and
            (datetime.now(timezone.utc) - datetime.fromisoformat(e["timestamp"])).seconds < 300
        ]

        # Check for rapid fire actions
        if len(recent_events) > 10:
            return True

        # Check for suspicious action sequences
        action_types = [e["event_type"] for e in recent_events]
        if action_types.count("failed_authentication") > 3:
            return True

        return False


class InputSanitationService:
    """Handles input validation and sanitization operations."""

    def __init__(self):
        """Initialize the input sanitation service."""
        self.max_length = 3000
        self.blocked_patterns = []

    def sanitize_text_input(self, text: str) -> str:
        """Sanitize text input for safe processing."""
        if not text:
            return ""

        # Remove control characters except newlines and tabs
        sanitized = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")

        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized.strip())

        # Truncate if too long
        if len(sanitized) > self.max_length:
            sanitized = sanitized[:self.max_length-3] + "..."

        return sanitized

    def validate_input_length(self, text: str, min_length: int = 10, max_length: int = 3000) -> Tuple[bool, str]:
        """Validate input length requirements."""
        if len(text) < min_length:
            return False, f"Input too short (minimum {min_length} characters)"

        if len(text) > max_length:
            return False, f"Input too long (maximum {max_length} characters)"

        return True, "Valid length"

    def detect_spam_patterns(self, text: str) -> Dict[str, Any]:
        """Detect potential spam patterns in text."""
        spam_indicators = []

        # Check for repetitive characters
        for char in set(text):
            if text.count(char * 10) > 0:
                spam_indicators.append("Repetitive characters")
                break

        # Check for excessive capitalization
        if len(text) > 20 and sum(1 for c in text if c.isupper()) / len(text) > 0.7:
            spam_indicators.append("Excessive capitalization")

        # Check for excessive punctuation
        punct_count = sum(1 for c in text if c in "!?.,;:")
        if len(text) > 20 and punct_count / len(text) > 0.3:
            spam_indicators.append("Excessive punctuation")

        return {
            "is_spam": len(spam_indicators) > 0,
            "indicators": spam_indicators,
            "spam_score": len(spam_indicators)
        }

    def validate_channel_format(self, channel_id: str) -> Tuple[bool, str]:
        """Validate channel ID format."""
        if not channel_id:
            return False, "Channel ID required"

        valid_prefixes = ["C", "G", "D"]  # Channel, Group, DM
        if not any(channel_id.startswith(prefix) for prefix in valid_prefixes):
            return False, "Invalid channel ID format"

        if len(channel_id) < 9:
            return False, "Channel ID too short"

        return True, "Valid channel ID"

    def clean_message_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate message metadata."""
        cleaned = {}

        safe_fields = ["channel_id", "user_id", "timestamp", "message_ts", "thread_ts"]
        for field in safe_fields:
            if field in metadata:
                value = metadata[field]
                if isinstance(value, str):
                    cleaned[field] = self.sanitize_text_input(value)
                else:
                    cleaned[field] = value

        return cleaned




class SecurityValidationOrchestrator:
    """Main orchestrator for core security and validation services."""

    def __init__(self):
        """Initialize the security validation orchestrator with core services."""
        self.user_verification = UserVerificationService()
        self.permission_validation = PermissionValidationService()
        self.security_compliance = SecurityComplianceService()
        self.input_sanitation = InputSanitationService()

    def get_user_verification_service(self) -> UserVerificationService:
        """Get the user verification service instance."""
        return self.user_verification

    def get_permission_validation_service(self) -> PermissionValidationService:
        """Get the permission validation service instance."""
        return self.permission_validation

    def get_security_compliance_service(self) -> SecurityComplianceService:
        """Get the security compliance service instance."""
        return self.security_compliance

    def get_input_sanitation_service(self) -> InputSanitationService:
        """Get the input sanitation service instance."""
        return self.input_sanitation


# Factory function for service creation
def create_security_validation_services() -> SecurityValidationOrchestrator:
    """Create and return a configured security validation services orchestrator.

    Returns:
        Configured SecurityValidationOrchestrator instance.
    """
    return SecurityValidationOrchestrator()