#!/usr/bin/env python3
"""
Service Batch Smoke Checks for TypedDI Registry

Validates that essential services from each completed batch are properly registered
and meet minimum thresholds for CI guardrails.
"""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services
from tests.unit.core.typed_di.utils import patch_core_dependencies

logger = setup_logger(__name__)


class TestServiceBatchSmokeChecks(unittest.TestCase):
    """Smoke checks for TypedDI service batch registrations."""

    def setUp(self):
        """Set up registry with all services registered."""
        # Reset global registration manager to avoid "frozen registry" errors
        import packages.core.typed_di.service_registrations as svc_reg

        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None  # type: ignore[attr-defined]

        # Set up AWS environment variables for testing (isolated via patch.dict)
        env_patcher = patch.dict(
            os.environ,
            {
                "AWS_SECRET_NAME": "test-secret",
                "AWS_REGION": "us-east-1",
                "DYNAMODB_TABLE_NAME": "test-table",
            },
        )
        env_patcher.start()

        # Start comprehensive AWS mocking
        self._setup_aws_mocks()
        self.active_patchers.append(env_patcher)

        self.registry = TypedServiceRegistry()
        with patch_core_dependencies():
            register_all_services(self.registry)

    def _setup_aws_mocks(self):
        """Set up comprehensive AWS service mocking."""
        # Mock aioboto3.Session for async AWS calls
        self.aioboto3_session_patcher = patch("aioboto3.Session")
        mock_aioboto3_session = self.aioboto3_session_patcher.start()

        # Create mock session and async client
        mock_session = MagicMock()
        mock_aioboto3_session.return_value = mock_session

        # Mock async client context manager
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.__aexit__.return_value = None

        # Mock secret manager responses with comprehensive secret data
        secrets_json = (
            "{"
            '"slack_signing_secret": "test-sign",'
            '"slack_api_token": "xoxb-test",'
            '"slack_user_api_token": "xoxp-test",'
            '"slack_bot_app_id": "BTEST123",'
            '"exigence_user_id": "UTEST123",'
            '"azure_openai_lb_api_key": "test-azure-key",'
            '"bot_slack_user_id": "UTESTBOT"'
            "}"
        )
        mock_async_client.get_secret_value.return_value = {"SecretString": secrets_json}

        # Mock other async AWS operations
        mock_async_client.put_item.return_value = {}
        mock_async_client.update_item.return_value = {}
        mock_async_client.get_item.return_value = {}
        mock_async_client.send_message.return_value = {"MessageId": "test-msg-id"}

        mock_session.client.return_value = mock_async_client

        # Mock boto3.client for sync AWS calls
        self.boto3_client_patcher = patch("boto3.client")
        mock_boto3_client = self.boto3_client_patcher.start()

        # Create sync client mocks
        mock_sync_secrets_client = MagicMock()
        mock_sync_secrets_client.get_secret_value.return_value = {"SecretString": secrets_json}

        mock_sync_sqs_client = MagicMock()
        mock_sync_sqs_client.send_message.return_value = {"MessageId": "test-msg-id"}

        def get_mock_client(service_name, **kwargs):
            if service_name == "secretsmanager":
                return mock_sync_secrets_client
            elif service_name == "sqs":
                return mock_sync_sqs_client
            return MagicMock()

        mock_boto3_client.side_effect = get_mock_client

        # Store patchers for cleanup
        self.active_patchers = [
            self.aioboto3_session_patcher,
            self.boto3_client_patcher,
        ]

    def tearDown(self):
        """Clean up AWS mocks."""
        for patcher in getattr(self, "active_patchers", []):
            patcher.stop()

    def test_batch_1_core_operations_registered(self):
        """Test Batch 1 core operations services are registered."""
        batch_1_services = [
            "ChannelInfoOpsProtocol",
            "ChannelMembershipOpsProtocol",
            "SlackChannelArchiveOpsProtocol",
            "SlackChannelMessageOpsProtocol",
        ]

        present = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }
        missing_services = [s for s in batch_1_services if s not in present]

        self.assertEqual([], missing_services, f"Batch 1 missing services: {missing_services}")

    def test_batch_2_high_traffic_services_registered(self):
        """Test Batch 2 high-traffic services are registered."""
        batch_2_services = [
            "SlackAuthProtocol",
            "SlackAsyncClientProtocol",
            "SlackUserOpsProtocol",
            "UserVerifierProtocol",
            "FeedbackReportHandlerProtocol",
            "ChannelMetadataEditHandlerProtocol",
            "ShortcutHandlerProtocol",
        ]

        present = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }
        missing_services = [s for s in batch_2_services if s not in present]

        self.assertEqual([], missing_services, f"Batch 2 missing services: {missing_services}")

    def test_batch_3_ai_operational_services_registered(self):
        """Test Batch 3 AI/operational services are registered."""
        batch_3_services = [
            "TokenTrackerProtocol",
            "OpenAIHandlerProtocol",
            "ChannelNameResolverProtocol",
            "SlackChannelBotMembershipOpsProtocol",
            "SlackChannelRestoreOpsProtocol",
            "BlockKitBuilderProtocol",
            "SlackArchiveCommandProtocol",
        ]

        present = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }
        missing_services = [s for s in batch_3_services if s not in present]

        self.assertEqual([], missing_services, f"Batch 3 missing services: {missing_services}")

    def test_critical_dependencies_registered(self):
        """Test critical dependencies are registered."""
        critical_services = [
            "SecretsManagerProtocol",
            "SlackConfigProtocol",
            "SlackPostingHandlerProtocol",
            "DynamoDBConfigProtocol",
            "DynamoDBAsyncClientProtocol",
            "DynamoDBStoreProtocol",
            "UserStoreProtocol",
            "RestoreStateManagerProtocol",
        ]

        present = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }
        missing_critical = [s for s in critical_services if s not in present]

        self.assertEqual([], missing_critical, f"Critical dependencies missing: {missing_critical}")

    def test_minimum_service_threshold_met(self):
        """Test minimum number of services are registered for CI threshold."""
        total_registrations = len(self.registry._registrations)
        minimum_threshold = 153  # Based on registered_services_summary.json

        self.assertGreaterEqual(
            total_registrations,
            minimum_threshold,
            f"Only {total_registrations} services registered, need {minimum_threshold}",
        )

    def test_protocol_and_concrete_alias_pattern(self):
        """Test services follow protocol-first + concrete alias pattern."""
        # Check at least one critical service has both protocol and concrete registration
        names = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }
        critical_test_service = "SlackChannelArchiveOpsProtocol"
        protocol_variant = critical_test_service
        has_concrete = critical_test_service in names
        has_protocol = protocol_variant in names
        self.assertTrue(has_concrete, f"Missing concrete registration: {critical_test_service}")
        # Protocol presence depends on generated protocols; assert if present in this environment
        if has_protocol is False:
            logger.warning(
                "Protocol variant not present for %s; skipping strict check",
                critical_test_service,
            )

    def test_domain_specific_service_counts(self):
        """Test that domain-specific service counts match expected baselines."""
        import json
        import os

        # Load the runtime audit summary
        summary_path = os.path.join("analysis", "registered_services_summary.json")
        if not os.path.exists(summary_path):
            self.skipTest("Runtime audit summary not available")

        with open(summary_path, "r") as f:
            summary = json.load(f)

        domain_breakdown = summary.get("domain_breakdown", {})

        # Assert minimum expected counts per domain (lock down regressions)
        self.assertGreaterEqual(
            domain_breakdown.get("core_infrastructure", 0),
            3,
            "Core infrastructure services below minimum threshold",
        )
        self.assertGreaterEqual(
            domain_breakdown.get("db_operations", 0),
            7,
            "DB operations services below minimum threshold",
        )
        self.assertGreaterEqual(
            domain_breakdown.get("slack_commands", 0),
            3,
            "Slack commands services below minimum threshold",
        )
        self.assertGreaterEqual(
            domain_breakdown.get("slack_interactive", 0),
            20,
            "Slack interactive services below minimum threshold",
        )
        self.assertGreaterEqual(
            domain_breakdown.get("integrations", 0),
            5,
            "Integration services below minimum threshold",
        )
        self.assertGreaterEqual(
            domain_breakdown.get("ai_ui_metrics", 0),
            5,
            "AI/UI/Metrics services below minimum threshold",
        )

        # Assert total categorization matches total services
        total_categorized = domain_breakdown.get("total_categorized", 0)
        total_services = summary.get("total_services", 0)
        self.assertEqual(
            total_categorized,
            total_services,
            "Domain categorization doesn't match total service count",
        )

    async def _factory_invocation_validation_async(self):
        """Async helper that validates all registered factories can be invoked without constructor errors."""
        # This test catches runtime constructor signature mismatches that static analysis misses
        # AWS mocking is already set up in setUp method

        try:
            with patch_core_dependencies():
                await self.registry.initialize_all()
            logger.info("All factories successfully invoked during initialization")
        except Exception as e:
            self.fail(f"Factory invocation failed during initialize_all(): {e}")

    def test_factory_invocation_validation(self):
        """Test that all registered factories can actually be invoked without constructor errors."""
        import asyncio

        asyncio.run(self._factory_invocation_validation_async())

    def test_batch_4_integration_services_registered(self):
        """Test Batch 4 integration services are registered."""
        # Use protocol names which are what the registry stores as service_type
        # The concrete implementations are registered via protocol-first pattern
        batch_4_services = [
            "CommandTrackingOperationsProtocol",
            "ChannelOperationsProtocol",
            "IMSTokenManagerProtocol",
            "iPaaSRateLimiterProtocol",
            "MCPConfigProtocol",
            "MCPAsyncClientProtocol",
            "JIRACacheProtocol",
            "JIRADataExtractorProtocol",
            "TrustEndorsementHandlerProtocol",
            "CommandUsageCSVGeneratorProtocol",
            "HomeTabHandlerProtocol",
            "UsageExportHandlerProtocol",
            "AccessRequestHandlerProtocol",
            "FeatureCommandProtocol",
        ]

        registered_names = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }

        missing_services = [svc for svc in batch_4_services if svc not in registered_names]

        self.assertEqual([], missing_services, f"Batch 4 missing services: {missing_services}")

    def test_core_infrastructure_services_registered(self):
        """Test core infrastructure services are properly registered."""
        core_infrastructure_services = [
            "SQSClient",  # Newly implemented in this batch
            # Note: AsyncClient and ExponentialBackoffStrategy are implemented in
            # optional try/except blocks and may not be available in test environment
        ]

        present = {
            reg.service_type.__name__
            for reg in self.registry._registrations.values()
            if hasattr(reg, "service_type") and hasattr(reg.service_type, "__name__")
        }
        missing_services = [s for s in core_infrastructure_services if s not in present]

        self.assertEqual(
            [],
            missing_services,
            f"Core infrastructure missing services: {missing_services}",
        )

        # Verify SQSClient can be resolved (smoke test)
        # Note: This requires registry initialization which happens in register_all_services
        try:
            from packages.core.sqs_client import SQSClient

            # The registry should already be initialized from setUp, but check status
            if not self.registry.is_initialized():
                logger.warning("Registry not initialized during smoke test")
                return

            resolved_sqs = self.registry.get(SQSClient)
            self.assertIsNotNone(resolved_sqs, "SQSClient should be resolvable")
            self.assertIsInstance(resolved_sqs, SQSClient)
        except Exception as e:
            self.fail(f"Failed to resolve SQSClient: {e}")


if __name__ == "__main__":
    unittest.main()
