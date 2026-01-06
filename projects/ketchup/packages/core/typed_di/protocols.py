# Central protocol imports for typed DI migration
# This file acts as a central import point for all protocol definitions

# Import all protocols from modular files
from .aws_protocols import (  # AWS-specific protocols
    KetchupConfigProtocol,
    SecretsManagerProtocol,
    SecretStoreProtocol,
    VersionComparatorProtocol,
)
from .core_protocols import (  # Type aliases and data classes
    AsyncFactory,
    AsyncProvider,
    DependencySpec,
    DIContainerProtocol,
    DistributedLockProtocol,
    Factory,
    FallbackRegistryProtocol,
    HTTPClientProtocol,
    InitializationStats,
    Provider,
    ServiceRegistration,
    T,
    TypedDIProtocol,
)
from .service_protocols import (  # Business service protocols
    AccessRequestServiceProtocol,
    AccessServiceProtocol,
    ChannelDynamoDBServiceProtocol,
    ChannelInfoOpsServiceProtocol,
    ChannelMetadataServiceProtocol,
    FeatureServiceProtocol,
    JIRAReporterServiceProtocol,
    JiraValidationServiceProtocol,
    KetchupAIServiceProtocol,
    KetchupJIRAClientProtocol,
    RateLimiterProtocol,
    StatusCommandServiceProtocol,
)
from .service_registrations.protocols.csopm_protocols import (  # CSOPM notifier protocols
    CSOPMJIRAPollerProtocol,
    CSOPMMetricsProtocol,
    CSOPMReminderServiceProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
    CSOPMTicket,
    FollowupRecord,
    NotificationRecord,
)
from .slack_protocols import (  # Slack-specific protocols
    CommandHandlerProtocol,
    EventHandlerProtocol,
    HomeTabHandlerProtocol,
    InteractiveHandlerProtocol,
    KetchupSlackServiceProtocol,
    MessageHandlerProtocol,
    SlackPostingHandlerProtocol,
    SlackUserStoreProtocol,
    SlackWebClientProtocol,
)

# Re-export all protocols for backward compatibility
__all__ = [
    # Type aliases and data classes
    "T",
    "Factory",
    "AsyncFactory",
    "Provider",
    "AsyncProvider",
    "DependencySpec",
    "InitializationStats",
    "ServiceRegistration",
    # Core infrastructure protocols
    "DIContainerProtocol",
    "TypedDIProtocol",
    "FallbackRegistryProtocol",
    "DistributedLockProtocol",
    "HTTPClientProtocol",
    # AWS-specific protocols
    "VersionComparatorProtocol",
    "SecretStoreProtocol",
    "SecretsManagerProtocol",
    "KetchupConfigProtocol",
    # Slack-specific protocols
    "SlackUserStoreProtocol",
    "SlackWebClientProtocol",
    "KetchupSlackServiceProtocol",
    "SlackPostingHandlerProtocol",
    "HomeTabHandlerProtocol",
    "MessageHandlerProtocol",
    "CommandHandlerProtocol",
    "InteractiveHandlerProtocol",
    "EventHandlerProtocol",
    # Business service protocols
    "ChannelMetadataServiceProtocol",
    "ChannelDynamoDBServiceProtocol",
    "AccessRequestServiceProtocol",
    "KetchupJIRAClientProtocol",
    "JIRAReporterServiceProtocol",
    "StatusCommandServiceProtocol",
    "KetchupAIServiceProtocol",
    "AccessServiceProtocol",
    "ChannelInfoOpsServiceProtocol",
    "JiraValidationServiceProtocol",
    "RateLimiterProtocol",
    "FeatureServiceProtocol",
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
