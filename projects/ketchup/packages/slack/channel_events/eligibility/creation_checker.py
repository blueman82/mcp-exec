"""
Checks eligibility criteria for newly created Slack channels.
"""

import re

from packages.core.constants import CHANNEL_KEYWORD_TO_PRODUCT
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager

logger = setup_logger(__name__)

# Special channels that Ketchup should always join regardless of naming conventions
EXEMPT_CHANNELS = [
    "ketchup_access_requests",  # For access request approvals (actual channel name)
    "ketchup-alerts",  # For monitoring and alerts
]


async def is_new_channel_eligible(
    channel_name: str, creator_id: str, secrets_manager: SecretsManager
) -> bool:
    """Check if a newly created channel meets eligibility criteria based on name and creator.

    Args:
        channel_name: The name of the newly created channel.
        creator_id: The Slack user ID of the person who created the channel.
        secrets_manager: An instance of SecretsManager to fetch authorized users.

    Returns:
        True if the channel is eligible, False otherwise.
    """
    # Check if this is an exempt channel that should always be eligible
    channel_name_normalized = channel_name.lower().replace("#", "")
    if channel_name_normalized in EXEMPT_CHANNELS:
        logger.info("Channel '%s' is in exempt list - automatically eligible", channel_name)
        return True

    # Get authorized user IDs from secrets
    exigence_user_id = await secrets_manager.get_exigence_user_id_async()
    authorized_users = [exigence_user_id, "W7MGASQ2K"]

    # Check if creator is authorized and channel name matches approved patterns
    is_authorized_creator = creator_id in authorized_users

    # Channel must contain 'cso' AND a valid product keyword
    # Both conditions must be met for eligibility
    logger.info(
        "Checking eligibility for channel name: '%s' against product keywords: %s and 'cso' requirement (both conditions must be met)",
        channel_name,
        list(CHANNEL_KEYWORD_TO_PRODUCT.keys()),
    )

    # Use regex to match product keywords as whole words or separated by _ or -
    channel_name_lower = channel_name.lower()
    keywords = list(CHANNEL_KEYWORD_TO_PRODUCT.keys())

    def contains_product_keyword(name: str, keywords: list[str]) -> bool:
        for key in keywords:
            pattern = rf"(?:^|[_-]){re.escape(key)}(?:[_-]|$)"
            logger.info("Checking pattern: %s against channel name: %s", pattern, name)
            if re.search(pattern, name):
                return True
        return False

    has_cso = "cso" in channel_name_lower
    has_product_keyword = contains_product_keyword(channel_name_lower, keywords)
    is_approved_channel_name = has_cso and has_product_keyword

    eligible = is_approved_channel_name
    logger.info(
        "Eligibility check for new channel '%s' by creator '%s': Authorized=%s, HasCSO=%s, HasProductKeyword=%s -> Eligible=%s (requires both CSO and product keyword)",
        channel_name,
        creator_id,
        is_authorized_creator,
        has_cso,
        has_product_keyword,
        eligible,
    )

    return eligible
