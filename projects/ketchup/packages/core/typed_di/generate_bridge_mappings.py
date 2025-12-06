#!/usr/bin/env python3
"""
Generate CompatibilityBridge Mappings

Parses client_map_to_protocol_mapping.json and generates Python dictionary
mappings for the CompatibilityBridge class in the format:
    service_name -> (ProtocolType, qualifier)

This script automates the generation of service mappings needed for
backward compatibility during migration to TypedDI system.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BridgeMappingGenerator:
    """Generator for CompatibilityBridge service mappings."""

    def __init__(self, json_file_path: str):
        """
        Initialize the generator.

        Args:
            json_file_path: Path to client_map_to_protocol_mapping.json
        """
        self.json_file_path = Path(json_file_path)
        self.mappings: Dict[str, Dict[str, any]] = {}

    def load_json_data(self) -> bool:
        """
        Load and parse the JSON mapping file.

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.json_file_path.exists():
                logger.error(f"JSON file not found: {self.json_file_path}")
                return False

            with open(self.json_file_path, "r", encoding="utf-8") as file:
                self.mappings = json.load(file)

            logger.info(f"Successfully loaded {len(self.mappings)} service mappings")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load JSON file: {e}")
            return False

    def validate_mapping_structure(self) -> bool:
        """
        Validate the structure of loaded mappings.

        Returns:
            True if structure is valid, False otherwise
        """
        required_fields = {"type", "protocol", "qualifier", "factory"}
        invalid_services = []

        for service_name, service_data in self.mappings.items():
            if not isinstance(service_data, dict):
                invalid_services.append(f"{service_name}: not a dictionary")
                continue

            missing_fields = required_fields - set(service_data.keys())
            if missing_fields:
                invalid_services.append(f"{service_name}: missing fields {missing_fields}")

        if invalid_services:
            logger.error("Invalid service structures found:")
            for error in invalid_services:
                logger.error(f"  - {error}")
            return False

        logger.info("All service mappings have valid structure")
        return True

    def generate_python_mappings(self) -> Dict[str, Tuple[str, Optional[str]]]:
        """
        Generate Python dictionary mappings in CompatibilityBridge format.

        Returns:
            Dictionary mapping service names to (protocol, qualifier) tuples
        """
        python_mappings = {}
        unknown_protocol_count = 0

        for service_name, service_data in self.mappings.items():
            protocol = service_data["protocol"]
            qualifier = service_data["qualifier"]

            # Track services with unknown protocols for statistics
            if protocol == "UnknownProtocol":
                unknown_protocol_count += 1
                logger.warning(f"Service '{service_name}' has UnknownProtocol")

            # Convert null to None for Python
            if qualifier == "null":
                qualifier = None

            python_mappings[service_name] = (protocol, qualifier)

        logger.info(f"Generated mappings for {len(python_mappings)} services")
        logger.info(f"Services with unknown protocols: {unknown_protocol_count}")

        return python_mappings

    def format_as_python_dict(self, mappings: Dict[str, Tuple[str, Optional[str]]]) -> str:
        """
        Format mappings as a Python dictionary string.

        Args:
            mappings: Dictionary of service mappings

        Returns:
            Formatted Python dictionary string
        """
        lines = ["GENERATED_MAPPINGS = {"]

        # Sort services alphabetically for consistent output
        sorted_services = sorted(mappings.items())

        for service_name, (protocol, qualifier) in sorted_services:
            # Format qualifier value
            qualifier_str = "None" if qualifier is None else f'"{qualifier}"'

            # Create the mapping line with proper indentation
            line = f'    "{service_name}": ("{protocol}", {qualifier_str}),'
            lines.append(line)

        lines.append("}")

        return "\n".join(lines)

    def generate_statistics(self, mappings: Dict[str, Tuple[str, Optional[str]]]) -> str:
        """
        Generate statistics about the mappings.

        Args:
            mappings: Dictionary of service mappings

        Returns:
            Statistics as a formatted string
        """
        stats = []
        stats.append(f"Total services: {len(mappings)}")

        # Count services by protocol type
        protocol_counts = {}
        qualifier_counts = {"with_qualifier": 0, "without_qualifier": 0}
        unknown_services = []

        for service_name, (protocol, qualifier) in mappings.items():
            # Count protocols
            protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1

            # Count qualifiers
            if qualifier is None:
                qualifier_counts["without_qualifier"] += 1
            else:
                qualifier_counts["with_qualifier"] += 1

            # Track unknown protocols
            if protocol == "UnknownProtocol":
                unknown_services.append(service_name)

        stats.append(f"Services with qualifiers: {qualifier_counts['with_qualifier']}")
        stats.append(f"Services without qualifiers: {qualifier_counts['without_qualifier']}")
        stats.append(f"Unknown protocol services: {len(unknown_services)}")

        if unknown_services:
            stats.append("Services with UnknownProtocol:")
            for service in unknown_services:
                stats.append(f"  - {service}")

        stats.append("\nProtocol distribution:")
        for protocol, count in sorted(protocol_counts.items()):
            stats.append(f"  - {protocol}: {count}")

        return "\n".join(stats)

    def save_mappings_to_file(self, mappings_str: str, output_file: str) -> bool:
        """
        Save generated mappings to a Python file.

        Args:
            mappings_str: Formatted Python dictionary string
            output_file: Output file path

        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = Path(output_file)

            # Create header comment
            header = [
                '"""',
                "Generated Service Mappings for CompatibilityBridge",
                "",
                "This file is automatically generated from client_map_to_protocol_mapping.json",
                "DO NOT EDIT MANUALLY - regenerate using generate_bridge_mappings.py",
                "",
                f"Source: {self.json_file_path}",
                f'Generated: {__import__("datetime").datetime.now().isoformat()}',
                '"""',
                "",
                "from typing import Dict, Optional, Tuple",
                "",
            ]

            # Write the file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(header))
                f.write(mappings_str)
                f.write("\n")

            logger.info(f"Saved mappings to: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save mappings to file: {e}")
            return False

    def run(self, output_file: Optional[str] = None, print_stats: bool = True) -> bool:
        """
        Run the complete mapping generation process.

        Args:
            output_file: Optional output file path
            print_stats: Whether to print statistics

        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting bridge mapping generation")

        # Load and validate JSON data
        if not self.load_json_data():
            return False

        if not self.validate_mapping_structure():
            return False

        # Generate mappings
        mappings = self.generate_python_mappings()
        if not mappings:
            logger.error("No mappings generated")
            return False

        # Format as Python dictionary
        mappings_str = self.format_as_python_dict(mappings)

        # Print to console
        print("\n" + "=" * 80)
        print("GENERATED COMPATIBILITY BRIDGE MAPPINGS")
        print("=" * 80)
        print(mappings_str)
        print("=" * 80)

        # Print statistics if requested
        if print_stats:
            stats = self.generate_statistics(mappings)
            print("\nSTATISTICS:")
            print("-" * 40)
            print(stats)
            print("-" * 40)

        # Save to file if requested
        if output_file:
            if not self.save_mappings_to_file(mappings_str, output_file):
                return False

        logger.info("Bridge mapping generation completed successfully")
        return True


def main():
    """Main entry point for the script."""
    # Default paths
    default_json_file = "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/analysis/client_map_to_protocol_mapping.json"

    # Handle command line arguments
    json_file = sys.argv[1] if len(sys.argv) > 1 else default_json_file
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Create and run generator
    generator = BridgeMappingGenerator(json_file)

    try:
        success = generator.run(output_file=output_file, print_stats=True)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
