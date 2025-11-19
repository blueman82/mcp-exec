"""Configuration management for Slack bot and external integrations.

Handles loading and validating configuration from environment variables,
including credentials for Slack and Jira APIs, logging levels, and
feature toggles.
"""

from typing import Optional

__all__ = [
    "get_slack_token",
    "get_jira_config",
    "get_log_level",
]
