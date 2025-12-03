"""Message formatting utilities for Slack bot responses.

Provides functions to format and structure messages for Slack delivery,
including block templates, interactive elements, and rich formatting
for task information, process details, and error messages.
"""

from typing import Any, Dict, List, Optional

__all__ = [
    "format_response",
    "format_task_message",
    "format_process_message",
    "format_error_message",
    "create_block_kit_message",
    "create_response_blocks",
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


def create_response_blocks(
    processes: Dict[str, Any],
    image_urls: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Create Block Kit response blocks with optional Miro diagrams.

    Builds a rich Block Kit response with process information, descriptions,
    and embedded Miro board screenshots. Each process is displayed with:
    - Header section with process name in bold
    - Optional Miro diagram image (if available)
    - Description text
    - Wiki link (if available)
    - Divider between processes

    Args:
        processes: Process configuration dict with process names as keys
        image_urls: Dict mapping process names to Slack image permalink URLs

    Returns:
        List of Block Kit block dictionaries ready for Slack API

    Example:
        >>> processes = {
        ...     'Service Review Process': {
        ...         'description': '8-step process for reviews',
        ...         'wiki_url': 'https://wiki.corp.adobe.com/...',
        ...         'miro_board_id': 'abc123'
        ...     }
        ... }
        >>> image_urls = {'Service Review Process': 'https://slack.com/...'}
        >>> blocks = create_response_blocks(processes, image_urls)
    """
    if image_urls is None:
        image_urls = {}

    blocks: List[Dict[str, Any]] = []

    # Add header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Maptimize Process Information",
            "emoji": True,
        }
    })

    blocks.append({"type": "divider"})

    if not processes:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No processes available._",
            }
        })
        return blocks

    # Add each process
    for process_name, process_info in processes.items():
        if not isinstance(process_info, dict):
            continue

        # Build process header text with description
        description = process_info.get("description", "")
        wiki_url = process_info.get("wiki_url", "")

        header_text = f"*{process_name}*"
        if description:
            header_text += f"\n{description}"

        # Add header section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header_text,
            }
        })

        # Add wiki link button if available
        if wiki_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": " ",  # Empty text to satisfy Block Kit requirements
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View on Wiki",
                        "emoji": True,
                    },
                    "url": wiki_url,
                    "action_id": f"wiki_link_{process_name.lower().replace(' ', '_')}",
                }
            })

        # Add Miro diagram image if available
        if process_name in image_urls:
            blocks.append({
                "type": "image",
                "image_url": image_urls[process_name],
                "alt_text": f"{process_name} Process Diagram",
            })

        # Add divider between processes
        blocks.append({"type": "divider"})

    return blocks


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
