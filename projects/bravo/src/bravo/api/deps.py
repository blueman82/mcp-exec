"""FastAPI Depends() helpers for service injection.

Extracts services from ``request.app.state.container`` and narrows
the return type via runtime ``isinstance`` checks against
``@runtime_checkable`` Protocol interfaces.
"""

from fastapi import Request

from bravo.protocols import NudgeServiceProto, PollerServiceProto


def get_nudge_service(request: Request) -> NudgeServiceProto:
    """Retrieve the nudge orchestration service.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The initialised NudgeServiceProto instance.
    """
    svc = request.app.state.container.get("nudge_service")
    assert isinstance(svc, NudgeServiceProto)
    return svc


def get_poller_service(request: Request) -> PollerServiceProto:
    """Retrieve the Jira polling service.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The initialised PollerServiceProto instance.
    """
    svc = request.app.state.container.get("poller_service")
    assert isinstance(svc, PollerServiceProto)
    return svc
