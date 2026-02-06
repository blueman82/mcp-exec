"""Service container factory for Bravo dependency injection.

Creates and wires a ServiceRegistry with all Bravo services,
establishing their dependency relationships.
"""

from bravo.config import Settings
from bravo.di import DependencySpec, ServiceRegistry
from bravo.services.gates import GateService
from bravo.services.jira import JiraMCPClient
from bravo.services.llm import LLMService
from bravo.services.nudge import NudgeService
from bravo.services.poller import PollerService
from bravo.services.slack import SlackService


async def _async(obj: object) -> object:
    """Wrap a sync value as an async factory result.

    Args:
        obj: The object to wrap.

    Returns:
        The same object, unchanged.
    """
    return obj


def create_container(settings: Settings) -> ServiceRegistry:
    """Create and wire the service container.

    Args:
        settings: Application configuration.

    Returns:
        A ServiceRegistry with all services registered.
    """
    registry = ServiceRegistry()

    # Leaf services (no cross-service deps)
    registry.register(DependencySpec(
        name="gate_service",
        factory=lambda: _async(GateService(settings.gates)),
    ))
    registry.register(DependencySpec(
        name="jira_client",
        factory=lambda: _async(JiraMCPClient(settings.jira)),
    ))
    registry.register(DependencySpec(
        name="slack_service",
        factory=lambda: _async(SlackService(settings.slack)),
    ))
    registry.register(DependencySpec(
        name="llm_service",
        factory=lambda: _async(LLMService(settings.llm)),
    ))

    # Composite services
    registry.register(DependencySpec(
        name="poller_service",
        factory=lambda jira_client: _async(PollerService(settings, jira_client)),
        depends_on=["jira_client"],
    ))
    registry.register(DependencySpec(
        name="nudge_service",
        factory=lambda jira_client, slack_service, gate_service, llm_service: _async(
            NudgeService(settings, jira_client, slack_service, gate_service, llm_service)
        ),
        depends_on=["jira_client", "slack_service", "gate_service", "llm_service"],
    ))

    return registry
