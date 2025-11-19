"""Slack bot application using slack-bolt framework.

Initializes and configures the Slack bot application instance with
event handlers, middleware, and context managers for lifecycle management.
"""

from typing import Optional

__all__ = [
    "create_app",
    "start_app",
    "stop_app",
]
