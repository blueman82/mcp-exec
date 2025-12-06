"""
Feature command parameter extraction.

This module provides utilities for extracting parameters from feature commands.
"""

import re

from packages.core.constants import (
    SLACK_CHANNEL_ID_REGEX,
    SLACK_CHANNEL_MENTION_REGEX,
)
from packages.core.logging import setup_logger
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    FeatureCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)

logger = setup_logger(__name__)


def extract_feature_params(command: str, context: CommandContext) -> FeatureCommandParams:
    """
    Extract parameters for feature commands.

    Format: /ketchup feature <feature_name> <action> [user_mention|channel_id]

    Available actions:
    - enable @user/<#channel> - Enable the feature for a specific user or channel
    - disable @user/<#channel> - Disable the feature for a specific user or channel
    - list - List all users/channels with the feature enabled
    - status - Show the current status of the feature

    Args:
        command: The full command string
        context: The command context (DM or public channel)

    Returns:
        Extracted feature command parameters

    Raises:
        ValidationError: If parameters are invalid
    """
    parts = command.split()

    # Validate command format - need at least feature name and action
    if len(parts) < 3:
        raise ValidationError(
            "Incomplete feature command",
            (
                "Feature command requires at least a feature name and an action. For example:\n"
                "`/ketchup feature status_updater enable C1234567890`\n"
                "`/ketchup feature jira_reporter enable C1234567890`\n"
                "`/ketchup feature trust_endorsement enable C1234567890`"
            ),
        )

    # Extract feature name and action
    feature_name = parts[2].lower()

    # Validate feature name
    if feature_name not in [
        "status_updater",
        "jira_reporter",
        "trust_endorsement",
        "access_management",
    ]:
        raise ValidationError(
            f"Invalid feature name: {feature_name}",
            f"Invalid feature name: '{feature_name}'. Currently supported features: status_updater, jira_reporter, trust_endorsement, access_management",
        )

    # Check if action is provided
    if len(parts) < 4:
        raise ValidationError(
            "Missing action for feature command",
            (
                "Feature command requires an action. Available actions:\n"
                "- `enable @user/<#channel>` - Enable the feature for a user/channel\n"
                "- `disable @user/<#channel>` - Disable the feature for a user/channel\n"
                "- `grant @user` - Grant access to a user (access_management only)\n"
                "- `revoke @user` - Revoke access from a user (access_management only)\n"
                "- `list` - List all users/channels with the feature\n"
                "- `status` - Show the current status of the feature"
            ),
        )

    # Extract action
    action = parts[3].lower()

    # Validate action
    if action not in ["enable", "disable", "list", "status", "grant", "revoke"]:
        raise ValidationError(
            f"Invalid feature action: {action}",
            f"Invalid action: '{action}'. Available actions: enable, disable, list, status, grant, revoke",
        )

    # Initialize params
    params = FeatureCommandParams(
        user_id="",  # Will be set by caller
        user_name="",  # Will be set by caller
        channel_id="",  # Will be set by caller
        command_text=command,
        response_url="",  # Will be set by caller
        original_command=command,
        command_type=CommandType.FEATURE,
        context=context,
        feature_name=feature_name,
        action=action,
        target_user_id=None,
        target_channel_id=None,
    )

    # Extract target for enable/disable/grant/revoke actions
    if action in ["enable", "disable", "grant", "revoke"]:
        if len(parts) < 5:
            if feature_name in ["status_updater", "jira_reporter", "trust_endorsement"]:
                raise ValidationError(
                    f"Missing channel for {action} action",
                    f"The {action} action requires a channel ID or mention. Example: `/ketchup feature {feature_name} {action} C1234567890` or `/ketchup feature {feature_name} {action} <#C1234567890|general>`",
                )
            else:
                raise ValidationError(
                    f"Missing user for {action} action",
                    f"The {action} action requires a user mention. Example: `/ketchup feature {feature_name} {action} @user`",
                )

        target_param = parts[4]

        # Handle based on feature type
        if feature_name in ["status_updater", "jira_reporter", "trust_endorsement"]:
            # Extract channel parameter
            # Check if it's a channel mention <#C1234567890|general>
            mention_match = SLACK_CHANNEL_MENTION_REGEX.match(target_param)
            if mention_match:
                params.target_channel_id = mention_match.group(1)
            # Check if it's a direct channel ID
            elif SLACK_CHANNEL_ID_REGEX.match(target_param):
                params.target_channel_id = target_param
            else:
                raise ValidationError(
                    f"Invalid channel format: {target_param}",
                    "Please provide a valid channel ID (C1234567890) or channel mention (<#C1234567890|general>)",
                )
        else:  # nlp or other user-based features
            # Extract user ID from mention format <@U12345> or <@U12345|username>
            user_id_match = re.match(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", target_param)

            if not user_id_match:
                raise ValidationError(
                    f"Invalid user mention format: {target_param}",
                    f"Please provide a valid user mention. Example: `/ketchup feature {feature_name} {action} @user`",
                )

            user_id = user_id_match.group(1)
            params.target_user_id = user_id

    return params
