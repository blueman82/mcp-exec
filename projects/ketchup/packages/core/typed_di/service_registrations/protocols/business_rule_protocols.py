"""
Business Rule Service Protocols

Protocol definitions for business rule engine services including rule engines,
policy validation, compliance checking, auditing, and governance systems.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

__all__ = [
    "RuleEngineServiceProtocol",
    "PolicyValidationServiceProtocol",
    "ComplianceServiceProtocol",
    "AuditServiceProtocol",
    "GovernanceServiceProtocol",
    "ConfigurationServiceProtocol",
]


@runtime_checkable
class RuleEngineServiceProtocol(Protocol):
    """Protocol for rule engine service operations."""

    async def evaluate_rule(self, rule_id: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a business rule against given context.

        Args:
            rule_id: Identifier for the rule to evaluate
            context: Context data for rule evaluation

        Returns:
            True if rule passes, False otherwise
        """
        ...

    async def add_rule(self, rule_id: str, rule_definition: Dict[str, Any]) -> None:
        """
        Add a new business rule to the engine.

        Args:
            rule_id: Unique identifier for the rule
            rule_definition: Rule definition and configuration
        """
        ...


@runtime_checkable
class PolicyValidationServiceProtocol(Protocol):
    """Protocol for policy validation service operations."""

    async def validate_policy(self, policy_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data against a specific policy.

        Args:
            policy_id: Identifier for the policy to validate against
            data: Data to validate

        Returns:
            Validation result with status and details
        """
        ...

    async def get_policy_requirements(self, policy_id: str) -> List[str]:
        """
        Get requirements for a specific policy.

        Args:
            policy_id: Identifier for the policy

        Returns:
            List of policy requirements
        """
        ...


@runtime_checkable
class ComplianceServiceProtocol(Protocol):
    """Protocol for compliance service operations."""

    async def check_compliance(self, entity_id: str, compliance_type: str) -> Dict[str, Any]:
        """
        Check compliance status for an entity.

        Args:
            entity_id: Identifier for the entity to check
            compliance_type: Type of compliance to check

        Returns:
            Compliance status and details
        """
        ...

    async def record_compliance_event(self, event_data: Dict[str, Any]) -> None:
        """
        Record a compliance-related event.

        Args:
            event_data: Event data to record
        """
        ...


@runtime_checkable
class AuditServiceProtocol(Protocol):
    """Protocol for audit service operations."""

    async def log_audit_event(self, event_type: str, details: Dict[str, Any]) -> str:
        """
        Log an audit event.

        Args:
            event_type: Type of audit event
            details: Event details and metadata

        Returns:
            Audit event ID
        """
        ...

    async def get_audit_trail(
        self, entity_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for an entity.

        Args:
            entity_id: Identifier for the entity
            start_date: Optional start date for the trail
            end_date: Optional end date for the trail

        Returns:
            List of audit events
        """
        ...


@runtime_checkable
class GovernanceServiceProtocol(Protocol):
    """Protocol for governance service operations."""

    async def apply_governance_rules(self, resource_id: str, action: str) -> Dict[str, Any]:
        """
        Apply governance rules to a resource action.

        Args:
            resource_id: Identifier for the resource
            action: Action being performed

        Returns:
            Governance decision and any restrictions
        """
        ...

    async def get_governance_policies(self, resource_type: str) -> List[Dict[str, Any]]:
        """
        Get governance policies for a resource type.

        Args:
            resource_type: Type of resource

        Returns:
            List of applicable governance policies
        """
        ...


@runtime_checkable
class ConfigurationServiceProtocol(Protocol):
    """Protocol for configuration management operations."""

    async def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        ...

    async def set_config(self, key: str, value: Any) -> None:
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        ...

    async def get_all_configs(self) -> Dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dictionary of all configurations
        """
        ...

    async def reload_config(self) -> None:
        """Reload configuration from source."""
        ...
