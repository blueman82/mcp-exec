# Central protocol imports for typed DI migration
# This file acts as a central import point for all protocol definitions

# Import all protocols from modular files
from .core_protocols import (
    # Type aliases and data classes
    T, Factory, AsyncFactory, Provider, AsyncProvider, DependencySpec,
    InitializationStats, ServiceRegistration, DIContainerProtocol,
    TypedDIProtocol,
    FallbackRegistryProtocol,
    DistributedLockProtocol,
    HTTPClientProtocol,
)

from .aws_protocols import (
    # AWS-specific protocols
    VersionComparatorProtocol,
    SecretStoreProtocol,
    SecretsManagerProtocol,
    KetchupConfigProtocol,
)

from .slack_protocols import (
    # Slack-specific protocols
    SlackUserStoreProtocol,
    SlackWebClientProtocol,
    KetchupSlackServiceProtocol,
    SlackPostingHandlerProtocol,
    HomeTabHandlerProtocol,
    MessageHandlerProtocol,
    CommandHandlerProtocol,
    InteractiveHandlerProtocol,
    EventHandlerProtocol,
)

from .service_protocols import (
    # Business service protocols
    ChannelMetadataServiceProtocol,
    ChannelDynamoDBServiceProtocol,
    AccessRequestServiceProtocol,
    KetchupJIRAClientProtocol,
    JIRAReporterServiceProtocol,
    StatusCommandServiceProtocol,
    KetchupAIServiceProtocol,
    AccessServiceProtocol,
    ChannelInfoOpsServiceProtocol,
    JiraValidationServiceProtocol,
    RateLimiterProtocol,
    FeatureServiceProtocol,
)

# Re-export all protocols for backward compatibility
__all__ = [
    # Type aliases and data classes
    'T', 'Factory', 'AsyncFactory', 'Provider', 'AsyncProvider', 'DependencySpec',
    'InitializationStats', 'ServiceRegistration',

    # Core infrastructure protocols
    'DIContainerProtocol', 'TypedDIProtocol', 'FallbackRegistryProtocol',
    'DistributedLockProtocol', 'HTTPClientProtocol',

    # AWS-specific protocols
    'VersionComparatorProtocol', 'SecretStoreProtocol',
    'SecretsManagerProtocol', 'KetchupConfigProtocol',

    # Slack-specific protocols
    'SlackUserStoreProtocol', 'SlackWebClientProtocol', 'KetchupSlackServiceProtocol',
    'SlackPostingHandlerProtocol', 'HomeTabHandlerProtocol', 'MessageHandlerProtocol',
    'CommandHandlerProtocol', 'InteractiveHandlerProtocol', 'EventHandlerProtocol',

    # Business service protocols
    'ChannelMetadataServiceProtocol', 'ChannelDynamoDBServiceProtocol',
    'AccessRequestServiceProtocol', 'KetchupJIRAClientProtocol',
    'JIRAReporterServiceProtocol', 'StatusCommandServiceProtocol',
    'KetchupAIServiceProtocol', 'AccessServiceProtocol',
    'ChannelInfoOpsServiceProtocol', 'JiraValidationServiceProtocol',
    'RateLimiterProtocol', 'FeatureServiceProtocol',
]