"""Message formatting utilities for Slack bot responses.

Provides functions to format and structure messages for Slack delivery,
including block templates, interactive elements, and rich formatting
for task information, process details, and error messages.
"""

from typing import Any, Dict, List

__all__ = [
    "format_task_message",
    "format_process_message",
    "format_error_message",
    "create_block_kit_message",
]
