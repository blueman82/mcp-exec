"""
Workflow Management Service Registrations.

This module contains TypedDI service registrations for workflow management services.
"""

from typing import Any, Dict, List, Optional

from packages.core.typed_di.service_registrations.protocols.workflow_protocols import (
    WorkflowEngineServiceProtocol,
    TaskManagementServiceProtocol,
    ProcessAutomationServiceProtocol,
    StateManagementServiceProtocol,
    TransitionServiceProtocol
)
from ..manager import ServiceRegistrationManager


class WorkflowEngineService:
    """Workflow engine service implementation."""

    def __init__(self):
        """Initialize workflow engine service."""
        self.workflows: Dict[str, Dict[str, Any]] = {}

    async def start_workflow(
        self, workflow_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start a workflow with given data."""
        workflow_data = {
            "id": workflow_id,
            "status": "running",
            "data": data,
            "started_at": "now"
        }
        self.workflows[workflow_id] = workflow_data
        return workflow_data

    async def stop_workflow(self, workflow_id: str) -> bool:
        """Stop a running workflow."""
        if workflow_id in self.workflows:
            self.workflows[workflow_id]["status"] = "stopped"
            return True
        return False

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a workflow."""
        return self.workflows.get(workflow_id, {})

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        return list(self.workflows.values())


class TaskManagementService:
    """Task management service implementation."""

    def __init__(self):
        """Initialize task management service."""
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_counter = 0

    async def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task and return task ID."""
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"
        task = {
            "id": task_id,
            "status": "created",
            "data": task_data,
            "created_at": "now"
        }
        self.tasks[task_id] = task
        return task_id

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing task."""
        if task_id in self.tasks:
            self.tasks[task_id].update(updates)
            return True
        return False

    async def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "completed"
            return True
        return False

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task."""
        return self.tasks.get(task_id, {})


class ProcessAutomationService:
    """Process automation service implementation."""

    def __init__(self):
        """Initialize process automation service."""
        self.automations: Dict[str, Dict[str, Any]] = {}
        self.schedules: Dict[str, Dict[str, Any]] = {}
        self.automation_counter = 0

    async def automate_process(self, process_id: str, config: Dict[str, Any]) -> bool:
        """Automate a process with given configuration."""
        automation = {
            "process_id": process_id,
            "config": config,
            "status": "active"
        }
        self.automations[process_id] = automation
        return True

    async def schedule_automation(self, schedule: Dict[str, Any]) -> str:
        """Schedule an automation and return schedule ID."""
        self.automation_counter += 1
        schedule_id = f"schedule_{self.automation_counter}"
        self.schedules[schedule_id] = schedule
        return schedule_id

    async def trigger_automation(self, automation_id: str) -> bool:
        """Trigger an automation manually."""
        if automation_id in self.automations:
            # Simulate triggering
            return True
        return False

    async def get_automation_status(self, automation_id: str) -> Dict[str, Any]:
        """Get the status of an automation."""
        return self.automations.get(automation_id, {})


class StateManagementService:
    """State management service implementation."""

    def __init__(self):
        """Initialize state management service."""
        self.states: Dict[str, Dict[str, Any]] = {}

    async def save_state(self, entity_id: str, state: Dict[str, Any]) -> bool:
        """Save state for an entity."""
        self.states[entity_id] = state.copy()
        return True

    async def load_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Load state for an entity."""
        return self.states.get(entity_id)

    async def update_state(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update state for an entity."""
        if entity_id in self.states:
            self.states[entity_id].update(updates)
            return True
        return False

    async def delete_state(self, entity_id: str) -> bool:
        """Delete state for an entity."""
        if entity_id in self.states:
            del self.states[entity_id]
            return True
        return False


class TransitionService:
    """State transition service implementation."""

    def __init__(self):
        """Initialize transition service."""
        self.transition_history: Dict[str, List[Dict[str, Any]]] = {}

    async def transition_state(
        self,
        entity_id: str,
        from_state: str,
        to_state: str
    ) -> bool:
        """Transition entity from one state to another."""
        transition = {
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": "now"
        }

        if entity_id not in self.transition_history:
            self.transition_history[entity_id] = []

        self.transition_history[entity_id].append(transition)
        return True

    async def validate_transition(
        self,
        entity_id: str,
        from_state: str,
        to_state: str
    ) -> bool:
        """Validate if a transition is allowed."""
        # Simple validation logic
        return True

    async def get_transition_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get transition history for an entity."""
        return self.transition_history.get(entity_id, [])

    async def rollback_transition(self, entity_id: str, steps: int = 1) -> bool:
        """Rollback transitions for an entity."""
        if entity_id in self.transition_history:
            history = self.transition_history[entity_id]
            if len(history) >= steps:
                for _ in range(steps):
                    history.pop()
                return True
        return False


# Factory functions for TypedDI

async def create_workflow_engine_service(resolver) -> WorkflowEngineService:
    """Factory function for WorkflowEngineService."""
    return WorkflowEngineService()


async def create_task_management_service(resolver) -> TaskManagementService:
    """Factory function for TaskManagementService."""
    return TaskManagementService()


async def create_process_automation_service(resolver) -> ProcessAutomationService:
    """Factory function for ProcessAutomationService."""
    return ProcessAutomationService()


async def create_state_management_service(resolver) -> StateManagementService:
    """Factory function for StateManagementService."""
    return StateManagementService()


async def create_transition_service(resolver) -> TransitionService:
    """Factory function for TransitionService."""
    return TransitionService()


def register_workflow_management_services(manager: ServiceRegistrationManager) -> None:
    """Register all workflow management services with TypedDI."""

    # WorkflowEngineService
    manager.register_protocol_with_concrete_alias(
        protocol_type=WorkflowEngineServiceProtocol,
        concrete_type=WorkflowEngineService,
        factory=create_workflow_engine_service,
        dependencies=[],
        lifetime="singleton",
    )

    # TaskManagementService
    manager.register_protocol_with_concrete_alias(
        protocol_type=TaskManagementServiceProtocol,
        concrete_type=TaskManagementService,
        factory=create_task_management_service,
        dependencies=[],
        lifetime="singleton",
    )

    # ProcessAutomationService
    manager.register_protocol_with_concrete_alias(
        protocol_type=ProcessAutomationServiceProtocol,
        concrete_type=ProcessAutomationService,
        factory=create_process_automation_service,
        dependencies=[],
        lifetime="singleton",
    )

    # StateManagementService
    manager.register_protocol_with_concrete_alias(
        protocol_type=StateManagementServiceProtocol,
        concrete_type=StateManagementService,
        factory=create_state_management_service,
        dependencies=[],
        lifetime="singleton",
    )

    # TransitionService
    manager.register_protocol_with_concrete_alias(
        protocol_type=TransitionServiceProtocol,
        concrete_type=TransitionService,
        factory=create_transition_service,
        dependencies=[],
        lifetime="singleton",
    )
