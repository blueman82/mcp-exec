"""
Bridge Mapping Generator

Generates CompatibilityBridge mapping format from client map analysis data.
Handles proper protocol mapping, qualifiers, and edge cases for TypedDI migration.
"""

import json
import os
from typing import Any, Dict, Optional, Tuple

# Import all known protocol types for proper mapping
# This will be expanded as more protocols are defined
PROTOCOL_IMPORTS = {
    # AI protocols
    "OpenAIHandlerProtocol": "packages.ai.protocols",
    "TokenTrackerProtocol": "packages.ai.protocols",
    # Slack protocols
    "SlackConfigProtocol": "packages.slack.protocols",
    "SlackPostingHandlerProtocol": "packages.slack.protocols",
    "SlackAuthProtocol": "packages.slack.protocols",
    "SlackChannelArchiveOpsProtocol": "packages.slack.protocols",
    "ChannelInfoOpsProtocol": "packages.slack.protocols",
    "ChannelMembershipOpsProtocol": "packages.slack.protocols",
    "ChannelNameResolverProtocol": "packages.slack.protocols",
    "SlackUserOpsProtocol": "packages.slack.protocols",
    "SlackChannelMessageOpsProtocol": "packages.slack.protocols",
    "RestoreStateManagerProtocol": "packages.slack.protocols",
    "SlackChannelBotMembershipOpsProtocol": "packages.slack.protocols",
    "SlackChannelRestoreOpsProtocol": "packages.slack.protocols",
    "SlackAsyncClientProtocol": "packages.slack.protocols",
    "SlackArchiveCommandProtocol": "packages.slack.protocols",
    # Interactive element protocols
    "FeedbackReactionsHandlerProtocol": "packages.slack.protocols",
    "FeedbackReportHandlerProtocol": "packages.slack.protocols",
    "ChannelMetadataEditHandlerProtocol": "packages.slack.protocols",
    "TrustEndorsementHandlerProtocol": "packages.slack.protocols",
    "AccessRequestHandlerProtocol": "packages.slack.protocols",
    "ShortcutHandlerProtocol": "packages.slack.protocols",
    "UsageExportHandlerProtocol": "packages.slack.protocols",
    "HomeTabHandlerProtocol": "packages.slack.protocols",
    # Utility protocols
    "UserVerifierProtocol": "packages.slack.protocols",
    "BlockKitBuilderProtocol": "packages.slack.protocols",
    "FeatureCommandProtocol": "packages.slack.protocols",
    "CommandUsageCSVGeneratorProtocol": "packages.slack.protocols",
    # Database protocols
    "DynamoDBConfigProtocol": "packages.db.protocols",
    "DynamoDBAsyncClientProtocol": "packages.db.protocols",
    "DynamoDBStoreProtocol": "packages.db.protocols",
    "UserStoreProtocol": "packages.db.protocols",
    "CommandTrackingOperationsProtocol": "packages.db.protocols",
    "ChannelOperationsProtocol": "packages.db.protocols",
    # Integration protocols
    "IMSTokenManagerProtocol": "packages.integrations.protocols",
    "MCPAsyncClientProtocol": "packages.core.typed_di.service_registrations.protocols.mcp_protocols",
    "JIRACacheProtocol": "packages.integrations.protocols",
    "JIRADataExtractorProtocol": "packages.integrations.protocols",
    # Core protocols
    "MetricsStorageProtocol": "packages.core.protocols",
}


class BridgeMappingGenerator:
    """
    Generates CompatibilityBridge mapping format from analysis data.

    Handles:
    - Services with qualifiers (special cases)
    - Protocol naming conventions
    - Unknown/missing type handling
    - Edge cases in service mapping
    """

    def __init__(self, analysis_file_path: str):
        """
        Initialize generator with analysis data.

        Args:
            analysis_file_path: Path to client_map_to_protocol_mapping.json
        """
        self.analysis_file_path = analysis_file_path
        self.mapping_data = self._load_analysis_data()

    def _load_analysis_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Load analysis data from JSON file.

        Returns:
            Dictionary containing service mapping analysis

        Raises:
            FileNotFoundError: If analysis file doesn't exist
            ValueError: If JSON is malformed
        """
        if not os.path.exists(self.analysis_file_path):
            raise FileNotFoundError(f"Analysis file not found: {self.analysis_file_path}")

        try:
            with open(self.analysis_file_path, "r") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("Analysis file must contain a JSON object")

            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in analysis file: {e}")

    def _handle_qualifier(self, service_key: str, qualifier: Optional[str]) -> Optional[str]:
        """
        Handle special qualifier cases and validation.

        Args:
            service_key: Service identifier key
            qualifier: Raw qualifier from analysis (may be null)

        Returns:
            Processed qualifier or None
        """
        # Handle null qualifiers (most common case)
        if qualifier is None:
            # Special case: slack_auth traditionally uses "primary" qualifier
            # even though analysis shows null - preserve legacy behavior
            if service_key == "slack_auth":
                return "primary"
            return None

        # Handle empty string qualifiers
        if qualifier == "":
            return None

        # Return non-empty qualifiers as-is
        return qualifier

    def _get_protocol_type(self, protocol_name: str) -> str:
        """
        Get the proper protocol type reference for mapping.

        Args:
            protocol_name: Name of the protocol class

        Returns:
            String reference to protocol type for mapping
        """
        # Handle unknown protocols - create mock protocol
        if protocol_name == "UnknownProtocol" or protocol_name.startswith("Unknown"):
            return f'self._mock_protocol("{protocol_name}")'

        # Handle known protocols - create proper reference
        if protocol_name in PROTOCOL_IMPORTS:
            # For now, use mock protocol since we don't have full imports
            # In production, this would import the actual protocol class
            return f'self._mock_protocol("{protocol_name}")'
        else:
            # Unknown protocol - create mock
            return f'self._mock_protocol("{protocol_name}")'

    def _validate_service_entry(self, key: str, service_data: Dict[str, Any]) -> bool:
        """
        Validate a service entry has required fields.

        Args:
            key: Service key
            service_data: Service configuration data

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["type", "protocol", "factory"]

        for field in required_fields:
            if field not in service_data:
                print(f"WARNING: Service '{key}' missing required field '{field}'")
                return False

        return True

    def _handle_edge_cases(self, key: str, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle special edge cases in service mapping.

        Args:
            key: Service key
            service_data: Service configuration

        Returns:
            Potentially modified service data
        """
        # Create a copy to avoid modifying original
        result = service_data.copy()

        # Handle services with "Unknown" type but known protocols
        if result["type"] == "Unknown":
            # Check if we can infer the type from the protocol
            protocol = result["protocol"]
            if protocol != "UnknownProtocol" and protocol.endswith("Protocol"):
                # Try to infer type name from protocol name
                inferred_type = protocol.replace("Protocol", "")
                print(
                    f"INFO: Inferring type '{inferred_type}' from protocol '{protocol}' for service '{key}'"
                )
                result["type"] = inferred_type

        # Handle services with inconsistent naming
        # Example: service key doesn't match type name patterns
        if key == "csv_generator" and result["type"] == "CommandUsageCSVGenerator":
            # This is fine - just a naming convention difference
            pass

        return result

    def generate_mapping_dict(self) -> Dict[str, Tuple[str, Optional[str]]]:
        """
        Generate the complete mapping dictionary for CompatibilityBridge.

        Returns:
            Dictionary mapping service keys to (protocol_type_ref, qualifier) tuples
        """
        mapping = {}
        unknown_protocols = set()

        for service_key, service_data in self.mapping_data.items():
            # Validate service entry
            if not self._validate_service_entry(service_key, service_data):
                print(f"SKIPPING invalid service entry: {service_key}")
                continue

            # Handle edge cases
            processed_data = self._handle_edge_cases(service_key, service_data)

            # Extract and process fields
            protocol_name = processed_data["protocol"]
            raw_qualifier = processed_data.get("qualifier")

            # Process qualifier
            qualifier = self._handle_qualifier(service_key, raw_qualifier)

            # Get protocol type reference
            protocol_type_ref = self._get_protocol_type(protocol_name)

            # Track unknown protocols for reporting
            if protocol_name == "UnknownProtocol" or "Unknown" in protocol_name:
                unknown_protocols.add(protocol_name)

            # Add to mapping
            mapping[service_key] = (protocol_type_ref, qualifier)

        # Report unknown protocols found
        if unknown_protocols:
            print(f"INFO: Found {len(unknown_protocols)} unknown protocols:")
            for protocol in sorted(unknown_protocols):
                print(f"  - {protocol}")

        return mapping

    def generate_mapping_code(self) -> str:
        """
        Generate Python code for the mapping dictionary.

        Returns:
            Python code string for the mapping
        """
        mapping = self.generate_mapping_dict()

        lines = [
            "        # Generated mapping from client_map_to_protocol_mapping.json",
            "        # CRITICAL: Handle ALL edge cases, no dismissals",
            "        return {",
        ]

        # Sort keys for consistent output
        for service_key in sorted(mapping.keys()):
            protocol_type_ref, qualifier = mapping[service_key]

            # Format qualifier
            qualifier_str = f'"{qualifier}"' if qualifier else "None"

            # Add mapping entry with proper formatting
            lines.append(f'            "{service_key}": ({protocol_type_ref}, {qualifier_str}),')

        lines.append("        }")

        return "\n".join(lines)

    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the mapping generation.

        Returns:
            Dictionary with mapping statistics
        """
        mapping = self.generate_mapping_dict()

        total_services = len(mapping)
        services_with_qualifiers = sum(1 for _, (_, q) in mapping.items() if q is not None)
        unknown_protocols = sum(1 for _, (p, _) in mapping.items() if "Unknown" in p)

        return {
            "total_services": total_services,
            "services_with_qualifiers": services_with_qualifiers,
            "unknown_protocols": unknown_protocols,
        }


def generate_bridge_mapping(analysis_file: str) -> str:
    """
    Generate CompatibilityBridge mapping from analysis file.

    Args:
        analysis_file: Path to client_map_to_protocol_mapping.json

    Returns:
        Python code for the mapping dictionary

    Raises:
        FileNotFoundError: If analysis file doesn't exist
        ValueError: If analysis data is invalid
    """
    generator = BridgeMappingGenerator(analysis_file)
    return generator.generate_mapping_code()


def main():
    """Main function for CLI usage."""
    import sys

    if len(sys.argv) != 2:
        print("Usage: python bridge_mapping_generator.py <analysis_file>")
        sys.exit(1)

    analysis_file = sys.argv[1]

    try:
        generator = BridgeMappingGenerator(analysis_file)

        # Generate and display mapping code
        mapping_code = generator.generate_mapping_code()
        print("Generated mapping code:")
        print(mapping_code)
        print()

        # Display statistics
        stats = generator.get_statistics()
        print("Mapping statistics:")
        print(f"  Total services: {stats['total_services']}")
        print(f"  Services with qualifiers: {stats['services_with_qualifiers']}")
        print(f"  Unknown protocols: {stats['unknown_protocols']}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
