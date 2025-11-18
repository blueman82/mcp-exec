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
from .core_protocols import (
    UserStoreProtocol,
    DynamoDBConfigProtocol,
    DynamoDBAsyncClientProtocol,
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
    SQSClientProtocol,
)

# Infrastructure protocols
from .infrastructure_protocols import (
    AsyncClientProtocol,
    ExponentialBackoffStrategyProtocol,
    MetricsStorageProtocol,
    TypedResolverProtocol,
    EventProcessorProtocol,
    BatchSizeManagerProtocol,
    iPaaSRateLimiterProtocol,
    DistributedLockProtocol,
    IMSTokenManagerProtocol,
    TokenTrackerProtocol,
)

# Slack protocols
from .slack_protocols import (
    SlackAsyncClientProtocol,
    SlackAuthProtocol,
    SlackChannelArchiveOpsProtocol,
    SlackChannelMessageOpsProtocol,
    SlackEventHandlerProtocol,
    SlackUserStoreProtocol,
    ChannelEligibilityServiceProtocol,
    ChannelPolicyServiceProtocol,
    ChannelMetricsServiceProtocol,
    ChannelAnalyticsServiceProtocol,
    ChannelValidationServiceProtocol,
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    ChannelMetadataEditHandlerProtocol,
    ChannelNameResolverProtocol,
    ChannelOperationsProtocol,
    SlackChannelBotMembershipOpsProtocol,
    SlackChannelRestoreOpsProtocol,
    SlackUserOpsProtocol,
    UserJoinNotificationServiceProtocol,
    ChannelNotificationServiceProtocol,
    StatusNotificationServiceProtocol,
    AlertNotificationServiceProtocol,
    SystemNotificationServiceProtocol,
    UserVerifierProtocol,
    ArchiveProcessorProtocol,
    CreationProcessorProtocol,
    JoinProcessorProtocol,
    PayloadProcessorProtocol,
    UnarchiveProcessorProtocol,
    UserManagementServiceProtocol,
    UserPermissionServiceProtocol,
    UserActivityServiceProtocol,
    UserPreferenceServiceProtocol,
    UserAnalyticsServiceProtocol,
)

# Operation protocols
from .operation_protocols import (
    BaseOperationsProtocol,
    RestoreStateOperationsProtocol,
    TrustOperationsProtocol,
    JoinNotificationOpsProtocol,
    RestoreStateManagerProtocol,
    AccessRequestOperationsProtocol,
    AccessRequestProtocol,
)

# Handler protocols
from .handler_protocols import (
    BaseCommandHandlerProtocol,
    FlagReviewDatabaseOperationsProtocol,
    FlagReviewDMHandlerProtocol,
    FlagReviewMessageHandlerProtocol,
    FlagReviewModalManagerProtocol,
    AccessRequestHandlerProtocol,
    AccessRequestBlocksProtocol,
    AccessRequestMonitorProtocol,
    FlagReviewHandlerProtocol,
    HomeTabHandlerProtocol,
    OpenAIHandlerProtocol,
    ShortcutHandlerProtocol,
    TrustEndorsementHandlerProtocol,
    UsageExportHandlerProtocol,
)

# AI protocols
from .ai_protocols import (
    ApiExecutorProtocol,
    MessagePreparerProtocol,
    AzureConfigProtocol,
    AIPromptTemplateServiceProtocol,
    AIContextWindowServiceProtocol,
    AITokenCountServiceProtocol,
    AICostCalculationServiceProtocol,
    AIModelSelectionServiceProtocol,
    AIResponseCacheServiceProtocol,
    AIStreamingServiceProtocol,
    AIBatchProcessingServiceProtocol,
    AIRateLimitServiceProtocol,
    AIRetryServiceProtocol,
    AIErrorHandlingServiceProtocol,
    AIPerformanceMonitoringServiceProtocol,
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

# MCP protocols
from .mcp_protocols import (
    MCPAsyncClientProtocol,
    MCPClientProtocol,
    MCPConfigProtocol,
)

# Command protocols
from .command_protocols import (
    AccessCommandProtocol,
    ListCommandProtocol,
    QueryCommandProtocol,
    VerifyCommandProtocol,
    StatusReportCommandProtocol,
    ShortLongCommandProtocol,
    SlackArchiveCommandProtocol,
    SlackListCommandProtocol,
    SlackQueryHandlerProtocol,
    SlackSummaryHandlerProtocol,
    CommandRouterProtocol,
    CommandTrackingOperationsProtocol,
    CommandUsageCSVGeneratorProtocol,
    FeatureCommandProtocol,
    FeatureServiceProtocol,
)

# UI protocols
from .ui_protocols import (
    BlockKitBuilderProtocol,
    SlackMessageFormatterProtocol,
    FeedbackOperationsProtocol,
    BlockBuilderProtocol,
    FeedbackReactionsHandlerProtocol,
    FeedbackReportHandlerProtocol,
    ArchiveMessageHandlerProtocol,
    LookupMessageHandlerProtocol,
    QueryMessageHandlerProtocol,
    ReportMessageHandlerProtocol,
    StatusMessageHandlerProtocol,
    SummaryMessageHandlerProtocol,
    ParameterMessageHandlerProtocol,
)

# JIRA protocols
from .jira_protocols import (
    JIRACacheProtocol,
    JIRADataExtractorProtocol,
    SlackReportsProtocol,
)

# Registry protocols
from .registry_protocols import (
    TypedServiceRegistryProtocol,
)

# Business rule protocols
from .business_rule_protocols import (
    RuleEngineServiceProtocol,
    PolicyValidationServiceProtocol,
    ComplianceServiceProtocol,
    AuditServiceProtocol,
    GovernanceServiceProtocol,
)

# Workflow management protocols
from .workflow_protocols import (
    WorkflowEngineServiceProtocol,
    TaskManagementServiceProtocol,
    ProcessAutomationServiceProtocol,
    StateManagementServiceProtocol,
    TransitionServiceProtocol,
)

# Status update protocols
from .status_update_protocols import (
    StatusUpdateProcessorProtocol,
    StatusGeneratorProtocol,
    StatusValidationServiceProtocol,
    StatusReportingServiceProtocol,
    StatusAnalyticsServiceProtocol,
)

# Archive processing protocols
from .archive_processing_protocols import (
    ArchiveValidationServiceProtocol,
    ArchiveReportingServiceProtocol,
    ArchiveAnalyticsServiceProtocol,
    ArchiveCleanupServiceProtocol,
)

# External API integration protocols
from .external_api_protocols import (
    APIGatewayServiceProtocol,
    ExternalServiceClientProtocol,
    WebhookServiceProtocol,
    CallbackServiceProtocol,
    IntegrationMonitoringServiceProtocol,
)

# Maintenance detection protocols
from .maintenance_protocols import (
    RavenMaintenanceClientProtocol,
    MaintenanceCheckerProtocol,
    JiraPromptHandlerProtocol,
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
    "MCPClientProtocol",
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
]