"""
Container Roles for role-based service registration.

Defines which Docker container is running so the DI system
can register only the services that container actually needs.
"""

from enum import Enum


class ContainerRole(Enum):
    """Role identifying which Docker container is running."""

    APP = "app"  # ketchup-app (FastAPI, all services)
    SCHEDULER = "scheduler"  # ketchup-unified-scheduler
    CSOPM_NOTIFIER = "csopm"  # ketchup-csopm-notifier
    ACCESS_MONITOR = "access"  # ketchup-access-monitor
