#!/usr/bin/env python3
"""
Constructor Signature Validation Tests for TypedDI Factories

CRITICAL REGRESSION TEST: Prevents constructor signature mismatches that cause
dependency injection failures at runtime.

Tests specifically focus on the SlackChannelArchiveOps constructor signature bug
that was fixed where factory parameters didn't match constructor parameters.
"""

import inspect
import unittest

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class TestConstructorSignatureValidation(unittest.TestCase):
    """Test factory function signatures match their corresponding class constructors."""

    def test_slack_channel_archive_ops_constructor_signature(self):
        """CRITICAL: Test SlackChannelArchiveOps constructor signature matches expectations."""
        from packages.slack.channel_operations.channel_archive_ops import (
            SlackChannelArchiveOps,
        )

        # Get constructor signature
        constructor_sig = inspect.signature(SlackChannelArchiveOps.__init__)
        constructor_params = list(constructor_sig.parameters.keys())[1:]  # Skip 'self'

        # These are the REQUIRED parameters that caused the original bug
        expected_params = [
            "posting_handler",  # NOT 'slack_posting'
            "secrets_manager",
            "dynamodb_store",
            "state_manager",  # This was MISSING
            "slack_config",
        ]

        # Validate constructor has expected parameters
        self.assertEqual(
            constructor_params[: len(expected_params)],
            expected_params,
            f"SlackChannelArchiveOps constructor parameters changed: {constructor_params}",
        )

    def test_slack_channel_archive_ops_factory_regression(self):
        """CRITICAL: Test factory source contains correct parameter names and dependencies."""
        import packages.core.typed_di.service_registrations as svc_reg

        # Get the complete source of the service_registrations module
        factory_source = inspect.getsource(svc_reg)

        # Check that SlackChannelArchiveOps factory exists
        self.assertIn(
            "create_slack_channel_archive_ops",
            factory_source,
            "SlackChannelArchiveOps factory function not found",
        )

        # REGRESSION TEST: Ensure factory uses CORRECT parameter names
        # These were the parameter names that caused the original bug:
        wrong_params = [
            "slack_posting=",  # Should be posting_handler=
            "return SlackChannelArchiveOps(\n            slack_config=",  # Wrong parameter order for this specific constructor
        ]

        for wrong_param in wrong_params:
            self.assertNotIn(
                wrong_param,
                factory_source,
                f"Factory contains WRONG parameter: {wrong_param}",
            )

        # REGRESSION TEST: Ensure factory uses CORRECT parameter names
        correct_params = [
            "posting_handler=posting_handler",
            "state_manager=state_manager",  # This dependency was MISSING
            "RestoreStateManager",  # This import was MISSING
        ]

        for correct_param in correct_params:
            self.assertIn(
                correct_param,
                factory_source,
                f"Factory missing CORRECT parameter/import: {correct_param}",
            )

    def test_restore_state_manager_dependency_included(self):
        """CRITICAL: Test RestoreStateManager is properly included in factory."""
        import packages.core.typed_di.service_registrations as svc_reg

        factory_source = inspect.getsource(svc_reg)

        # RestoreStateManager was completely missing from original factory
        required_restore_state_elements = [
            "from packages.slack.channel_operations.restore_state_manager import RestoreStateManager",
            "await resolver.aget(RestoreStateManager)",
            "state_manager=state_manager",
            "DependencySpec(RestoreStateManager)",
        ]

        for element in required_restore_state_elements:
            self.assertIn(
                element,
                factory_source,
                f"Factory missing RestoreStateManager element: {element}",
            )

    def test_slack_channel_archive_ops_factory_parameter_order(self):
        """CRITICAL: Test factory parameters are passed in correct order to constructor."""
        import packages.core.typed_di.service_registrations as svc_reg

        # Validation done via factory source inspection
        factory_source = inspect.getsource(svc_reg)

        # Find the SlackChannelArchiveOps constructor call in factory
        # Look for the return statement
        lines = factory_source.split("\n")
        constructor_call_lines = []
        in_constructor_call = False

        for line in lines:
            if "return SlackChannelArchiveOps(" in line:
                in_constructor_call = True

            if in_constructor_call:
                constructor_call_lines.append(line)
                if ")" in line and "return" not in line:
                    break

        constructor_call = "\n".join(constructor_call_lines)

        # Verify parameter order matches constructor
        expected_order = [
            "posting_handler=",
            "secrets_manager=",
            "dynamodb_store=",
            "state_manager=",
            "slack_config=",
        ]

        last_pos = -1
        for param in expected_order:
            pos = constructor_call.find(param)
            self.assertGreater(pos, -1, f"Parameter {param} not found in factory call")
            self.assertGreater(pos, last_pos, f"Parameter {param} in wrong order")
            last_pos = pos


if __name__ == "__main__":
    unittest.main()
