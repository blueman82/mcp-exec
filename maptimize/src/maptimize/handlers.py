"""Event handlers for Slack bot interactions.

Implements handlers for various Slack events including app mentions,
messages, and shortcuts. Routes events to appropriate processors and
manages error handling and logging.
"""

from typing import Any, Callable, Dict

__all__ = [
    "handle_app_mention",
    "handle_message",
    "handle_shortcut",
    "register_handlers",
]
