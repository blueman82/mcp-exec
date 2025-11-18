Running full production test...
=== Azure OpenAI Authentication Test ===
INFO:__main__:Initializing Azure OpenAI client with proper authentication...
2025-08-21 17:02:41,227 - packages.secrets.manager - INFO - Starting get_azure_openai_lb_api_key function.
2025-08-21 17:02:41,227 - packages.secrets.manager - INFO - Starting get_app_secrets function.
2025-08-21 17:02:41,227 - packages.secrets.manager - INFO - Starting get_secret_async function.
INFO:aiobotocore.credentials:Found credentials in shared credentials file: ~/.aws/credentials
2025-08-21 17:02:41,618 - packages.secrets.manager - INFO - Application secrets retrieved successfully from AWS Secrets Manager.
2025-08-21 17:02:41,618 - packages.secrets.manager - INFO - Secrets cache updated
INFO:__main__:✓ Azure OpenAI API key retrieved from AWS Secrets Manager
2025-08-21 17:02:41,618 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient initialized with endpoint: https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15
2025-08-21 17:02:41,618 - packages.core.async_client - INFO - Entering setup() for AzureAsyncClient. Current session: None, Closed: N/A
INFO:AzureAsyncClient:Session creation attempt 1/5
INFO:AzureAsyncClient:Session created attempt 1/5. State - Closed: False
2025-08-21 17:02:41,618 - packages.core.async_client - INFO - Successfully established session in setup() for AzureAsyncClient.
INFO:__main__:✓ Azure OpenAI client initialized and connected
✓ Azure OpenAI client initialized successfully
INFO:__main__:Testing Azure OpenAI embeddings...
2025-08-21 17:02:41,618 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient._make_azure_api_request: Received URL: 'https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15'
2025-08-21 17:02:41,618 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient._make_azure_api_request: URL contains '?': True
2025-08-21 17:02:41,618 - packages.core.async_client - INFO - Entering setup() for AzureAsyncClient. Current session: <aiohttp.client.ClientSession object at 0x1051a1310>, Closed: False
2025-08-21 17:02:41,618 - packages.core.async_client - INFO - Session already exists and is open for AzureAsyncClient.
2025-08-21 17:02:41,618 - packages.core.async_client - INFO - Making POST request to https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15 for AzureAsyncClient (params=None)
2025-08-21 17:02:42,076 - packages.core.async_client - INFO - Request for AzureAsyncClient to https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15 completed with status 200
INFO:__main__:✓ Embeddings test successful: 1536 dimensions
INFO:__main__:✓ Embedding sample: [-0.018798266, -0.012451324, -0.009284591, -0.015213793, 0.009574314]...
✓ Azure OpenAI embeddings test passed

=== DI Container Initialization ===
Initializing production services...
2025-08-21 17:02:42,171 - packages.core.di_container - INFO - Initializing DIContainer with all modular clients
2025-08-21 17:02:42,171 - packages.core.client_factory.secrets_factory - INFO - Initializing core/global client instances (e.g., secrets_manager)
2025-08-21 17:02:42,171 - packages.core.client_factory.secrets_factory - INFO - Initialized core client: secrets_manager
2025-08-21 17:02:42,172 - packages.core.client_factory.db_factory - INFO - Initializing all DB-related client instances using DB_CLIENT_MAP
2025-08-21 17:02:42,172 - packages.db.operations.restore_state_operations - INFO - RestoreStateOperations initialized for table ketchup_channel_information with SK RESTORE_STATE
2025-08-21 17:02:42,172 - packages.db.operations.command_tracking_operations - INFO - CommandTrackingOperations initialized with table: ketchup_channel_information
2025-08-21 17:02:42,172 - packages.core.client_factory.db_factory - INFO - All DB client instances initialized successfully: ['dynamodb_config', 'dynamodb_async_client', 'dynamodb_store', 'user_store', 'command_tracking_ops', 'channel_operations']
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - Initializing all integration-related client instances using INTEGRATION_CLIENT_MAP
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: ims_token_manager (Singleton: True)
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - IMSTokenManager instance created successfully.
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: ims_token_manager
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: mcp_client (Singleton: True)
2025-08-21 17:02:42,172 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - MCPAsyncClient instance created successfully.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: mcp_client
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: jira_cache (Singleton: True)
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - JIRACache instance created successfully.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: jira_cache
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: local_metrics_collector (Singleton: True)
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,173 - packages.integrations.local_metrics - INFO - Metrics directory ensured at: /tmp/ketchup_metrics
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - LocalMetricsCollector instance created successfully.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: local_metrics_collector
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: jira_data_extractor (Singleton: True)
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - JIRADataExtractor instance created successfully.
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: jira_data_extractor
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: local_metrics_service (Singleton: True)
2025-08-21 17:02:42,173 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,175 - packages.core.local_metrics - ERROR - Failed to create log directory /var/log/jira_reporter: [Errno 13] Permission denied: '/var/log/jira_reporter'
2025-08-21 17:02:42,175 - packages.core.local_metrics - ERROR - Failed to create log directory /var/log/jira_reporter: [Errno 13] Permission denied: '/var/log/jira_reporter'
2025-08-21 17:02:42,175 - packages.core.client_factory.integration_factory - INFO - AccessRequestMonitor instance created successfully.
2025-08-21 17:02:42,175 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: local_metrics_service
2025-08-21 17:02:42,175 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: distributed_lock (Singleton: True)
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - DistributedLock instance created successfully.
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: distributed_lock
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - Initializing integration client: access_request_operations (Singleton: True)
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - AccessRequestOperations instance created successfully.
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - Successfully initialized client: access_request_operations
2025-08-21 17:02:42,176 - packages.core.client_factory.integration_factory - INFO - All integration client instances initialized successfully: ['ims_token_manager', 'mcp_client', 'jira_cache', 'local_metrics_collector', 'jira_data_extractor', 'local_metrics_service', 'distributed_lock', 'access_request_operations']
2025-08-21 17:02:42,176 - packages.core.client_factory.cloud_factory - INFO - Initializing all Cloud-related client instances using CLOUD_CLIENT_MAP
2025-08-21 17:02:42,176 - packages.core.client_factory.cloud_factory - INFO - Initializing Cloud client: cloudwatch_metrics (Singleton: True)
2025-08-21 17:02:42,176 - packages.core.client_factory.cloud_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,180 - packages.core.client_factory.cloud_factory - INFO - CloudWatchMetrics instance created successfully.
2025-08-21 17:02:42,180 - packages.core.client_factory.cloud_factory - INFO - Successfully initialized client: cloudwatch_metrics
2025-08-21 17:02:42,180 - packages.core.client_factory.cloud_factory - INFO - All Cloud client instances initialized successfully: ['cloudwatch_metrics']
2025-08-21 17:02:42,181 - packages.core.client_factory.slack_factory - INFO - Initializing all Slack-related client instances using SLACK_CLIENT_MAP
2025-08-21 17:02:42,181 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: slack_config (Singleton: True)
2025-08-21 17:02:42,181 - packages.core.client_factory.slack_factory - INFO - Creating SlackConfig instance via async factory function.
2025-08-21 17:02:42,181 - packages.secrets.manager - INFO - Starting get_slack_api_token_async function.
2025-08-21 17:02:42,181 - packages.secrets.manager - INFO - Starting get_app_secrets function.
2025-08-21 17:02:42,181 - packages.secrets.manager - INFO - Starting get_secret_async function.
INFO:aiobotocore.credentials:Found credentials in shared credentials file: ~/.aws/credentials
2025-08-21 17:02:42,497 - packages.secrets.manager - INFO - Application secrets retrieved successfully from AWS Secrets Manager.
2025-08-21 17:02:42,497 - packages.secrets.manager - INFO - Secrets cache updated
2025-08-21 17:02:42,497 - packages.slack.config.slack_config - INFO - SlackConfig initialized with instance-specific token.
2025-08-21 17:02:42,497 - packages.core.client_factory.slack_factory - INFO - SlackConfig instance created successfully.
2025-08-21 17:02:42,497 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: slack_config
2025-08-21 17:02:42,497 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: slack_async_client (Singleton: True)
2025-08-21 17:02:42,497 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: slack_async_client
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: slack_posting (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - SlackPostingHandler instance created successfully.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: slack_posting
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: slack_auth (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - SlackAuth instance created successfully.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: slack_auth
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: restore_state (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,498 - packages.slack.channel_operations.restore_state_manager - INFO - RestoreStateManager initialized with DynamoDBStore.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - RestoreStateManager instance created successfully.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: restore_state
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: archive_ops (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,498 - packages.slack.channel_operations.channel_archive_ops - INFO - SlackChannelArchiveOps initialized with injected dependencies.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - SlackChannelArchiveOps instance created successfully.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: archive_ops
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: info_ops (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,498 - packages.slack.channel_operations.channel_info_ops - INFO - ChannelInfoOps initialized with injected dependencies.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - ChannelInfoOps instance created successfully.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: info_ops
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: membership_ops (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,498 - packages.slack.channel_operations.channel_membership_ops - INFO - ChannelMembershipOps initialized.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - ChannelMembershipOps instance created successfully.
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: membership_ops
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: channel_name_resolver (Singleton: True)
2025-08-21 17:02:42,498 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,499 - packages.slack.channel_operations.channel_name_resolver - INFO - ChannelNameResolver initialized.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - ChannelNameResolver instance created successfully.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: channel_name_resolver
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: user_ops (Singleton: True)
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,499 - packages.slack.user_operations.user_ops - INFO - SlackUserOps initialized with injected UserStore.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - SlackUserOps instance created successfully.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: user_ops
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: msg_ops (Singleton: True)
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,499 - packages.slack.channel_operations.slack_message_formatter - INFO - SlackMessageFormatter initialized.
2025-08-21 17:02:42,499 - packages.slack.channel_operations.channel_msg_ops - INFO - SlackChannelMessageOps initialized with injected dependencies.
2025-08-21 17:02:42,499 - packages.secrets.manager - INFO - Starting get_bot_slack_user_id_async function.
2025-08-21 17:02:42,499 - packages.secrets.manager - INFO - Returning cached secrets (age: 0.3 seconds)
2025-08-21 17:02:42,499 - packages.slack.channel_operations.channel_msg_ops - INFO - Bot user ID set to U084HFUQMFE for message filtering
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Set bot_user_id U084HFUQMFE for message filtering
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - SlackChannelMessageOps instance created successfully.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: msg_ops
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: bot_membership_ops (Singleton: True)
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,499 - packages.slack.channel_operations.channel_bot_membership_ops - INFO - SlackChannelBotMembershipOps initialized.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - SlackChannelBotMembershipOps instance created successfully.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: bot_membership_ops
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: restore_ops (Singleton: True)
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,499 - packages.slack.channel_operations.channel_restore_ops - INFO - SlackChannelRestoreOps initialized with injected dependencies (including BotMembershipOps).
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - SlackChannelRestoreOps instance created successfully.
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: restore_ops
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: feedback_reactions_handler (Singleton: True)
2025-08-21 17:02:42,499 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,500 - packages.slack.interactive_elements.feedback_reactions - INFO - FeedbackReactionsHandler initialized.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - FeedbackReactionsHandler instance created successfully.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: feedback_reactions_handler
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: feedback_report_handler (Singleton: True)
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,500 - packages.slack.interactive_elements.feedback_report - INFO - FeedbackReportHandler initialized.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - FeedbackReportHandler instance created successfully.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: feedback_report_handler
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: channel_metadata_edit_handler (Singleton: True)
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,500 - packages.slack.interactive_elements.channel_metadata_edit - INFO - ChannelMetadataEditHandler initialized.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - ChannelMetadataEditHandler instance created successfully.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: channel_metadata_edit_handler
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: trust_endorsement_handler (Singleton: True)
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - TrustEndorsementHandler instance created successfully.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: trust_endorsement_handler
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: access_request_handler (Singleton: True)
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - AccessRequestHandler instance created successfully.
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: access_request_handler
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: flag_review_handler (Singleton: True)
2025-08-21 17:02:42,500 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,507 - packages.core.client_factory.slack_factory - INFO - FlagReviewHandler instance created successfully.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: flag_review_handler
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: shortcut_handler (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,508 - packages.slack.interactive_elements.shortcuts - INFO - ShortcutHandler initialized.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - ShortcutHandler instance created successfully.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: shortcut_handler
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: user_verifier (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,508 - packages.slack.authorisation.user_verification - INFO - UserVerifier initialized with secrets manager
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - UserVerifier instance created successfully.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: user_verifier
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: block_kit_builder (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - BlockKitBuilder instance created and configured successfully.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: block_kit_builder
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: archive_command (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating SlackArchiveCommand instance
2025-08-21 17:02:42,508 - packages.slack.command_processing.base_command_handler - INFO - BaseCommandHandler initialized with dependencies: []
2025-08-21 17:02:42,508 - packages.slack.command_processing.archive_command - INFO - SlackArchiveCommand initialized.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - SlackArchiveCommand instance created successfully.
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: archive_command
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: csv_generator (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating CommandUsageCSVGenerator instance
2025-08-21 17:02:42,508 - packages.core.exports.csv_generator - INFO - CommandUsageCSVGenerator initialized
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: csv_generator
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: usage_export_handler (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating UsageExportHandler instance
2025-08-21 17:02:42,508 - packages.slack.interactive_elements.usage_export_handler - INFO - UsageExportHandler initialized
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: usage_export_handler
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: home_tab_handler (Singleton: True)
2025-08-21 17:02:42,508 - packages.core.client_factory.slack_factory - INFO - Creating HomeTabHandler instance
2025-08-21 17:02:42,508 - packages.secrets.manager - INFO - Starting get_secret_async function.
INFO:aiobotocore.credentials:Found credentials in shared credentials file: ~/.aws/credentials
2025-08-21 17:02:42,823 - packages.slack.home.home - INFO - HomeTabHandler initialized with dependencies
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: home_tab_handler
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: feature_service (Singleton: True)
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Creating FeatureService instance via async factory function
2025-08-21 17:02:42,823 - packages.slack.command_processing.feature_service - INFO - FeatureService initialized
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - FeatureService instance created successfully
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: feature_service
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Initializing Slack client: feature_command (Singleton: True)
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Creating FeatureCommand instance
2025-08-21 17:02:42,823 - packages.slack.command_processing.base_command_handler - INFO - BaseCommandHandler initialized with dependencies: []
2025-08-21 17:02:42,823 - packages.slack.command_processing.feature_command - INFO - FeatureCommand initialized
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - Successfully initialized client: feature_command
2025-08-21 17:02:42,823 - packages.core.client_factory.slack_factory - INFO - All Slack client instances initialized successfully: ['slack_config', 'slack_async_client', 'slack_posting', 'slack_auth', 'restore_state', 'archive_ops', 'info_ops', 'membership_ops', 'channel_name_resolver', 'user_ops', 'msg_ops', 'bot_membership_ops', 'restore_ops', 'feedback_reactions_handler', 'feedback_report_handler', 'channel_metadata_edit_handler', 'trust_endorsement_handler', 'access_request_handler', 'flag_review_handler', 'shortcut_handler', 'user_verifier', 'block_kit_builder', 'archive_command', 'csv_generator', 'usage_export_handler', 'home_tab_handler', 'feature_service', 'feature_command']
2025-08-21 17:02:42,823 - packages.core.client_factory.ai_factory - INFO - Initializing all AI-related client instances using AI_CLIENT_MAP
2025-08-21 17:02:42,823 - packages.core.client_factory.ai_factory - INFO - Initializing AI client: openai (Singleton: True)
2025-08-21 17:02:42,823 - packages.core.client_factory.ai_factory - INFO - Creating instance via factory function.
2025-08-21 17:02:42,823 - packages.core.client_factory.ai_factory - INFO - JIRA data extractor found, OpenAI handler will enrich with JIRA context
2025-08-21 17:02:42,823 - packages.ai.core.openai_factory - INFO - Creating OpenAIHandler with dependencies
2025-08-21 17:02:42,823 - packages.ai.core.openai_handler - INFO - OpenAIHandler: Initializing with AZURE_OPENAI_ENDPOINT: https://ketchup-prod1.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview
2025-08-21 17:02:42,823 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient initialized with endpoint: https://ketchup-prod1.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview
2025-08-21 17:02:42,823 - packages.ai.core.openai_handler - INFO - Initializing OpenAIHandler and submodules...
2025-08-21 17:02:42,823 - packages.secrets.manager - INFO - Starting get_azure_openai_lb_api_key function.
2025-08-21 17:02:42,823 - packages.secrets.manager - INFO - Starting get_app_secrets function.
2025-08-21 17:02:42,823 - packages.secrets.manager - INFO - Starting get_secret_async function.
INFO:aiobotocore.credentials:Found credentials in shared credentials file: ~/.aws/credentials
2025-08-21 17:02:43,146 - packages.secrets.manager - INFO - Application secrets retrieved successfully from AWS Secrets Manager.
2025-08-21 17:02:43,146 - packages.secrets.manager - INFO - Secrets cache updated
2025-08-21 17:02:43,146 - packages.core.async_client - INFO - Entering setup() for OpenAIHandler. Current session: None, Closed: N/A
INFO:OpenAIHandler:Session creation attempt 1/5
INFO:OpenAIHandler:Session created attempt 1/5. State - Closed: False
2025-08-21 17:02:43,147 - packages.core.async_client - INFO - Successfully established session in setup() for OpenAIHandler.
2025-08-21 17:02:43,147 - packages.ai.core.openai_handler - INFO - OpenAIHandler initialized successfully.
2025-08-21 17:02:43,147 - packages.ai.core.openai_factory - INFO - OpenAIHandler initialized successfully
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - OpenAIHandler instance created and initialized successfully.
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Successfully initialized client: openai
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Initializing AI client: token_tracker (Singleton: True)
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Successfully initialized client: token_tracker
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Initializing AI client: embedding_client (Singleton: True)
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Creating embedding client via factory function.
2025-08-21 17:02:43,147 - packages.secrets.manager - INFO - Starting get_azure_openai_lb_api_key function.
2025-08-21 17:02:43,147 - packages.secrets.manager - INFO - Returning cached secrets (age: 1.0 seconds)
2025-08-21 17:02:43,147 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient initialized with endpoint: https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15
2025-08-21 17:02:43,147 - packages.core.async_client - INFO - Entering setup() for AzureAsyncClient. Current session: None, Closed: N/A
INFO:AzureAsyncClient:Session creation attempt 1/5
INFO:AzureAsyncClient:Session created attempt 1/5. State - Closed: False
2025-08-21 17:02:43,147 - packages.core.async_client - INFO - Successfully established session in setup() for AzureAsyncClient.
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Embedding client initialized with Azure OpenAI LB API key
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - Successfully initialized client: embedding_client
2025-08-21 17:02:43,147 - packages.core.client_factory.ai_factory - INFO - All AI client instances initialized successfully: ['openai', 'token_tracker', 'embedding_client']
2025-08-21 17:02:43,147 - packages.core.di_container - INFO - Resolving circular dependencies
2025-08-21 17:02:43,147 - packages.core.di_container - INFO - DIContainer initialized successfully
✓ Services initialized

=== DI Container Azure Client Test ===
INFO:__main__:Testing Azure OpenAI client from DI container...
INFO:__main__:Testing Azure OpenAI embeddings...
2025-08-21 17:02:43,148 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient._make_azure_api_request: Received URL: 'https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15'
2025-08-21 17:02:43,148 - packages.ai.core.azure_async_client - INFO - AzureAsyncClient._make_azure_api_request: URL contains '?': True
2025-08-21 17:02:43,148 - packages.core.async_client - INFO - Entering setup() for AzureAsyncClient. Current session: <aiohttp.client.ClientSession object at 0x1048ba710>, Closed: False
2025-08-21 17:02:43,148 - packages.core.async_client - INFO - Session already exists and is open for AzureAsyncClient.
2025-08-21 17:02:43,148 - packages.core.async_client - INFO - Making POST request to https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15 for AzureAsyncClient (params=None)
2025-08-21 17:02:43,580 - packages.core.async_client - INFO - Request for AzureAsyncClient to https://ketchup-prod1.openai.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15 completed with status 200
INFO:__main__:✓ Embeddings test successful: 1536 dimensions
INFO:__main__:✓ Embedding sample: [-0.018798266, -0.012451324, -0.009284591, -0.015213793, 0.009574314]...
INFO:__main__:✓ DI container Azure client test successful
✓ DI container Azure client test passed

=== Service Health Checks ===
ERROR:__main__:Fatal error during production test initialization: Service health check failed: Dependency 'jira_search' not found
Traceback (most recent call last):
  File "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/tests/setup/production_analyze_test.py", line 259, in check_service_health
    service = container.get_by_name(service_name)
  File "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/packages/core/di_container.py", line 176, in get_by_name
    raise RuntimeError(f"Dependency '{name}' not found")
RuntimeError: Dependency 'jira_search' not found

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/tests/setup/production_analyze_test.py", line 521, in run_full_production_test
    await check_service_health(container)
  File "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/tests/setup/production_analyze_test.py", line 266, in check_service_health
    raise RuntimeError(f"Service health check failed: {e}")
RuntimeError: Service health check failed: Dependency 'jira_search' not found

Fatal error: Service health check failed: Dependency 'jira_search' not found

=== Cleanup ===
2025-08-21 17:02:43,683 - packages.core.async_client - INFO - Closing session in AzureAsyncClient.cleanup()
2025-08-21 17:02:43,786 - packages.core.async_client - INFO - Successfully closed session in AzureAsyncClient
✓ Azure OpenAI client cleanup complete
2025-08-21 17:02:43,786 - packages.core.di_container - INFO - Cleaning up DIContainer
2025-08-21 17:02:43,786 - packages.core.di_container - INFO - Cleaning up Slack clients
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: slack_posting
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: archive_ops
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: info_ops
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: membership_ops
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: user_ops
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: msg_ops
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: bot_membership_ops
2025-08-21 17:02:43,787 - packages.core.client_factory.slack_factory - INFO - Cleaning up Slack client: restore_ops
2025-08-21 17:02:43,787 - packages.slack.channel_operations.channel_restore_ops - INFO - Cleaning up SlackChannelRestoreOps (calling parent SlackAsyncClient cleanup)
2025-08-21 17:02:43,787 - packages.slack.core.slack_async_client - INFO - Cleaning up SlackAsyncClient resources
2025-08-21 17:02:43,787 - packages.slack.channel_operations.channel_restore_ops - INFO - SlackChannelRestoreOps cleanup completed.
2025-08-21 17:02:43,788 - packages.core.di_container - INFO - Cleaning up Integration clients
2025-08-21 17:02:43,788 - packages.core.client_factory.integration_factory - INFO - Cleaning up integration client: mcp_client
2025-08-21 17:02:43,788 - packages.core.client_factory.integration_factory - INFO - Cleaning up integration client: local_metrics_collector
2025-08-21 17:02:43,788 - packages.integrations.local_metrics - INFO - Metrics collector cleaned up
2025-08-21 17:02:43,788 - packages.core.client_factory.integration_factory - INFO - Cleaning up integration client: local_metrics_service
2025-08-21 17:02:43,788 - packages.core.client_factory.integration_factory - INFO - Cleaning up integration client: access_request_operations
2025-08-21 17:02:43,788 - packages.db.operations.base_operations - INFO - Cleaning up AccessRequestOperations instance
2025-08-21 17:02:43,788 - packages.core.di_container - INFO - Cleaning up DB clients
2025-08-21 17:02:43,788 - packages.core.client_factory.db_factory - INFO - Cleaning up DB client: dynamodb_async_client 
2025-08-21 17:02:43,788 - packages.db.core.dynamodb_async_client - INFO - Cleaning up DynamoDB async client resources
2025-08-21 17:02:43,788 - packages.core.client_factory.db_factory - INFO - Cleaning up DB client: dynamodb_store 
2025-08-21 17:02:43,788 - packages.db.dynamodb_store - INFO - Cleaning up DynamoDB Store
2025-08-21 17:02:43,788 - packages.db.operations.channel_operations - INFO - Cleaning up ChannelOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.channel_query_operations - INFO - Cleaning up ChannelQueryOperations resources
2025-08-21 17:02:43,788 - packages.db.operations.base_operations - INFO - Cleaning up ChannelQueryOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.channel_filter_operations - INFO - Cleaning up ChannelFilterOperations resources
2025-08-21 17:02:43,788 - packages.db.operations.base_operations - INFO - Cleaning up ChannelFilterOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.base_operations - INFO - Cleaning up ChannelOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.archive_operations - INFO - Cleaning up ArchiveOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.base_operations - INFO - Cleaning up ArchiveOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.feedback_operations - INFO - Cleaning up FeedbackOperations instance
2025-08-21 17:02:43,788 - packages.db.operations.base_operations - INFO - Cleaning up FeedbackOperations instance
2025-08-21 17:02:43,789 - packages.db.operations.trust_operations - INFO - TrustOperations cleanup completed
2025-08-21 17:02:43,789 - packages.db.dynamodb_store - INFO - DynamoDB Store internal cleanup finished.
2025-08-21 17:02:43,789 - packages.core.client_factory.db_factory - INFO - Cleaning up DB client: command_tracking_ops 
2025-08-21 17:02:43,789 - packages.db.operations.base_operations - INFO - Cleaning up CommandTrackingOperations instance
2025-08-21 17:02:43,789 - packages.core.client_factory.db_factory - INFO - Cleaning up DB client: channel_operations 
2025-08-21 17:02:43,789 - packages.db.operations.channel_operations - INFO - Cleaning up ChannelOperations instance
2025-08-21 17:02:43,789 - packages.db.operations.channel_query_operations - INFO - Cleaning up ChannelQueryOperations resources
2025-08-21 17:02:43,789 - packages.db.operations.base_operations - INFO - Cleaning up ChannelQueryOperations instance
2025-08-21 17:02:43,789 - packages.db.operations.channel_filter_operations - INFO - Cleaning up ChannelFilterOperations resources
2025-08-21 17:02:43,789 - packages.db.operations.base_operations - INFO - Cleaning up ChannelFilterOperations instance
2025-08-21 17:02:43,789 - packages.db.operations.base_operations - INFO - Cleaning up ChannelOperations instance
2025-08-21 17:02:43,789 - packages.core.di_container - INFO - Cleaning up AI clients
2025-08-21 17:02:43,789 - packages.core.client_factory.ai_factory - INFO - Cleaning up AI client: openai
2025-08-21 17:02:43,789 - packages.ai.core.openai_handler - INFO - Cleaning up OpenAIHandler resources (closing session)
2025-08-21 17:02:43,789 - packages.core.async_client - INFO - Closing session in OpenAIHandler.cleanup()
2025-08-21 17:02:43,789 - packages.core.async_client - INFO - Successfully closed session in OpenAIHandler
2025-08-21 17:02:43,789 - packages.ai.core.openai_handler - INFO - OpenAIHandler cleanup completed.
2025-08-21 17:02:43,789 - packages.core.client_factory.ai_factory - INFO - Cleaning up AI client: embedding_client
2025-08-21 17:02:43,789 - packages.core.async_client - INFO - Closing session in AzureAsyncClient.cleanup()
2025-08-21 17:02:43,894 - packages.core.async_client - INFO - Successfully closed session in AzureAsyncClient
2025-08-21 17:02:43,895 - packages.core.di_container - INFO - Cleaning up Cloud clients
2025-08-21 17:02:43,895 - packages.core.di_container - INFO - DIContainer cleaned up successfully
✓ DI container cleanup complete
✓ All cleanup completed successfully
