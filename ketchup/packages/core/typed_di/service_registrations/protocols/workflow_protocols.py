"""
Workflow Management Protocol Definitions.

This module contains protocol definitions for workflow management services
in the TypedDI service registration system.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class WorkflowEngineServiceProtocol(Protocol):
    """Protocol for workflow engine operations."""

    async def start_workflow(self, workflow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Start a workflow with given data."""
        ...

    async def stop_workflow(self, workflow_id: str) -> bool:
        """Stop a running workflow."""
        ...

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a workflow."""
        ...

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        ...


@runtime_checkable
class TaskManagementServiceProtocol(Protocol):
    """Protocol for task management operations."""

    async def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task and return task ID."""
        ...

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing task."""
        ...

    async def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        ...

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task."""
        ...


@runtime_checkable
class ProcessAutomationServiceProtocol(Protocol):
    """Protocol for process automation operations."""

    async def automate_process(self, process_id: str, config: Dict[str, Any]) -> bool:
        """Automate a process with given configuration."""
        ...

    async def schedule_automation(self, schedule: Dict[str, Any]) -> str:
        """Schedule an automation and return schedule ID."""
        ...

    async def trigger_automation(self, automation_id: str) -> bool:
        """Trigger an automation manually."""
        ...

    async def get_automation_status(self, automation_id: str) -> Dict[str, Any]:
        """Get the status of an automation."""
        ...


@runtime_checkable
class StateManagementServiceProtocol(Protocol):
    """Protocol for state management operations."""

    async def save_state(self, entity_id: str, state: Dict[str, Any]) -> bool:
        """Save state for an entity."""
        ...

    async def load_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Load state for an entity."""
        ...

    async def update_state(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update state for an entity."""
        ...

    async def delete_state(self, entity_id: str) -> bool:
        """Delete state for an entity."""
        ...


@runtime_checkable
class TransitionServiceProtocol(Protocol):
    """Protocol for state transition operations."""

    async def transition_state(
        self,
        entity_id: str,
        from_state: str,
        to_state: str
    ) -> bool:
        """Transition entity from one state to another."""
        ...

    async def validate_transition(
        self,
        entity_id: str,
        from_state: str,
        to_state: str
    ) -> bool:
        """Validate if a transition is allowed."""
        ...

    async def get_transition_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get transition history for an entity."""
        ...

    async def rollback_transition(self, entity_id: str, steps: int = 1) -> bool:
        """Rollback transitions for an entity."""
        ...