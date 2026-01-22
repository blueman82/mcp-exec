"""
channel_resolver.py

Shared channel parameter resolution logic used by command handlers and decorators.
Extracted to avoid code duplication across SlackSummaryHandler, SlackReports,
SlackQueryHandler, and command_decorators.
"""

from typing import Optional

from packages.core.constants import SLACK_CHANNEL_MENTION_REGEX
from packages.core.logging import setup_logger
from packages.core.typed_di.exceptions import MissingDependencyError
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelNameResolverProtocol,
)
from packages.core.typed_di_integration import get_typed_registry

logger = setup_logger(__name__)


async def resolve_channel_parameter(
    channel_param: str,
    context: str = "",
    return_none_on_failure: bool = True,
) -> Optional[str]:
    """
    Resolve channel parameter to actual channel ID.

    Args:
        channel_param: The channel parameter to resolve (ID, name, or mention format)
        context: Optional context string for logging (e.g., "Decorator", "Query")
        return_none_on_failure: If True, return None on resolution failure;
                                if False, return original channel_param

    Returns:
        Resolved channel ID, None on failure (if return_none_on_failure=True),
        or original value on failure (if return_none_on_failure=False)
    """
    if not channel_param:
        return channel_param

    log_prefix = f"{context} " if context else ""

    try:
        # Attempt to resolve using TypedDI registry
        channel_name_resolver = None
        try:
            registry = get_typed_registry()
            channel_name_resolver = await registry.aget(ChannelNameResolverProtocol)
        except (RuntimeError, MissingDependencyError):
            # Service not available - proceed with fallback
            pass

        if not channel_name_resolver:
            logger.warning(
                "%sChannelNameResolver not available, using fallback parsing",
                log_prefix,
            )
            # Fallback: try to extract channel ID from Slack mention format
            mention_match = SLACK_CHANNEL_MENTION_REGEX.match(channel_param)
            if mention_match:
                channel_id = mention_match.group(1)
                logger.info(
                    "%sExtracted channel ID '%s' from mention format '%s'",
                    log_prefix,
                    channel_id,
                    channel_param,
                )
                return channel_id
            # If not a mention format, return as-is (might be already a valid ID)
            return channel_param

        resolved_id, format_type = await channel_name_resolver.resolve_channel_parameter(  # type: ignore[attr-defined]
            channel_param
        )
        if resolved_id:
            logger.info(
                "%sResolved channel parameter '%s' to ID '%s' (type: %s)",
                log_prefix,
                channel_param,
                resolved_id,
                format_type,
            )
            return resolved_id
        else:
            if return_none_on_failure:
                logger.error(
                    "%sFailed to resolve channel parameter: %s",
                    log_prefix,
                    format_type,
                )
                return None
            else:
                logger.warning(
                    "%sFailed to resolve channel parameter '%s': %s",
                    log_prefix,
                    channel_param,
                    format_type,
                )
                return channel_param

    except Exception as e:
        logger.error(
            "%sError resolving channel parameter '%s': %s",
            log_prefix,
            channel_param,
            str(e),
        )
        # On exception, return original value (consistent with existing behavior)
        return channel_param
