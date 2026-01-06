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
from .ai_protocols import (
    AIBatchProcessingServiceProtocol,
    AIContextWindowServiceProtocol,
    AICostCalculationServiceProtocol,
    AIErrorHandlingServiceProtocol,
    AIModelSelectionServiceProtocol,
    AIPerformanceMonitoringServiceProtocol,
    AIPromptTemplateServiceProtocol,
    AIRateLimitServiceProtocol,
    AIResponseCacheServiceProtocol,
    AIRetryServiceProtocol,
    AIStreamingServiceProtocol,
    AITokenCountServiceProtocol,
    ApiExecutorProtocol,
    AzureConfigProtocol,
    MessagePreparerProtocol,
)

# Archive processing protocols
from .archive_processing_protocols import (
    ArchiveAnalyticsServiceProtocol,
    ArchiveCleanupServiceProtocol,
    ArchiveReportingServiceProtocol,
    ArchiveValidationServiceProtocol,
)

# Business rule protocols
from .business_rule_protocols import (
    AuditServiceProtocol,
    ComplianceServiceProtocol,
    GovernanceServiceProtocol,
    PolicyValidationServiceProtocol,
    RuleEngineServiceProtocol,
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
    ShortLongCommandProtocol,
    SlackArchiveCommandProtocol,
    SlackListCommandProtocol,
    SlackQueryHandlerProtocol,
    SlackSummaryHandlerProtocol,
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

# Database protocols
from .database_protocols import (
    DatabaseBackupServiceProtocol,
    DatabaseConnectionServiceProtocol,
    DatabaseIndexServiceProtocol,
    DatabaseMigrationServiceProtocol,
    DatabaseMonitoringServiceProtocol,
    DatabasePoolServiceProtocol,
    DatabaseQueryServiceProtocol,
    DatabaseRestoreServiceProtocol,
    DatabaseTransactionServiceProtocol,
)

# External API integration protocols
from .external_api_protocols import (
    APIGatewayServiceProtocol,
    CallbackServiceProtocol,
    ExternalServiceClientProtocol,
    IntegrationMonitoringServiceProtocol,
    WebhookServiceProtocol,
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
    SummaryMessageHandlerProtocol,
)

# Workflow management protocols
from .workflow_protocols import (
    ProcessAutomationServiceProtocol,
    StateManagementServiceProtocol,
    TaskManagementServiceProtocol,
    TransitionServiceProtocol,
    WorkflowEngineServiceProtocol,
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
    "SlackSummaryHandlerProtocol",
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
    "AIErrorHandlingServiceProtocol",
    "AIPerformanceMonitoringServiceProtocol",
    # Command service protocols
    "ListCommandProtocol",
    "QueryCommandProtocol",
    "VerifyCommandProtocol",
    "StatusReportCommandProtocol",
    "ShortLongCommandProtocol",
    # Event processor protocols
    "ArchiveProcessorProtocol",
    "CreationProcessorProtocol",
    "JoinProcessorProtocol",
    "PayloadProcessorProtocol",
    # Message handler protocols
    "QueryMessageHandlerProtocol",
    "ReportMessageHandlerProtocol",
    "StatusMessageHandlerProtocol",
    "SummaryMessageHandlerProtocol",
    "ParameterMessageHandlerProtocol",
    # Additional UI service protocols
    "SlackMessageFormatterProtocol",
    "FeedbackOperationsProtocol",
    "BlockBuilderProtocol",
    # Database service protocols
    "DatabaseBackupServiceProtocol",
    "DatabaseConnectionServiceProtocol",
    "DatabaseIndexServiceProtocol",
    "DatabaseMigrationServiceProtocol",
    "DatabaseMonitoringServiceProtocol",
    "DatabasePoolServiceProtocol",
    "DatabaseQueryServiceProtocol",
    "DatabaseRestoreServiceProtocol",
    "DatabaseTransactionServiceProtocol",
    # AI enhancement service protocols
    "AIBatchProcessingServiceProtocol",
    "AICostCalculationServiceProtocol",
    "AIContextWindowServiceProtocol",
    "AIModelSelectionServiceProtocol",
    "AIPromptTemplateServiceProtocol",
    "AIRateLimitServiceProtocol",
    "AIResponseCacheServiceProtocol",
    "AIRetryServiceProtocol",
    "AIStreamingServiceProtocol",
    "AITokenCountServiceProtocol",
    # Business rule service protocols
    "RuleEngineServiceProtocol",
    "PolicyValidationServiceProtocol",
    "ComplianceServiceProtocol",
    "AuditServiceProtocol",
    "GovernanceServiceProtocol",
    # Workflow management protocols
    "WorkflowEngineServiceProtocol",
    "TaskManagementServiceProtocol",
    "ProcessAutomationServiceProtocol",
    "StateManagementServiceProtocol",
    "TransitionServiceProtocol",
    # Status update protocols
    "StatusUpdateProcessorProtocol",
    "StatusGeneratorProtocol",
    "StatusValidationServiceProtocol",
    "StatusReportingServiceProtocol",
    "StatusAnalyticsServiceProtocol",
    # Archive processing protocols
    "ArchiveValidationServiceProtocol",
    "ArchiveReportingServiceProtocol",
    "ArchiveAnalyticsServiceProtocol",
    "ArchiveCleanupServiceProtocol",
    # External API integration protocols
    "APIGatewayServiceProtocol",
    "ExternalServiceClientProtocol",
    "WebhookServiceProtocol",
    "CallbackServiceProtocol",
    "IntegrationMonitoringServiceProtocol",
    # Maintenance detection protocols
    "RavenMaintenanceClientProtocol",
    "MaintenanceCheckerProtocol",
    "JiraPromptHandlerProtocol",
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
