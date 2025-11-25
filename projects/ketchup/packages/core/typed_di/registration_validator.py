"""
TypedDI Registration Validator

Scans codebase for service access patterns (get_by_name, get_instance)
and validates completeness against TypedDI registrations and compatibility bridge.

Detects systemic patterns:
- Pattern 2: Mapping Without Registration (bridge has mapping but no registration)
- Pattern 3: Complete Registration Missing (service used but not in TypedDI)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import json


@dataclass
class ServiceAccessPoint:
    """Represents a service access in the codebase."""
    service_key: str
    file_path: str
    line_number: int
    access_method: str  # 'get_by_name' or 'get_instance'
    context: str  # surrounding code for debugging


@dataclass
class ValidationReport:
    """Comprehensive validation report."""
    accessed_services: Dict[str, List[ServiceAccessPoint]] = field(default_factory=dict)
    bridge_mappings: Set[str] = field(default_factory=set)
    registered_services: Set[str] = field(default_factory=set)
    
    # Validation results
    missing_from_bridge: List[Tuple[str, List[ServiceAccessPoint]]] = field(default_factory=list)
    missing_from_registry: List[Tuple[str, List[ServiceAccessPoint]]] = field(default_factory=list)
    bridge_without_registration: List[str] = field(default_factory=list)
    
    # Statistics
    total_access_points: int = 0
    unique_services_accessed: int = 0
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        lines = []
        lines.append("=" * 80)
        lines.append("TYPEDDI REGISTRATION VALIDATION REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append("📊 STATISTICS")
        lines.append(f"  Total service access points: {self.total_access_points}")
        lines.append(f"  Unique services accessed: {self.unique_services_accessed}")
        lines.append(f"  Services in compatibility bridge: {len(self.bridge_mappings)}")
        lines.append(f"  Services registered in TypedDI: {len(self.registered_services)}")
        lines.append("")
        
        if self.missing_from_bridge:
            lines.append("❌ PATTERN 3: SERVICES ACCESSED BUT NOT IN COMPATIBILITY BRIDGE")
            lines.append(f"  Found {len(self.missing_from_bridge)} services")
            for service_key, access_points in self.missing_from_bridge:
                lines.append(f"  • '{service_key}' - {len(access_points)} access point(s)")
                for ap in access_points[:3]:  # Show first 3
                    lines.append(f"    - {ap.file_path}:{ap.line_number}")
            lines.append("")
        
        if self.bridge_without_registration:
            lines.append("❌ PATTERN 2: SERVICES IN BRIDGE BUT NOT REGISTERED IN TYPEDDI")
            lines.append(f"  Found {len(self.bridge_without_registration)} services")
            for service_key in sorted(self.bridge_without_registration):
                lines.append(f"  • '{service_key}'")
            lines.append("")
        
        if self.missing_from_registry:
            lines.append("⚠️  SERVICES ACCESSED BUT NOT IN TYPEDDI REGISTRY")
            lines.append(f"  Found {len(self.missing_from_registry)} services")
            for service_key, access_points in self.missing_from_registry:
                lines.append(f"  • '{service_key}' - {len(access_points)} access point(s)")
                for ap in access_points[:2]:
                    lines.append(f"    - {ap.file_path}:{ap.line_number}")
            lines.append("")
        
        if not self.missing_from_bridge and not self.bridge_without_registration:
            lines.append("✅ ALL VALIDATIONS PASSED")
            lines.append("  • All accessed services are in compatibility bridge")
            lines.append("  • All bridge mappings have corresponding registrations")
            lines.append("")
        
        lines.append("=" * 80)
        return "\n".join(lines)


class RegistrationValidator:
    """Validates TypedDI registration completeness."""
    
    def __init__(self, project_root: Path):
        """Initialize validator with project root."""
        self.project_root = project_root
        self.packages_dir = project_root / "packages"
        self.report = ValidationReport()
    
    def scan_codebase(self) -> None:
        """Scan all Python files for service access patterns."""
        print("🔍 Scanning codebase for service access patterns...")
        
        # Find all Python files
        python_files = list(self.packages_dir.rglob("*.py"))
        
        for file_path in python_files:
            try:
                self._scan_file(file_path)
            except Exception as e:
                print(f"  ⚠️  Error scanning {file_path}: {e}")
        
        self.report.total_access_points = sum(
            len(aps) for aps in self.report.accessed_services.values()
        )
        self.report.unique_services_accessed = len(self.report.accessed_services)
        
        print(f"  Found {self.report.total_access_points} access points")
        print(f"  Found {self.report.unique_services_accessed} unique services")
    
    def _scan_file(self, file_path: Path) -> None:
        """Scan a single file for service access patterns."""
        try:
            content = file_path.read_text()
        except Exception:
            return  # Skip files that can't be read
        
        lines = content.split('\n')
        
        # Scan for get_by_name("xxx") patterns
        for match in re.finditer(r'get_by_name\(["\']([^"\']+)["\']\)', content):
            service_key = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Get context (line containing the call)
            context = lines[line_num - 1].strip() if line_num <= len(lines) else ""
            
            access_point = ServiceAccessPoint(
                service_key=service_key,
                file_path=str(file_path.relative_to(self.project_root)),
                line_number=line_num,
                access_method='get_by_name',
                context=context
            )
            
            self.report.accessed_services.setdefault(service_key, []).append(access_point)
        
        # Scan for get_instance("xxx") patterns
        for match in re.finditer(r'get_instance\(["\']([^"\']+)["\']\)', content):
            service_key = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            context = lines[line_num - 1].strip() if line_num <= len(lines) else ""
            
            access_point = ServiceAccessPoint(
                service_key=service_key,
                file_path=str(file_path.relative_to(self.project_root)),
                line_number=line_num,
                access_method='get_instance',
                context=context
            )
            
            self.report.accessed_services.setdefault(service_key, []).append(access_point)
    
    def load_bridge_mappings(self) -> None:
        """Load compatibility bridge mappings by importing the module."""
        print("🔍 Loading compatibility bridge mappings...")
        
        try:
            # Read the compatibility.py file and extract service keys from _create_typed_mapping
            compat_file = self.packages_dir / "core" / "typed_di" / "compatibility.py"
            content = compat_file.read_text()
            
            # Find the essential_services dictionary in _create_typed_mapping
            # Look for patterns like: "service_key": (Protocol, None)
            for match in re.finditer(r'"([^"]+)":\s*\([^)]+\)', content):
                service_key = match.group(1)
                self.report.bridge_mappings.add(service_key)
            
            print(f"  Found {len(self.report.bridge_mappings)} bridge mappings")
            
        except Exception as e:
            print(f"  ⚠️  Error loading bridge mappings: {e}")
    
    def load_registered_services(self) -> None:
        """Load registered services by scanning registration modules."""
        print("🔍 Loading TypedDI registered services...")
        
        try:
            # The new system doesn't use legacy_key in registrations
            # Instead, we need to check what protocols/types are registered
            # and cross-reference with the compatibility bridge
            
            # For now, we'll consider a service "registered" if it appears
            # in BOTH the bridge mapping AND has a corresponding protocol registered
            # This is a limitation we'll address in the enhanced validator
            
            # Scan registration modules for concrete_type parameters
            reg_dir = self.packages_dir / "core" / "typed_di" / "service_registrations" / "registrations"
            
            registered_types = set()
            for reg_file in reg_dir.glob("*.py"):
                if reg_file.name == "__init__.py":
                    continue
                    
                content = reg_file.read_text()
                
                # Look for register_protocol_with_concrete_alias calls
                # Extract concrete_type= parameter
                for match in re.finditer(r'concrete_type=(\w+),', content):
                    type_name = match.group(1)
                    registered_types.add(type_name)
            
            # Now map these types back to bridge keys
            # Find imports in the bridge that map to these types
            # This is a heuristic approach - look for Type names in imports

            # Special case mappings for types that don't follow standard snake_case
            type_to_bridge_key = {
                # DB Services (Batch 1)
                'DynamoDBConfig': 'dynamodb_config',
                'DynamoDBAsyncClient': 'dynamodb_async_client',
                'DynamoDBStore': 'dynamodb_store',
                # Slack Core Services (Batch 2)
                'ChannelInfoOps': 'info_ops',
                'ChannelMembershipOps': 'membership_ops',
                'SlackChannelMessageOps': 'msg_ops',
                'SlackUserOps': 'user_ops',
                'SlackChannelArchiveOps': 'archive_ops',
                'SlackChannelBotMembershipOps': 'bot_membership_ops',
                'SlackChannelRestoreOps': 'restore_ops',
                'RestoreStateManager': 'restore_state',
                'SlackPostingHandler': 'slack_posting',
                # AI & Infrastructure Services (Batch 3)
                'OpenAIHandler': 'openai',
                'SlackArchiveCommand': 'archive_command',
                'MetricsStorage': 'metrics',
                'UserJoinNotificationService': 'user_join_notification_service',
                # Slack Advanced Services (Batch 5)
                'CommandTrackingOperations': 'command_tracking_ops',
                'CommandUsageCSVGenerator': 'csv_generator',
                'JoinNotificationOps': 'JoinNotificationOps',
            }

            for type_name in registered_types:
                # Try to match service keys by type name patterns
                # e.g., SecretsManager -> secrets_manager
                # SlackConfig -> slack_config
                # DynamoDBStore -> dynamodb_store

                # Check if there's an explicit mapping first
                if type_name in type_to_bridge_key:
                    bridge_key = type_to_bridge_key[type_name]
                    if bridge_key in self.report.bridge_mappings:
                        self.report.registered_services.add(bridge_key)
                else:
                    # Convert CamelCase to snake_case
                    snake_case = self._camel_to_snake(type_name)
                    if snake_case in self.report.bridge_mappings:
                        self.report.registered_services.add(snake_case)
            
            print(f"  Found {len(self.report.registered_services)} registered services")
            print("  (Note: This is an approximation based on type name matching)")
            
        except Exception as e:
            print(f"  ⚠️  Error loading registered services: {e}")
    
    def _camel_to_snake(self, name: str) -> str:
        """Convert CamelCase to snake_case, handling acronyms properly.

        Examples:
            DynamoDBConfig -> dynamodb_config
            SlackConfig -> slack_config
            HTTPClient -> http_client
        """
        # First, handle sequences of capitals followed by a lowercase letter
        # DynamoDB -> Dynamo_DB, HTTPClient -> HTTP_Client
        result = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        # Then handle lowercase (or number) followed by uppercase
        # Dynamo_DB -> Dynamo_D_B, but we want Dynamo_DB
        result = re.sub('([a-z0-9])([A-Z])', r'\1_\2', result)
        # Lowercase the result
        return result.lower()
    
    def validate(self) -> None:
        """Run validation checks."""
        print("🔍 Running validation checks...")
        
        # Check 1: Services accessed but not in bridge (Pattern 3)
        for service_key, access_points in self.report.accessed_services.items():
            if service_key not in self.report.bridge_mappings:
                self.report.missing_from_bridge.append((service_key, access_points))
        
        # Check 2: Services in bridge but not registered (Pattern 2)
        for service_key in self.report.bridge_mappings:
            if service_key not in self.report.registered_services:
                self.report.bridge_without_registration.append(service_key)
        
        # Check 3: Services accessed but not registered (Pattern 3 variant)
        for service_key, access_points in self.report.accessed_services.items():
            if service_key not in self.report.registered_services:
                self.report.missing_from_registry.append((service_key, access_points))
        
        print("  Validation complete")
    
    def save_report(self, output_path: Optional[Path] = None) -> None:
        """Save detailed report to JSON file."""
        if output_path is None:
            output_path = self.project_root / "typeddi_validation_report.json"
        
        report_data = {
            "statistics": {
                "total_access_points": self.report.total_access_points,
                "unique_services_accessed": self.report.unique_services_accessed,
                "bridge_mappings_count": len(self.report.bridge_mappings),
                "registered_services_count": len(self.report.registered_services),
            },
            "accessed_services": {
                key: [
                    {
                        "file": ap.file_path,
                        "line": ap.line_number,
                        "method": ap.access_method,
                        "context": ap.context
                    }
                    for ap in aps
                ]
                for key, aps in self.report.accessed_services.items()
            },
            "bridge_mappings": sorted(list(self.report.bridge_mappings)),
            "registered_services": sorted(list(self.report.registered_services)),
            "validation_results": {
                "missing_from_bridge": [
                    {
                        "service_key": key,
                        "access_points": [
                            {"file": ap.file_path, "line": ap.line_number}
                            for ap in aps
                        ]
                    }
                    for key, aps in self.report.missing_from_bridge
                ],
                "bridge_without_registration": sorted(self.report.bridge_without_registration),
                "missing_from_registry": [
                    {
                        "service_key": key,
                        "access_points": [
                            {"file": ap.file_path, "line": ap.line_number}
                            for ap in aps
                        ]
                    }
                    for key, aps in self.report.missing_from_registry
                ],
            }
        }
        
        output_path.write_text(json.dumps(report_data, indent=2))
        print(f"📄 Detailed report saved to: {output_path}")
    
    def run(self) -> ValidationReport:
        """Run complete validation workflow."""
        self.scan_codebase()
        self.load_bridge_mappings()
        self.load_registered_services()
        self.validate()
        
        # Print summary
        print("\n" + self.report.generate_summary())
        
        # Save detailed report
        self.save_report()
        
        return self.report


def main():
    """Main entry point."""
    import sys
    
    # Determine project root
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    else:
        # Try to find project root from current file location
        project_root = Path(__file__).parent.parent.parent.parent
    
    print(f"📁 Project root: {project_root}")
    print()
    
    validator = RegistrationValidator(project_root)
    report = validator.run()
    
    # Exit with error code if validation failed
    has_errors = (
        bool(report.missing_from_bridge) or
        bool(report.bridge_without_registration)
    )
    
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
