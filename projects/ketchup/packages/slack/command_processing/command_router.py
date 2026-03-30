"""
command_router.py

Routes Slack commands to the appropriate handlers based on command type.
"""

import time
from typing import Any, Dict, cast

from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger
from packages.db.operations.command_tracking_operations import (
    CommandTrackingOperations,
)
from packages.db.user_store import UserStore
from packages.slack.authorisation.user_verification import UserVerifier
from packages.slack.blockkits.handlers.access_request_blocks import AccessRequestBlocks
from packages.slack.channel_events.models import ProcessingResult
from packages.slack.command_processing.command_logger import (
    extract_command_details,
    log_command_execution,
)
from packages.slack.command_processing.command_parameters.models import (
    AccessCommandParams,
    ArchiveCommandParams,
    CommandType,
    FeatureCommandParams,
    ListCommandParams,
    MetricsCommandParams,
    QueryCommandParams,
    StatusReportCommandParams,
)
from packages.slack.command_processing.verify_command import verify_and_extract_command
from packages.slack.messages.posting import SlackPostingHandler

logger = setup_logger(__name__)


class CommandRouter:
    """
    Routes commands to appropriate handlers based on command type.
    Relies on injected dependencies, specifically pre-initialized command handlers.
    """

    def __init__(
        self,
        command_handlers: Dict[
            str, Any
        ],  # Expects a dict mapping command type value to handler instance
        slack_posting_handler: SlackPostingHandler,  # Still needed for error messages
        user_verifier: UserVerifier,
        user_store: UserStore,
        command_tracking_ops: CommandTrackingOperations | None = None,
    ):
        """
        Initialize the CommandRouter with pre-initialized command handlers.

        Args:
            command_handlers: A dictionary mapping command type values (e.g., 'list')
                              to their corresponding handler instances.
            slack_posting_handler: Handler for posting messages (used for errors).
            user_verifier: Handler for verifying user authorization.
            user_store: Store for user data retrieval.
        """
        self.command_handlers = command_handlers
        self.slack_posting_handler = slack_posting_handler
        self._user_verifier = user_verifier
        self._user_store = user_store
        # Optional – if provided we will log each successful command invocation
        self._command_tracking_ops = command_tracking_ops
        logger.info("CommandRouter initialized with injected command handlers and user verifier.")

    async def route_command(self, body: Dict[str, Any], response_url: str = "") -> ProcessingResult:
        """
        Route a Slack command to the appropriate handler.

        Args:
            body: The parsed Slack command payload
            response_url: The response URL from Slack (optional, defaults to empty string)

        Returns:
            A dictionary representing the result or an error
        """
        # ⏱️ START TIMING: End-to-end command performance
        start_time = time.perf_counter()

        # Extract command parameters
        command = body.get("command", [""])[0]
        text = body.get("text", [""])[0].strip()
        incoming_channel = body.get("channel_id", [""])[0]
        channel_name = body.get("channel_name", [""])[0]
        user_id = body.get("user_id", [""])[0]
        user_name = body.get("user_name", [""])[0]
        response_url = body.get("response_url", [""])[0]

        # Create command identifier for logging
        command_id = f"{command} {text[:50]}" if text else command

        # Log command details
        logger.info(
            "Command: %s, Text: %s, Incoming Channel: %s, Channel Name: %s, User: %s, Response URL: %s",
            command,
            text,
            incoming_channel,
            channel_name,
            user_name,
            response_url,
        )

        # Special case: access command bypasses authorization check
        if command == "/ketchup" and text.lower().strip().startswith("access"):
            # Skip authorization check and proceed to normal command processing
            logger.info("Access command detected - bypassing authorization check")
        else:
            # Validate user authorization using the injected UserVerifier
            if not await self._user_verifier.validate_user_id(user_id):
                # Check if access request automation is enabled
                if FeatureFlags.is_access_request_automation_enabled():
                    # Check if this is a DM channel (Slack uses "directmessage" or channel starts with "D")
                    is_dm = channel_name == "directmessage" or incoming_channel.startswith("D")
                    if is_dm:
                        # Show access request UI in DMs
                        try:
                            access_blocks = AccessRequestBlocks()
                            blocks = access_blocks.build_unauthorized_message(
                                user_id=user_id, show_request_button=True
                            )

                            await self.slack_posting_handler.post_message(
                                user_id=user_id,
                                channel_id=incoming_channel,
                                blocks=blocks,
                                message="Access Required",  # Fallback text
                                response_url=response_url,
                            )
                        except Exception as e:
                            logger.error("Error posting access request UI to Slack: %s", str(e))
                            # Fallback to simple message
                            non_authorised_message = "You don't have access to Ketchup. Please try running any Ketchup command in a DM to request access."
                            await self.slack_posting_handler.post_message(
                                user_id=user_id,
                                channel_id=incoming_channel,
                                message=non_authorised_message,
                                response_url=response_url,
                            )
                    else:
                        # In channels, direct them to use DM for access requests
                        non_authorised_message = "You don't have access to Ketchup. Please run any Ketchup command in a direct message with me to request access."
                        try:
                            await self.slack_posting_handler.post_message(
                                user_id=user_id,
                                channel_id=incoming_channel,
                                message=non_authorised_message,
                                response_url=response_url,
                            )
                        except Exception as e:
                            logger.error("Error posting message to Slack: %s", str(e))
                else:
                    # Feature disabled - show traditional message
                    non_authorised_message = "You are unauthorised to run Ketchup. Please contact ORG-OMEARA-ALL@adobe.com to request access."
                    try:
                        await self.slack_posting_handler.post_message(
                            user_id=user_id,
                            channel_id=incoming_channel,
                            message=non_authorised_message,
                        )
                    except Exception as e:
                        logger.error("Error posting message to Slack: %s", str(e))
                return ProcessingResult(status_code=200, body="")

        # Fetch user's real name from database for proper JIRA query handling
        user_real_name = user_name  # Default to Slack username
        try:
            user_data = await self._user_store.get_user(user_id)
            if user_data and user_data.get("real_name"):
                user_real_name = user_data["real_name"]
                logger.info(
                    f"Using real name '{user_real_name}' for user {user_id} (slack username: {user_name})"
                )
        except Exception as e:
            logger.warning(
                f"Could not fetch real name for user {user_id}, using slack username: {e}"
            )

        # Combine command and text for full command string
        combined_command = " ".join([command, text]).strip()
        logger.info("Combined Command: %s", combined_command)

        # Verify command and extract parameters
        params = await verify_and_extract_command(
            command=combined_command,
            user_id=user_id,
            incoming_channel=incoming_channel,
            response_url=response_url,
            slack_posting_handler=self.slack_posting_handler,
            channel_name=channel_name,
        )

        if not params:
            logger.warning("Command verification failed: %s", combined_command)
            return ProcessingResult(status_code=200, body="")

        logger.info("Routing command type: %s", params.command_type)

        # -----------------------------------------------------------
        #  Command usage logging (non-blocking, best-effort)
        # -----------------------------------------------------------
        if self._command_tracking_ops:
            try:
                # Always take the enum value as the canonical command type
                command_type_value = params.command_type.value

                # Only log recognised (non-unknown) command types
                if command_type_value != "unknown":
                    cmd_details = await extract_command_details(params)
                    await log_command_execution(
                        command_tracking_ops=self._command_tracking_ops,
                        user_id=user_id,
                        user_name=user_name,
                        command_type=command_type_value,
                        channel_id=cmd_details.get("channel_id", incoming_channel) or "",
                        command_text=cmd_details.get("command_text", combined_command),
                    )
                else:
                    logger.info("Skipping command usage logging because command_type is 'unknown'.")
            except Exception as e:  # noqa: BLE001 – we must never break main flow
                logger.error("Failed to log command execution: %s", str(e))

        # Route to appropriate handler using the handlers dictionary
        handler = self.command_handlers.get(params.command_type.value)

        if not handler:
            logger.error("No handler found for command type: %s", params.command_type)
            await self.slack_posting_handler.post_message(
                user_id=user_id,
                channel_id=incoming_channel,
                message=f"Sorry, the command `{combined_command}` is not supported or configured correctly.",
            )
            return ProcessingResult(status_code=400, body="Unsupported command type")

        logger.info("Found handler: %s", type(handler).__name__)

        try:
            # Call the appropriate processing method on the retrieved handler
            if params.command_type == CommandType.LIST:
                # Cast params to ListCommandParams if needed, though it might not have unique attrs here
                list_params = cast(ListCommandParams, params)
                result = await handler.process_list_params(
                    params=list_params,
                    user_id=user_id,
                    incoming_channel=incoming_channel,
                    response_url=response_url,
                )
            elif params.command_type == CommandType.ARCHIVE:
                # Cast params to ArchiveCommandParams if needed
                archive_params = cast(ArchiveCommandParams, params)
                result = await handler.process_archive_params(
                    params=archive_params,
                    user_id=user_id,
                    incoming_channel=incoming_channel,
                    response_url=response_url,
                )
            elif params.command_type == CommandType.QUERY:
                # Cast params to QueryCommandParams before accessing target_channel_id
                query_params = cast(QueryCommandParams, params)
                result = await handler.process_query_request(
                    params=query_params,
                    user_id=user_id,
                    channel_id=query_params.target_channel_id,  # Use casted var
                    dm_channel_id=incoming_channel,
                    response_url=response_url,
                    user_name=user_real_name,  # Pass user_name
                )
            elif params.command_type in [CommandType.SHORT, CommandType.LONG]:
                # Cast params to SummaryCommandParams before accessing target_channel_id
                summary_params = cast(SummaryCommandParams, params)
                result = await handler.process_summary_params(
                    params=summary_params,
                    user_id=user_id,
                    channel_id=summary_params.target_channel_id,  # Use casted var
                    dm_channel_id=incoming_channel,
                    response_url=response_url,
                )
            elif params.command_type in [CommandType.STATUS, CommandType.REPORT]:
                # Cast params to StatusReportCommandParams before accessing report_type/target_channel_id
                report_params = cast(StatusReportCommandParams, params)
                if report_params.report_type == "status":
                    result = await handler.process_status_request(
                        command_verified=report_params.original_command,
                        text=f"status {report_params.target_channel_id}",  # Use casted var
                        user_id=user_id,
                        incoming_channel=incoming_channel,
                        dm_channel_id=incoming_channel,
                        response_url=response_url,
                        channel_id=report_params.target_channel_id,  # Use casted var
                        user_name=user_real_name,  # Pass user_name
                    )
                else:  # report_params.report_type == "report"
                    result = await handler.process_report_request(
                        command_verified=report_params.original_command,
                        text=f"report {report_params.target_channel_id}",  # Use casted var
                        user_id=user_id,
                        incoming_channel=incoming_channel,
                        dm_channel_id=incoming_channel,
                        response_url=response_url,
                        channel_id=report_params.target_channel_id,  # Use casted var
                        user_name=user_real_name,  # Pass user_name
                    )
            elif params.command_type == CommandType.FEATURE:
                # Cast params to FeatureCommandParams
                feature_params = cast(FeatureCommandParams, params)
                result = await handler.process_feature_params(
                    params=feature_params,
                    user_id=user_id,
                    incoming_channel=incoming_channel,
                    response_url=response_url,
                )
            elif params.command_type == CommandType.ACCESS:
                # Cast params to AccessCommandParams
                access_params = cast(AccessCommandParams, params)
                result = await handler.process_access_params(
                    params=access_params,
                    user_id=user_id,
                    incoming_channel=incoming_channel,
                    response_url=response_url,
                )
            elif params.command_type == CommandType.METRICS:
                # Cast params to MetricsCommandParams
                metrics_params = cast(MetricsCommandParams, params)
                result = await handler.process_metrics_params(
                    params=metrics_params,
                    user_id=user_id,
                    incoming_channel=incoming_channel,
                    response_url=response_url,
                )
            else:
                # Should not happen if handler was found, but safety check
                raise NotImplementedError(
                    f"Processing logic not implemented for handler: {type(handler).__name__}"
                )

            # ⏱️ END TIMING: Command completed successfully
            duration = time.perf_counter() - start_time
            logger.info("⏱️ COMMAND E2E: %s | SUCCESS | %.2fs", command_id, duration)
            return result

        except Exception as e:
            # Handle unexpected errors during handler execution
            error_message = (
                f"Error processing command with handler {type(handler).__name__}: {str(e)}"
            )
            logger.exception(error_message)

            # Reuse existing TaskGroup check and general error posting logic
            if "unhandled errors in a TaskGroup" in str(e):
                friendly_message = "Your request is currently being processed. I can only handle one command at a time, and additional requests will be blocked until the current one completes. Please wait a moment before trying again. This helps ensure all your data is processed correctly."
                await self.slack_posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=friendly_message,
                    response_url=response_url,
                )
            else:
                await self.slack_posting_handler.post_message(
                    user_id=user_id,
                    channel_id=incoming_channel,
                    message=f"Error: {str(e)}",
                    response_url=response_url,
                )

            return ProcessingResult(status_code=500, body=error_message)
