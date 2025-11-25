"""Message formatting utilities for Slack bot responses.

Provides functions to format and structure messages for Slack delivery,
including block templates, interactive elements, and rich formatting
for task information, process details, and error messages.
"""

from typing import Any, Dict

__all__ = [
    "format_response",
    "format_task_message",
    "format_process_message",
    "format_error_message",
    "create_block_kit_message",
]


def format_response(processes: Dict[str, Any]) -> str:
    """Format processes into mrkdwn message for Slack.

    Converts process configuration dictionary into a clean, readable
    Slack mrkdwn formatted message with proper link formatting.

    Args:
        processes: Dictionary of process configurations with wiki URLs

    Returns:
        Formatted mrkdwn message string suitable for Slack say()

    Example:
        >>> processes = {
        ...     'Service Review Process': {
        ...         'wiki_url': 'https://wiki.corp.adobe.com/display/neolane/Service-Review'
        ...     }
        ... }
        >>> message = format_response(processes)
        >>> print(message)
    """
    if not processes:
        return "No processes available"

    lines = ["Hi! Here's what I have available from Maptimize:", ""]

    for process_name, process_info in processes.items():
        wiki_url = process_info.get("wiki_url", "")
        if wiki_url:
            # Slack mrkdwn link format: <URL|text>
            link = f"<{wiki_url}|View on Wiki>"
            lines.append(f"*{process_name}*")
            lines.append(link)
            lines.append("")
        else:
            lines.append(f"*{process_name}* (no wiki link)")
            lines.append("")

    return "\n".join(lines)


def create_block_kit_message(processes: Dict[str, Any]) -> str:
    """Create a formatted message from process configuration.

    Formats process configuration into a readable text message
    suitable for ephemeral Slack messages.

    Args:
        processes: Dictionary of process configurations

    Returns:
        Formatted message text

    Example:
        >>> processes = {
        ...     'Service Review Process': {
        ...         'wiki_url': 'https://wiki.corp.adobe.com/...'
        ...     }
        ... }
        >>> message = create_block_kit_message(processes)
    """
    if not processes:
        return "No processes available."

    lines = ["Available Processes:\n"]
    for process_name, process_info in processes.items():
        lines.append(f"• {process_name}")
        if isinstance(process_info, dict):
            if "wiki_url" in process_info:
                lines.append(f"  Wiki: {process_info['wiki_url']}")

    return "\n".join(lines)


def format_task_message(task_id: str, task_info: Dict[str, Any]) -> str:
    """Format a task message.

    Args:
        task_id: Task identifier
        task_info: Task information dictionary

    Returns:
        Formatted task message for display in Slack
    """
    return f"Task {task_id}: {task_info}"


def format_process_message(process_name: str, process_info: Dict[str, Any]) -> str:
    """Format a process message.

    Args:
        process_name: Name of the process
        process_info: Process information dictionary

    Returns:
        Formatted process message for display in Slack
    """
    return f"Process: {process_name} - {process_info}"


def format_error_message(error: str) -> str:
    """Format an error message.

    Args:
        error: Error message text

    Returns:
        Formatted error message for display in Slack
    """
    return f"❌ Error: {error}"
