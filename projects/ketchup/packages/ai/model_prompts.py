"""
model_prompts.py

This module provides a function to generate instructions for different types of model prompts
used in the ketchup application by importing them from the prompts directory.
"""

from typing import Any, Dict, Optional

# Import prompts from the new directory structure
from packages.ai.prompts.common_guidelines import COMMON_GUIDELINES_PROMPT
from packages.ai.prompts.customer_extraction import get_customer_name_extraction_prompt
from packages.ai.prompts.query import get_query_prompt
from packages.ai.prompts.report import get_report_prompt
from packages.ai.prompts.status import get_status_prompt
from packages.core.logging import setup_logger

# Set up module logger
logger = setup_logger(__name__)


def get_prompt_for_command(
    command: str,
    query_text: Optional[str] = None,
    user_prefs: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generate the appropriate instructions based on the command type.

    Args:
        command: The command type for which instructions are needed
        query_text: The query text for query commands
        user_prefs: Optional dictionary of user preferences

    Returns:
        The instructions for the given command or None if the command is not recognized
    """
    logger.info("Command: %s: Query: %s", command, query_text)

    if command.startswith("/ketchup list"):
        logger.info("Setting instructions for a list extraction command.")
        return f"{COMMON_GUIDELINES_PROMPT}\n{get_customer_name_extraction_prompt()}"

    elif command.startswith("/ketchup query"):
        logger.info("Setting instructions for a query command.")
        query_prompt_text = get_query_prompt(query_text or "")
        return f"{COMMON_GUIDELINES_PROMPT}\n{query_prompt_text}"

    elif command.startswith("/ketchup status"):
        logger.info("Setting instructions for a status command.")
        status_prompt_text = (
            f"{COMMON_GUIDELINES_PROMPT}\n{get_status_prompt(user_prefs=user_prefs)}"
        )
        return status_prompt_text

    elif command.startswith("/ketchup report"):
        logger.info("Setting instructions for a report command.")
        report_prompt_text = get_report_prompt(
            user_prefs=user_prefs,
        )
        return report_prompt_text

    # Return None if the command is not recognized
    logger.warning("Unrecognized command for prompt generation: %s", command)
    return None
