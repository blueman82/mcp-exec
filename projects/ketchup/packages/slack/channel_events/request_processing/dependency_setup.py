"""
dependency_setup.py

Module for setting up dependencies required for Slack event/command processing.
"""

from typing import Any, Awaitable, Callable, Dict, cast

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry

# Import CSOPMSlackNotifier directly for ketchup-app interactive handling
# (protocol is only registered in csopm_notifier container)
from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

# Additional protocols for Phase 2 Tier 1 migration
from packages.core.typed_di.service_registrations import (
    AccessRequestHandlerProtocol,
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    FeatureServiceProtocol,
    FlagReviewHandlerProtocol,
    HomeTabHandlerProtocol,
    OpenAIHandlerProtocol,
    RestoreStateManagerProtocol,
    SlackChannelArchiveOpsProtocol,
    SlackChannelBotMembershipOpsProtocol,
    SlackChannelMessageOpsProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackConfigProtocol,
    SlackUserOpsProtocol,
    TrustEndorsementHandlerProtocol,
    UserJoinNotificationServiceProtocol,
    UserStoreProtocol,
)
from packages.core.typed_di.service_registrations.protocols import (
    ChannelMetadataEditHandlerProtocol,
    CommandRouterProtocol,
    FeedbackReactionsHandlerProtocol,
    FeedbackReportHandlerProtocol,
    ShortcutHandlerProtocol,
)
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.secrets.manager import SecretsManager
from packages.slack.authorisation.auth import SlackAuth
from packages.slack.authorisation.user_verification import UserVerifier
from packages.slack.blockkits.base import BlockKitBuilder
from packages.slack.channel_events.events import SlackEventHandler
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_eligibility import (
    ChannelEligibilityService,
)
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps
from packages.slack.command_processing.access_command import AccessCommand
from packages.slack.command_processing.archive_command import SlackArchiveCommand
from packages.slack.command_processing.command_parameters.models import CommandType
from packages.slack.command_processing.command_router import CommandRouter
from packages.slack.command_processing.feature_command import FeatureCommand
from packages.slack.command_processing.list_command import SlackListCommand
from packages.slack.command_processing.query_command import SlackQueryHandler
from packages.slack.command_processing.short_long_command import SlackSummaryHandler
from packages.slack.command_processing.status_report_command import SlackReports
from packages.slack.interactive_elements.channel_metadata_edit import (
    ChannelMetadataEditHandler,
)
from packages.slack.interactive_elements.csopm_handler import CSOPMHandler
from packages.slack.interactive_elements.feedback_reactions import (
    FeedbackReactionsHandler,
)
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler
from packages.slack.interactive_elements.shortcuts import ShortcutHandler
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps

logger = setup_logger(__name__)


def instantiate_command_handlers(
    handler_clients: Dict[str, Any],
    block_kit_builder: BlockKitBuilder,
    secrets_manager: SecretsManager,
) -> Dict[str, Any]:
    """
    Instantiate all command handlers with their dependencies.

    Args:
        handler_clients: Dictionary of shared clients for handlers
        block_kit_builder: The BlockKitBuilder instance
        secrets_manager: The SecretsManager instance (required for strict DI)

    Returns:
        Dictionary containing all command handlers
    """
    # Hinting expected types for handler clients (no runtime checks)
    channel_info_ops = cast(ChannelInfoOps, handler_clients["info_ops"])
    channel_membership_ops = cast(ChannelMembershipOps, handler_clients["membership_ops"])
    slack_posting_handler = cast(SlackPostingHandler, handler_clients["slack_posting_handler"])
    dynamodb_store = cast(DynamoDBStore, handler_clients["dynamodb_store"])
    archive_ops = cast(SlackChannelArchiveOps, handler_clients["archive_ops"])
    channel_message_ops = cast(SlackChannelMessageOps, handler_clients["channel_message_ops"])
    openai_handler = handler_clients["openai_handler"]
    channel_restore_ops = handler_clients["restore_ops"]
    slack_config = handler_clients["slack_config"]
    user_store = cast(UserStore, handler_clients["user_store"])
    feedback_reactions_handler = handler_clients.get("feedback_reactions_handler")

    # Instantiate list command handler
    list_handler = SlackListCommand(
        channel_info_ops=channel_info_ops,
        channel_membership_ops=channel_membership_ops,
        slack_posting_handler=slack_posting_handler,
        dynamodb_store=dynamodb_store,
        block_kit_builder=block_kit_builder,
        user_store=user_store,
        feedback_reactions_handler=feedback_reactions_handler,
    )

    # Instantiate query command handler
    query_handler = SlackQueryHandler(
        channel_info_ops=channel_info_ops,
        archive_ops=archive_ops,
        openai_handler=openai_handler,
        block_kit_builder=block_kit_builder,
        channel_message_ops=channel_message_ops,
        slack_posting_handler=slack_posting_handler,
        user_store=user_store,
        slack_config=slack_config,
        secrets_manager=secrets_manager,
        user_ops=SlackUserOps(user_store=user_store, slack_config=slack_config),
        channel_restore_ops=channel_restore_ops,
        dynamodb_store=dynamodb_store,
        feedback_reactions_handler=feedback_reactions_handler,
    )

    # Instantiate summary command handler
    summary_handler = SlackSummaryHandler(
        channel_info_ops=channel_info_ops,
        archive_ops=archive_ops,
        openai_handler=openai_handler,
        block_kit_builder=block_kit_builder,
        channel_message_ops=channel_message_ops,
        slack_posting_handler=slack_posting_handler,
        user_store=user_store,
        channel_restore_ops=channel_restore_ops,
        dynamodb_store=dynamodb_store,
        feedback_reactions_handler=feedback_reactions_handler,
    )

    # Instantiate status report command handler
    status_report_handler = SlackReports(
        channel_info_ops=channel_info_ops,
        archive_ops=archive_ops,
        openai_handler=openai_handler,
        block_kit_builder=block_kit_builder,
        slack_posting_handler=slack_posting_handler,
        dynamodb_store=dynamodb_store,
        channel_restore_ops=channel_restore_ops,
        secrets_manager=secrets_manager,
        slack_config=slack_config,
        user_store=user_store,
        feedback_reactions_handler=feedback_reactions_handler,
    )

    # Instantiate archive command handler
    archive_handler = SlackArchiveCommand(
        channel_info_ops=channel_info_ops,
        slack_posting_handler=slack_posting_handler,
        archive_ops=archive_ops,
        dynamodb_store=dynamodb_store,
        block_kit_builder=block_kit_builder,
        channel_restore_ops=channel_restore_ops,
        user_store=user_store,
    )

    # Create command handlers dictionary
    command_handlers_dict = {
        CommandType.LIST.value: list_handler,
        CommandType.QUERY.value: query_handler,
        CommandType.SHORT.value: summary_handler,
        CommandType.LONG.value: summary_handler,
        CommandType.STATUS.value: status_report_handler,
        CommandType.REPORT.value: status_report_handler,
        CommandType.ARCHIVE.value: archive_handler,
    }

    result = {
        "command_handlers_dict": command_handlers_dict,
        "list_handler": list_handler,
        "query_handler": query_handler,
        "summary_handler": summary_handler,
        "status_report_handler": status_report_handler,
        "archive_handler": archive_handler,
    }

    return result


async def setup_dependencies(container: TypedServiceRegistry) -> Dict[str, Any]:
    """
    Sets up and returns a dictionary of all necessary service and handler instances.

    Uses resilient dependency resolution to handle missing Slack services gracefully.

    Args:
        container: The TypedServiceRegistry instance.

    Returns:
        Dictionary containing all instantiated dependencies.

    Raises:
        ValueError: If essential core dependencies are missing.
    """
    logger.info("Setting up dependencies for request processing.")

    # Core dependencies - these must exist
    try:
        dynamodb_store = cast(DynamoDBStore, container.get(DynamoDBStore))
        user_store = cast(UserStore, await container.aget(UserStoreProtocol))
        secrets_manager = cast(SecretsManager, container.get(SecretsManager))
    except Exception as e:
        logger.error("Failed to retrieve core dependencies: %s", e)
        raise ValueError(f"Missing essential dependencies: {e}")

    # Slack dependencies - these might be missing due to credential issues
    slack_posting_handler = None
    slack_auth = None
    user_verifier = None
    slack_config = None

    try:
        slack_posting_handler = cast(SlackPostingHandler, container.get(SlackPostingHandler))
        logger.info("SlackPostingHandler available")
    except Exception as e:
        logger.warning("SlackPostingHandler not available: %s", e)

    try:
        slack_auth = cast(SlackAuth, container.get(SlackAuth))
        logger.info("SlackAuth available")
    except Exception as e:
        logger.warning("SlackAuth not available: %s", e)

    try:
        user_verifier = cast(UserVerifier, container.get(UserVerifier))
        logger.info("UserVerifier available")
    except Exception as e:
        logger.warning("UserVerifier not available: %s", e)

    try:
        slack_config = await container.aget(SlackConfigProtocol)
        logger.info("SlackConfig available")
    except Exception as e:
        logger.warning("SlackConfig not available: %s", e)

    # Optional Slack operational dependencies
    openai_handler = None
    archive_ops = None
    channel_info_ops = None
    channel_membership_ops = None
    user_ops = None
    channel_message_ops = None
    restore_state_manager = None
    bot_membership_ops = None
    channel_restore_ops = None

    try:
        openai_handler = await container.aget(OpenAIHandlerProtocol)
    except Exception as e:
        logger.warning("OpenAI handler not available: %s", e)

    try:
        archive_ops = cast(
            SlackChannelArchiveOps, await container.aget(SlackChannelArchiveOpsProtocol)
        )
    except Exception as e:
        logger.warning("Archive ops not available: %s", e)

    try:
        channel_info_ops = cast(ChannelInfoOps, await container.aget(ChannelInfoOpsProtocol))
    except Exception as e:
        logger.warning("Channel info ops not available: %s", e)

    try:
        channel_membership_ops = cast(
            ChannelMembershipOps, await container.aget(ChannelMembershipOpsProtocol)
        )
    except Exception as e:
        logger.warning("Channel membership ops not available: %s", e)

    try:
        user_ops = cast(SlackUserOps, await container.aget(SlackUserOpsProtocol))
    except Exception as e:
        logger.warning("User ops not available: %s", e)

    try:
        channel_message_ops = cast(
            SlackChannelMessageOps, await container.aget(SlackChannelMessageOpsProtocol)
        )
    except Exception as e:
        logger.warning("Channel message ops not available: %s", e)

    try:
        restore_state_manager = await container.aget(RestoreStateManagerProtocol)
    except Exception as e:
        logger.warning("Restore state manager not available: %s", e)

    try:
        bot_membership_ops = await container.aget(SlackChannelBotMembershipOpsProtocol)
    except Exception as e:
        logger.warning("Bot membership ops not available: %s", e)

    try:
        channel_restore_ops = await container.aget(SlackChannelRestoreOpsProtocol)
    except Exception as e:
        logger.warning("Channel restore ops not available: %s", e)

    # Interactive element handlers
    feedback_reactions_handler = None
    feedback_report_handler = None
    channel_metadata_edit_handler = None
    shortcut_handler = None
    trust_endorsement_handler = None
    access_request_handler = None
    flag_review_handler = None
    home_tab_handler = None

    try:
        feedback_reactions_handler = cast(
            FeedbackReactionsHandler, container.get(FeedbackReactionsHandlerProtocol)
        )
    except Exception as e:
        logger.warning("FeedbackReactionsHandler not available: %s", e)

    try:
        feedback_report_handler = cast(
            FeedbackReportHandler, container.get(FeedbackReportHandlerProtocol)
        )
    except Exception as e:
        logger.warning("FeedbackReportHandler not available: %s", e)

    try:
        channel_metadata_edit_handler = cast(
            ChannelMetadataEditHandler, container.get(ChannelMetadataEditHandlerProtocol)
        )
    except Exception as e:
        logger.warning("ChannelMetadataEditHandler not available: %s", e)

    try:
        shortcut_handler = cast(ShortcutHandler, container.get(ShortcutHandlerProtocol))
    except Exception as e:
        logger.warning("ShortcutHandler not available: %s", e)

    try:
        trust_endorsement_handler = await container.aget(TrustEndorsementHandlerProtocol)
    except Exception as e:
        logger.warning("TrustEndorsementHandler not available: %s", e)

    try:
        access_request_handler = await container.aget(AccessRequestHandlerProtocol)
    except Exception as e:
        logger.warning("AccessRequestHandler not available: %s", e)

    try:
        flag_review_handler = await container.aget(FlagReviewHandlerProtocol)
    except Exception as e:
        logger.warning("FlagReviewHandler not available: %s", e)

    try:
        home_tab_handler = await container.aget(HomeTabHandlerProtocol)
    except Exception as e:
        logger.warning("HomeTabHandler not available: %s", e)

    # CSOPM Handler for interactive button actions
    # Note: CSOPMSlackNotifier is instantiated directly here because the protocol
    # is only registered in the csopm_notifier container, not in ketchup-app.
    # state_tracker and metrics are None (graceful degradation - core actions still work)
    csopm_handler = None
    try:
        mcp_client = await container.aget(AsyncMCPClient)
        if slack_posting_handler and user_ops and mcp_client:
            # Create CSOPMSlackNotifier directly (not via protocol)
            csopm_notifier = CSOPMSlackNotifier(
                posting_handler=slack_posting_handler,
                user_ops=user_ops,
                mcp_client=mcp_client,
                state_tracker=None,  # Not available in ketchup-app context
                metrics=None,  # Not available in ketchup-app context
            )
            csopm_handler = CSOPMHandler(
                slack_notifier=csopm_notifier,
                mcp_client=mcp_client,
                posting_handler=slack_posting_handler,
            )
            logger.info("CSOPMHandler instantiated with direct CSOPMSlackNotifier")
    except Exception as e:
        logger.warning("CSOPMHandler not available: %s", e)

    # Handle missing Slack dependencies gracefully
    if not slack_posting_handler:
        logger.error(
            "SlackPostingHandler is required but not available. Cannot proceed without Slack integration."
        )
        raise ValueError("SlackPostingHandler is required for request processing")

    # Instantiate dependencies NOT managed by the container
    block_kit_builder = BlockKitBuilder(posting_handler=slack_posting_handler)
    logger.info("BlockKitBuilder instantiated directly.")

    # Configure BlockKitBuilder with error handling
    if not hasattr(slack_posting_handler, "post_message") or not callable(
        slack_posting_handler.post_message
    ):
        logger.error("SlackPostingHandler or its post_message method is missing/not callable.")
        raise ValueError("Missing message sender for BlockKitBuilder configuration.")

    if not hasattr(dynamodb_store, "get_channel_details") or not callable(
        dynamodb_store.get_channel_details
    ):
        logger.error(
            "Required channel details getter method (get_channel_details) is missing/not callable from DynamoDBStore."
        )
        raise ValueError("Missing channel details getter for BlockKitBuilder configuration.")
    channel_details_getter = cast(
        Callable[..., Awaitable[Dict[str, Any]]], dynamodb_store.get_channel_details
    )

    # Only configure feedback blocks if handler is available
    feedback_builder_func = None
    if (
        feedback_reactions_handler
        and hasattr(feedback_reactions_handler, "build_feedback_blocks")
        and callable(feedback_reactions_handler.build_feedback_blocks)
    ):
        feedback_builder_func = feedback_reactions_handler.build_feedback_blocks
        logger.info("Feedback blocks builder available")
    else:
        logger.warning(
            "Feedback blocks builder not available - feedback functionality will be limited"
        )

    # Configure BlockKitBuilder with available components
    block_kit_builder.configure(
        channel_details_getter=channel_details_getter,
        build_feedback_blocks_func=feedback_builder_func,
    )
    logger.info("BlockKitBuilder configured with available components.")

    # Instantiate Services using available dependencies
    channel_eligibility_service = None
    if channel_info_ops and slack_posting_handler and dynamodb_store:
        channel_eligibility_service = ChannelEligibilityService(
            channel_info_ops=channel_info_ops,
            posting_handler=slack_posting_handler,
            dynamodb_store=dynamodb_store,
        )
        logger.info("ChannelEligibilityService instantiated")
    else:
        logger.warning("ChannelEligibilityService not available due to missing dependencies")

    # --- Instantiate Command Handlers --- #
    command_handlers = {"command_handlers_dict": {}}

    # Only instantiate command handlers if we have minimum dependencies
    if (
        channel_info_ops
        and channel_membership_ops
        and slack_posting_handler
        and dynamodb_store
        and block_kit_builder
    ):

        # Prepare the client dictionary for the handler instantiation function
        handler_clients = {
            "info_ops": channel_info_ops,
            "membership_ops": channel_membership_ops,
            "slack_posting_handler": slack_posting_handler,
            "dynamodb_store": dynamodb_store,
            "block_kit_builder": block_kit_builder,
            "archive_ops": archive_ops,
            "openai_handler": openai_handler,
            "channel_message_ops": channel_message_ops,
            "user_store": user_store,
            "user_ops": user_ops,
            "restore_ops": channel_restore_ops,
            "slack_config": slack_config,
            "feedback_reactions_handler": feedback_reactions_handler,
        }

        try:
            command_handlers = instantiate_command_handlers(
                handler_clients, block_kit_builder, secrets_manager
            )
            logger.info("Command handlers instantiated successfully")
        except Exception as e:
            logger.warning("Failed to instantiate command handlers: %s", e)
            command_handlers = {"command_handlers_dict": {}}
    else:
        logger.warning("Insufficient dependencies for command handlers - skipping instantiation")

    # Get optional services from container
    feature_service = None
    user_join_notification_service = None

    try:
        feature_service = await container.aget(FeatureServiceProtocol)
    except Exception as e:
        logger.warning("Feature service not available: %s", e)

    try:
        user_join_notification_service = await container.aget(UserJoinNotificationServiceProtocol)
    except Exception as e:
        logger.warning("User join notification service not available: %s", e)

    # Instantiate feature command handler if available
    if feature_service and slack_posting_handler and user_ops:
        try:
            feature_handler = FeatureCommand(
                feature_service=feature_service,
                slack_posting_handler=slack_posting_handler,
                slack_user_ops=user_ops,
                secrets_manager=secrets_manager,
            )
            # Add feature handler to command handlers dictionary
            command_handlers["command_handlers_dict"][CommandType.FEATURE.value] = feature_handler
            command_handlers["feature_handler"] = feature_handler
            logger.info("Feature command handler instantiated")
        except Exception as e:
            logger.warning("Failed to instantiate feature command handler: %s", e)

    # Instantiate access command handler if dependencies available
    if slack_posting_handler and user_verifier:
        try:
            access_handler = AccessCommand(
                slack_posting_handler=slack_posting_handler, user_verifier=user_verifier
            )
            # Add to command handlers dictionary
            command_handlers["command_handlers_dict"][CommandType.ACCESS.value] = access_handler
            command_handlers["access_handler"] = access_handler
            logger.info("Access command handler instantiated")
        except Exception as e:
            logger.warning("Failed to instantiate access command handler: %s", e)

    # --- Get CommandRouter from TypedDI Container --- #
    # TypedDI already registers CommandRouter with all handlers including metrics
    command_router = None
    try:
        command_router = await container.aget(CommandRouterProtocol)
        if command_router is None:
            logger.error("CommandRouter resolved to None from TypedDI container")
        else:
            logger.info(
                "CommandRouter retrieved from TypedDI container with all registered handlers."
            )
    except Exception as e:
        logger.warning("Failed to retrieve CommandRouter from TypedDI container: %s", e)
        # Fallback: Manually instantiate CommandRouter when TypedDI is disabled
        # This happens when smoke checks fail and system falls back to legacy DI
        if (
            slack_posting_handler
            and user_verifier
            and user_store
            and command_handlers.get("command_handlers_dict")
        ):
            try:
                logger.info("Manually instantiating CommandRouter as fallback")
                command_router = CommandRouter(
                    command_handlers=command_handlers["command_handlers_dict"],
                    slack_posting_handler=slack_posting_handler,
                    user_verifier=user_verifier,
                    user_store=user_store,
                    command_tracking_ops=None,  # Optional - not available in legacy DI
                )
                logger.info("CommandRouter successfully instantiated as fallback")
            except Exception as fallback_error:
                logger.error("Failed to manually instantiate CommandRouter: %s", fallback_error)

    # --- Instantiate SlackEventHandler --- #
    event_handler = None
    if secrets_manager and dynamodb_store and slack_posting_handler and user_store:
        try:
            event_handler = SlackEventHandler(
                secrets_manager=secrets_manager,
                dynamodb_store=dynamodb_store,
                posting_handler=slack_posting_handler,
                channel_info_ops=channel_info_ops,
                channel_membership_ops=channel_membership_ops,
                channel_restore_ops=channel_restore_ops,
                block_kit_builder=block_kit_builder,
                channel_eligibility_service=channel_eligibility_service,
                restore_state_manager=restore_state_manager,
                list_command=command_handlers.get("list_handler"),
                feature_service=feature_service,
                user_join_notification_service=user_join_notification_service,
                user_store=user_store,
            )
            logger.info("SlackEventHandler instantiated.")
        except Exception as e:
            logger.warning("Failed to instantiate SlackEventHandler: %s", e)
    else:
        logger.warning("SlackEventHandler not instantiated due to missing dependencies")

    logger.info("Dependencies setup complete.")

    # Return all instantiated/retrieved components
    all_dependencies = {
        # Core clients/ops (using standard keys)
        "slack_posting": slack_posting_handler,
        "dynamodb_store": dynamodb_store,
        "openai": openai_handler,
        "archive_ops": archive_ops,
        "info_ops": channel_info_ops,
        "membership_ops": channel_membership_ops,
        "user_ops": user_ops,
        "msg_ops": channel_message_ops,
        "restore_state": restore_state_manager,
        "bot_membership_ops": bot_membership_ops,
        "restore_ops": channel_restore_ops,
        "feedback_reactions_handler": feedback_reactions_handler,
        "feedback_report_handler": feedback_report_handler,
        "channel_metadata_edit_handler": channel_metadata_edit_handler,
        "shortcut_handler": shortcut_handler,
        "trust_endorsement_handler": trust_endorsement_handler,
        "access_request_handler": access_request_handler,
        "flag_review_handler": flag_review_handler,
        "csopm_handler": csopm_handler,
        "secrets_manager": secrets_manager,
        "slack_auth": slack_auth,
        "user_verifier": user_verifier,
        # Locally instantiated components
        "block_kit_builder": block_kit_builder,
        "channel_eligibility_service": channel_eligibility_service,
        "event_handler": event_handler,
        "command_router": command_router,
        # Add specific command handlers
        **command_handlers,
        # Add HomeTabHandler for Home tab events
        "home_tab_handler": home_tab_handler,
    }

    return all_dependencies
