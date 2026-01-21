"""
system_channels.py

Configuration for system channels excluded from metrics.
"""

import os
from typing import Set

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

# Default system channels to exclude from CSO metrics (ID -> name mapping)
DEFAULT_EXCLUDED_CHANNELS = {
    "C090V88CB1N": "ketchup_access",
    "C08CQN1JCSC": "ketchup_feedback",
}


def get_excluded_channels() -> Set[str]:
    """
    Get set of channel IDs to exclude from CSO metrics.

    Loads from EXCLUDED_CSO_CHANNELS environment variable if set,
    otherwise uses defaults.

    Returns:
        Set of channel IDs to exclude
    """
    env_value = os.environ.get("EXCLUDED_CSO_CHANNELS")

    if env_value is not None:
        # Environment variable is explicitly set, use it (even if empty)
        env_value = env_value.strip()
        excluded = {ch.strip() for ch in env_value.split(",") if ch.strip()}
        logger.info(f"Loaded {len(excluded)} excluded channels from environment")
        return excluded

    # Use defaults when env var not set
    logger.info(f"Using default excluded channels: {set(DEFAULT_EXCLUDED_CHANNELS.keys())}")
    return set(DEFAULT_EXCLUDED_CHANNELS.keys())


def get_excluded_channel_names() -> list[str]:
    """
    Get list of excluded channel names for display purposes.

    Returns:
        List of channel names (e.g., ["ketchup_access", "ketchup_feedback"])
    """
    return list(DEFAULT_EXCLUDED_CHANNELS.values())
