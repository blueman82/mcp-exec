"""
command_decorators.py

This module contains decorators for Slack command processing.
"""

from functools import wraps
from typing import Any, Callable, Optional

from packages.core.logging import setup_logger
from packages.slack.channel_events.models import ProcessingResult

logger = setup_logger(__name__)


async def _resolve_channel_parameter_in_decorator(channel_param: str) -> Optional[str]:
    """Resolve channel parameter to actual channel ID in decorator context."""
    from packages.slack.command_processing.channel_resolver import resolve_channel_parameter

    return await resolve_channel_parameter(
        channel_param,
        context="Decorator",
        return_none_on_failure=False,
    )  # Return original on error


def _extract_channel_params(kwargs):
    user_id = kwargs.get("user_id")
    params = kwargs.get("params")
    target_channel_id = kwargs.get("channel_id")
    if not target_channel_id and params and hasattr(params, "channel_id"):
        target_channel_id = params.channel_id
    dm_channel_id = kwargs.get("incoming_channel")
    response_url = kwargs.get("response_url")
    return user_id, target_channel_id, dm_channel_id, response_url


async def _post_error_to_slack(instance, user_id, channel_id, response_url, message):
    if not hasattr(instance, "slack_posting_handler") or instance.slack_posting_handler is None:
        raise ValueError(
            "slack_posting_handler must be provided via dependency injection on the handler instance"
        )
    error_poster = instance.slack_posting_handler
    await error_poster.post_message(
        user_id=user_id,
        channel_id=channel_id,
        response_url=response_url,
        message=message,
    )
    if not getattr(instance, "slack_posting_handler", None):
        await error_poster.cleanup()


def _get_restore_ops(instance):
    return getattr(instance, "channel_restore_ops", None)


async def _handle_missing_params(instance, user_id, target_channel_id, dm_channel_id, response_url):
    logger.error(
        "Missing required parameters (user_id=%s, target_channel_id=%s, dm_channel_id=%s) for handle_archived_channel decorator. Need user_id and at least one channel ID.",
        user_id,
        target_channel_id,
        dm_channel_id,
    )
    if response_url:
        try:
            await _post_error_to_slack(
                instance,
                user_id,
                dm_channel_id or target_channel_id,
                response_url,
                "Error: Missing required parameters to process the command.",
            )
        except Exception as post_err:
            logger.error("Failed to send error via response_url: %s", post_err)
    if hasattr(instance, "create_validation_error_response"):
        return instance.create_validation_error_response("Missing required parameters")
    return ProcessingResult(status_code=400, body="Missing required parameters", feedback_sent=True)


async def _handle_missing_restore_ops(
    instance, user_id, dm_channel_id, target_channel_id, response_url
):
    logger.error(
        "SlackChannelRestoreOps dependency not found on instance using attribute 'channel_restore_ops' in handle_archived_channel"
    )
    if response_url:
        try:
            await _post_error_to_slack(
                instance,
                user_id,
                dm_channel_id or target_channel_id,
                response_url,
                "Internal error: Cannot check channel status.",
            )
        except Exception as post_err:
            logger.error("Failed to send error via response_url: %s", post_err)
    if hasattr(instance, "create_error_response"):
        return instance.create_error_response("Internal configuration error", status_code=500)
    return ProcessingResult(status_code=500, body="Internal configuration error", feedback_sent=True)


async def _handle_restore_failure(instance, channel_to_check):
    logger.warning(
        "Channel restore failed for %s, stopping command execution.",
        channel_to_check,
    )
    if hasattr(instance, "create_error_response"):
        return instance.create_error_response(
            f"Failed to access channel {channel_to_check}", status_code=400
        )
    return ProcessingResult(status_code=400, body=f"Failed to access channel {channel_to_check}", feedback_sent=True)


async def _handle_exception(instance, e, kwargs, response_url):
    logger.error(
        "Exception within handle_archived_channel decorator: %s",
        str(e),
        exc_info=True,
    )
    if response_url:
        try:
            await _post_error_to_slack(
                instance,
                kwargs.get("user_id"),
                kwargs.get("dm_channel_id") or kwargs.get("params", {}).get("channel_id"),
                response_url,
                f"An internal error occurred: {str(e)}",
            )
        except Exception as post_err:
            logger.error("Failed to send decorator exception via response_url: %s", post_err)
    if hasattr(instance, "create_error_response"):
        return instance.create_error_response(f"Internal server error: {str(e)}", status_code=500)
    return ProcessingResult(status_code=500, body=f"Internal server error: {str(e)}", feedback_sent=True)


async def _handle_finally(
    instance, originally_archived, restore_ops, channel_to_check, kwargs, response_url
):
    if originally_archived and restore_ops and channel_to_check:
        logger.info(
            "Command execution finished for originally archived channel %s, re-archiving.",
            channel_to_check,
        )
        final_user_id = kwargs.get("user_id")
        final_dm_channel_id = kwargs.get("incoming_channel")
        if final_user_id and final_dm_channel_id:
            await restore_ops.rearchive_channel_if_needed(
                user_id=final_user_id,
                channel_id=channel_to_check,
                dm_channel_id=final_dm_channel_id,
                response_url=response_url,
            )
        else:
            logger.error(
                "Could not re-archive channel %s: Missing user_id or dm_channel_id in finally block.",
                channel_to_check,
            )
    else:
        if originally_archived:
            logger.error(
                "Could not re-archive channel %s: Missing restore_ops or channel_id in finally block.",
                channel_to_check or "unknown",
            )


def handle_archived_channel(func: Callable) -> Callable:
    """
    Decorator to handle archived channel logic before executing a command.

    This decorator checks if the target channel for a command is archived.
    If it is, it temporarily unarchives it, allows the command to run,
    and then re-archives it.

    It assumes the decorated function is an async method of a class
    that has access to `get_dependency` and the required kwargs
    (user_id, channel_id/target_channel, incoming_channel, response_url).
    """

    @wraps(func)
    async def wrapper(instance: Any, *args: Any, **kwargs: Any) -> Any:
        originally_archived = False
        restore_ops = None
        target_channel_id = None
        channel_to_check = None
        response_url = None
        try:
            user_id, target_channel_id, dm_channel_id, response_url = _extract_channel_params(
                kwargs
            )
            if not user_id or not (target_channel_id or dm_channel_id):
                return await _handle_missing_params(
                    instance, user_id, target_channel_id, dm_channel_id, response_url
                )
            restore_ops = _get_restore_ops(instance)
            if not restore_ops:
                return await _handle_missing_restore_ops(
                    instance, user_id, dm_channel_id, target_channel_id, response_url
                )
            channel_to_check = target_channel_id or dm_channel_id

            # Resolve channel parameter before making API calls
            original_channel_param = channel_to_check
            resolved_channel = await _resolve_channel_parameter_in_decorator(channel_to_check)
            if resolved_channel != channel_to_check:
                logger.info(
                    "Decorator resolved channel '%s' to '%s'",
                    channel_to_check,
                    resolved_channel,
                )
                channel_to_check = resolved_channel
                # Update the kwargs with resolved channel ID for the actual command
                if target_channel_id:
                    kwargs["channel_id"] = resolved_channel
                # Also update the text parameter if it contains the original channel parameter
                text = kwargs.get("text", "")
                if text and original_channel_param in text:
                    # Replace the original channel parameter with the resolved ID in the text
                    kwargs["text"] = text.replace(original_channel_param, resolved_channel, 1)
                    logger.info("Updated text parameter: '%s' -> '%s'", text, kwargs["text"])

            success, originally_archived = await restore_ops.restore_archived_channel(
                user_id=user_id,
                channel_id=channel_to_check,
                dm_channel_id=dm_channel_id,
                response_url=response_url,
            )
            if not success:
                return await _handle_restore_failure(instance, channel_to_check)
            result = await func(instance, *args, **kwargs)
            return result
        except Exception as e:
            return await _handle_exception(instance, e, kwargs, response_url)
        finally:
            await _handle_finally(
                instance,
                originally_archived,
                restore_ops,
                channel_to_check,
                kwargs,
                response_url,
            )

    return wrapper
