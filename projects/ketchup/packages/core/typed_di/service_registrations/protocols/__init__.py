"""
Service Registration Protocols Module

This module provides clean access to all service protocols without circular imports.
It acts as a bridge between the modular protocol definitions and the
registration system.

All protocols are now organized into domain-specific modules to avoid
circular dependencies and improve maintainability.
"""

# Import protocols from modular files instead of service_registrations_original
# Core infrastructure protocols
# AI protocols
# Agent protocols
from .agent_protocols import (
    AgentBackfillIngestorProtocol,
    AgentContextBuilderProtocol,
    AgentConversationStoreProtocol,
    AgentEmbeddingsClientProtocol,
    AgentEngineProtocol,
    AgentJiraBackfillIngestorProtocol,
    AgentRealtimeIngestorProtocol,
    AgentRetrieverProtocol,
    AgentSlackHandlerProtocol,
    AgentThreadFilterProtocol,
    AgentThreadManagerProtocol,
    AgentVectorStoreProtocol,
    JiraBulkIndexerProtocol,
    RCAToolExecutorProtocol,
    SkillRegistryProtocol,
    SkillRouterProtocol,
)
from .ai_protocols import (
    ApiExecutorProtocol,
    AzureConfigProtocol,
    MessagePreparerProtocol,
)

# Command protocols
from .command_protocols import (
    AccessCommandProtocol,
    CommandRouterProtocol,
    CommandTrackingOperationsProtocol,
    CommandUsageCSVGeneratorProtocol,
    FeatureCommandProtocol,
    FeatureServiceProtocol,
    ListCommandProtocol,
    QueryCommandProtocol,
    SlackArchiveCommandProtocol,
    SlackListCommandProtocol,
    SlackQueryHandlerProtocol,
    StatusReportCommandProtocol,
    VerifyCommandProtocol,
)
from .core_protocols import (
    DynamoDBAsyncClientProtocol,
    DynamoDBConfigProtocol,
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
    SQSClientProtocol,
    UserStoreProtocol,
)

# CSOPM notifier protocols
from .csopm_protocols import (
    CSOPMJIRAPollerProtocol,
    CSOPMMetricsProtocol,
    CSOPMReminderServiceProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
    FollowupRecord,
    NotificationRecord,
)

# Handler protocols
from .handler_protocols import (
    AccessRequestBlocksProtocol,
    AccessRequestHandlerProtocol,
    AccessRequestMonitorProtocol,
    BaseCommandHandlerProtocol,
    FlagReviewDatabaseOperationsProtocol,
    FlagReviewDMHandlerProtocol,
    FlagReviewHandlerProtocol,
    FlagReviewMessageHandlerProtocol,
    FlagReviewModalManagerProtocol,
    HomeTabHandlerProtocol,
    OpenAIHandlerProtocol,
    ShortcutHandlerProtocol,
    TrustEndorsementHandlerProtocol,
    UsageExportHandlerProtocol,
)

# Infrastructure protocols
from .infrastructure_protocols import (
    AsyncClientProtocol,
    BatchSizeManagerProtocol,
    DistributedLockProtocol,
    EventProcessorProtocol,
    ExponentialBackoffStrategyProtocol,
    IMSTokenManagerProtocol,
    MetricsStorageProtocol,
    TokenTrackerProtocol,
    TypedResolverProtocol,
    iPaaSRateLimiterProtocol,
)

# JIRA protocols
from .jira_protocols import (
    JIRACacheProtocol,
    JIRADataExtractorProtocol,
    SlackReportsProtocol,
)

# Maintenance detection protocols
from .maintenance_protocols import (
    JiraPromptHandlerProtocol,
    MaintenanceCheckerProtocol,
    RavenMaintenanceClientProtocol,
)

# MCP protocols (only MCPAsyncClientProtocol remains after consolidation)
from .mcp_protocols import (
    MCPAsyncClientProtocol,
    MCPConfigProtocol,
)

# Operation protocols
from .operation_protocols import (
    AccessRequestOperationsProtocol,
    AccessRequestProtocol,
    BaseOperationsProtocol,
    JoinNotificationOpsProtocol,
    RestoreStateManagerProtocol,
    RestoreStateOperationsProtocol,
    TrustOperationsProtocol,
)

# Registry protocols
from .registry_protocols import (
    TypedServiceRegistryProtocol,
)

# Slack protocols
from .slack_protocols import (
    AlertNotificationServiceProtocol,
    ArchiveProcessorProtocol,
    ChannelAnalyticsServiceProtocol,
    ChannelEligibilityServiceProtocol,
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    ChannelMetadataEditHandlerProtocol,
    ChannelMetricsServiceProtocol,
    ChannelNameResolverProtocol,
    ChannelNotificationServiceProtocol,
    ChannelOperationsProtocol,
    ChannelPolicyServiceProtocol,
    ChannelValidationServiceProtocol,
    CreationProcessorProtocol,
    JoinProcessorProtocol,
    PayloadProcessorProtocol,
    SlackAsyncClientProtocol,
    SlackAuthProtocol,
    SlackChannelArchiveOpsProtocol,
    SlackChannelBotMembershipOpsProtocol,
    SlackChannelMessageOpsProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackEventHandlerProtocol,
    SlackUserOpsProtocol,
    SlackUserStoreProtocol,
    StatusNotificationServiceProtocol,
    SystemNotificationServiceProtocol,
    UnarchiveProcessorProtocol,
    UserActivityServiceProtocol,
    UserAnalyticsServiceProtocol,
    UserJoinNotificationServiceProtocol,
    UserManagementServiceProtocol,
    UserPermissionServiceProtocol,
    UserPreferenceServiceProtocol,
    UserVerifierProtocol,
)

# Status update protocols
from .status_update_protocols import (
    StatusAnalyticsServiceProtocol,
    StatusGeneratorProtocol,
    StatusReportingServiceProtocol,
    StatusUpdateProcessorProtocol,
    StatusValidationServiceProtocol,
)

# UI protocols
from .ui_protocols import (
    ArchiveMessageHandlerProtocol,
    BlockBuilderProtocol,
    BlockKitBuilderProtocol,
    FeedbackOperationsProtocol,
    FeedbackReactionsHandlerProtocol,
    FeedbackReportHandlerProtocol,
    LookupMessageHandlerProtocol,
    ParameterMessageHandlerProtocol,
    QueryMessageHandlerProtocol,
    ReportMessageHandlerProtocol,
    SlackMessageFormatterProtocol,
    StatusMessageHandlerProtocol,
)

# All protocols are imported from modular domain-specific files

__all__ = [
    # Critical protocols needed by compatibility.py
    "UserStoreProtocol",
    "DynamoDBConfigProtocol",
    "DynamoDBAsyncClientProtocol",
    "DynamoDBStoreProtocol",
    "SecretsManagerProtocol",
    "SlackConfigProtocol",
    "SlackPostingHandlerProtocol",
    # Infrastructure protocols
    "AsyncClientProtocol",
    "ExponentialBackoffStrategyProtocol",
    "MetricsStorageProtocol",
    "SQSClientProtocol",
    "TypedResolverProtocol",
    "TypedServiceRegistryProtocol",
    # All other protocols
    "AccessCommandProtocol",
    "ApiExecutorProtocol",
    "ArchiveMessageHandlerProtocol",
    "AzureConfigProtocol",
    "BaseCommandHandlerProtocol",
    "BaseOperationsProtocol",
    "BatchSizeManagerProtocol",
    "BlockKitBuilderProtocol",
    "ChannelEligibilityServiceProtocol",
    "ChannelPolicyServiceProtocol",
    "ChannelMetricsServiceProtocol",
    "ChannelAnalyticsServiceProtocol",
    "ChannelValidationServiceProtocol",
    "ChannelInfoOpsProtocol",
    "ChannelMembershipOpsProtocol",
    "ChannelMetadataEditHandlerProtocol",
    "ChannelNameResolverProtocol",
    "ChannelOperationsProtocol",
    "CommandRouterProtocol",
    "CommandTrackingOperationsProtocol",
    "CommandUsageCSVGeneratorProtocol",
    "EventProcessorProtocol",
    "FeatureCommandProtocol",
    "FeatureServiceProtocol",
    "FeedbackReactionsHandlerProtocol",
    "FeedbackReportHandlerProtocol",
    "FlagReviewDatabaseOperationsProtocol",
    "FlagReviewDMHandlerProtocol",
    "FlagReviewMessageHandlerProtocol",
    "FlagReviewModalManagerProtocol",
    "FlagReviewHandlerProtocol",
    "HomeTabHandlerProtocol",
    "IMSTokenManagerProtocol",
    "JIRACacheProtocol",
    "JIRADataExtractorProtocol",
    "JoinNotificationOpsProtocol",
    "LookupMessageHandlerProtocol",
    "MCPAsyncClientProtocol",
    "MCPConfigProtocol",
    "MessagePreparerProtocol",
    "OpenAIHandlerProtocol",
    "RestoreStateManagerProtocol",
    "RestoreStateOperationsProtocol",
    "ShortcutHandlerProtocol",
    "SlackArchiveCommandProtocol",
    "SlackAsyncClientProtocol",
    "SlackAuthProtocol",
    "SlackChannelArchiveOpsProtocol",
    "SlackChannelBotMembershipOpsProtocol",
    "SlackChannelMessageOpsProtocol",
    "SlackChannelRestoreOpsProtocol",
    "SlackEventHandlerProtocol",
    "SlackListCommandProtocol",
    "SlackQueryHandlerProtocol",
    "SlackReportsProtocol",
    "SlackUserOpsProtocol",
    "SlackUserStoreProtocol",
    "TokenTrackerProtocol",
    "TrustEndorsementHandlerProtocol",
    "TrustOperationsProtocol",
    "UsageExportHandlerProtocol",
    "UserJoinNotificationServiceProtocol",
    "ChannelNotificationServiceProtocol",
    "StatusNotificationServiceProtocol",
    "AlertNotificationServiceProtocol",
    "SystemNotificationServiceProtocol",
    "UserVerifierProtocol",
    "UserManagementServiceProtocol",
    "UserPermissionServiceProtocol",
    "UserActivityServiceProtocol",
    "UserPreferenceServiceProtocol",
    "UserAnalyticsServiceProtocol",
    "iPaaSRateLimiterProtocol",
    "DistributedLockProtocol",
    "AccessRequestOperationsProtocol",
    "AccessRequestProtocol",
    "AccessRequestHandlerProtocol",
    "AccessRequestBlocksProtocol",
    "AccessRequestMonitorProtocol",
    "UnarchiveProcessorProtocol",
    # Command service protocols
    "ListCommandProtocol",
    "QueryCommandProtocol",
    "VerifyCommandProtocol",
    "StatusReportCommandProtocol",
    # Event processor protocols
    "ArchiveProcessorProtocol",
    "CreationProcessorProtocol",
    "JoinProcessorProtocol",
    "PayloadProcessorProtocol",
    # Message handler protocols
    "QueryMessageHandlerProtocol",
    "ReportMessageHandlerProtocol",
    "StatusMessageHandlerProtocol",
    "ParameterMessageHandlerProtocol",
    # Additional UI service protocols
    "SlackMessageFormatterProtocol",
    "FeedbackOperationsProtocol",
    "BlockBuilderProtocol",
    # Status update protocols
    "StatusUpdateProcessorProtocol",
    "StatusGeneratorProtocol",
    "StatusValidationServiceProtocol",
    "StatusReportingServiceProtocol",
    "StatusAnalyticsServiceProtocol",
    # Maintenance detection protocols
    "RavenMaintenanceClientProtocol",
    "MaintenanceCheckerProtocol",
    "JiraPromptHandlerProtocol",
    # Agent protocols
    "AgentEmbeddingsClientProtocol",
    "AgentVectorStoreProtocol",
    "AgentConversationStoreProtocol",
    "AgentRetrieverProtocol",
    "AgentContextBuilderProtocol",
    "AgentEngineProtocol",
    "AgentRealtimeIngestorProtocol",
    "AgentBackfillIngestorProtocol",
    "AgentJiraBackfillIngestorProtocol",
    "AgentSlackHandlerProtocol",
    "AgentThreadManagerProtocol",
    "AgentThreadFilterProtocol",
    "JiraBulkIndexerProtocol",
    "RCAToolExecutorProtocol",
    "SkillRegistryProtocol",
    "SkillRouterProtocol",
    # CSOPM notifier protocols (data classes)
    "CSOPMTicket",
    "NotificationRecord",
    "FollowupRecord",
    # CSOPM notifier protocols (service protocols)
    "CSOPMJIRAPollerProtocol",
    "CSOPMStateTrackerProtocol",
    "CSOPMSlackNotifierProtocol",
    "CSOPMReminderServiceProtocol",
    "CSOPMMetricsProtocol",
]
