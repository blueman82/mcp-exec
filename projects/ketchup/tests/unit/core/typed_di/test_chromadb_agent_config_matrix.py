"""
Config matrix tests for ChromaDB/Agent two-tier service registration.

Validates all 4 flag combinations produce the expected number of services
and that register_chromadb_services and register_agent_services behave
correctly as independent functions.
"""

import os
import unittest
from unittest.mock import patch

from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations.manager import (
    ServiceRegistrationManager,
)
from packages.core.typed_di.service_registrations.registrations.agent_services import (
    register_agent_services,
    register_chromadb_services,
)


def _fresh_manager() -> ServiceRegistrationManager:
    """Create a fresh registry + manager for each test."""
    registry = TypedServiceRegistry()
    return ServiceRegistrationManager(registry)


class TestChromadbAgentConfigMatrix(unittest.TestCase):
    """Validate all 4 flag combinations for the two-tier registration."""

    @patch.dict(
        os.environ,
        {"KETCHUP_CHROMADB_ENABLED": "false", "KETCHUP_AGENT_ENABLED": "false"},
    )
    def test_both_disabled_registers_zero(self):
        """Both flags off: no chromadb or agent services registered."""
        manager = _fresh_manager()
        chromadb_count = register_chromadb_services(manager)
        agent_count = register_agent_services(manager)
        assert chromadb_count == 0
        assert agent_count == 0
        assert len(manager.registered_services) == 0

    @patch.dict(
        os.environ,
        {"KETCHUP_CHROMADB_ENABLED": "true", "KETCHUP_AGENT_ENABLED": "false"},
    )
    def test_chromadb_only_registers_four(self):
        """ChromaDB enabled, agent off: 4 foundation services only."""
        manager = _fresh_manager()
        chromadb_count = register_chromadb_services(manager)
        agent_count = register_agent_services(manager)
        assert chromadb_count == 4
        assert agent_count == 0
        assert len(manager.registered_services) == 4

    @patch.dict(
        os.environ,
        {"KETCHUP_CHROMADB_ENABLED": "true", "KETCHUP_AGENT_ENABLED": "true"},
    )
    def test_both_enabled_registers_twelve(self):
        """Both flags on: 4 chromadb + 8 agent = 12 services."""
        manager = _fresh_manager()
        chromadb_count = register_chromadb_services(manager)
        agent_count = register_agent_services(manager)
        assert chromadb_count == 4
        assert agent_count == 8
        assert len(manager.registered_services) == 12

    @patch.dict(
        os.environ,
        {"KETCHUP_CHROMADB_ENABLED": "false", "KETCHUP_AGENT_ENABLED": "true"},
    )
    def test_agent_only_registers_twelve(self):
        """Agent enabled, chromadb flag off: chromadb still registers
        because agent implies chromadb. Total = 4 + 8 = 12."""
        manager = _fresh_manager()
        chromadb_count = register_chromadb_services(manager)
        agent_count = register_agent_services(manager)
        # chromadb registers because agent_enabled is true
        assert chromadb_count == 4
        assert agent_count == 8
        assert len(manager.registered_services) == 12


class TestRegistrationIndependence(unittest.TestCase):
    """Verify register_chromadb_services and register_agent_services
    are truly independent — no hidden internal calls."""

    @patch.dict(
        os.environ,
        {"KETCHUP_CHROMADB_ENABLED": "true", "KETCHUP_AGENT_ENABLED": "true"},
    )
    def test_agent_does_not_call_chromadb_internally(self):
        """Calling only register_agent_services should NOT register chromadb services.
        This verifies the P2 fix — no hidden internal call."""
        manager = _fresh_manager()
        agent_count = register_agent_services(manager)
        assert agent_count == 8
        # Should only have agent services, not chromadb
        assert len(manager.registered_services) == 8
        # Verify no chromadb protocols in registered services
        service_names = [v["protocol_type"] for v in manager.registered_services.values()]
        assert "AgentEmbeddingsClientProtocol" not in service_names
        assert "AgentVectorStoreProtocol" not in service_names
        assert "AgentRealtimeIngestorProtocol" not in service_names

    @patch.dict(
        os.environ,
        {"KETCHUP_CHROMADB_ENABLED": "true", "KETCHUP_AGENT_ENABLED": "false"},
    )
    def test_chromadb_alone_has_correct_protocols(self):
        """Chromadb-only mode registers exactly the 4 expected protocols."""
        manager = _fresh_manager()
        register_chromadb_services(manager)
        service_names = {v["protocol_type"] for v in manager.registered_services.values()}
        expected = {
            "AgentEmbeddingsClientProtocol",
            "AgentVectorStoreProtocol",
            "AgentConversationStoreProtocol",
            "AgentRealtimeIngestorProtocol",
        }
        assert service_names == expected


if __name__ == "__main__":
    unittest.main()
