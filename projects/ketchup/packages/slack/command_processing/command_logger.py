"""
command_logger.py

This module provides middleware functionality to log command executions to DynamoDB.
It's designed to be non-blocking and fail gracefully if logging operations encounter errors.
"""

from typing import Any, Dict

from packages.core.logging import setup_logger
from packages.db.operations.command_tracking_operations import CommandTrackingOperations

logger = setup_logger(__name__)


async def log_command_execution(
    command_tracking_ops: CommandTrackingOperations,
    user_id: str,
    user_name: str,
    command_type: str,
    channel_id: str = "",
    command_text: str = "",
) -> None:
    """
    Log a command execution to DynamoDB without blocking the main execution flow.

    This function is designed to be called after command routing is successful,
    but before or after the actual command execution. It catches all exceptions
    to ensure that command execution is not disrupted by logging failures.

    Args:
        command_tracking_ops: The CommandTrackingOperations instance to use for logging
        user_id: The Slack user ID of the user who executed the command
        user_name: The Slack username of the user who executed the command
        command_type: The type of command executed (e.g., 'status', 'report', 'analyze')
        channel_id: Optional channel ID where the command was executed
        command_text: Optional full text of the command
    """
    try:
        logger.info(
            f"Logging command execution: user={user_name}, type={command_type}, channel={channel_id}"
        )

        # Attempt to log the command asynchronously
        await command_tracking_ops.log_command(
            user_id=user_id,
            user_name=user_name,
            command_type=command_type,
            channel_id=channel_id,
            command_text=command_text,
        )

    except Exception as e:
        # Log the error but don't raise it - we don't want to disrupt command execution
        logger.error(f"Failed to log command execution: {str(e)}")
        logger.info(
            f"Command details: user={user_name}, type={command_type}", exc_info=True
        )


async def extract_command_details(params: Any) -> Dict[str, str]:
    """
    Extract relevant command details from different parameter types.

    This helper function normalizes the extraction of command details from
    different parameter objects that might be passed from the command router.

    Args:
        params: The command parameters object from the command router

    Returns:
        Dict containing normalized command details
    """
    try:
        details = {
            "command_type": (
                getattr(params, "command_type", "unknown").value
                if hasattr(getattr(params, "command_type", None), "value")
                else str(getattr(params, "command_type", "unknown"))
            ),
            "channel_id": "",
            "command_text": getattr(params, "original_command", ""),
        }

        # Try to extract target channel ID from various parameter types
        if hasattr(params, "target_channel_id"):
            details["channel_id"] = params.target_channel_id

        # For more complex command texts
        if hasattr(params, "query_text") and params.query_text:
            details["command_text"] += f" {params.query_text}"

        return details

    except Exception as e:
        logger.error(f"Error extracting command details: {str(e)}")
        return {"command_type": "unknown", "channel_id": "", "command_text": ""}
