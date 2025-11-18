"""
Maintenance Detection Module

Convenience module for resolving maintenance detection services via TypedDI.
"""

from packages.core.typed_di.typed_resolver import resolve_typed
from packages.core.typed_di.service_registrations.protocols import (
    JiraPromptHandlerProtocol,
)


async def get_jira_prompt_handler() -> JiraPromptHandlerProtocol:
    """
    Get JiraPromptHandler instance via TypedDI.
    
    Uses the TypedDI factory which automatically resolves all dependencies.
    
    Returns:
        JiraPromptHandler: Configured handler instance with all dependencies resolved
    """
    return await resolve_typed(JiraPromptHandlerProtocol)


__all__ = ["get_jira_prompt_handler"]
